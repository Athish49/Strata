"""
Backfill embeddings for Federal Register regulatory_action records that are
present in the DB but missing from Qdrant.

Run:
    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python scripts/backfill_fr_embeddings.py

This script:
  1. Queries all FR records from the DB
  2. Finds which db_ids already have at least one vector in Qdrant
  3. Embeds the missing ones and upserts into Qdrant
  4. Reports progress and verifies the final count
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.db import AsyncSessionLocal
from app.regulatory.ingestion.embedder import embed_and_store_action, get_embedding_model
from app.services.vector import get_qdrant_client, project_filter
from qdrant_client.models import Filter, FieldCondition, MatchValue
from sqlalchemy import text


def get_embedded_fr_db_ids(q) -> set:
    """Scroll through Qdrant and collect all db_ids already embedded for FR."""
    db_ids = set()
    offset = None
    while True:
        pts, next_offset = q.scroll(
            "regulation_chunks",
            scroll_filter=Filter(
                must=[
                    *project_filter().must,
                    FieldCondition(key="source_system", match=MatchValue(value="federal_register")),
                ]
            ),
            limit=250,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for p in pts:
            db_id = p.payload.get("db_id")
            if db_id is not None:
                db_ids.add(db_id)
        if next_offset is None:
            break
        offset = next_offset
    return db_ids


async def backfill():
    print("Loading embedding model...")
    get_embedding_model()
    print("Model loaded.")

    qdrant = get_qdrant_client()

    # Step 1: Get all FR records from DB
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            text(
                """
                SELECT id, source_id, source_system, title, abstract, agency, status, action_type
                FROM regulatory_actions
                WHERE source_system = 'federal_register'
                ORDER BY id
                """
            )
        )
        rows = r.fetchall()

    db_records = [dict(row._mapping) for row in rows]
    all_db_ids = {row["id"] for row in db_records}
    print(f"Total FR records in DB: {len(db_records)}")

    # Step 2: Get IDs already in Qdrant
    print("Scanning Qdrant for existing FR vectors...")
    embedded_ids = get_embedded_fr_db_ids(qdrant)
    print(f"FR records already embedded in Qdrant: {len(embedded_ids)}")

    missing_ids = all_db_ids - embedded_ids
    print(f"FR records missing vectors: {len(missing_ids)}")

    if not missing_ids:
        print("Nothing to backfill — all FR records are already embedded.")
        return

    # Step 3: Embed missing records
    missing_records = [r for r in db_records if r["id"] in missing_ids]
    print(f"\nBackfilling {len(missing_records)} records...")

    success = 0
    failed = 0
    consecutive_failures = 0

    for i, rec in enumerate(missing_records):
        try:
            n_chunks = embed_and_store_action(
                record_id=rec["id"],
                source_id=rec["source_id"] or "",
                source_system=rec["source_system"],
                title=rec["title"] or "",
                abstract=rec["abstract"] or "",
                agency=rec["agency"] or "",
                status=rec["status"] or "in_progress",
                action_type=rec["action_type"] or "",
                qdrant_client=qdrant,
            )
            success += 1
            consecutive_failures = 0
            if (i + 1) % 100 == 0:
                print(f"  Progress: {i + 1}/{len(missing_records)} embedded ({success} ok, {failed} failed)")
        except Exception as e:
            failed += 1
            consecutive_failures += 1
            print(f"  ERROR on id={rec['id']} source_id={rec['source_id']}: {e}")
            if consecutive_failures >= 10:
                print("ABORT: 10 consecutive failures — likely a connectivity or quota issue.")
                break

    print(f"\nBackfill complete: {success} succeeded, {failed} failed.")

    # Step 4: Verify final count
    final_embedded_ids = get_embedded_fr_db_ids(qdrant)
    still_missing = all_db_ids - final_embedded_ids
    print(f"\nVerification:")
    print(f"  Total FR records in DB:       {len(all_db_ids)}")
    print(f"  FR records with vectors now:  {len(final_embedded_ids)}")
    print(f"  Still missing:                {len(still_missing)}")

    if not still_missing:
        print("\nSUCCESS: All FR records now have at least one vector in Qdrant.")
    else:
        print(f"\nWARNING: {len(still_missing)} records still missing: {sorted(still_missing)[:20]}")


if __name__ == "__main__":
    asyncio.run(backfill())

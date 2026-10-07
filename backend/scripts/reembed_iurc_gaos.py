"""
One-off script: re-embed iurc_gaos records in Qdrant.

The abstract and action_text fields were populated for all 42 rows after the
original Qdrant vectors were created, so those vectors lack the abstract text.

Steps:
  1. Record baseline counts for safety.
  2. Delete all Qdrant points where source_system='iurc_gaos'.
  3. Re-embed all 42 DB rows using embed_and_store_action().
  4. Verify counts and spot-check chunk_text for abstract content.

Run:
    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python scripts/reembed_iurc_gaos.py
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
from qdrant_client.models import (
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)
from sqlalchemy import text

TARGET_SOURCE = "iurc_gaos"
COLLECTION = "regulation_chunks"


def count_vectors(q, source_system: str) -> int:
    return q.count(
        COLLECTION,
        count_filter=Filter(
            must=[
                *project_filter().must,
                FieldCondition(key="source_system", match=MatchValue(value=source_system)),
            ]
        ),
        exact=True,
    ).count


async def main():
    print("Loading embedding model (first run may take a moment)...")
    get_embedding_model()
    print("Model loaded.\n")

    qdrant = get_qdrant_client()

    # --- Baseline ---
    baseline = count_vectors(qdrant, TARGET_SOURCE)
    print(f"[baseline] {TARGET_SOURCE} vectors: {baseline}")

    # --- Query DB ---
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            text(
                """
                SELECT id, source_id, source_system, title, abstract, agency, status, action_type
                FROM regulatory_actions
                WHERE source_system = :src
                ORDER BY id
                """
            ),
            {"src": TARGET_SOURCE},
        )
        rows = r.fetchall()

    records = [dict(row._mapping) for row in rows]
    non_empty_abstract = sum(1 for r in records if r.get("abstract"))
    print(f"DB records found: {len(records)} ({non_empty_abstract} with non-empty abstract)\n")

    if not records:
        print("No records found — exiting.")
        return

    # --- Delete existing Qdrant vectors ---
    print(f"Deleting existing Qdrant points for {TARGET_SOURCE}...")
    qdrant.delete(
        collection_name=COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    *project_filter().must,
                    FieldCondition(key="source_system", match=MatchValue(value=TARGET_SOURCE)),
                ]
            )
        ),
        wait=True,
    )
    after_delete = count_vectors(qdrant, TARGET_SOURCE)
    print(f"After delete — {TARGET_SOURCE}: {after_delete} vectors (expect 0)\n")

    # --- Re-embed ---
    print("Re-embedding records...")
    success = 0
    failed = 0
    consecutive_failures = 0

    for i, rec in enumerate(records):
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
            if (i + 1) % 10 == 0 or (i + 1) == len(records):
                print(f"  [{i + 1}/{len(records)}] ok (last: id={rec['id']}, {n_chunks} chunks)")
        except Exception as e:
            failed += 1
            consecutive_failures += 1
            print(f"  ERROR id={rec['id']} source_id={rec.get('source_id')}: {e}")
            if consecutive_failures >= 10:
                print("ABORT: 10 consecutive failures — possible connectivity issue.")
                break

    print(f"\nRe-embed complete: {success} succeeded, {failed} failed.")

    # --- Verification ---
    print("\n=== Verification ===")
    final_count = count_vectors(qdrant, TARGET_SOURCE)
    print(f"{TARGET_SOURCE}: {final_count} vectors in Qdrant (from {len(records)} DB rows)")

    # Spot-check: first record with a non-empty abstract
    pts, _ = qdrant.scroll(
        COLLECTION,
        scroll_filter=Filter(
            must=[
                *project_filter().must,
                FieldCondition(key="source_system", match=MatchValue(value=TARGET_SOURCE)),
            ]
        ),
        limit=1,
        with_payload=True,
        with_vectors=False,
    )
    if pts:
        payload = pts[0].payload
        chunk = payload.get("chunk_text", "")[:150]
        db_id = payload.get("db_id")
        db_rec = next((r for r in records if r["id"] == db_id), None)
        if db_rec:
            abstract = (db_rec.get("abstract") or "")[:60]
            title = (db_rec.get("title") or "")[:60]
            if abstract and abstract[:40] in chunk:
                verdict = "GOOD — abstract is in chunk_text"
            elif title and title[:40] in chunk:
                verdict = "WARNING — title in chunk_text (abstract may be empty for this record)"
            else:
                verdict = "CHECK MANUALLY"
            print(f"  id={db_id}: {verdict}")
            print(f"  chunk_text[:150]: {chunk!r}")
        else:
            print(f"  point found but no matching DB record (id={db_id})")
    else:
        print("  No points found!")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())

"""
Re-embed IURC and IDEM regulatory_action records in Qdrant.

These records were originally embedded with empty abstracts. The abstracts have
since been populated in the DB, so this script:
  1. Records baseline vector counts (safety check).
  2. Deletes all Qdrant points where:
       project=<tag>, record_type="regulatory_action",
       source_system IN ('iurc_rulemakings', 'idem_rulemakings')
  3. Re-embeds every matching DB row using embed_and_store_action().
  4. Verifies counts and spot-checks chunk_text to confirm abstracts are present.

Run:
    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python scripts/reembed_state_actions.py
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
    MatchAny,
    FilterSelector,
)
from sqlalchemy import text

TARGET_SOURCES = ["iurc_rulemakings", "idem_rulemakings"]
COLLECTION = "regulation_chunks"


def count_vectors(q, source_system: str) -> int:
    """Count Qdrant points for a given source_system (source_system is indexed)."""
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


def count_non_state_action_vectors(q) -> int:
    """
    Count vectors NOT in the target source systems — used as a safety baseline.
    Uses only indexed fields (project + source_system exclusion via must_not).
    """
    return q.count(
        COLLECTION,
        count_filter=Filter(
            must=[
                *project_filter().must,
            ],
            must_not=[
                FieldCondition(
                    key="source_system",
                    match=MatchAny(any=TARGET_SOURCES),
                ),
            ],
        ),
        exact=True,
    ).count


def delete_state_action_vectors(q) -> None:
    """
    Delete all Qdrant points for target source systems.
    Only touches iurc_rulemakings and idem_rulemakings — code_section source systems
    (cfr, iac) are never in TARGET_SOURCES so they are never affected.
    Uses only indexed fields (project + source_system).
    """
    delete_filter = Filter(
        must=[
            *project_filter().must,
            FieldCondition(
                key="source_system",
                match=MatchAny(any=TARGET_SOURCES),
            ),
        ]
    )
    q.delete(
        collection_name=COLLECTION,
        points_selector=FilterSelector(filter=delete_filter),
        wait=True,
    )


async def main():
    print("Loading embedding model (first run may take a moment)...")
    get_embedding_model()
    print("Model loaded.\n")

    qdrant = get_qdrant_client()

    # --- Safety baseline ---
    # Count all vectors NOT in our target source systems — must not change after re-embed
    non_target_baseline = count_non_state_action_vectors(qdrant)
    print(f"[baseline] non-target vectors (cfr/iac/federal_register/etc): {non_target_baseline} (must not change)")
    for src in TARGET_SOURCES:
        n = count_vectors(qdrant, src)
        print(f"[baseline] {src} vectors: {n}")

    # --- Query DB ---
    async with AsyncSessionLocal() as db:
        r = await db.execute(
            text(
                """
                SELECT id, source_id, source_system, title, abstract, agency, status, action_type
                FROM regulatory_actions
                WHERE source_system = ANY(:sources)
                ORDER BY source_system, id
                """
            ),
            {"sources": TARGET_SOURCES},
        )
        rows = r.fetchall()

    records = [dict(row._mapping) for row in rows]
    print(f"\nDB records to re-embed: {len(records)}")
    for src in TARGET_SOURCES:
        n = sum(1 for r in records if r["source_system"] == src)
        non_empty_abstract = sum(
            1 for r in records if r["source_system"] == src and r.get("abstract")
        )
        print(f"  {src}: {n} rows, {non_empty_abstract} with non-empty abstract")

    if not records:
        print("No records found — exiting.")
        return

    # --- Delete existing Qdrant vectors ---
    print(f"\nDeleting existing Qdrant points for {TARGET_SOURCES}...")
    delete_state_action_vectors(qdrant)
    for src in TARGET_SOURCES:
        n = count_vectors(qdrant, src)
        print(f"  After delete — {src}: {n} vectors (expect 0)")

    # --- Re-embed ---
    print("\nRe-embedding records...")
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
    non_target_after = count_non_state_action_vectors(qdrant)
    print(
        f"non-target vectors: {non_target_after} "
        f"({'OK — unchanged' if non_target_after == non_target_baseline else 'WARNING — changed!'})"
    )

    for src in TARGET_SOURCES:
        n = count_vectors(qdrant, src)
        db_count = sum(1 for r in records if r["source_system"] == src)
        print(f"{src}: {n} vectors in Qdrant (from {db_count} DB rows)")

    # Spot-check: verify chunk_text starts with abstract, not title
    print("\nSpot-checking payloads (chunk 0 per source)...")
    for src in TARGET_SOURCES:
        pts, _ = qdrant.scroll(
            COLLECTION,
            scroll_filter=Filter(
                must=[
                    *project_filter().must,
                    FieldCondition(key="source_system", match=MatchValue(value=src)),
                ]
            ),
            limit=1,
            with_payload=True,
            with_vectors=False,
        )
        if pts:
            p = pts[0]
            payload = p.payload
            chunk = payload.get("chunk_text", "")[:120]
            db_id = payload.get("db_id")
            # Find matching DB record
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
                print(f"  {src} id={db_id}: {verdict}")
                print(f"    chunk_text[:120]: {chunk!r}")
            else:
                print(f"  {src}: point found but no matching DB record (id={db_id})")
        else:
            print(f"  {src}: no points found!")

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())

"""
Patch existing IAC Qdrant points to add missing snapshot_date and section_number fields.
Scrolls all existing IAC vectors, groups by db_id, then patches via set_payload.
Run: cd backend && .venv/bin/python scripts/patch_qdrant_iac_payloads.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.regulatory.models.code_section import CodeSection
from app.services.vector import get_qdrant_client
from qdrant_client.models import PointIdsList

COLLECTION = "regulation_chunks"


async def patch():
    qdrant = get_qdrant_client()

    # Step 1: Load DB sections into a lookup dict
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CodeSection).where(CodeSection.source_system == "iac")
        )
        sections = result.scalars().all()

    section_map = {
        s.id: {
            "snapshot_date": str(s.snapshot_date) if s.snapshot_date else "",
            "section_number": s.section_number or "",
        }
        for s in sections
    }
    print(f"DB IAC sections: {len(section_map)}")

    # Step 2: Scroll all IAC points from Qdrant
    # Point IDs for code_section: record_id * 1000 + chunk_index
    # Min record_id for IAC sections (they were ingested after CFR)
    # Use large ID range scroll — start from 0, collect points with source_system=iac in payload
    # We'll group by db_id (from payload) then patch per-section
    all_points: list = []
    offset = None
    batch_size = 1000
    scrolled = 0

    print("Scrolling IAC vectors from Qdrant...")
    while True:
        results, next_offset = qdrant.scroll(
            collection_name=COLLECTION,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for pt in results:
            payload = pt.payload or {}
            if payload.get("source_system") == "iac" and payload.get("record_type") == "code_section":
                all_points.append(pt)
        scrolled += len(results)
        if scrolled % 5000 == 0:
            print(f"  Scrolled {scrolled} total points, {len(all_points)} IAC so far...")
        if next_offset is None:
            break
        offset = next_offset

    print(f"Found {len(all_points)} IAC points in Qdrant")

    # Step 3: Group point IDs by db_id
    from collections import defaultdict
    by_db_id: dict[int, list[int]] = defaultdict(list)
    for pt in all_points:
        db_id = (pt.payload or {}).get("db_id")
        if db_id is not None:
            by_db_id[int(db_id)].append(pt.id)

    # Step 4: Patch each group
    patched_sections = 0
    patched_points = 0
    errors = 0
    for db_id, point_ids in by_db_id.items():
        payload_update = section_map.get(db_id)
        if not payload_update:
            continue
        try:
            qdrant.set_payload(
                collection_name=COLLECTION,
                payload=payload_update,
                points=PointIdsList(points=point_ids),
            )
            patched_sections += 1
            patched_points += len(point_ids)
        except Exception as exc:
            errors += 1
            if errors <= 3:
                print(f"  Error patching db_id={db_id}: {exc}")

    print(f"Done. Patched {patched_sections} sections ({patched_points} points), {errors} errors.")


if __name__ == "__main__":
    asyncio.run(patch())

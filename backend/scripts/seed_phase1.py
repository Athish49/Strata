"""
Phase 1 baseline seed ingestion script.
Run: cd backend && .venv/bin/python scripts/seed_phase1.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.db import AsyncSessionLocal
from app.regulatory.ingestion.pipeline import run_ingestion
from app.regulatory.adapters.ecfr import ECFRAdapter

async def seed_ecfr():
    print("=== Phase 1 Baseline: eCFR Ingestion ===")
    print("Date: 2025-01-02 (baseline snapshot)")
    from sqlalchemy import text
    adapter = ECFRAdapter()
    async with AsyncSessionLocal() as db:
        # Pre-seed cursor to fetch historical snapshot at 2025-01-02
        await db.execute(text("""
            INSERT INTO sync_state (source_system, cursor_data, last_sync_at)
            VALUES ('cfr', '{"as_of_date": "2025-01-02"}', NOW())
            ON CONFLICT (source_system) DO UPDATE SET cursor_data = '{"as_of_date": "2025-01-02"}'
        """))
        await db.commit()

    async with AsyncSessionLocal() as db:
        summary = await run_ingestion(adapter, db)
        print(f"Result: {summary}")
        return summary

async def seed_federal_register():
    print("\n=== Phase 1 Baseline: Federal Register Ingestion ===")
    print("Date range: 2025-01-01 to 2025-03-31 (Q1 2025)")
    from app.regulatory.adapters.federal_register import FederalRegisterAdapter
    from sqlalchemy import text

    adapter = FederalRegisterAdapter()

    # Pre-seed the cursor to ensure we start from Q1 2025
    # (adapter defaults to 2025-01-01, but explicitly set to be safe)
    async with AsyncSessionLocal() as db:
        await db.execute(text("""
            INSERT INTO sync_state (source_system, cursor_data, last_sync_at)
            VALUES ('federal_register', '{"last_publication_date": "2025-01-01", "end_date": "2025-03-31"}', NOW())
            ON CONFLICT (source_system) DO UPDATE SET cursor_data = EXCLUDED.cursor_data
        """))
        await db.commit()

    async with AsyncSessionLocal() as db:
        summary = await run_ingestion(adapter, db)
        print(f"Result: {summary}")

    # Run stitching pass after FR ingestion to link actions to CFR sections
    from sqlalchemy import select
    from app.regulatory.models.regulatory_action import RegulatoryAction
    from app.regulatory.ingestion.stitcher import stitch_action_to_codebook, stitch_action_chains

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RegulatoryAction).where(
            RegulatoryAction.source_system == 'federal_register'
        ))
        actions = result.scalars().all()
        stitched = 0
        for action in actions:
            n = await stitch_action_to_codebook(action, db)
            stitched += n
        await db.commit()
        print(f"Stitched {stitched} codebook links from FR actions")

    return summary


async def main():
    ecfr_result = await seed_ecfr()
    fr_result = await seed_federal_register()
    print("\n=== Phase 1 Summary ===")
    print(f"eCFR: {ecfr_result}")
    print(f"Federal Register: {fr_result}")

if __name__ == "__main__":
    asyncio.run(main())

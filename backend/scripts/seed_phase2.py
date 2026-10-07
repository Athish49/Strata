"""
Phase 2 update seed ingestion script — detects changes since Phase 1 baseline.
Run: cd backend && .venv/bin/python scripts/seed_phase2.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.db import AsyncSessionLocal
from app.regulatory.ingestion.pipeline import run_ingestion

async def seed_ecfr_update():
    print("=== Phase 2 Update: eCFR Re-ingestion ===")
    print("Fetching current eCFR — comparing against Phase 1 baseline")
    from app.regulatory.adapters.ecfr import ECFRAdapter
    adapter = ECFRAdapter()
    async with AsyncSessionLocal() as db:
        # Set cursor to fetch current snapshot at 2026-10-06
        from sqlalchemy import text
        await db.execute(text(
            "UPDATE sync_state SET cursor_data = '{\"as_of_date\": \"2026-10-06\"}' WHERE source_system = 'cfr'"
        ))
        await db.commit()

        summary = await run_ingestion(adapter, db)
        print(f"Result: {summary}")
        return summary

async def seed_federal_register_q2():
    print("\n=== Phase 2 Update: Federal Register Q2 2025 ===")
    print("Date range: 2025-04-01 to 2025-06-30")
    from app.regulatory.adapters.federal_register import FederalRegisterAdapter
    from app.regulatory.models.regulatory_action import RegulatoryAction
    from app.regulatory.ingestion.stitcher import stitch_action_chains
    from sqlalchemy import select, text

    adapter = FederalRegisterAdapter()
    async with AsyncSessionLocal() as db:
        # Set cursor for Q2 2025 date range
        await db.execute(text("""
            INSERT INTO sync_state (source_system, cursor_data, last_sync_at)
            VALUES ('federal_register', '{"last_publication_date": "2025-04-01", "end_date": "2025-06-30"}', NOW())
            ON CONFLICT (source_system) DO UPDATE SET cursor_data = '{"last_publication_date": "2025-04-01", "end_date": "2025-06-30"}'
        """))
        await db.commit()

        summary = await run_ingestion(adapter, db)
        print(f"Ingestion result: {summary}")

    # Run action chain stitching: link Q1 proposed rules to Q2 final rules via RIN
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(RegulatoryAction).where(
            RegulatoryAction.source_system == 'federal_register',
            RegulatoryAction.rin != None,
        ))
        actions_with_rin = result.scalars().all()
        chains_created = 0
        for action in actions_with_rin:
            n = await stitch_action_chains(action, db)
            chains_created += n
        await db.commit()
        print(f"Action chains created: {chains_created}")

    return summary


async def main():
    ecfr_result = await seed_ecfr_update()
    fr_result = await seed_federal_register_q2()

    print("\n=== Phase 2 Summary ===")
    print(f"eCFR update: {ecfr_result}")
    print(f"Federal Register Q2: {fr_result}")

    if ecfr_result.get("changed", 0) > 0:
        print(f"  → {ecfr_result['changed']} sections changed — version chains created")
    if ecfr_result.get("unchanged", 0) > 0:
        print(f"  → {ecfr_result['unchanged']} sections unchanged — skipped")
    if fr_result.get("created", 0) > 0:
        print(f"  → {fr_result['created']} FR Q2 actions ingested")
    if fr_result.get("skipped", 0) > 0:
        print(f"  → {fr_result['skipped']} FR Q2 actions skipped (already exist)")

if __name__ == "__main__":
    asyncio.run(main())

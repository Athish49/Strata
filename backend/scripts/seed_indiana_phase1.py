"""
Phase 1 Indiana seed — IAC 2025 edition (rules through 2024-12-31).
Run: cd backend && .venv/bin/python scripts/seed_indiana_phase1.py
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

from app.db import AsyncSessionLocal
from app.regulatory.ingestion.pipeline import run_ingestion
from app.regulatory.adapters.iac import IACAdapter


async def seed_iac_phase1():
    adapter = IACAdapter()
    async with AsyncSessionLocal() as db:
        # Pre-seed cursor for Phase 1
        from sqlalchemy import text

        await db.execute(
            text("""
            INSERT INTO sync_state (source_system, cursor_data, last_sync_at)
            VALUES ('iac', '{"edition_year": 2025, "snapshot_date": "2024-12-31"}', NOW())
            ON CONFLICT (source_system) DO UPDATE
              SET cursor_data = EXCLUDED.cursor_data, last_sync_at = NOW()
        """)
        )
        await db.commit()
        summary = await run_ingestion(adapter, db)
        print(f"IAC Phase 1: {summary}")


if __name__ == "__main__":
    asyncio.run(seed_iac_phase1())

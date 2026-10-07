"""
Seed Indiana non-codified data for both Phase 1 and Phase 2.
Run: cd backend && .venv/bin/python scripts/seed_indiana_noncodified.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.db import AsyncSessionLocal
from app.regulatory.ingestion.pipeline import run_ingestion
from app.regulatory.adapters.iurc_rulemakings import IURCRulemakerAdapter
from app.regulatory.adapters.iurc_gaos import IURCGAOAdapter
from app.regulatory.adapters.iurc_investigations import IURCInvestigationsAdapter
from app.regulatory.adapters.idem_rulemakings import IDEMRulemakerAdapter

ADAPTERS = [
    IURCRulemakerAdapter,
    IURCGAOAdapter,
    IURCInvestigationsAdapter,
    IDEMRulemakerAdapter,
]


async def main():
    async with AsyncSessionLocal() as db:
        for AdapterClass in ADAPTERS:
            adapter = AdapterClass()
            print(f"\n--- Running {adapter.source_system} ---")
            try:
                summary = await run_ingestion(adapter, db)
                print(f"{adapter.source_system}: {summary}")
            except Exception as e:
                print(f"{adapter.source_system}: ERROR — {e}")


if __name__ == "__main__":
    asyncio.run(main())

"""
Backfill effective_date for IAC sections where it is NULL.
Uses the broadened _parse_effective_date from iac.py against stored body_text.
Run: cd backend && .venv/bin/python scripts/fix_iac_effective_dates.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from datetime import date as date_type
from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.regulatory.models.code_section import CodeSection
from app.regulatory.adapters.iac import _parse_effective_date


async def fix():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(CodeSection).where(
                CodeSection.source_system == "iac",
                CodeSection.effective_date.is_(None),
                CodeSection.body_text.isnot(None),
            )
        )
        sections = result.scalars().all()
        print(f"IAC sections with null effective_date: {len(sections)}")

        fixed = 0
        for s in sections:
            parsed = _parse_effective_date(s.body_text or "")
            if parsed:
                from datetime import datetime as dt
                try:
                    s.effective_date = dt.strptime(parsed, "%Y-%m-%d").date()
                    fixed += 1
                except ValueError:
                    pass

        await db.commit()
        print(f"Fixed: {fixed} / {len(sections)}")


if __name__ == "__main__":
    asyncio.run(fix())

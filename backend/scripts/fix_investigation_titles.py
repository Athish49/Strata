"""
Patch existing iurc_investigations RegulatoryAction titles to strip sub-case artifacts.
Artifacts look like: "37394 - NONE Indiana..." or "171 Southern Indiana..."
Run: cd backend && .venv/bin/python scripts/fix_investigation_titles.py
"""
import asyncio
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.regulatory.models.regulatory_action import RegulatoryAction

_PREFIX_RE = re.compile(r"^(\d+\s+(?=[A-Z])|[-–]\s*[A-Z]+\s*\d+\s+)")


async def fix():
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(RegulatoryAction).where(
                RegulatoryAction.source_system == "iurc_investigations"
            )
        )
        actions = result.scalars().all()
        print(f"Total iurc_investigations records: {len(actions)}")

        fixed = 0
        for a in actions:
            original = a.title or ""
            cleaned = re.sub(r"^\s*[-–]\s*[A-Z]+\s*\d+\s*", "", original)
            cleaned = re.sub(r"^\s*\d+\s+(?=[A-Z])", "", cleaned).strip()
            if cleaned and cleaned != original:
                a.title = cleaned
                fixed += 1

        await db.commit()
        print(f"Fixed: {fixed} / {len(actions)} titles")


if __name__ == "__main__":
    asyncio.run(fix())

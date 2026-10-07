"""
Backfill IAC cross-citations for existing code_sections rows.

Reads all IAC code_sections, re-extracts federal_refs, iac_cross_refs, and dins
from body_text using the same regex patterns as the IAC adapter, then updates
each row. Commits in batches of 500.

Usage:
    cd /path/to/backend && source .venv/bin/activate
    python scripts/backfill_iac_cross_citations.py
"""

import asyncio
import sys
import os

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select, update
from app.db import AsyncSessionLocal
from app.regulatory.models.code_section import CodeSection
from app.regulatory.adapters.iac import extract_cross_refs

BATCH_SIZE = 500


async def main() -> None:
    async with AsyncSessionLocal() as db:
        # Fetch all IAC sections: id + body_text only
        stmt = (
            select(CodeSection.id, CodeSection.body_text)
            .where(CodeSection.source_system == "iac")
        )
        result = await db.execute(stmt)
        rows = result.fetchall()

    total = len(rows)
    print(f"Found {total} IAC code_sections to backfill.")

    if total == 0:
        print("Nothing to do.")
        return

    counts = {"federal_refs": 0, "iac_cross_refs": 0, "dins": 0}
    processed = 0

    # Process in batches
    for batch_start in range(0, total, BATCH_SIZE):
        batch = rows[batch_start : batch_start + BATCH_SIZE]

        async with AsyncSessionLocal() as db:
            for row in batch:
                section_id, body_text = row.id, row.body_text
                refs = extract_cross_refs(body_text or "")

                await db.execute(
                    update(CodeSection)
                    .where(CodeSection.id == section_id)
                    .values(
                        federal_refs=refs["federal_refs"] or None,
                        iac_cross_refs=refs["iac_cross_refs"] or None,
                        dins=refs["dins"] or None,
                    )
                )

                if refs["federal_refs"]:
                    counts["federal_refs"] += 1
                if refs["iac_cross_refs"]:
                    counts["iac_cross_refs"] += 1
                if refs["dins"]:
                    counts["dins"] += 1

            await db.commit()

        processed += len(batch)
        print(f"  Committed batch: {processed}/{total} rows processed.")

    print("\nBackfill complete.")
    print(f"  Total rows updated : {total}")
    print(f"  Rows with federal_refs   : {counts['federal_refs']}")
    print(f"  Rows with iac_cross_refs : {counts['iac_cross_refs']}")
    print(f"  Rows with dins           : {counts['dins']}")


if __name__ == "__main__":
    asyncio.run(main())

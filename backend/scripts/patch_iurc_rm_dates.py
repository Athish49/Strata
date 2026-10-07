"""
Patch NULL date_published values for two IURC rulemaking records.

Dates sourced from the official IURC notices-and-documents pages:

RM-23-03 (docket_ids: ['RM-23-03', 'LSA-24-91']):
  - Notices page: https://www.in.gov/iurc/rulemakings/rulemakings-pending-and-effective/
                  rm-23-03-regarding-170-iac-4-11/iurc-rm-23-03-notices-and-documents
  - Earliest document: 2023-09-06 (Governor's List Regarding Emergency Rules LSA #23-652)
  - Proposed rule notice published in Indiana Register: 2024-03-20
    ("2024-03-20 - Notice of First Public Comment Period LSA #24-91")
  - date_published set to 2024-03-20 (Indiana Register publication of proposed rule),
    consistent with what the IURC adapter normally extracts from detail page text.

RM-24-06 (docket_ids: ['RM-24-06']):
  - Notices page: https://www.in.gov/iurc/rulemakings/rulemakings-pending-and-effective/
                  rm-24-06-amending-170-iac-5-5/iurc-rm-24-06-notices-and-documents
  - Agency Correction rule; no LSA number on listing page.
  - Earliest document: 2024-12-30 (IURC Order Approving Agency Correction of 170 IAC 5-5)
  - Published in Indiana Register: 2025-01-28
  - Effective: 2025-02-14
  - date_published set to 2024-12-30 (IURC Order date, earliest document for this rulemaking).
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

# Allow running from repo root or scripts/ directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import text

load_dotenv()


PATCHES = [
    {
        "source_id": "RM-23-03",
        "date_published": date(2024, 3, 20),
        "note": "Proposed rule notice published in Indiana Register (LSA #24-91). "
                "Source: IURC RM #23-03 notices page, document dated 2024-03-20.",
    },
    {
        "source_id": "RM-24-06",
        "date_published": date(2024, 12, 30),
        "note": "IURC Order Approving Agency Correction of 170 IAC 5-5 (LSA #22-359). "
                "Earliest document on RM-24-06 notices page, dated 2024-12-30. "
                "Published in Indiana Register 2025-01-28; effective 2025-02-14.",
    },
]


async def main() -> None:
    from app.db import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        for patch in PATCHES:
            result = await db.execute(
                text("""
                    UPDATE regulatory_actions
                    SET date_published = :date_published
                    WHERE source_system = 'iurc_rulemakings'
                      AND source_id = :source_id
                      AND date_published IS NULL
                """),
                {
                    "source_id": patch["source_id"],
                    "date_published": patch["date_published"],
                },
            )
            print(
                f"[{patch['source_id']}] rows updated: {result.rowcount} | "
                f"date_published = {patch['date_published']}"
            )
            print(f"  Note: {patch['note']}")

        await db.commit()
        print("\nCommitted. Verifying...")

        r = await db.execute(
            text("""
                SELECT source_id, date_published
                FROM regulatory_actions
                WHERE source_system = 'iurc_rulemakings'
                  AND source_id IN ('RM-23-03', 'RM-24-06')
                ORDER BY source_id
            """)
        )
        for row in r:
            d = dict(row._mapping)
            status = "OK" if d["date_published"] else "STILL NULL"
            print(f"  {d['source_id']}: date_published = {d['date_published']} [{status}]")


if __name__ == "__main__":
    asyncio.run(main())

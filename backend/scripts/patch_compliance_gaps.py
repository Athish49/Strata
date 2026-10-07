"""
Patch existing DB rows to reflect compliance gap fixes:
  1. jurisdiction_geo = 'IN' for all Indiana non-codified regulatory_actions
  2. status = 'in_progress' for iurc_investigations (were wrongly 'approved')
  3. docket_ids = [source_id] for idem_rulemakings where empty
  4. action_type = 'proposed_rule' for iurc_rulemakings where 'rulemaking'
  5. status = 'repealed' for IAC code_sections with (Repealed) in heading

Run from backend/:
    .venv/bin/python scripts/patch_compliance_gaps.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv()

from app.db import AsyncSessionLocal
from sqlalchemy import text


async def main():
    async with AsyncSessionLocal() as session:
        # 1. jurisdiction_geo for Indiana non-codified
        r1 = await session.execute(text("""
            UPDATE regulatory_actions
            SET jurisdiction_geo = 'IN'
            WHERE source_system IN ('iurc_rulemakings', 'iurc_gaos', 'iurc_investigations', 'idem_rulemakings')
              AND (jurisdiction_geo IS NULL OR jurisdiction_geo != 'IN')
        """))
        print(f"jurisdiction_geo patched: {r1.rowcount} rows")

        # 2. status for investigations
        r2 = await session.execute(text("""
            UPDATE regulatory_actions
            SET status = 'in_progress'
            WHERE source_system = 'iurc_investigations'
              AND status = 'approved'
        """))
        print(f"iurc_investigations status → in_progress: {r2.rowcount} rows")

        # 3. docket_ids for IDEM (empty array → [source_id])
        r3 = await session.execute(text("""
            UPDATE regulatory_actions
            SET docket_ids = ARRAY[source_id]
            WHERE source_system = 'idem_rulemakings'
              AND (docket_ids IS NULL OR cardinality(docket_ids) = 0)
        """))
        print(f"idem_rulemakings docket_ids patched: {r3.rowcount} rows")

        # 4. action_type for IURC Rulemakings
        r4 = await session.execute(text("""
            UPDATE regulatory_actions
            SET action_type = 'proposed_rule'
            WHERE source_system = 'iurc_rulemakings'
              AND action_type = 'rulemaking'
        """))
        print(f"iurc_rulemakings action_type → proposed_rule: {r4.rowcount} rows")

        # 5. IAC repealed sections
        r5 = await session.execute(text("""
            UPDATE code_sections
            SET status = 'repealed'
            WHERE source_system = 'iac'
              AND heading ILIKE '%(Repealed)%'
              AND status = 'approved'
        """))
        print(f"IAC repealed sections patched: {r5.rowcount} rows")

        await session.commit()
        print("All patches committed.")


if __name__ == "__main__":
    asyncio.run(main())

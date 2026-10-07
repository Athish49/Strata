"""
DB patch script for two data quality fixes:

Issue #3: Clear cfr_references for iurc_rulemakings rows (all are IAC citations,
          which belong in legal_refs only; stitcher reads legal_refs for IAC).

Issue #6: Backfill date_filed = date_published for iurc_rulemakings and
          idem_rulemakings rows that have date_published but no date_filed.
"""

import asyncio
from dotenv import load_dotenv

load_dotenv()


async def main():
    from app.db import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        # --- PRE-PATCH state ---
        print("=== PRE-PATCH STATE ===")
        r = await db.execute(text("""
            SELECT source_system, count(*) as n,
                   count(date_published) as has_date_pub,
                   count(date_filed) as has_date_filed,
                   sum(case when cfr_references != '{}' then 1 else 0 end) as has_cfr
            FROM regulatory_actions
            WHERE source_system IN ('iurc_rulemakings', 'idem_rulemakings')
            GROUP BY source_system
        """))
        for row in r:
            print(dict(row._mapping))

        # --- ISSUE #3: Clear cfr_references for iurc_rulemakings ---
        result3 = await db.execute(text("""
            UPDATE regulatory_actions
            SET cfr_references = '{}'
            WHERE source_system = 'iurc_rulemakings'
              AND cfr_references != '{}'
        """))
        print(f"\nIssue #3: cleared cfr_references on {result3.rowcount} iurc_rulemakings rows")

        # --- ISSUE #6: Backfill date_filed from date_published ---
        result6 = await db.execute(text("""
            UPDATE regulatory_actions
            SET date_filed = date_published
            WHERE source_system IN ('iurc_rulemakings', 'idem_rulemakings')
              AND date_filed IS NULL
              AND date_published IS NOT NULL
        """))
        print(f"Issue #6: backfilled date_filed on {result6.rowcount} rows")

        await db.commit()

        # --- POST-PATCH state ---
        print("\n=== POST-PATCH STATE ===")
        r2 = await db.execute(text("""
            SELECT source_system, count(*) as n,
                   count(date_published) as has_date_pub,
                   count(date_filed) as has_date_filed,
                   sum(case when cfr_references != '{}' then 1 else 0 end) as has_cfr
            FROM regulatory_actions
            WHERE source_system IN ('iurc_rulemakings', 'idem_rulemakings')
            GROUP BY source_system
        """))
        rows = []
        for row in r2:
            d = dict(row._mapping)
            rows.append(d)
            print(d)

        # --- Assertions ---
        print("\n=== ASSERTIONS ===")
        for d in rows:
            src = d['source_system']
            assert d['has_cfr'] == 0, f"{src}: expected has_cfr=0, got {d['has_cfr']}"
            print(f"{src}: cfr_references cleared OK")
            assert d['has_date_filed'] == d['has_date_pub'], (
                f"{src}: date_filed ({d['has_date_filed']}) != date_published ({d['has_date_pub']})"
            )
            print(f"{src}: date_filed == date_published ({d['has_date_pub']}) OK")

        print("\nAll assertions passed.")


if __name__ == "__main__":
    asyncio.run(main())

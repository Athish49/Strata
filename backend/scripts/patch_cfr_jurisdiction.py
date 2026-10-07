"""
Patch script: CFR jurisdiction_geo + date_filed + verification

Fixes:
1. Sets jurisdiction_geo = 'US' for all CFR code_sections where it is NULL.
2. Sets date_filed = date_published for all regulatory_actions where date_filed
   is NULL and date_published is NOT NULL.

Run:
    cd backend && source .venv/bin/activate && python scripts/patch_cfr_jurisdiction.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def main():
    from app.db import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        # --- Before counts ---
        r = await db.execute(text("""
            SELECT source_system,
                   COUNT(*) AS n,
                   COUNT(jurisdiction_geo) AS has_geo,
                   COUNT(CASE WHEN jurisdiction_geo = 'US' THEN 1 END) AS geo_us,
                   COUNT(CASE WHEN jurisdiction_geo = 'IN' THEN 1 END) AS geo_in
            FROM code_sections
            GROUP BY source_system
            ORDER BY source_system
        """))
        print("=== code_sections jurisdiction_geo BEFORE ===")
        for row in r:
            print(dict(row._mapping))

        r = await db.execute(text("""
            SELECT source_system, COUNT(*) AS n, COUNT(date_filed) AS has_date_filed
            FROM regulatory_actions
            GROUP BY source_system
            ORDER BY source_system
        """))
        print("\n=== regulatory_actions date_filed BEFORE ===")
        for row in r:
            print(dict(row._mapping))

        # --- Patch 1: Set CFR jurisdiction_geo ---
        r = await db.execute(text("""
            UPDATE code_sections
            SET jurisdiction_geo = 'US'
            WHERE source_system = 'cfr' AND jurisdiction_geo IS NULL
        """))
        print(f"\nCFR jurisdiction_geo patched: {r.rowcount} rows")

        # --- Patch 2: Set date_filed from date_published ---
        r = await db.execute(text("""
            UPDATE regulatory_actions
            SET date_filed = date_published
            WHERE date_filed IS NULL AND date_published IS NOT NULL
        """))
        print(f"date_filed patched: {r.rowcount} rows")

        await db.commit()

        # --- After counts ---
        r = await db.execute(text("""
            SELECT source_system,
                   COUNT(*) AS n,
                   COUNT(jurisdiction_geo) AS has_geo,
                   COUNT(CASE WHEN jurisdiction_geo = 'US' THEN 1 END) AS geo_us,
                   COUNT(CASE WHEN jurisdiction_geo = 'IN' THEN 1 END) AS geo_in
            FROM code_sections
            GROUP BY source_system
            ORDER BY source_system
        """))
        print("\n=== code_sections jurisdiction_geo AFTER ===")
        for row in r:
            print(dict(row._mapping))

        r = await db.execute(text("""
            SELECT source_system, COUNT(*) AS n, COUNT(date_filed) AS has_date_filed
            FROM regulatory_actions
            GROUP BY source_system
            ORDER BY source_system
        """))
        print("\n=== regulatory_actions date_filed AFTER ===")
        for row in r:
            print(dict(row._mapping))


asyncio.run(main())

import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.regulatory.models.agency import Agency

AGENCIES = [
    Agency(
        agency_id="ferc",
        name="Federal Energy Regulatory Commission",
        aliases=["FERC", "federal-energy-regulatory-commission"],
        jurisdiction_level="federal",
        jurisdiction_geo=None,
        codebook_title="18",
        domain=["energy", "electricity"],
    ),
    Agency(
        agency_id="epa",
        name="Environmental Protection Agency",
        aliases=["EPA", "environmental-protection-agency"],
        jurisdiction_level="federal",
        jurisdiction_geo=None,
        codebook_title="40",
        domain=["environment", "energy"],
    ),
    # Indiana agencies
    Agency(
        agency_id="iurc",
        name="Indiana Utility Regulatory Commission",
        aliases=["IURC"],
        jurisdiction_level="state",
        jurisdiction_geo="IN",
        codebook_title="170",
        domain=["energy", "electricity", "utilities", "telecom"],
    ),
    Agency(
        agency_id="idem",
        name="Indiana Department of Environmental Management",
        aliases=["IDEM"],
        jurisdiction_level="state",
        jurisdiction_geo="IN",
        codebook_title="326",
        domain=["environment", "air quality", "water quality"],
    ),
]

async def seed():
    async with AsyncSessionLocal() as db:
        for agency in AGENCIES:
            existing = await db.get(Agency, agency.agency_id)
            if existing:
                print(f"  Already exists: {agency.agency_id}")
            else:
                db.add(agency)
                print(f"  Inserted: {agency.agency_id} — {agency.name}")
        await db.commit()
    print("Done.")

if __name__ == "__main__":
    asyncio.run(seed())

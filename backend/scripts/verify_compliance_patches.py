"""Verify all compliance gap DB patches were applied correctly."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv()

from app.db import AsyncSessionLocal
from sqlalchemy import text


async def verify():
    async with AsyncSessionLocal() as db:
        checks = [
            ("Indiana non-codified jurisdiction_geo=IN", """
                SELECT COUNT(*) FROM regulatory_actions
                WHERE source_system IN ('iurc_rulemakings','iurc_gaos','iurc_investigations','idem_rulemakings')
                  AND jurisdiction_geo = 'IN'
            """),
            ("Indiana non-codified missing jurisdiction_geo (expect 0)", """
                SELECT COUNT(*) FROM regulatory_actions
                WHERE source_system IN ('iurc_rulemakings','iurc_gaos','iurc_investigations','idem_rulemakings')
                  AND (jurisdiction_geo IS NULL OR jurisdiction_geo != 'IN')
            """),
            ("iurc_investigations status=in_progress", """
                SELECT COUNT(*) FROM regulatory_actions
                WHERE source_system = 'iurc_investigations' AND status = 'in_progress'
            """),
            ("iurc_investigations status=approved (expect 0)", """
                SELECT COUNT(*) FROM regulatory_actions
                WHERE source_system = 'iurc_investigations' AND status = 'approved'
            """),
            ("idem docket_ids populated", """
                SELECT COUNT(*) FROM regulatory_actions
                WHERE source_system = 'idem_rulemakings' AND cardinality(docket_ids) > 0
            """),
            ("iurc_rulemakings action_type=proposed_rule", """
                SELECT COUNT(*) FROM regulatory_actions
                WHERE source_system = 'iurc_rulemakings' AND action_type = 'proposed_rule'
            """),
            ("iurc_rulemakings action_type=rulemaking (expect 0)", """
                SELECT COUNT(*) FROM regulatory_actions
                WHERE source_system = 'iurc_rulemakings' AND action_type = 'rulemaking'
            """),
            ("IAC repealed sections", """
                SELECT COUNT(*) FROM code_sections
                WHERE source_system = 'iac' AND status = 'repealed'
            """),
            ("IAC approved sections", """
                SELECT COUNT(*) FROM code_sections
                WHERE source_system = 'iac' AND status = 'approved'
            """),
        ]
        for label, sql in checks:
            r = await db.execute(text(sql))
            print(f"  {label}: {r.scalar()}")


if __name__ == "__main__":
    asyncio.run(verify())

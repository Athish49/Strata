"""
backfill_citations.py

Backfill resolution_status, code_section_id, and in_knowledge_base
for all rows in company.clause_citations.

Usage:
    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python scripts/backfill_citations.py
"""

import os
import sys
from collections import defaultdict

from dotenv import load_dotenv
import psycopg2

# Allow imports from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.company_ingest.enrich.resolve_citations_db import resolve_all_citations


def main():
    load_dotenv()

    raw_url = os.environ["DATABASE_URL"]
    url = raw_url.replace("+asyncpg", "").split("?")[0]

    print(f"Connecting to database …")
    conn = psycopg2.connect(url, sslmode="require")
    conn.autocommit = False

    print("Running citation resolver …")
    counts = resolve_all_citations(conn)

    print("\nResolution counts (rows updated this run):")
    total = 0
    for status, n in sorted(counts.items()):
        print(f"  {status:<25} {n:>5}")
        total += n
    print(f"  {'TOTAL':<25} {total:>5}")

    # Post-run sanity check
    cur = conn.cursor()
    cur.execute(
        "SELECT resolution_status, COUNT(*) FROM company.clause_citations GROUP BY 1 ORDER BY 1"
    )
    print("\nFull table distribution after backfill:")
    grand_total = 0
    for row in cur.fetchall():
        status, cnt = row
        print(f"  {status or 'NULL':<25} {cnt:>5}")
        grand_total += cnt
    print(f"  {'TOTAL':<25} {grand_total:>5}")

    cur.execute(
        "SELECT COUNT(*) FROM company.clause_citations WHERE resolution_status = 'resolved'"
    )
    resolved_count = cur.fetchone()[0]
    sanity = "YES" if resolved_count >= 408 else "NO"
    print(f"\nSanity check: resolved >= 408? {sanity}  (actual: {resolved_count})")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

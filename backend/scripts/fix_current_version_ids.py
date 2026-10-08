"""
fix_current_version_ids.py — Re-point company_documents.current_version_id to the
clause set that actually holds the document's prose clauses.

Cause: cli/ingest.py derives the P1 clause version_id as uuid5(company, doc, fm.version or "v1")
while insert_document_versions / company_documents use the register version. For documents whose
front matter has no `version`, the clauses sit under the "v1" id and current_version_id points at
an id with zero clauses.

Fix (one transaction, nothing deleted): for each affected document, the prose clause set (not
register_row, has no document_versions row, preferably the one document_scope is keyed on) becomes
the version:
  1. document_versions row of the old current id gets version_id = chosen id (all metadata kept)
  2. company_documents.current_version_id = chosen id
Nothing else references the old id (checked: scope, defined_terms, clauses). Separate register-file
clause sets (unit_kind 'register_row') are left untouched.

Run::

    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python scripts/fix_current_version_ids.py --company-id rpl          # dry run
    .venv/bin/python scripts/fix_current_version_ids.py --company-id rpl --apply  # write
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import psycopg2


def choose_target(current_id: str, sets: list[dict]) -> tuple[str | None, str]:
    """Pick the clause version_id to make current. Returns (version_id or None, reason).

    Each set: {version_id, n, has_dv, has_scope, prose} (prose = not only register_row units).
    """
    by_id = {s["version_id"]: s for s in sets}
    cur = by_id.get(current_id)
    if cur and cur["n"] > 0:
        return None, "ok: current version already has clauses"
    cands = [s for s in sets if s["n"] > 0 and not s["has_dv"] and s["prose"]]
    scoped = [s for s in cands if s["has_scope"]]
    pool = scoped or cands
    if len(pool) == 1:
        return pool[0]["version_id"], "prose set without document_versions row"
    return None, f"ambiguous or none ({len(pool)} candidates); skipped"


SETS_SQL = """
SELECT c.version_id::text, count(*) AS n,
       EXISTS (SELECT 1 FROM company.document_versions v WHERE v.version_id = c.version_id) AS has_dv,
       EXISTS (SELECT 1 FROM company.document_scope s WHERE s.version_id = c.version_id) AS has_scope,
       bool_or(c.unit_kind <> 'register_row') AS prose
FROM company.clauses c
WHERE c.company_id = %s AND c.doc_id = %s
GROUP BY c.version_id
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company-id", default="rpl")
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    args = ap.parse_args()

    url = os.environ["DATABASE_URL"].replace("+asyncpg", "").split("?")[0]
    conn = psycopg2.connect(url, sslmode="require")
    cur = conn.cursor()
    plan = []
    cur.execute(
        "SELECT doc_id, current_version_id::text FROM company.company_documents "
        "WHERE company_id = %s ORDER BY doc_id", (args.company_id,))
    for doc_id, current_id in cur.fetchall():
        cur.execute(SETS_SQL, (args.company_id, doc_id))
        sets = [dict(zip(("version_id", "n", "has_dv", "has_scope", "prose"), r)) for r in cur.fetchall()]
        target, reason = choose_target(current_id, sets)
        print(f"{doc_id}: current={current_id} -> {target or '(no change)'}  [{reason}]")
        if target:
            plan.append((doc_id, current_id, target))

    for doc_id, old, new in plan:
        cur.execute(
            "UPDATE company.document_versions SET version_id = %s "
            "WHERE company_id = %s AND doc_id = %s AND version_id = %s",
            (new, args.company_id, doc_id, old))
        dv = cur.rowcount
        cur.execute(
            "UPDATE company.company_documents SET current_version_id = %s "
            "WHERE company_id = %s AND doc_id = %s", (new, args.company_id, doc_id))
        print(f"  {doc_id}: document_versions rows updated={dv}, company_documents rows updated={cur.rowcount}")
        if dv != 1 or cur.rowcount != 1:
            conn.rollback()
            print("unexpected row count; rolled back")
            return 1

    if args.apply:
        conn.commit()
        print(f"APPLIED: {len(plan)} documents fixed")
    else:
        conn.rollback()
        print(f"DRY RUN (rolled back): {len(plan)} documents would be fixed; use --apply")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
recompute_citation_fragments.py — Recompute company.clause_parameters.is_citation_fragment.

Rule (data_model.md section 2): TRUE when kind = 'number' AND unit IS NULL AND
value_text is a whole token inside any citation_raw of the same clause.
Whole token = not adjacent to other digits; a decimal point is a section
separator, so it does not glue ("4" and "16" are whole in "170 IAC 4-1-16",
"6" in "16.6", "761" in "761.180"; "4" is not whole in "14").

Idempotent: only rows whose flag differs from the computed value are updated.
Only is_citation_fragment is written.

Run::

    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python scripts/recompute_citation_fragments.py          # dry run
    .venv/bin/python scripts/recompute_citation_fragments.py --apply  # write
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import psycopg2


def is_whole_token(value_text: str | None, citation_raw: str | None) -> bool:
    """True if value_text occurs in citation_raw not glued to other digits."""
    if not value_text or not citation_raw:
        return False
    v = value_text.strip()
    if not v:
        return False
    pat = r"(?<!\d)" + re.escape(v) + r"(?!\d)"
    return re.search(pat, citation_raw) is not None


def is_citation_fragment(kind, unit, value_text, citations) -> bool:
    if kind != "number" or unit is not None:
        return False
    return any(is_whole_token(value_text, c) for c in citations)


def main(apply: bool = False) -> None:
    db_url = os.environ["DATABASE_URL"].replace("+asyncpg", "").split("?")[0]
    conn = psycopg2.connect(db_url, sslmode="require", connect_timeout=30)
    cur = conn.cursor()

    cur.execute("SELECT clause_pk, array_agg(citation_raw) FROM company.clause_citations"
                " WHERE citation_raw IS NOT NULL GROUP BY clause_pk")
    cites = {pk: arr for pk, arr in cur.fetchall()}

    cur.execute("SELECT parameter_pk, clause_pk, kind, unit, value_text, is_citation_fragment"
                " FROM company.clause_parameters")
    rows = cur.fetchall()

    new_true: list = []
    changes: list = []  # (new_value, parameter_pk)
    total_by_kind: Counter = Counter()
    true_by_kind: Counter = Counter()
    for pk, clause_pk, kind, unit, vt, cur_flag in rows:
        new = is_citation_fragment(kind, unit, vt, cites.get(clause_pk, []))
        total_by_kind[kind] += 1
        if new:
            true_by_kind[kind] += 1
            new_true.append(pk)
        if bool(cur_flag) != new:
            changes.append((new, pk))

    print(f"Parameters: {len(rows)}; computed TRUE: {len(new_true)}; rows to change: {len(changes)}")
    for k in sorted(total_by_kind, key=str):
        print(f"  kind={k}: TRUE {true_by_kind[k]} / total {total_by_kind[k]}")

    if not apply:
        print("dry run: no writes performed (use --apply).")
        conn.close()
        return

    if changes:
        cur.executemany(
            "UPDATE company.clause_parameters SET is_citation_fragment = %s WHERE parameter_pk = %s",
            changes,
        )
        conn.commit()
    cur.execute("SELECT COUNT(*) FROM company.clause_parameters WHERE is_citation_fragment")
    print(f"Applied. TRUE rows now in DB: {cur.fetchone()[0]}")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recompute clause_parameters.is_citation_fragment.")
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry run).")
    args = parser.parse_args()
    main(apply=args.apply)

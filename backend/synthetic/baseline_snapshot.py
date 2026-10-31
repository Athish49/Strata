"""Task 0.1 — capture the pre-v2 production baseline.

Read-only. Writes baseline_before_v2.json next to this file.

Why this exists: the v2 migration TRUNCATEs company.* and engine.*. Once it has
run, these numbers cannot be reconstructed, and the cutover parity gate
(verify_parity.py) has nothing to compare against. Run this BEFORE any migration.

Usage:
    cd backend && .venv/bin/python synthetic/baseline_snapshot.py
    cd backend && .venv/bin/python synthetic/baseline_snapshot.py --out /tmp/x.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parent
DEFAULT_OUT = HERE / "baseline_before_v2.json"


def _dsn() -> str:
    """Resolve DATABASE_URL from the environment or backend/.env.

    Never hardcode a connection string here (see task 1.1).
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        from dotenv import load_dotenv

        load_dotenv(BACKEND / ".env")
        url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL not set and not found in backend/.env")
    # psycopg2 wants a plain scheme; app.db uses postgresql+asyncpg.
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


# Each entry: key -> (sql, "scalar" | "rows")
QUERIES: dict[str, tuple[str, str]] = {
    "clauses_total": ("SELECT count(*) FROM company.clauses", "scalar"),
    "clauses_by_unit_kind": (
        "SELECT unit_kind, count(*) FROM company.clauses GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "clauses_by_doc": (
        "SELECT doc_id, count(*) FROM company.clauses GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "citations_total": ("SELECT count(*) FROM company.clause_citations", "scalar"),
    "citations_resolved": (
        "SELECT count(code_section_id) FROM company.clause_citations",
        "scalar",
    ),
    "citations_by_status": (
        "SELECT resolution_status, count(*) FROM company.clause_citations "
        "GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "citations_by_unit_kind": (
        "SELECT c.unit_kind, count(*) FROM company.clause_citations cc "
        "JOIN company.clauses c ON c.clause_pk = cc.clause_pk GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "citations_resolved_by_unit_kind": (
        "SELECT c.unit_kind, count(cc.code_section_id) FROM company.clause_citations cc "
        "JOIN company.clauses c ON c.clause_pk = cc.clause_pk GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "distinct_code_sections_by_unit_kind": (
        "SELECT c.unit_kind, count(DISTINCT cc.code_section_id) "
        "FROM company.clause_citations cc "
        "JOIN company.clauses c ON c.clause_pk = cc.clause_pk "
        "WHERE cc.code_section_id IS NOT NULL GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "distinct_code_sections_total": (
        "SELECT count(DISTINCT code_section_id) FROM company.clause_citations "
        "WHERE code_section_id IS NOT NULL",
        "scalar",
    ),
    "assessable_by_unit_kind": (
        "SELECT unit_kind, count(*) FROM company.clauses "
        "WHERE assessable = true AND clause_role <> 'boilerplate' GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "document_scope_rows": ("SELECT count(*) FROM company.document_scope", "scalar"),
    "documents_total": ("SELECT count(*) FROM company.company_documents", "scalar"),
    "document_versions_total": ("SELECT count(*) FROM company.document_versions", "scalar"),
    "findings_total": ("SELECT count(*) FROM engine.findings", "scalar"),
    "findings_by_unit_kind": (
        "SELECT coalesce(c.unit_kind, '<no clause>'), count(*) FROM engine.findings f "
        "LEFT JOIN company.clauses c ON c.clause_pk = f.clause_pk GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "findings_by_doc": (
        "SELECT doc_id, count(*) FROM engine.findings GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "engine_runs_by_status": (
        "SELECT status, count(*) FROM engine.runs GROUP BY 1 ORDER BY 2 DESC",
        "rows",
    ),
    "code_sections_total": ("SELECT count(*) FROM public.code_sections", "scalar"),
}

# Tables whose row counts are recorded verbatim. The last three are expected to be
# zero: that is the evidence that dropping them in task 3.1 costs nothing.
TABLE_COUNTS = [
    "clause_parameters",
    "clause_links",
    "defined_terms",
    "term_usages",
    "table_columns",
    "people",
    "company_attributes",
    "ingest_runs",
    "llm_extractions",
    "parameter_checks",
    "datasets",
    "dataset_columns",
]

EXPECT_ZERO = {"parameter_checks", "datasets", "dataset_columns"}


def collect(cur) -> dict:
    snap: dict = {}
    for key, (sql, kind) in QUERIES.items():
        try:
            cur.execute(sql)
            if kind == "scalar":
                snap[key] = cur.fetchone()[0]
            else:
                snap[key] = {str(r[0]): r[1] for r in cur.fetchall()}
        except Exception as exc:  # a missing table is data, not a crash
            cur.connection.rollback()
            snap[key] = {"error": str(exc).strip().splitlines()[0]}

    counts: dict = {}
    for t in TABLE_COUNTS:
        try:
            cur.execute(f"SELECT count(*) FROM company.{t}")
            counts[t] = cur.fetchone()[0]
        except Exception as exc:
            cur.connection.rollback()
            counts[t] = {"error": str(exc).strip().splitlines()[0]}
    snap["table_counts"] = counts

    try:
        cur.execute(
            "SELECT run_id::text, metrics FROM engine.score_reports "
            "ORDER BY run_id LIMIT 50"
        )
        snap["score_reports"] = [{"run_id": r[0], "metrics": r[1]} for r in cur.fetchall()]
    except Exception as exc:
        cur.connection.rollback()
        snap["score_reports"] = {"error": str(exc).strip().splitlines()[0]}

    return snap


def report(snap: dict) -> None:
    print("=== Pre-v2 baseline ===")
    print(f"  captured_at            {snap['captured_at']}")
    print(f"  documents / versions   {snap['documents_total']} / {snap['document_versions_total']}")
    print(f"  clauses                {snap['clauses_total']}")
    for k, v in snap["clauses_by_unit_kind"].items():
        print(f"      {k:18s} {v}")
    print(f"  citations              {snap['citations_total']} "
          f"({snap['citations_resolved']} resolved)")
    print(f"  distinct code_sections {snap['distinct_code_sections_total']}")
    for k, v in snap["distinct_code_sections_by_unit_kind"].items():
        print(f"      {k:18s} {v}")
    print(f"  document_scope rows    {snap['document_scope_rows']}")
    print(f"  engine findings        {snap['findings_total']}")
    for k, v in snap["findings_by_unit_kind"].items():
        print(f"      {k:18s} {v}")
    print(f"  code_sections (KB)     {snap['code_sections_total']}   <- must survive cutover")
    print("  table counts:")
    for t, n in snap["table_counts"].items():
        flag = ""
        if t in EXPECT_ZERO:
            flag = "  <- expected 0 (safe to drop)" if n == 0 else "  <- NOT ZERO, investigate"
        print(f"      {t:20s} {n}{flag}")

    unexpected = [t for t in EXPECT_ZERO
                  if isinstance(snap["table_counts"].get(t), int)
                  and snap["table_counts"][t] != 0]
    if unexpected:
        print(f"\n  WARNING: expected-empty tables are populated: {unexpected}")
        print("  Task 3.1 drops these. Re-evaluate before proceeding.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture the pre-v2 production baseline")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    import psycopg2

    conn = psycopg2.connect(_dsn())
    conn.set_session(readonly=True)
    try:
        cur = conn.cursor()
        snap = collect(cur)
    finally:
        conn.close()

    snap["captured_at"] = datetime.now(timezone.utc).isoformat()
    snap["schema_version"] = "pre-v2"

    out = Path(args.out)
    out.write_text(json.dumps(snap, indent=2, sort_keys=True, default=str), encoding="utf-8")
    report(snap)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

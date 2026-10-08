"""
extract_register_citations.py

T5 — Retention register citations.

Scans ALL register_row clauses for citation-shaped text in any cell value,
using find_citation_spans + parse_citation from the citations grammar.
Inserts new rows into company.clause_citations with:
  - extraction_method = 'register_cell_parse'
  - stable citation_pk (UUID5 deterministic on clause_pk + column_name + citation_raw)
  - ON CONFLICT (citation_pk) DO NOTHING for idempotency

After inserting, calls resolve_all_citations(conn) to resolve new rows.

Skips cells where all parsed citations are source_system='unknown'.
Skips cells that already produced citations via an earlier run (idempotent).

Usage
-----
    cd /path/to/backend
    .venv/bin/python scripts/extract_register_citations.py
"""

from __future__ import annotations

import os
import sys
import uuid
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Bootstrap path so local app imports work
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

import psycopg2

from app.company_ingest.enrich.citations_grammar import (
    ParsedCitation,
    find_citation_spans,
    parse_citation,
)
from app.company_ingest.enrich.resolve_citations_db import resolve_all_citations


# ---------------------------------------------------------------------------
# Stable UUID helper
# ---------------------------------------------------------------------------

_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def stable_uuid(clause_pk: str, column_name: str, citation_raw: str) -> uuid.UUID:
    """Deterministic UUID5 so re-runs produce the same citation_pk."""
    name = f"{clause_pk}|{column_name}|{citation_raw}"
    return uuid.uuid5(_NAMESPACE, name)


# ---------------------------------------------------------------------------
# Helpers to map version_id -> doc label for reporting
# ---------------------------------------------------------------------------

def _build_version_doc_map(cur) -> dict[str, str]:
    """Return {version_id: doc_id} from company.document_versions."""
    cur.execute("SELECT version_id, doc_id FROM company.document_versions")
    return {str(r[0]): r[1] for r in cur.fetchall()}


def _rrs_version_id(cur) -> Optional[str]:
    """
    Find the version_id that contains rrs_id-keyed register rows.
    RPL-LEG-RRS-001 is identifiable because its row_cells have an 'rrs_id' key.
    """
    cur.execute(
        """
        SELECT DISTINCT version_id
        FROM company.clauses
        WHERE unit_kind = 'register_row'
          AND row_cells ? 'rrs_id'
        LIMIT 1
        """
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


# ---------------------------------------------------------------------------
# Before/after counters
# ---------------------------------------------------------------------------

def _citation_count_for_version(cur, version_id: str) -> int:
    cur.execute(
        """
        SELECT COUNT(cc.citation_pk)
        FROM company.clause_citations cc
        JOIN company.clauses cl ON cc.clause_pk = cl.clause_pk
        WHERE cl.version_id = %s
          AND cl.unit_kind = 'register_row'
        """,
        (version_id,),
    )
    return cur.fetchone()[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    url = os.environ["DATABASE_URL"].replace("+asyncpg", "").split("?")[0]
    conn = psycopg2.connect(url, sslmode="require")
    conn.autocommit = False
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # Identify the RRS version for before/after reporting
    # ------------------------------------------------------------------
    rrs_version_id = _rrs_version_id(cur)
    if rrs_version_id is None:
        print("No register_row clauses with rrs_id found; nothing to do.")
        conn.close()
        return

    before_rrs = _citation_count_for_version(cur, rrs_version_id)
    print(f"Before RPL-LEG-RRS-001: {before_rrs} citations")

    # ------------------------------------------------------------------
    # Fetch all register_row clauses
    # ------------------------------------------------------------------
    cur.execute(
        """
        SELECT clause_pk, version_id, row_cells
        FROM company.clauses
        WHERE unit_kind = 'register_row'
          AND row_cells IS NOT NULL
        """
    )
    all_rows = cur.fetchall()
    print(f"Total register_row clauses found: {len(all_rows)}")

    # ------------------------------------------------------------------
    # For each clause, scan each cell value for citations
    # ------------------------------------------------------------------
    inserts: list[tuple] = []

    for clause_pk, version_id, row_cells in all_rows:
        clause_pk_str = str(clause_pk)

        for col_name, cell_value in row_cells.items():
            if cell_value is None:
                continue
            cell_str = str(cell_value).strip()
            if not cell_str:
                continue

            # Find all citation spans within this cell string
            spans = find_citation_spans(cell_str)
            if not spans:
                continue

            for span_start, span_end, raw in spans:
                parsed_list = parse_citation(raw)
                for parsed in parsed_list:
                    # Skip unparseable citations
                    if parsed.source_system == "unknown":
                        continue

                    cpk = stable_uuid(clause_pk_str, col_name, parsed.citation_raw)

                    # Build the insert tuple
                    section_val: Optional[Decimal] = parsed.section  # may be None
                    inserts.append((
                        str(cpk),          # citation_pk
                        clause_pk_str,     # clause_pk
                        parsed.citation_raw,    # citation_raw
                        span_start,             # span_start
                        span_end,               # span_end
                        parsed.source_system,   # source_system
                        parsed.title,           # title (int or None)
                        parsed.article,         # article
                        parsed.rule,            # rule
                        section_val,            # section (Decimal or None)
                        parsed.subsection_path, # subsection_path
                        parsed.granularity,     # granularity
                        "register_cell_parse",  # extraction_method
                        "register_column",      # context
                    ))

    print(f"Citation candidates to insert: {len(inserts)}")

    if not inserts:
        print("No new citations to insert.")
        conn.close()
        return

    # ------------------------------------------------------------------
    # Batch insert with ON CONFLICT DO NOTHING
    # ------------------------------------------------------------------
    inserted = 0
    for row in inserts:
        cur.execute(
            """
            INSERT INTO company.clause_citations (
                citation_pk,
                clause_pk,
                citation_raw,
                span_start,
                span_end,
                source_system,
                title,
                article,
                rule,
                section,
                subsection_path,
                granularity,
                extraction_method,
                context,
                resolution_status,
                code_section_id,
                in_knowledge_base
            ) VALUES (
                %s::uuid, %s::uuid, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s,
                NULL, NULL, NULL
            )
            ON CONFLICT (citation_pk) DO NOTHING
            """,
            row,
        )
        inserted += cur.rowcount

    conn.commit()
    print(f"New rows inserted: {inserted}")

    # ------------------------------------------------------------------
    # Resolve new citations
    # ------------------------------------------------------------------
    print("Resolving new citations...")
    resolution_counts = resolve_all_citations(conn)
    print(f"Resolution counts: {resolution_counts}")

    # ------------------------------------------------------------------
    # After counts
    # ------------------------------------------------------------------
    after_rrs = _citation_count_for_version(cur, rrs_version_id)
    print(f"\nAfter RPL-LEG-RRS-001: {after_rrs} citations")
    print(f"New rows inserted across all register docs: {inserted}")
    print(
        f"Resolution of new rows: "
        + ", ".join(f"{k}={v}" for k, v in sorted(resolution_counts.items()))
    )

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()

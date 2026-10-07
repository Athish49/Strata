"""Task 3.2.1 — Register-row segmenter for P2 CSV registers.

Parses a P2 register CSV file into one ClauseUnit per data row.
"""
from __future__ import annotations

import csv
import logging
from pathlib import Path

from app.company_ingest.constants import ColumnRole, UnitKind, SectionKind
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.parse.text import normalize, sha256_text
from app.company_ingest.run_context import RunContext

logger = logging.getLogger(__name__)

# Column names that carry implementation-clause or cross-doc references
_REFERENCE_LIST_COLS = frozenset(
    {"implementation_clause", "wave2_clause_ref", "implementation_doc", "implementation_docs"}
)

# Column names that map to summary_text role
_SUMMARY_TEXT_COLS = frozenset(
    {"description", "title", "record_series_name", "notes"}
)

# Column names that map to status or enum role
_STATUS_COLS = frozenset({"status"})
_ENUM_COLS = frozenset({"priority"})


def _provisional_role(col_name: str, is_first_col: bool) -> str | None:
    """Return the provisional ColumnRole for a header column name.

    Rules (checked in order):
    1. First column → 'id'
    2. 'clause_id' → 'id' (doesn't exist in corpus, but guard it)
    3. Contains 'citation' → 'citation'
    4. Ends with '_id' (excluding the first col already handled) → 'owner_person'
    5. Ends with '_date' → 'date'
    6. In reference-list set → 'reference_list'
    7. In status set → 'status'
    8. In enum set → 'enum'
    9. In summary-text set → 'summary_text'
    10. Otherwise → None
    """
    if is_first_col:
        return ColumnRole.ID

    lower = col_name.lower()

    if lower == "clause_id":
        return ColumnRole.ID

    if "citation" in lower:
        return ColumnRole.CITATION

    if lower in _REFERENCE_LIST_COLS:
        return ColumnRole.REFERENCE_LIST

    if lower in _STATUS_COLS:
        return ColumnRole.STATUS

    if lower in _ENUM_COLS:
        return ColumnRole.ENUM

    if lower in _SUMMARY_TEXT_COLS:
        return ColumnRole.SUMMARY_TEXT

    if lower.endswith("_id"):
        return ColumnRole.OWNER_PERSON

    if lower.endswith("_date"):
        return ColumnRole.DATE

    return None


def _build_column_roles(headers: list[str]) -> dict[str, str | None]:
    """Build a {column_name: provisional_role} mapping from the header list."""
    roles: dict[str, str | None] = {}
    for i, col in enumerate(headers):
        roles[col] = _provisional_role(col, is_first_col=(i == 0))
    return roles


def segment_register(
    version_id: str,
    doc_id: str,
    csv_path: Path,
    document_title: str,
    ctx: RunContext,
) -> tuple[list[ClauseUnit], dict[str, str | None]]:
    """Parse a P2 register CSV into ClauseUnit objects, one per data row.

    The CSV is read with the csv module (RFC 4180, UTF-8), never pandas.

    Returns
    -------
    (clauses, column_roles)
        clauses       – one ClauseUnit per data row
        column_roles  – {column_name: provisional ColumnRole | None}
    """
    table_id = csv_path.stem
    heading_path = [document_title, table_id]

    clauses: list[ClauseUnit] = []
    column_roles: dict[str, str | None] = {}

    with csv_path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)

        if reader.fieldnames is None:
            ctx.issue(
                "warning",
                "3.2.1",
                "REGISTER_EMPTY_HEADERS",
                f"No headers found in {csv_path}",
                doc_id=doc_id,
                path=str(csv_path),
            )
            return [], {}

        headers: list[str] = list(reader.fieldnames)

        # Log empty/blank headers as info
        for col in headers:
            if not col.strip():
                ctx.issue(
                    "info",
                    "3.2.1",
                    "REGISTER_BLANK_HEADER",
                    f"Blank/empty column header in {csv_path}",
                    doc_id=doc_id,
                    path=str(csv_path),
                )

        column_roles = _build_column_roles(headers)

        # The first column is the row-ID column
        if not headers:
            ctx.issue(
                "warning",
                "3.2.1",
                "REGISTER_NO_HEADERS",
                f"CSV has no columns: {csv_path}",
                doc_id=doc_id,
                path=str(csv_path),
            )
            return [], {}

        first_col = headers[0]

        for row_number, row in enumerate(reader, start=1):
            # first_column_value is the row's unique ID
            row_id = row.get(first_col, "").strip()
            if not row_id:
                ctx.issue(
                    "info",
                    "3.2.1",
                    "REGISTER_MISSING_ROW_ID",
                    f"Row {row_number} in {csv_path} has no value in first column '{first_col}'",
                    doc_id=doc_id,
                    path=str(csv_path),
                )
                row_id = f"ROW_{row_number}"

            clause_id = f"{doc_id}:{row_id}"
            local_id = row_id

            # row_cells: all columns as strings
            row_cells: dict[str, str] = dict(row)

            # text_raw: non-empty cells rendered as "col: val" lines, in header order
            lines: list[str] = []
            for col in headers:
                val = row.get(col, "")
                if val is not None and val.strip():
                    lines.append(f"{col}: {val}")
            text_raw = "\n".join(lines)

            char_start = 0
            char_end = len(text_raw)

            text_norm = normalize(text_raw)
            text_sha = sha256_text(text_raw)

            clause = ClauseUnit(
                version_id=version_id,
                doc_id=doc_id,
                clause_id=clause_id,
                local_id=local_id,
                parent_clause_id=None,
                unit_kind=UnitKind.REGISTER_ROW,
                heading_path=heading_path,
                section_kind=SectionKind.PROCEDURE,
                ordinal=row_number,
                char_start=char_start,
                char_end=char_end,
                line_start=row_number,
                text_raw=text_raw,
                text_norm=text_norm,
                text_sha256=text_sha,
                table_id=table_id,
                row_cells=row_cells,
            )
            clauses.append(clause)

    ctx.count("register_rows_parsed", len(clauses))
    return clauses, column_roles

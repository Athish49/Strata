"""Task 3.2.1 — Register-row segmenter for P2 CSV registers.

Parses a P2 register CSV into one ClauseUnit per data row.  The ingest
service calls :func:`segment_register_text` with decoded text and the
declared ``RegisterSpec`` columns.
"""
from __future__ import annotations

import csv
import io
import logging
from collections.abc import Iterable

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


def _build_column_roles(
    headers: list[str],
    id_column: str | None = None,
    citation_columns: Iterable[str] = (),
) -> dict[str, str | None]:
    """Build a {column_name: provisional_role} mapping from the header list.

    When *id_column* is declared (``RegisterSpec.id_column``) it — not
    ``headers[0]`` — gets the ``id`` role, and the first column is classified
    like any other.  Declared *citation_columns* always get the ``citation``
    role, whatever they are named (TDD §3.4 gaps 1 and 2).
    """
    declared_citations = set(citation_columns)
    roles: dict[str, str | None] = {}
    for i, col in enumerate(headers):
        if id_column is not None:
            role = ColumnRole.ID if col == id_column else _provisional_role(col, is_first_col=False)
        else:
            role = _provisional_role(col, is_first_col=(i == 0))
        if col in declared_citations and col != id_column:
            role = ColumnRole.CITATION
        roles[col] = role
    return roles


def segment_register_text(
    version_id: str,
    doc_id: str,
    csv_text: str,
    document_title: str,
    ctx: RunContext,
    *,
    table_id: str,
    id_column: str | None = None,
    citation_columns: Iterable[str] = (),
    source_label: str | None = None,
) -> tuple[list[ClauseUnit], dict[str, str | None]]:
    """Parse already-decoded register CSV text, one ClauseUnit per data row.

    This is the entry point the ingest service uses: the API holds uploaded
    bytes, decodes them (``utf-8-sig``) and validates them against the declared
    ``RegisterSpec`` before this is called, so no file is read here.

    * *id_column* — the declared ``RegisterSpec.id_column``; ``clause_id`` is
      ``f"{doc_id}:{row[id_column]}"``.  ``None`` keeps the legacy
      ``headers[0]`` behaviour.
    * *citation_columns* — the declared ``RegisterSpec.citation_columns``;
      they get the ``citation`` column role.
    * A leading BOM is stripped; wholly blank rows (``,,,`` spreadsheet
      artefacts) are skipped and do not consume a row number, matching
      ``register_spec.validate_register_spec``'s numbering.
    * A row whose field count differs from the header emits a ``ctx.issue``
      warning; overflow fields (``csv.DictReader``'s ``None`` key) are kept
      in ``row_cells`` under ``"_overflow"`` rather than silently lost.

    The CSV is read with the csv module (RFC 4180), never pandas.
    """
    label = source_label or table_id
    heading_path = [document_title, table_id]
    csv_text = csv_text.lstrip("\ufeff")

    clauses: list[ClauseUnit] = []
    column_roles: dict[str, str | None] = {}

    reader = csv.DictReader(io.StringIO(csv_text, newline=""))

    if reader.fieldnames is None:
        ctx.issue(
            "warning",
            "3.2.1",
            "REGISTER_EMPTY_HEADERS",
            f"No headers found in {label}",
            doc_id=doc_id,
            path=label,
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
                f"Blank/empty column header in {label}",
                doc_id=doc_id,
                path=label,
            )

    if not headers:
        ctx.issue(
            "warning",
            "3.2.1",
            "REGISTER_NO_HEADERS",
            f"CSV has no columns: {label}",
            doc_id=doc_id,
            path=label,
        )
        return [], {}

    if id_column is not None and id_column not in headers:
        raise ValueError(
            f"id_column {id_column!r} is not a column of register {label!r}; "
            "validate the RegisterSpec (register_spec.validate_register_spec) first"
        )

    column_roles = _build_column_roles(headers, id_column, citation_columns)
    row_id_col = id_column if id_column is not None else headers[0]

    row_number = 0
    for row in reader:
        overflow = row.pop(None, None)  # type: ignore[call-overload]
        values = [v for v in row.values() if v is not None]
        if not overflow and not any(v.strip() for v in values):
            continue  # wholly blank row
        row_number += 1

        if overflow or any(v is None for v in row.values()):
            ctx.issue(
                "warning",
                "3.2.1",
                "REGISTER_RAGGED_ROW",
                f"Row {row_number} in {label} has "
                f"{len(values) + len(overflow or [])} fields; the header has "
                f"{len(headers)} — its column mapping may be wrong",
                doc_id=doc_id,
                path=label,
            )

        row_id = (row.get(row_id_col) or "").strip()
        if not row_id:
            ctx.issue(
                "info",
                "3.2.1",
                "REGISTER_MISSING_ROW_ID",
                f"Row {row_number} in {label} has no value in id column '{row_id_col}'",
                doc_id=doc_id,
                path=label,
            )
            row_id = f"ROW_{row_number}"

        clause_id = f"{doc_id}:{row_id}"
        local_id = row_id

        # row_cells: all columns as strings
        row_cells: dict[str, str] = {k: (v if v is not None else "") for k, v in row.items()}
        if overflow:
            row_cells["_overflow"] = "; ".join(overflow)

        # text_raw: non-empty cells rendered as "col: val" lines, in header order
        lines: list[str] = []
        for col in headers:
            val = row.get(col, "")
            if val is not None and val.strip():
                lines.append(f"{col}: {val}")
        text_raw = "\n".join(lines)

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
            char_start=0,
            char_end=len(text_raw),
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

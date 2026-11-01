"""Tests for task 3.2.1: Register-row segmenter (P2).

Unit tests use inline CSV fixtures (via tmp_path).
"""
from __future__ import annotations

import csv
import textwrap
from pathlib import Path

import pytest

from app.company_ingest.constants import ColumnRole
from app.company_ingest.parse.register_segmenter import segment_register_text
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_ctx() -> RunContext:
    return RunContext(company_id="test_co")


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> Path:
    """Write a CSV file from a list of row dicts.  Returns the path."""
    if fieldnames is None and rows:
        fieldnames = list(rows[0].keys())
    elif fieldnames is None:
        fieldnames = []
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestBasicParsing:
    """Basic 3-row CSV parses into 3 ClauseUnits."""

    def test_produces_correct_count(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "test_register.csv",
            [
                {"obligation_id": "OBL-001", "title": "Obligation 1", "status": "active"},
                {"obligation_id": "OBL-002", "title": "Obligation 2", "status": "active"},
                {"obligation_id": "OBL-003", "title": "Obligation 3", "status": "closed"},
            ],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Test Register", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert len(clauses) == 3

    def test_clause_id_format(self, tmp_path: Path) -> None:
        """clause_id = doc_id + ':' + first_column_value."""
        csv_file = write_csv(
            tmp_path / "compliance.csv",
            [{"obligation_id": "OBL-2024-0001", "title": "First"}],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "RPL-CMP-REG-001", csv_file.read_text(encoding="utf-8-sig"), "Compliance Register", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].clause_id == "RPL-CMP-REG-001:OBL-2024-0001"

    def test_local_id_is_first_column_value(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-2024-0001", "title": "First"}],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "RPL-CMP-REG-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].local_id == "OBL-2024-0001"

    def test_row_cells_contains_all_columns(self, tmp_path: Path) -> None:
        fieldnames = ["obligation_id", "citation", "title", "status"]
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "citation": "§1.2", "title": "T1", "status": "active"}],
            fieldnames=fieldnames,
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert set(clauses[0].row_cells.keys()) == {"obligation_id", "citation", "title", "status"}

    def test_text_raw_nonempty_cells_only(self, tmp_path: Path) -> None:
        """text_raw skips empty cells and renders as col: val lines."""
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "citation": "", "title": "My Title", "notes": ""}],
            fieldnames=["obligation_id", "citation", "title", "notes"],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        text = clauses[0].text_raw
        assert "obligation_id: OBL-001" in text
        assert "title: My Title" in text
        # Empty cols should not appear
        assert "citation:" not in text
        assert "notes:" not in text

    def test_text_raw_format_is_col_colon_val_lines(self, tmp_path: Path) -> None:
        """text_raw lines follow 'col: val' format, newline separated."""
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"event_id": "EVT-001", "title": "Annual Review"}],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        lines = clauses[0].text_raw.split("\n")
        assert lines[0] == "event_id: EVT-001"
        assert lines[1] == "title: Annual Review"

    def test_char_start_is_zero(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "reg.csv", [{"rrs_id": "RRS-001", "description": "Desc"}])
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].char_start == 0

    def test_char_end_equals_len_text_raw(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "reg.csv", [{"rrs_id": "RRS-001", "description": "Desc value"}])
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        unit = clauses[0]
        assert unit.char_end == len(unit.text_raw)

    def test_table_id_is_file_stem(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "compliance_register_2024-12-31.csv", [{"obligation_id": "OBL-001"}])
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].table_id == "compliance_register_2024-12-31"

    def test_heading_path_is_doc_title_and_table_id(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "calendar_events_2025.csv", [{"event_id": "EVT-001"}])
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Calendar Events 2025", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].heading_path == ["Calendar Events 2025", "calendar_events_2025"]

    def test_unit_kind_is_register_row(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "reg.csv", [{"obligation_id": "OBL-001"}])
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].unit_kind == "register_row"

    def test_section_kind_is_procedure(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "reg.csv", [{"obligation_id": "OBL-001"}])
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].section_kind == "procedure"

    def test_parent_clause_id_is_none(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "reg.csv", [{"obligation_id": "OBL-001"}])
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].parent_clause_id is None

    def test_ordinal_is_1indexed_row_number(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [
                {"obligation_id": "OBL-001"},
                {"obligation_id": "OBL-002"},
                {"obligation_id": "OBL-003"},
            ],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert [c.ordinal for c in clauses] == [1, 2, 3]

    def test_line_start_is_1indexed_row_number(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [
                {"obligation_id": "OBL-001"},
                {"obligation_id": "OBL-002"},
            ],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].line_start == 1
        assert clauses[1].line_start == 2

    def test_all_clause_ids_unique(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": f"OBL-{i:03d}"} for i in range(10)],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        ids = [c.clause_id for c in clauses]
        assert len(ids) == len(set(ids))

    def test_version_id_and_doc_id_propagated(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "reg.csv", [{"obligation_id": "OBL-001"}])
        ctx = make_ctx()
        clauses, _ = segment_register_text("my-ver-id", "MY-DOC", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].version_id == "my-ver-id"
        assert clauses[0].doc_id == "MY-DOC"


class TestColumnRoles:
    """Provisional column role detection."""

    def test_first_column_gets_id_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(tmp_path / "reg.csv", [{"obligation_id": "OBL-001", "title": "T"}])
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["obligation_id"] == ColumnRole.ID

    def test_citation_column_gets_citation_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "citation": "§1.1"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["citation"] == ColumnRole.CITATION

    def test_column_containing_citation_gets_citation_role(self, tmp_path: Path) -> None:
        """Any column whose name contains 'citation' → citation role."""
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"event_id": "EVT-001", "reg_citation": "§2.3"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["reg_citation"] == ColumnRole.CITATION

    def test_owner_id_column_gets_owner_person_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "accountable_owner_id": "P001"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["accountable_owner_id"] == ColumnRole.OWNER_PERSON

    def test_date_column_gets_date_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"event_id": "EVT-001", "due_date": "2025-01-01"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["due_date"] == ColumnRole.DATE

    def test_implementation_clause_gets_reference_list_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "implementation_clause": "§3.1"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["implementation_clause"] == ColumnRole.REFERENCE_LIST

    def test_wave2_clause_ref_gets_reference_list_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"rrs_id": "RRS-001", "wave2_clause_ref": "§4.2"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["wave2_clause_ref"] == ColumnRole.REFERENCE_LIST

    def test_implementation_doc_gets_reference_list_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "implementation_doc": "POL-001"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["implementation_doc"] == ColumnRole.REFERENCE_LIST

    def test_implementation_docs_gets_reference_list_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"rrs_id": "RRS-001", "implementation_docs": "POL-001, POL-002"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["implementation_docs"] == ColumnRole.REFERENCE_LIST

    def test_status_column_gets_status_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "status": "active"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["status"] == ColumnRole.STATUS

    def test_priority_column_gets_enum_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "priority": "high"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["priority"] == ColumnRole.ENUM

    def test_description_gets_summary_text_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "description": "Some text"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["description"] == ColumnRole.SUMMARY_TEXT

    def test_title_gets_summary_text_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "title": "A Title"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["title"] == ColumnRole.SUMMARY_TEXT

    def test_unknown_column_gets_none_role(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "some_weird_column": "value"}],
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert roles["some_weird_column"] is None

    def test_all_headers_present_in_roles(self, tmp_path: Path) -> None:
        fieldnames = ["obligation_id", "citation", "title", "status", "notes"]
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "citation": "§1", "title": "T", "status": "active", "notes": "n"}],
            fieldnames=fieldnames,
        )
        ctx = make_ctx()
        _, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert set(roles.keys()) == set(fieldnames)


class TestEdgeCases:
    """Edge cases: empty cells, special characters, etc."""

    def test_empty_csv_returns_empty_list(self, tmp_path: Path) -> None:
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("obligation_id,title\n", encoding="utf-8")
        ctx = make_ctx()
        clauses, roles = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses == []
        assert "obligation_id" in roles

    def test_all_cells_in_row_empty_except_id(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "title": "", "notes": ""}],
            fieldnames=["obligation_id", "title", "notes"],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        # text_raw should contain only the ID line
        assert "obligation_id: OBL-001" in clauses[0].text_raw
        assert "title:" not in clauses[0].text_raw
        assert "notes:" not in clauses[0].text_raw

    def test_run_context_counts_rows(self, tmp_path: Path) -> None:
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": f"OBL-{i:03d}"} for i in range(5)],
        )
        ctx = make_ctx()
        segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert ctx.stats.get("register_rows_parsed", 0) == 5

    def test_text_norm_is_normalized_text_raw(self, tmp_path: Path) -> None:
        """text_norm should be the normalized form of text_raw."""
        from app.company_ingest.parse.text import normalize
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "title": "UPPER CASE TITLE"}],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].text_norm == normalize(clauses[0].text_raw)

    def test_text_sha256_is_hash_of_text_raw(self, tmp_path: Path) -> None:
        """text_sha256 should be sha256 of text_raw (not text_norm)."""
        from app.company_ingest.parse.text import sha256_text
        csv_file = write_csv(
            tmp_path / "reg.csv",
            [{"obligation_id": "OBL-001", "title": "Title"}],
        )
        ctx = make_ctx()
        clauses, _ = segment_register_text("ver-1", "DOC-001", csv_file.read_text(encoding="utf-8-sig"), "Doc", ctx, table_id=csv_file.stem, source_label=str(csv_file))
        assert clauses[0].text_sha256 == sha256_text(clauses[0].text_raw)

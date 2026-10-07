"""Tests for task 3.1.1: Markdown clause segmenter.

Run non-corpus tests with:
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_markdown_segmenter.py -v -k "not qdrant and not corpus and not neon"

Run corpus integration tests (requires corpus docs on disk):
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_markdown_segmenter.py -v -m corpus
"""
from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.company_ingest.constants import SectionKind, UnitKind
from app.company_ingest.parse.markdown_segmenter import segment, segment_with_ctx
from app.company_ingest.run_context import RunContext

VERSION_ID = "00000000-0000-0000-0000-000000000001"
DOC_ID = "RPL-TEST-DOC-001"


# ===========================================================================
# Test 1: Simple numbered clauses 1.1, 1.2, 1.3
# ===========================================================================

SIMPLE_BODY = textwrap.dedent("""\
    <!-- clause: RPL-TEST-DOC-001:1.1 -->
    First clause content.

    <!-- clause: RPL-TEST-DOC-001:1.2 -->
    Second clause content.

    <!-- clause: RPL-TEST-DOC-001:1.3 -->
    Third clause content.
""")


def test_simple_numbered_clauses_count():
    units = segment(VERSION_ID, DOC_ID, SIMPLE_BODY, 0)
    assert len(units) == 3


def test_simple_numbered_clauses_ids():
    units = segment(VERSION_ID, DOC_ID, SIMPLE_BODY, 0)
    ids = [u.clause_id for u in units]
    assert ids == [
        "RPL-TEST-DOC-001:1.1",
        "RPL-TEST-DOC-001:1.2",
        "RPL-TEST-DOC-001:1.3",
    ]


def test_simple_numbered_clauses_local_ids():
    units = segment(VERSION_ID, DOC_ID, SIMPLE_BODY, 0)
    assert [u.local_id for u in units] == ["1.1", "1.2", "1.3"]


def test_simple_numbered_clauses_text():
    units = segment(VERSION_ID, DOC_ID, SIMPLE_BODY, 0)
    assert "First clause content." in units[0].text_raw
    assert "Second clause content." in units[1].text_raw
    assert "Third clause content." in units[2].text_raw


def test_simple_numbered_clauses_unit_kind():
    units = segment(VERSION_ID, DOC_ID, SIMPLE_BODY, 0)
    for u in units:
        assert u.unit_kind == UnitKind.SECTION


def test_simple_numbered_clauses_ordinals():
    units = segment(VERSION_ID, DOC_ID, SIMPLE_BODY, 0)
    assert [u.ordinal for u in units] == [0, 1, 2]


# ===========================================================================
# Test 2: Nested clauses — parent_clause_id
# ===========================================================================

NESTED_BODY = textwrap.dedent("""\
    <!-- clause: RPL-TEST-DOC-001:7.2 -->
    Section 7.2 intro.

    <!-- clause: RPL-TEST-DOC-001:7.2.1 -->
    Subsection 7.2.1 text.

    <!-- clause: RPL-TEST-DOC-001:7.2.2 -->
    Subsection 7.2.2 text.
""")


def test_nested_parent_clause_id_direct():
    units = segment(VERSION_ID, DOC_ID, NESTED_BODY, 0)
    by_id = {u.clause_id: u for u in units}
    assert by_id["RPL-TEST-DOC-001:7.2"].parent_clause_id is None
    assert by_id["RPL-TEST-DOC-001:7.2.1"].parent_clause_id == "RPL-TEST-DOC-001:7.2"
    assert by_id["RPL-TEST-DOC-001:7.2.2"].parent_clause_id == "RPL-TEST-DOC-001:7.2"


# ===========================================================================
# Test 3: Table marker → table_row ClauseUnits
# ===========================================================================

TABLE_BODY = textwrap.dedent("""\
    ## Regulatory Basis

    <!-- table: RPL-TEST-DOC-001:T1 -->
    | ID | Citation | Description |
    |---|---|---|
    | T1-1 | IAC 1-1 | First rule |
    | T1-2 | IAC 1-2 | Second rule |
    | T1-3 | IAC 1-3 | Third rule |
""")


def test_table_marker_produces_three_rows():
    units = segment(VERSION_ID, DOC_ID, TABLE_BODY, 0)
    assert len(units) == 3


def test_table_rows_unit_kind():
    units = segment(VERSION_ID, DOC_ID, TABLE_BODY, 0)
    for u in units:
        assert u.unit_kind == UnitKind.TABLE_ROW


def test_table_rows_table_id():
    units = segment(VERSION_ID, DOC_ID, TABLE_BODY, 0)
    for u in units:
        assert u.table_id == "T1"


def test_table_rows_clause_ids():
    units = segment(VERSION_ID, DOC_ID, TABLE_BODY, 0)
    ids = [u.clause_id for u in units]
    assert ids == [
        "RPL-TEST-DOC-001:T1-1",
        "RPL-TEST-DOC-001:T1-2",
        "RPL-TEST-DOC-001:T1-3",
    ]


def test_table_rows_row_cells():
    units = segment(VERSION_ID, DOC_ID, TABLE_BODY, 0)
    assert units[0].row_cells == {"ID": "T1-1", "Citation": "IAC 1-1", "Description": "First rule"}
    assert units[1].row_cells == {"ID": "T1-2", "Citation": "IAC 1-2", "Description": "Second rule"}
    assert units[2].row_cells == {"ID": "T1-3", "Citation": "IAC 1-3", "Description": "Third rule"}


def test_table_rows_text_raw():
    units = segment(VERSION_ID, DOC_ID, TABLE_BODY, 0)
    # text_raw should contain column: value pairs
    assert "ID: T1-1" in units[0].text_raw
    assert "Citation: IAC 1-1" in units[0].text_raw
    assert "Description: First rule" in units[0].text_raw


# ===========================================================================
# Test 4: Form-field clause App-A.F1
# ===========================================================================

FORM_BODY = textwrap.dedent("""\
    <!-- clause: RPL-TEST-DOC-001:App-A.F1 -->
    Field: Customer Name

    <!-- clause: RPL-TEST-DOC-001:App-A.F2 -->
    Field: Account Number
""")


def test_form_field_unit_kind():
    units = segment(VERSION_ID, DOC_ID, FORM_BODY, 0)
    assert len(units) == 2
    assert units[0].unit_kind == UnitKind.FORM_FIELD
    assert units[1].unit_kind == UnitKind.FORM_FIELD


def test_form_field_local_ids():
    units = segment(VERSION_ID, DOC_ID, FORM_BODY, 0)
    assert units[0].local_id == "App-A.F1"
    assert units[1].local_id == "App-A.F2"


# ===========================================================================
# Test 5: Tariff clause R01.D01 → tariff_subrule
# ===========================================================================

TARIFF_BODY = textwrap.dedent("""\
    <!-- clause: RPL-TEST-DOC-001:R01.D01 -->
    Tariff subrule definition text.

    <!-- clause: RPL-TEST-DOC-001:R02.1 -->
    Another tariff subrule.
""")


def test_tariff_subrule_unit_kind():
    units = segment(VERSION_ID, DOC_ID, TARIFF_BODY, 0)
    assert len(units) == 2
    assert units[0].unit_kind == UnitKind.TARIFF_SUBRULE
    assert units[1].unit_kind == UnitKind.TARIFF_SUBRULE


# ===========================================================================
# Test 6: Section clause S01.1 → section unit_kind
# ===========================================================================

SHEET_BODY = textwrap.dedent("""\
    <!-- clause: RPL-TEST-DOC-001:S01.1 -->
    Sheet one, section one content.

    <!-- clause: RPL-TEST-DOC-001:S04.3 -->
    Sheet four, section three content.
""")


def test_sheet_section_unit_kind():
    units = segment(VERSION_ID, DOC_ID, SHEET_BODY, 0)
    assert len(units) == 2
    assert units[0].unit_kind == UnitKind.SECTION
    assert units[1].unit_kind == UnitKind.SECTION


# ===========================================================================
# Test 7: heading_path updated correctly
# ===========================================================================

HEADING_BODY = textwrap.dedent("""\
    ## Section One

    <!-- clause: RPL-TEST-DOC-001:1.1 -->
    Content under section one.

    ## Section Two

    <!-- clause: RPL-TEST-DOC-001:2.1 -->
    Content under section two.

    ### Section Two Sub

    <!-- clause: RPL-TEST-DOC-001:2.1.1 -->
    Content under sub-section.
""")


def test_heading_path_updates():
    units = segment(VERSION_ID, DOC_ID, HEADING_BODY, 0)
    by_id = {u.clause_id: u for u in units}
    assert by_id["RPL-TEST-DOC-001:1.1"].heading_path == ["Section One"]
    assert by_id["RPL-TEST-DOC-001:2.1"].heading_path == ["Section Two"]
    assert by_id["RPL-TEST-DOC-001:2.1.1"].heading_path == ["Section Two", "Section Two Sub"]


def test_heading_path_ordinals():
    units = segment(VERSION_ID, DOC_ID, HEADING_BODY, 0)
    assert [u.local_id for u in units] == ["1.1", "2.1", "2.1.1"]


# ===========================================================================
# Test 8: section_kind — Definitions heading → definitions
# ===========================================================================

SECTION_KIND_BODY = textwrap.dedent("""\
    ## Definitions

    <!-- clause: RPL-TEST-DOC-001:3.1 -->
    Term: Means something.

    ## Purpose

    <!-- clause: RPL-TEST-DOC-001:1.1 -->
    This procedure establishes...

    ## Scope and Applicability

    <!-- clause: RPL-TEST-DOC-001:2.1 -->
    Applies to all employees.

    ## Revision History

    <!-- clause: RPL-TEST-DOC-001:20.1 -->
    Version 1.0: initial.
""")


def test_section_kind_definitions():
    units = segment(VERSION_ID, DOC_ID, SECTION_KIND_BODY, 0)
    by_id = {u.clause_id: u for u in units}
    assert by_id["RPL-TEST-DOC-001:3.1"].section_kind == SectionKind.DEFINITIONS


def test_section_kind_purpose():
    units = segment(VERSION_ID, DOC_ID, SECTION_KIND_BODY, 0)
    by_id = {u.clause_id: u for u in units}
    assert by_id["RPL-TEST-DOC-001:1.1"].section_kind == SectionKind.PURPOSE


def test_section_kind_scope():
    units = segment(VERSION_ID, DOC_ID, SECTION_KIND_BODY, 0)
    by_id = {u.clause_id: u for u in units}
    assert by_id["RPL-TEST-DOC-001:2.1"].section_kind == SectionKind.SCOPE


def test_section_kind_revision_history():
    units = segment(VERSION_ID, DOC_ID, SECTION_KIND_BODY, 0)
    by_id = {u.clause_id: u for u in units}
    assert by_id["RPL-TEST-DOC-001:20.1"].section_kind == SectionKind.REVISION_HISTORY


# ===========================================================================
# Test 9: Mermaid block → row_cells has has_mermaid=True
# ===========================================================================

MERMAID_BODY = textwrap.dedent("""\
    <!-- clause: RPL-TEST-DOC-001:5.1 -->
    Process overview:

    ```mermaid
    graph TD
        A --> B
    ```

    <!-- clause: RPL-TEST-DOC-001:5.2 -->
    No diagram here.
""")


def test_mermaid_block_sets_row_cells():
    units = segment(VERSION_ID, DOC_ID, MERMAID_BODY, 0)
    assert len(units) == 2
    assert units[0].row_cells == {"has_mermaid": True}
    assert units[1].row_cells is None


# ===========================================================================
# Test 10: Unclaimed text (text before first marker in section)
# ===========================================================================

UNCLAIMED_BODY = textwrap.dedent("""\
    ## Section One

    This text has no clause marker yet.
    More unclaimed text here.

    <!-- clause: RPL-TEST-DOC-001:1.1 -->
    First clause content.
""")


def test_unclaimed_text_still_counted_via_ctx():
    ctx = RunContext()
    units = segment_with_ctx(VERSION_ID, DOC_ID, UNCLAIMED_BODY, 0, ctx)
    # The unclaimed text before 1.1 should be counted in stats
    assert ctx.stats.get("unclaimed_text_chars", 0) > 0


def test_unclaimed_text_clause_still_produced():
    """Even with unclaimed text before it, the clause is still produced."""
    units = segment(VERSION_ID, DOC_ID, UNCLAIMED_BODY, 0)
    assert len(units) == 1
    assert units[0].clause_id == "RPL-TEST-DOC-001:1.1"


# ===========================================================================
# Test 11: body_offset — slicing full file text reproduces text_raw
# ===========================================================================

PREAMBLE = "---\nyaml: true\n---\n"
OFFSET_BODY = textwrap.dedent("""\
    <!-- clause: RPL-TEST-DOC-001:1.1 -->
    Line one.
    Line two.

    <!-- clause: RPL-TEST-DOC-001:1.2 -->
    Line three.
""")


def test_body_offset_char_start_end():
    body_offset = len(PREAMBLE)
    full_text = PREAMBLE + OFFSET_BODY
    units = segment(VERSION_ID, DOC_ID, OFFSET_BODY, body_offset)
    for unit in units:
        assert full_text[unit.char_start:unit.char_end] == unit.text_raw, (
            f"Slice mismatch for {unit.clause_id}: "
            f"expected {unit.text_raw!r}, "
            f"got {full_text[unit.char_start:unit.char_end]!r}"
        )


def test_body_offset_zero_also_works():
    units = segment(VERSION_ID, DOC_ID, OFFSET_BODY, 0)
    for unit in units:
        assert OFFSET_BODY[unit.char_start:unit.char_end] == unit.text_raw


# ===========================================================================
# Test 12: No duplicate clause IDs in a document
# ===========================================================================

UNIQUE_BODY = textwrap.dedent("""\
    ## Section A

    <!-- clause: RPL-TEST-DOC-001:1.1 -->
    Clause 1.1.

    <!-- clause: RPL-TEST-DOC-001:1.2 -->
    Clause 1.2.

    ## Section B

    <!-- clause: RPL-TEST-DOC-001:2.1 -->
    Clause 2.1.

    <!-- table: RPL-TEST-DOC-001:T1 -->
    | ID | Value |
    |---|---|
    | T1-1 | Alpha |
    | T1-2 | Beta |
""")


def test_no_duplicate_clause_ids():
    units = segment(VERSION_ID, DOC_ID, UNIQUE_BODY, 0)
    ids = [u.clause_id for u in units]
    assert len(ids) == len(set(ids)), f"Duplicate clause IDs found: {ids}"


# ===========================================================================
# Test 13: Non-matching ID → unit_kind=section (with warning in ctx)
# ===========================================================================

NONMATCH_BODY = textwrap.dedent("""\
    <!-- clause: RPL-TEST-DOC-001:WEIRD-ID -->
    Some content.
""")


def test_nonmatching_id_unit_kind_section():
    units = segment(VERSION_ID, DOC_ID, NONMATCH_BODY, 0)
    assert len(units) == 1
    assert units[0].unit_kind == UnitKind.SECTION


def test_nonmatching_id_issues_warning():
    ctx = RunContext()
    units = segment_with_ctx(VERSION_ID, DOC_ID, NONMATCH_BODY, 0, ctx)
    warnings_found = [
        i for i in ctx.issues
        if i.severity == "warning" and i.code == "unknown_local_id"
    ]
    assert len(warnings_found) == 1


# ===========================================================================
# Test: Format 2 clause markers (no "clause:" prefix)
# ===========================================================================

FORMAT2_BODY = textwrap.dedent("""\
    ## Sheet 1

    <!-- RPL-TEST-DOC-001:S01.1 -->
    Sheet one section one.

    <!-- RPL-TEST-DOC-001:S01.2 -->
    Sheet one section two.
""")


def test_format2_clause_markers_parsed():
    units = segment(VERSION_ID, DOC_ID, FORMAT2_BODY, 0)
    assert len(units) == 2
    ids = [u.clause_id for u in units]
    assert "RPL-TEST-DOC-001:S01.1" in ids
    assert "RPL-TEST-DOC-001:S01.2" in ids


# ===========================================================================
# Test: Heading ending a clause (level <= current heading)
# ===========================================================================

HEADING_BOUNDARY_BODY = textwrap.dedent("""\
    ## Sheet One

    <!-- RPL-TEST-DOC-001:S01.1 -->
    Content of S01.1.

    <!-- RPL-TEST-DOC-001:S01.2 -->
    Content of S01.2.

    ## Sheet Two

    <!-- RPL-TEST-DOC-001:S02.1 -->
    Content of S02.1.
""")


def test_heading_ends_clause_correctly():
    units = segment(VERSION_ID, DOC_ID, HEADING_BOUNDARY_BODY, 0)
    assert len(units) == 3
    # S01.2 content should not include Sheet Two heading
    s012 = next(u for u in units if u.local_id == "S01.2")
    assert "Sheet Two" not in s012.text_raw


def test_s02_heading_path():
    units = segment(VERSION_ID, DOC_ID, HEADING_BOUNDARY_BODY, 0)
    s021 = next(u for u in units if u.local_id == "S02.1")
    assert s021.heading_path == ["Sheet Two"]


# ===========================================================================
# Test: doc_id and version_id are set on units
# ===========================================================================

def test_doc_id_and_version_id_set():
    units = segment(VERSION_ID, DOC_ID, SIMPLE_BODY, 0)
    for u in units:
        assert u.doc_id == DOC_ID
        assert u.version_id == VERSION_ID


# ===========================================================================
# Test: text_norm and text_sha256 are populated
# ===========================================================================

def test_text_norm_and_sha256():
    units = segment(VERSION_ID, DOC_ID, SIMPLE_BODY, 0)
    for u in units:
        assert u.text_norm  # non-empty
        assert len(u.text_sha256) == 64  # SHA-256 hex


# ===========================================================================
# Corpus integration tests  (requires corpus docs on disk)
# ===========================================================================

CORPUS_DOCS_DIR = (
    Path(__file__).parents[2]
    / "app" / "company" / "corpus" / "docs"
)

P1_DOC_IDS = [
    "RPL-CS-PRO-004",
    "RPL-CS-PRO-007",
    "RPL-CS-PRO-011",
    "RPL-DCC-PRO-003",
    "RPL-DO-PLN-002",
    "RPL-ENV-PRO-005",
    "RPL-MTR-PGM-001",
    "RPL-SAF-PRO-009",
    "RPL-TAR-GRR-012",
    "RPL-CMP-REG-001",
    "RPL-LEG-RRS-001",
    "RPL-REG-CAL-2025",
]


def _find_md_file(doc_id: str) -> Path | None:
    doc_dir = CORPUS_DOCS_DIR / doc_id
    if not doc_dir.exists():
        return None
    for f in doc_dir.glob("*.md"):
        return f
    return None


@pytest.mark.corpus
@pytest.mark.parametrize("doc_id", P1_DOC_IDS)
def test_corpus_clause_count_positive(doc_id: str):
    md_path = _find_md_file(doc_id)
    if md_path is None:
        pytest.skip(f"Corpus file not found for {doc_id}")

    full_text = md_path.read_text(encoding="utf-8")

    # Split front matter off to get body
    from app.company_ingest.parse.front_matter import split_front_matter
    _fm, body_text, body_offset = split_front_matter(full_text, doc_id)

    units = segment(VERSION_ID, doc_id, body_text, body_offset)
    assert len(units) > 0, f"{doc_id}: expected at least one clause unit"


@pytest.mark.corpus
@pytest.mark.parametrize("doc_id", P1_DOC_IDS)
def test_corpus_clause_ids_unique(doc_id: str):
    md_path = _find_md_file(doc_id)
    if md_path is None:
        pytest.skip(f"Corpus file not found for {doc_id}")

    full_text = md_path.read_text(encoding="utf-8")

    from app.company_ingest.parse.front_matter import split_front_matter
    _fm, body_text, body_offset = split_front_matter(full_text, doc_id)

    units = segment(VERSION_ID, doc_id, body_text, body_offset)
    ids = [u.clause_id for u in units]
    assert len(ids) == len(set(ids)), (
        f"{doc_id}: duplicate clause IDs: "
        + ", ".join(cid for cid in set(ids) if ids.count(cid) > 1)
    )


@pytest.mark.corpus
@pytest.mark.parametrize("doc_id", P1_DOC_IDS)
def test_corpus_body_offset_slicing(doc_id: str):
    """char_start/char_end must slice the original file text to reproduce text_raw."""
    md_path = _find_md_file(doc_id)
    if md_path is None:
        pytest.skip(f"Corpus file not found for {doc_id}")

    full_text = md_path.read_text(encoding="utf-8")

    from app.company_ingest.parse.front_matter import split_front_matter
    _fm, body_text, body_offset = split_front_matter(full_text, doc_id)

    units = segment(VERSION_ID, doc_id, body_text, body_offset)

    # Table rows have char_start/char_end pointing to their raw pipe-table line,
    # not to text_raw (which is the rendered version).  Skip table rows.
    prose_units = [u for u in units if u.unit_kind != UnitKind.TABLE_ROW]
    for u in prose_units:
        sliced = full_text[u.char_start:u.char_end]
        assert sliced == u.text_raw, (
            f"{doc_id} {u.clause_id}: "
            f"full_text[{u.char_start}:{u.char_end}] = {sliced!r} "
            f"!= text_raw = {u.text_raw!r}"
        )

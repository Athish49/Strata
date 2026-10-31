"""Tests for task 4.2: DOCX extractor.

Run with:
    cd backend && .venv/bin/python -m pytest tests/company_ingest/test_extract_docx.py -v

The corpus-backed tests are marked ``corpus`` (deselect with -m "not corpus").
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

import pytest

docx_lib = pytest.importorskip("docx")

from app.company_ingest.extract import (  # noqa: E402
    DOCX_CONTENT_TYPE,
    DocumentExtractor,
    DocxExtractor,
    ExtractedDocument,
    anchor_clauses,
    extractor_for,
    marker_doc_id_supported,
)
from app.company_ingest.extract.docx import UnreadableDocumentError  # noqa: E402
from app.company_ingest.parse.front_matter import split_front_matter  # noqa: E402
from app.company_ingest.parse.markdown_segmenter import segment_with_ctx  # noqa: E402
from app.company_ingest.run_context import RunContext  # noqa: E402

BACKEND_ROOT = Path(__file__).resolve().parents[2]
CORPUS = BACKEND_ROOT / "synthetic" / "corpus" / "docs"
FIXTURE_DOC_ID = "RPL-CS-PRO-004"
# Test-owned copy (not the deletable synthetic/ corpus render, which this module used to
# read directly): same reasoning as task 9.4's fix for test_jobs_recovery.py/test_service.py.
FIXTURE_DOCX = BACKEND_ROOT / "tests" / "fixtures" / "docx" / f"{FIXTURE_DOC_ID}_v5.1.docx"
FIXTURE_MD = CORPUS / FIXTURE_DOC_ID / f"{FIXTURE_DOC_ID}_v5.1.md"
VERSION_ID = "00000000-0000-0000-0000-000000000042"

# Smallest valid 1x1 PNG, for the image-only document.
_PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFAAH"
    "/q842iQAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_bytes(document) -> bytes:
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def _heading_lines(markdown: str) -> list[str]:
    return [
        line
        for line in markdown.splitlines()
        if re.match(r"^#{1,6}\s+\S", line)
    ]


def _clause_count(body: str, doc_id: str, offset: int = 0) -> int:
    ctx = RunContext(company_id="RPL")
    return len(segment_with_ctx(VERSION_ID, doc_id, body, offset, ctx))


@pytest.fixture(scope="module")
def extracted() -> ExtractedDocument:
    if not FIXTURE_DOCX.exists():  # pragma: no cover - corpus missing
        pytest.skip(f"corpus fixture missing: {FIXTURE_DOCX}")
    return DocxExtractor().extract(FIXTURE_DOCX.read_bytes(), FIXTURE_DOCX.name)


# ---------------------------------------------------------------------------
# Contract / registry
# ---------------------------------------------------------------------------

def test_docx_extractor_satisfies_protocol():
    assert isinstance(DocxExtractor(), DocumentExtractor)
    assert DOCX_CONTENT_TYPE in DocxExtractor.content_types


def test_registry_maps_content_type_to_extractor():
    assert isinstance(extractor_for(DOCX_CONTENT_TYPE), DocxExtractor)
    # Tolerates parameters on the header.
    assert isinstance(
        extractor_for(f"{DOCX_CONTENT_TYPE}; charset=utf-8"), DocxExtractor
    )
    # PDF is deliberately unregistered: that is the 415 path.
    assert extractor_for("application/pdf") is None
    assert extractor_for(None) is None


def test_method_identifies_library_and_version():
    method = DocxExtractor().method
    assert method.startswith("python-docx/")
    assert re.match(r"^python-docx/\d+\.\d+", method), method


def test_corrupt_bytes_raise_unreadable_document_error():
    with pytest.raises(UnreadableDocumentError):
        DocxExtractor().extract(b"not a docx at all", "bogus.docx")


# ---------------------------------------------------------------------------
# Acceptance: headings
# ---------------------------------------------------------------------------

@pytest.mark.corpus
def test_fixture_yields_at_least_thirty_heading_lines(extracted):
    headings = _heading_lines(extracted.markdown)
    assert len(headings) >= 30, f"only {len(headings)} heading lines"


@pytest.mark.corpus
def test_heading_levels_match_source_styles(extracted):
    """`Heading1` ×2 and `Heading2` ×31 must come out as `#` ×2 and `##` ×31."""
    document = docx_lib.Document(io.BytesIO(FIXTURE_DOCX.read_bytes()))
    style_counts: dict[str, int] = {}
    for paragraph in document.paragraphs:
        if not paragraph.text.strip():
            continue
        name = (paragraph.style.name or "").replace(" ", "")
        if name.startswith("Heading"):
            style_counts[name] = style_counts.get(name, 0) + 1

    level_counts: dict[int, int] = {}
    for line in _heading_lines(extracted.markdown):
        level = len(line) - len(line.lstrip("#"))
        level_counts[level] = level_counts.get(level, 0) + 1

    assert style_counts.get("Heading1") == 2
    assert style_counts.get("Heading2") == 31
    assert level_counts.get(1) == style_counts["Heading1"]
    assert level_counts.get(2) == style_counts["Heading2"]


@pytest.mark.corpus
def test_page_count_and_confidence(extracted):
    assert extracted.page_count is None  # DOCX stores no pagination
    assert extracted.confidence == 1.0


# ---------------------------------------------------------------------------
# Acceptance: tables
# ---------------------------------------------------------------------------

@pytest.mark.corpus
def test_tables_render_as_pipe_tables_with_separator(extracted):
    lines = extracted.markdown.splitlines()
    separators = [i for i, line in enumerate(lines) if re.match(r"^\|[\s\-:|]+\|$", line)]
    assert separators, "no separator row found"
    for i in separators:
        assert lines[i - 1].startswith("|"), "separator must follow a header row"
        assert lines[i + 1].startswith("|"), "separator must precede a data row"
    # One separator per rendered table.
    table_starts = sum(
        1
        for i, line in enumerate(lines)
        if line.startswith("|") and (i == 0 or not lines[i - 1].startswith("|"))
    )
    assert len(separators) == table_starts


def test_table_cells_are_escaped_and_flattened():
    document = docx_lib.Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Header | A"
    table.cell(0, 1).text = "Header B"
    table.cell(1, 0).text = "line one"
    table.cell(1, 0).add_paragraph("line two")
    table.cell(1, 1).text = "value"

    markdown = DocxExtractor().extract(_to_bytes(document), "t.docx").markdown
    rows = [line for line in markdown.splitlines() if line.startswith("|")]
    # A literal pipe becomes an entity, not "\|": the segmenter splits on "|"
    # without honouring escapes, so "\|" would still misalign the row.
    assert rows[0] == "| Header &#124; A | Header B |"
    assert rows[1] == "| --- | --- |"
    assert rows[2] == "| line one line two | value |"
    # Every row has the same pipe count, so the segmenter's cell split lines up.
    assert len({row.count("|") for row in rows}) == 1


def test_blank_header_cells_get_positional_names():
    document = docx_lib.Document()
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = ""
    table.cell(0, 1).text = ""
    table.cell(1, 0).text = "a"
    table.cell(1, 1).text = "b"
    markdown = DocxExtractor().extract(_to_bytes(document), "t.docx").markdown
    assert "| Column 1 | Column 2 |" in markdown


# ---------------------------------------------------------------------------
# Document order and escaping
# ---------------------------------------------------------------------------

def test_body_is_walked_in_document_order():
    """`document.paragraphs` and `document.tables` are separate sequences."""
    document = docx_lib.Document()
    document.add_paragraph("Alpha", style="Heading 1")
    table = document.add_table(rows=1, cols=1)
    table.cell(0, 0).text = "Beta"
    document.add_paragraph("Gamma")

    markdown = DocxExtractor().extract(_to_bytes(document), "t.docx").markdown
    assert markdown.index("# Alpha") < markdown.index("Beta") < markdown.index("Gamma")


def test_markdown_constructs_in_body_text_are_escaped():
    document = docx_lib.Document()
    document.add_paragraph("# not a heading")
    document.add_paragraph("```not a fence")
    document.add_paragraph("|not a table row")
    document.add_paragraph("Heading", style="Heading 2")
    document.add_paragraph("Body text.")

    markdown = DocxExtractor().extract(_to_bytes(document), "t.docx").markdown
    assert r"\# not a heading" in markdown
    assert "\\```not a fence" in markdown
    assert r"\|not a table row" in markdown
    # The real heading still parses, i.e. nothing got swallowed by a fence.
    assert "## Heading" in _heading_lines(markdown)[0]
    units = segment_with_ctx(
        VERSION_ID,
        "RPL-TEST-DOC-001",
        anchor_clauses(markdown, "RPL-TEST-DOC-001"),
        0,
        RunContext(),
    )
    # One preamble clause for the escaped lines, one for the real heading.
    # A level-2 heading with no number synthesizes a depth-2 id.
    assert [u.local_id for u in units] == ["s0", "s1.1"]
    assert "Body text." in units[1].text_raw


def test_list_styles_map_to_markdown_lists():
    document = docx_lib.Document()
    document.add_paragraph("bullet one", style="List Bullet")
    document.add_paragraph("number one", style="List Number")
    markdown = DocxExtractor().extract(_to_bytes(document), "t.docx").markdown
    assert "- bullet one" in markdown
    assert "1. number one" in markdown


# ---------------------------------------------------------------------------
# Acceptance: empty-extraction guard input (TDD §3.2, consumed by task 6.1)
# ---------------------------------------------------------------------------

def test_image_only_docx_yields_empty_markdown(tmp_path: Path):
    png = tmp_path / "pixel.png"
    png.write_bytes(_PNG_1PX)
    document = docx_lib.Document()
    document.add_picture(str(png))
    document.add_picture(str(png))

    result = DocxExtractor().extract(_to_bytes(document), "images.docx")
    assert result.markdown.strip() == "", repr(result.markdown[:200])


def test_empty_docx_yields_empty_markdown():
    result = DocxExtractor().extract(_to_bytes(docx_lib.Document()), "empty.docx")
    assert result.markdown.strip() == ""


# ---------------------------------------------------------------------------
# Clause anchoring
# ---------------------------------------------------------------------------

def test_anchor_clauses_uses_section_numbers_then_synthesized_ids():
    markdown = "# Overview\n\nText.\n\n## 7. Notice Requirements\n\nMore.\n"
    anchored = anchor_clauses(markdown, "RPL-TEST-DOC-001")
    assert "<!-- clause: RPL-TEST-DOC-001:s1 -->" in anchored
    assert "<!-- clause: RPL-TEST-DOC-001:7 -->" in anchored
    units = segment_with_ctx(
        VERSION_ID, "RPL-TEST-DOC-001", anchored, 0, RunContext()
    )
    assert [u.local_id for u in units] == ["s1", "7"]
    assert units[1].heading_path == ["Overview", "7. Notice Requirements"]


def test_prose_after_a_table_stays_inside_a_clause():
    """A table marker closes the open clause; the next prose needs a new one."""
    document = docx_lib.Document()
    document.add_paragraph("7. Notice Requirements", style="Heading 2")
    document.add_paragraph("Before the table.")
    table = document.add_table(rows=2, cols=2)
    table.cell(0, 0).text = "Step"
    table.cell(0, 1).text = "Owner"
    table.cell(1, 0).text = "Mail notice"
    table.cell(1, 1).text = "CSR"
    document.add_paragraph("AFTER THE TABLE this text must survive.")

    anchored = anchor_clauses(
        DocxExtractor().extract(_to_bytes(document), "t.docx").markdown,
        "RPL-TEST-DOC-001",
    )
    units = segment_with_ctx(
        VERSION_ID, "RPL-TEST-DOC-001", anchored, 0, RunContext()
    )
    sections = [u for u in units if u.unit_kind != "table_row"]
    assert any("AFTER THE TABLE" in u.text_raw for u in sections)
    assert any("Before the table." in u.text_raw for u in sections)
    # Continuation keeps the numbered-section grammar, so parenting still works.
    assert [u.local_id for u in sections] == ["7", "7a"]


def test_preamble_before_first_heading_is_claimed():
    document = docx_lib.Document()
    document.add_paragraph("Rockridge Power & Light Company")
    document.add_paragraph("1. Purpose", style="Heading 2")
    document.add_paragraph("Body.")
    anchored = anchor_clauses(
        DocxExtractor().extract(_to_bytes(document), "t.docx").markdown,
        "RPL-TEST-DOC-001",
    )
    units = segment_with_ctx(
        VERSION_ID, "RPL-TEST-DOC-001", anchored, 0, RunContext()
    )
    assert units[0].local_id == "s0"
    assert "Rockridge" in units[0].text_raw


@pytest.mark.corpus
def test_no_body_text_is_left_outside_a_clause(extracted):
    """Every prose line of the fixture must land inside some clause span."""
    anchored = anchor_clauses(extracted.markdown, FIXTURE_DOC_ID)
    units = segment_with_ctx(
        VERSION_ID, FIXTURE_DOC_ID, anchored, 0, RunContext()
    )
    spans = [
        (u.char_start, u.char_end) for u in units if u.unit_kind != "table_row"
    ]
    pos = 0
    orphans: list[str] = []
    for line in anchored.splitlines(keepends=True):
        text = line.strip()
        is_prose = (
            text
            and not text.startswith("|")
            and not text.startswith("<!--")
            and not text.startswith("#")
        )
        if is_prose and not any(s <= pos < e for s, e in spans):
            orphans.append(text[:60])
        pos += len(line)
    assert orphans == []


def test_anchor_clauses_marks_each_table_once():
    markdown = "| A | B |\n| --- | --- |\n| 1 | 2 |\n\nText.\n\n| C |\n| --- |\n| 3 |\n"
    anchored = anchor_clauses(markdown, "RPL-TEST-DOC-001")
    assert anchored.count("<!-- table: RPL-TEST-DOC-001:T1 -->") == 1
    assert anchored.count("<!-- table: RPL-TEST-DOC-001:T2 -->") == 1


def test_anchor_clauses_rejects_doc_ids_the_segmenter_cannot_match():
    # The segmenter's explicit markers accept any id token without whitespace
    # or ':'; anything else must fail loudly, not yield 0 clauses.
    assert marker_doc_id_supported("RPL-CS-PRO-004")
    assert marker_doc_id_supported("DOC-000123")
    assert not marker_doc_id_supported("my company policy")
    assert not marker_doc_id_supported("DOC:1")
    with pytest.raises(ValueError):
        anchor_clauses("# X\n", "my company policy")


# ---------------------------------------------------------------------------
# Acceptance: clause count vs the Markdown source (±25%)
# ---------------------------------------------------------------------------

@pytest.mark.corpus
def test_clause_count_within_25_percent_of_markdown_source(extracted):
    if not FIXTURE_MD.exists():  # pragma: no cover - corpus missing
        pytest.skip(f"corpus fixture missing: {FIXTURE_MD}")

    md_text = FIXTURE_MD.read_text(encoding="utf-8")
    _fm, body, offset = split_front_matter(md_text, FIXTURE_DOC_ID)
    md_clauses = _clause_count(body, FIXTURE_DOC_ID, offset)

    anchored = anchor_clauses(extracted.markdown, FIXTURE_DOC_ID)
    docx_clauses = _clause_count(anchored, FIXTURE_DOC_ID)

    assert md_clauses > 0
    ratio = docx_clauses / md_clauses
    assert 0.75 <= ratio <= 1.25, (
        f"docx={docx_clauses} md={md_clauses} ratio={ratio:.2f}"
    )


def test_anchor_clauses_system_assigned_doc_id_round_trips_through_segmenter():
    """A system-assigned id (DOC-000123) anchors and segments into clauses."""
    from app.company_ingest.parse.markdown_segmenter import segment

    md = "# 1 Purpose\n\nWhy.\n\n## 1.1 Scope\n\nWhere.\n"
    anchored = anchor_clauses(md, "DOC-000123")
    units = segment("ver-1", "DOC-000123", anchored, 0)
    assert [u.clause_id for u in units] == ["DOC-000123:1", "DOC-000123:1.1"]

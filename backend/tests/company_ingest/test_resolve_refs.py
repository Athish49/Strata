"""Tests for task 6.1.1 — resolve_references.

All ClauseUnit objects are built directly; no DB, no corpus, no external I/O.
"""
from __future__ import annotations

import hashlib

import pytest

from app.company_ingest.constants import LinkType, UnitKind, SectionKind
from app.company_ingest.enrich.ref_entry import RefEntry
from app.company_ingest.link.resolve_refs import ClauseLink, resolve_references
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_VERSION = "00000000-0000-0000-0000-000000000001"


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _make_unit(
    doc_id: str,
    local_id: str,
    *,
    unit_kind: str = UnitKind.SECTION,
    section_kind: str = SectionKind.OTHER,
    text_raw: str = "",
    heading_path: list[str] | None = None,
    sheet_no: str | None = None,
    row_cells: dict | None = None,
    refs: list[RefEntry] | None = None,
    ordinal: int = 0,
    parent_clause_id: str | None = None,
) -> ClauseUnit:
    clause_id = f"{doc_id}:{local_id}"
    return ClauseUnit(
        version_id=_FAKE_VERSION,
        doc_id=doc_id,
        clause_id=clause_id,
        local_id=local_id,
        parent_clause_id=parent_clause_id,
        unit_kind=unit_kind,
        heading_path=heading_path or [],
        section_kind=section_kind,
        ordinal=ordinal,
        char_start=0,
        char_end=len(text_raw),
        line_start=0,
        text_raw=text_raw,
        text_norm=text_raw.lower(),
        text_sha256=_sha(text_raw),
        sheet_no=sheet_no,
        row_cells=row_cells,
        refs=refs or [],
    )


def _ref(ref_type: str, target_hint: str | None, raw: str = "matched") -> RefEntry:
    return RefEntry(
        ref_type=ref_type,
        raw=raw,
        span_start=0,
        span_end=len(raw),
        target_hint=target_hint,
    )


def _ctx() -> RunContext:
    return RunContext()


# ---------------------------------------------------------------------------
# Test 1: references_doc — target in registered_doc_ids → link with to_doc_id
# ---------------------------------------------------------------------------

def test_references_doc_found():
    source = _make_unit("DOC-A", "1.1", refs=[_ref(LinkType.REFERENCES_DOC, "DOC-B")])
    ctx = _ctx()
    links = resolve_references([source], registered_doc_ids=["DOC-B"], ctx=ctx)

    assert len(links) == 1
    lnk = links[0]
    assert lnk.from_clause_id == "DOC-A:1.1"
    assert lnk.to_doc_id == "DOC-B"
    assert lnk.to_clause_id is None
    assert lnk.link_type == LinkType.REFERENCES_DOC
    assert lnk.method == "regex"
    assert lnk.confidence == 1.0


# ---------------------------------------------------------------------------
# Test 2: references_doc — target not found → warning, no link
# ---------------------------------------------------------------------------

def test_references_doc_not_found():
    source = _make_unit("DOC-A", "1.1", refs=[_ref(LinkType.REFERENCES_DOC, "DOC-MISSING")])
    ctx = _ctx()
    links = resolve_references([source], registered_doc_ids=[], ctx=ctx)

    assert links == []
    assert ctx.stats.get("links_unresolved", 0) == 1
    assert ctx.stats.get("links_resolved", 0) == 0


# ---------------------------------------------------------------------------
# Test 3: references_clause — full DOC:LOCAL → ClauseLink(to_clause_id=target)
# ---------------------------------------------------------------------------

def test_references_clause_full_id():
    target_unit = _make_unit("DOC-B", "3.4")
    source = _make_unit(
        "DOC-A", "1.1",
        refs=[_ref(LinkType.REFERENCES_CLAUSE, "DOC-B:3.4")],
    )
    ctx = _ctx()
    links = resolve_references([source, target_unit], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    lnk = links[0]
    assert lnk.to_clause_id == "DOC-B:3.4"
    assert lnk.to_doc_id is None
    assert lnk.link_type == LinkType.REFERENCES_CLAUSE


# ---------------------------------------------------------------------------
# Test 4: references_clause — local-only hint (§7.2 same-doc) → prepend unit.doc_id
# ---------------------------------------------------------------------------

def test_references_clause_same_doc_local():
    target_unit = _make_unit("DOC-A", "7.2")
    source = _make_unit(
        "DOC-A", "1.1",
        refs=[_ref(LinkType.REFERENCES_CLAUSE, "7.2")],
    )
    ctx = _ctx()
    links = resolve_references([source, target_unit], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert links[0].to_clause_id == "DOC-A:7.2"


# ---------------------------------------------------------------------------
# Test 5: references_tariff sheet:4 → link to all clauses with sheet_no="4"
# ---------------------------------------------------------------------------

def test_references_tariff_single_sheet():
    sheet_unit = _make_unit("TARIFF", "T4.1", sheet_no="4")
    sheet_unit2 = _make_unit("TARIFF", "T4.2", sheet_no="4")
    source = _make_unit(
        "DOC-A", "1.1",
        refs=[_ref(LinkType.REFERENCES_TARIFF, "sheet:4")],
    )
    ctx = _ctx()
    links = resolve_references([source, sheet_unit, sheet_unit2], registered_doc_ids=[], ctx=ctx)

    to_ids = {lnk.to_clause_id for lnk in links}
    assert "TARIFF:T4.1" in to_ids
    assert "TARIFF:T4.2" in to_ids
    assert len(links) == 2


# ---------------------------------------------------------------------------
# Test 6: references_tariff sheet:4-6 → links to sheets 4, 5, 6
# ---------------------------------------------------------------------------

def test_references_tariff_sheet_range():
    units = [
        _make_unit("TARIFF", f"T{n}.1", sheet_no=str(n))
        for n in range(4, 7)  # sheets 4, 5, 6
    ]
    source = _make_unit(
        "DOC-A", "2.1",
        refs=[_ref(LinkType.REFERENCES_TARIFF, "sheet:4-6")],
    )
    ctx = _ctx()
    links = resolve_references([source] + units, registered_doc_ids=[], ctx=ctx)

    assert len(links) == 3
    to_sheets = {lnk.to_clause_id for lnk in links}
    assert "TARIFF:T4.1" in to_sheets
    assert "TARIFF:T5.1" in to_sheets
    assert "TARIFF:T6.1" in to_sheets


# ---------------------------------------------------------------------------
# Test 7: references_tariff rule:16 → all R16.x clauses
# ---------------------------------------------------------------------------

def test_references_tariff_rule():
    r16_a = _make_unit("TARIFF", "R16.1")
    r16_b = _make_unit("TARIFF", "R16.2")
    r17 = _make_unit("TARIFF", "R17.1")  # should not be included
    source = _make_unit(
        "DOC-A", "1.1",
        refs=[_ref(LinkType.REFERENCES_TARIFF, "rule:16")],
    )
    ctx = _ctx()
    links = resolve_references([source, r16_a, r16_b, r17], registered_doc_ids=[], ctx=ctx)

    to_ids = {lnk.to_clause_id for lnk in links}
    assert "TARIFF:R16.1" in to_ids
    assert "TARIFF:R16.2" in to_ids
    assert "TARIFF:R17.1" not in to_ids
    assert len(links) == 2


# ---------------------------------------------------------------------------
# Test 8: references_form → link to appendix clause
# ---------------------------------------------------------------------------

def test_references_form():
    # Form ID embedded in heading_path
    form_unit = _make_unit(
        "DOC-X", "APP-F",
        heading_path=["Appendix", "Form ABC-F-001"],
        unit_kind=UnitKind.APPENDIX,
    )
    source = _make_unit(
        "DOC-A", "3.1",
        refs=[_ref(LinkType.REFERENCES_FORM, "ABC-F-001")],
    )
    ctx = _ctx()
    links = resolve_references([source, form_unit], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert links[0].to_clause_id == "DOC-X:APP-F"
    assert links[0].link_type == LinkType.REFERENCES_FORM


# ---------------------------------------------------------------------------
# Test 9: references_record_series → link to P2 row
# ---------------------------------------------------------------------------

def test_references_record_series():
    row = _make_unit(
        "REG", "RRS-PROC-001",
        unit_kind=UnitKind.REGISTER_ROW,
    )
    source = _make_unit(
        "DOC-A", "5.1",
        refs=[_ref(LinkType.REFERENCES_RECORD_SERIES, "RRS-PROC-001")],
    )
    ctx = _ctx()
    links = resolve_references([source, row], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert links[0].to_clause_id == "REG:RRS-PROC-001"
    assert links[0].link_type == LinkType.REFERENCES_RECORD_SERIES


# ---------------------------------------------------------------------------
# Test 10: references_obligation → link to P2 row
# ---------------------------------------------------------------------------

def test_references_obligation():
    row = _make_unit(
        "REG", "OBL-42-007",
        unit_kind=UnitKind.REGISTER_ROW,
    )
    source = _make_unit(
        "DOC-A", "6.2",
        refs=[_ref(LinkType.REFERENCES_OBLIGATION, "OBL-42-007")],
    )
    ctx = _ctx()
    links = resolve_references([source, row], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert links[0].to_clause_id == "REG:OBL-42-007"
    assert links[0].link_type == LinkType.REFERENCES_OBLIGATION


# ---------------------------------------------------------------------------
# Test 11: P2 register_row source → method="register_column" on link
# ---------------------------------------------------------------------------

def test_register_row_method_is_register_column():
    target = _make_unit("DOC-B", "2.1")
    source = _make_unit(
        "REG", "OBL-01-001",
        unit_kind=UnitKind.REGISTER_ROW,
        refs=[_ref(LinkType.REFERENCES_CLAUSE, "DOC-B:2.1")],
    )
    ctx = _ctx()
    links = resolve_references([source, target], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert links[0].method == "register_column"


# ---------------------------------------------------------------------------
# Test 12: deduplication — same (from, to, type) → one link only
# ---------------------------------------------------------------------------

def test_deduplication():
    target = _make_unit("DOC-B", "3.4")
    source = _make_unit(
        "DOC-A", "1.1",
        refs=[
            _ref(LinkType.REFERENCES_CLAUSE, "DOC-B:3.4", raw="first match"),
            _ref(LinkType.REFERENCES_CLAUSE, "DOC-B:3.4", raw="second match"),
        ],
    )
    ctx = _ctx()
    links = resolve_references([source, target], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert links[0].evidence == "first match"


# ---------------------------------------------------------------------------
# Test 13: ctx.count incremented correctly
# ---------------------------------------------------------------------------

def test_ctx_count_incremented():
    target = _make_unit("DOC-B", "1.1")
    missing_target_ref = _ref(LinkType.REFERENCES_CLAUSE, "DOC-B:MISSING")
    source = _make_unit(
        "DOC-A", "1.1",
        refs=[
            _ref(LinkType.REFERENCES_CLAUSE, "DOC-B:1.1"),
            missing_target_ref,
        ],
    )
    ctx = _ctx()
    links = resolve_references([source, target], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert ctx.stats["links_resolved"] == 1
    assert ctx.stats["links_unresolved"] == 1


# ---------------------------------------------------------------------------
# Test: references_form via text_raw first line (fallback)
# ---------------------------------------------------------------------------

def test_references_form_via_text_raw():
    form_unit = _make_unit(
        "DOC-X", "FORM-SEC",
        text_raw="XYZ-F-099 Submission Form\nSome body text.",
    )
    source = _make_unit(
        "DOC-A", "4.2",
        refs=[_ref(LinkType.REFERENCES_FORM, "XYZ-F-099")],
    )
    ctx = _ctx()
    links = resolve_references([source, form_unit], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert links[0].to_clause_id == "DOC-X:FORM-SEC"


# ---------------------------------------------------------------------------
# Test: references_doc found in doc_index (not registered_doc_ids) → still resolves
# ---------------------------------------------------------------------------

def test_references_doc_found_in_doc_index():
    """A doc that has units in the corpus should also resolve even if not in registered_doc_ids."""
    target_unit = _make_unit("DOC-INTERNAL", "1.0")
    source = _make_unit(
        "DOC-A", "1.1",
        refs=[_ref(LinkType.REFERENCES_DOC, "DOC-INTERNAL")],
    )
    ctx = _ctx()
    links = resolve_references([source, target_unit], registered_doc_ids=[], ctx=ctx)

    assert len(links) == 1
    assert links[0].to_doc_id == "DOC-INTERNAL"

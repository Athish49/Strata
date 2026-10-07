"""Tests for task 6.1.3 — document_scope rollup."""
from __future__ import annotations

import pytest

from app.company_ingest.enrich.citation_entry import CitationEntry
from app.company_ingest.enrich.citations_grammar import ParsedCitation
from app.company_ingest.link.document_scope import DocumentScopeRow, build_document_scope
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext
from decimal import Decimal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx() -> RunContext:
    return RunContext()


def _make_parsed(
    normalized_key: str = "170 IAC 4-1-16",
    rule_key: str = "170 IAC 4-1",
    source_system: str = "iac",
) -> ParsedCitation:
    return ParsedCitation(
        source_system=source_system,
        title=170,
        article="4-1",
        rule="4-1-16",
        section=Decimal("16"),
        subsection_path="",
        granularity="section",
        normalized_key=normalized_key,
        rule_key=rule_key,
        citation_raw="170 IAC 4-1-16",
    )


def _make_citation(
    context: str = "inline",
    resolution_status: str = "resolved",
    normalized_key: str = "170 IAC 4-1-16",
    rule_key: str = "170 IAC 4-1",
    source_system: str = "iac",
) -> CitationEntry:
    return CitationEntry(
        parsed=_make_parsed(normalized_key, rule_key, source_system),
        context=context,
        span_start=0,
        span_end=15,
        resolution_status=resolution_status,
        code_section_id=None,
        in_knowledge_base=source_system == "iac",
    )


def _make_unit(
    clause_id: str = "DOC1:c001",
    citations: list[CitationEntry] | None = None,
) -> ClauseUnit:
    return ClauseUnit(
        version_id="ver-1",
        doc_id="DOC1",
        clause_id=clause_id,
        local_id=clause_id.split(":")[1],
        parent_clause_id=None,
        unit_kind="clause",
        heading_path=[],
        section_kind="body",
        ordinal=1,
        char_start=0,
        char_end=100,
        line_start=1,
        text_raw="some text",
        text_norm="some text",
        text_sha256="abc",
        citations=citations or [],
    )


# ---------------------------------------------------------------------------
# Test 1: One IAC citation in one unit → one section row, one rule row
# ---------------------------------------------------------------------------

def test_single_citation_produces_section_and_rule_rows():
    ctx = _make_ctx()
    unit = _make_unit(citations=[_make_citation()])
    rows = build_document_scope("DOC1", "ver-1", [unit], [], ctx)

    section_rows = [r for r in rows if r.scope_level == "section"]
    rule_rows = [r for r in rows if r.scope_level == "rule"]

    assert len(section_rows) == 1
    assert len(rule_rows) == 1
    assert section_rows[0].scope_key == "170 IAC 4-1-16"
    assert rule_rows[0].scope_key == "170 IAC 4-1"
    assert section_rows[0].clause_count == 1
    assert rule_rows[0].clause_count == 1


# ---------------------------------------------------------------------------
# Test 2: Two units same section → clause_count=2
# ---------------------------------------------------------------------------

def test_two_units_same_section_clause_count_2():
    ctx = _make_ctx()
    unit1 = _make_unit(clause_id="DOC1:c001", citations=[_make_citation()])
    unit2 = _make_unit(clause_id="DOC1:c002", citations=[_make_citation()])
    rows = build_document_scope("DOC1", "ver-1", [unit1, unit2], [], ctx)

    section_rows = [r for r in rows if r.scope_level == "section"]
    rule_rows = [r for r in rows if r.scope_level == "rule"]

    assert len(section_rows) == 1
    assert section_rows[0].clause_count == 2
    assert rule_rows[0].clause_count == 2


# ---------------------------------------------------------------------------
# Test 3: Two units different sections same rule → one rule row (clause_count=2),
#          two section rows
# ---------------------------------------------------------------------------

def test_two_units_different_sections_same_rule():
    ctx = _make_ctx()
    unit1 = _make_unit(
        clause_id="DOC1:c001",
        citations=[_make_citation(normalized_key="170 IAC 4-1-16", rule_key="170 IAC 4-1")],
    )
    unit2 = _make_unit(
        clause_id="DOC1:c002",
        citations=[_make_citation(normalized_key="170 IAC 4-1-17", rule_key="170 IAC 4-1")],
    )
    rows = build_document_scope("DOC1", "ver-1", [unit1, unit2], [], ctx)

    section_rows = [r for r in rows if r.scope_level == "section"]
    rule_rows = [r for r in rows if r.scope_level == "rule"]

    assert len(section_rows) == 2
    assert len(rule_rows) == 1
    assert rule_rows[0].clause_count == 2
    section_keys = {r.scope_key for r in section_rows}
    assert "170 IAC 4-1-16" in section_keys
    assert "170 IAC 4-1-17" in section_keys


# ---------------------------------------------------------------------------
# Test 4: Front-matter string → parsed, adds scope entry
# ---------------------------------------------------------------------------

def test_front_matter_string_parsed():
    ctx = _make_ctx()
    rows = build_document_scope("DOC1", "ver-1", [], ["170 IAC 4-1-16"], ctx)

    section_rows = [r for r in rows if r.scope_level == "section"]
    assert len(section_rows) == 1
    assert section_rows[0].scope_key == "170 IAC 4-1-16"
    assert "front_matter" in section_rows[0].sources


# ---------------------------------------------------------------------------
# Test 5: Front-matter only (no clause citation) → scope row with clause_count=0
# ---------------------------------------------------------------------------

def test_front_matter_only_clause_count_zero():
    ctx = _make_ctx()
    rows = build_document_scope("DOC1", "ver-1", [], ["170 IAC 4-1-16"], ctx)

    section_rows = [r for r in rows if r.scope_level == "section"]
    assert section_rows[0].clause_count == 0


# ---------------------------------------------------------------------------
# Test 6: regulatory_basis_table context → sources includes "regulatory_basis_section"
# ---------------------------------------------------------------------------

def test_regulatory_basis_table_context_label():
    ctx = _make_ctx()
    unit = _make_unit(citations=[_make_citation(context="regulatory_basis_table")])
    rows = build_document_scope("DOC1", "ver-1", [unit], [], ctx)

    section_rows = [r for r in rows if r.scope_level == "section"]
    assert "regulatory_basis_section" in section_rows[0].sources


# ---------------------------------------------------------------------------
# Test 7: inline context → sources includes "inline"
# ---------------------------------------------------------------------------

def test_inline_context_label():
    ctx = _make_ctx()
    unit = _make_unit(citations=[_make_citation(context="inline")])
    rows = build_document_scope("DOC1", "ver-1", [unit], [], ctx)

    section_rows = [r for r in rows if r.scope_level == "section"]
    assert "inline" in section_rows[0].sources


# ---------------------------------------------------------------------------
# Test 8: External (non-IAC) → excluded
# ---------------------------------------------------------------------------

def test_non_iac_excluded():
    ctx = _make_ctx()
    unit = _make_unit(citations=[
        _make_citation(source_system="cfr", normalized_key="40 CFR 112", rule_key="40 CFR"),
    ])
    rows = build_document_scope("DOC1", "ver-1", [unit], [], ctx)
    assert rows == []


def test_resolution_status_external_excluded():
    ctx = _make_ctx()
    unit = _make_unit(citations=[_make_citation(resolution_status="external")])
    rows = build_document_scope("DOC1", "ver-1", [unit], [], ctx)
    assert rows == []


# ---------------------------------------------------------------------------
# Test 9: sources is deduplicated sorted list
# ---------------------------------------------------------------------------

def test_sources_deduplicated_and_sorted():
    ctx = _make_ctx()
    # Same unit, multiple citations to same section with different contexts
    citations = [
        _make_citation(context="inline"),
        _make_citation(context="inline"),
        _make_citation(context="regulatory_basis_table"),
    ]
    unit = _make_unit(citations=citations)
    rows = build_document_scope("DOC1", "ver-1", [unit], [], ctx)

    section_rows = [r for r in rows if r.scope_level == "section"]
    sources = section_rows[0].sources
    # Deduplicated
    assert len(sources) == len(set(sources))
    # Sorted
    assert sources == sorted(sources)
    assert "inline" in sources
    assert "regulatory_basis_section" in sources


# ---------------------------------------------------------------------------
# Test 10: Empty inputs → empty list
# ---------------------------------------------------------------------------

def test_empty_inputs():
    ctx = _make_ctx()
    rows = build_document_scope("DOC1", "ver-1", [], [], ctx)
    assert rows == []


# ---------------------------------------------------------------------------
# Test 11: ctx.count incremented
# ---------------------------------------------------------------------------

def test_ctx_count_incremented():
    ctx = _make_ctx()
    unit = _make_unit(citations=[_make_citation()])
    build_document_scope("DOC1", "ver-1", [unit], [], ctx)

    assert ctx.stats.get("scope_rows_section", 0) == 1
    assert ctx.stats.get("scope_rows_rule", 0) == 1


def test_ctx_count_multiple_rows():
    ctx = _make_ctx()
    unit1 = _make_unit(
        clause_id="DOC1:c001",
        citations=[_make_citation(normalized_key="170 IAC 4-1-16", rule_key="170 IAC 4-1")],
    )
    unit2 = _make_unit(
        clause_id="DOC1:c002",
        citations=[_make_citation(normalized_key="170 IAC 4-1-17", rule_key="170 IAC 4-1")],
    )
    build_document_scope("DOC1", "ver-1", [unit1, unit2], [], ctx)

    assert ctx.stats.get("scope_rows_section", 0) == 2
    assert ctx.stats.get("scope_rows_rule", 0) == 1

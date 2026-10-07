"""Tests for task 4.1.1 — enrich_citations().

Run with:
    cd /Users/athish/Documents/Strata/backend
    .venv/bin/python -m pytest tests/company_ingest/test_citations_enrich.py -v
"""
from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock

import pytest

from app.company_ingest.enrich.citation_entry import CitationEntry
from app.company_ingest.enrich.citations import enrich_citations
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_unit(
    text_raw: str = "",
    unit_kind: str = "section",
    section_kind: str = "procedure",
    row_cells: dict | None = None,
) -> ClauseUnit:
    """Build a minimal ClauseUnit for testing."""
    return ClauseUnit(
        version_id="v1",
        doc_id="DOC1",
        clause_id="DOC1:c1",
        local_id="c1",
        parent_clause_id=None,
        unit_kind=unit_kind,
        heading_path=["Section 1"],
        section_kind=section_kind,
        ordinal=0,
        char_start=0,
        char_end=len(text_raw),
        line_start=1,
        text_raw=text_raw,
        text_norm=text_raw,
        text_sha256="",
        row_cells=row_cells,
    )


def _make_ctx() -> RunContext:
    return RunContext()


@dataclass
class FakeCodeSection:
    pk: str
    status: str = "active"


# ---------------------------------------------------------------------------
# Test 1: P1 unit with inline IAC citation → context="inline"
# ---------------------------------------------------------------------------

def test_p1_inline_iac_citation():
    unit = _make_unit("See 170 IAC 4-1-16 for details.")
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert len(unit.citations) == 1
    entry: CitationEntry = unit.citations[0]
    assert entry.context == "inline"
    assert entry.parsed.source_system == "iac"
    assert entry.parsed.normalized_key == "170 IAC 4-1-16"


# ---------------------------------------------------------------------------
# Test 2: P1 unit in section_kind="regulatory_basis" → context="regulatory_basis_table"
# ---------------------------------------------------------------------------

def test_p1_regulatory_basis_context():
    unit = _make_unit(
        "170 IAC 4-1-16",
        section_kind="regulatory_basis",
    )
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert len(unit.citations) == 1
    assert unit.citations[0].context == "regulatory_basis_table"


# ---------------------------------------------------------------------------
# Test 3: P2 register_row with citation column → context="register_column", span_start=0
# ---------------------------------------------------------------------------

def test_p2_register_row_citation_column():
    row_cells = {
        "Rule:citation": "170 IAC 4-1-16",
        "Description:free_text": "some text",
    }
    unit = _make_unit(
        text_raw="",
        unit_kind="register_row",
        section_kind="other",
        row_cells=row_cells,
    )
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert len(unit.citations) == 1
    entry: CitationEntry = unit.citations[0]
    assert entry.context == "register_column"
    assert entry.span_start == 0
    assert entry.parsed.normalized_key == "170 IAC 4-1-16"


# ---------------------------------------------------------------------------
# Test 4: No citations in text → unit.citations is empty
# ---------------------------------------------------------------------------

def test_no_citations_in_text():
    unit = _make_unit("This text has no regulatory citations at all.")
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert unit.citations == []


# ---------------------------------------------------------------------------
# Test 5: Resolved citation (mock repo returns a CodeSection)
# ---------------------------------------------------------------------------

def test_resolved_citation():
    unit = _make_unit("Refer to 170 IAC 4-1-16.")
    ctx = _make_ctx()

    mock_section = FakeCodeSection(pk="abc-123", status="active")
    repo = MagicMock(return_value=mock_section)

    enrich_citations([unit], ctx, code_section_repo=repo)
    assert len(unit.citations) == 1
    entry = unit.citations[0]
    assert entry.resolution_status == "resolved"
    assert entry.code_section_id == "abc-123"
    assert entry.in_knowledge_base is True


# ---------------------------------------------------------------------------
# Test 6: Not-found citation (mock repo returns None)
# ---------------------------------------------------------------------------

def test_not_found_citation():
    unit = _make_unit("Refer to 170 IAC 4-1-99.")
    ctx = _make_ctx()

    repo = MagicMock(return_value=None)

    enrich_citations([unit], ctx, code_section_repo=repo)
    assert len(unit.citations) == 1
    entry = unit.citations[0]
    assert entry.resolution_status == "not_found"
    assert entry.code_section_id is None


# ---------------------------------------------------------------------------
# Test 7: External citation (IC, CFR) → resolution_status="external", in_knowledge_base=False
# ---------------------------------------------------------------------------

def test_external_citation_ic():
    unit = _make_unit("See IC 8-1-2-121 for details.")
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert len(unit.citations) == 1
    entry = unit.citations[0]
    assert entry.resolution_status == "external"
    assert entry.in_knowledge_base is False


def test_external_citation_cfr():
    unit = _make_unit("Refer to 40 CFR 112.")
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert len(unit.citations) == 1
    entry = unit.citations[0]
    assert entry.resolution_status == "external"
    assert entry.in_knowledge_base is False


# ---------------------------------------------------------------------------
# Test 8: Range expansion → 3 CitationEntry objects for "through" range
# ---------------------------------------------------------------------------

def test_range_expansion():
    unit = _make_unit("See 170 IAC 4-1-4 through 4-1-6 for more information.")
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert len(unit.citations) == 3
    keys = [e.parsed.normalized_key for e in unit.citations]
    assert "170 IAC 4-1-4" in keys
    assert "170 IAC 4-1-5" in keys
    assert "170 IAC 4-1-6" in keys
    # All should share same span (the range text)
    assert all(e.span_start == unit.citations[0].span_start for e in unit.citations)


# ---------------------------------------------------------------------------
# Test 9: ctx.count("citations_found") incremented correctly
# ---------------------------------------------------------------------------

def test_ctx_count_citations_found():
    unit1 = _make_unit("See 170 IAC 4-1-16.")
    unit2 = _make_unit("Also 170 IAC 4-1-17 and IC 8-1-2-121.")
    ctx = _make_ctx()
    enrich_citations([unit1, unit2], ctx)
    # unit1 has 1, unit2 has 2
    assert ctx.stats.get("citations_found", 0) == 3


# ---------------------------------------------------------------------------
# Test 10: Cache — second call with same key doesn't call repo again
# ---------------------------------------------------------------------------

def test_cache_prevents_second_repo_call():
    unit1 = _make_unit("See 170 IAC 4-1-16.")
    unit2 = _make_unit("Also see 170 IAC 4-1-16.")
    ctx = _make_ctx()

    mock_section = FakeCodeSection(pk="sec-1", status="active")
    repo = MagicMock(return_value=mock_section)

    enrich_citations([unit1, unit2], ctx, code_section_repo=repo)
    # Both units have the same citation; repo should only be called once
    repo.assert_called_once_with("170 IAC 4-1-16")
    assert unit1.citations[0].resolution_status == "resolved"
    assert unit2.citations[0].resolution_status == "resolved"


# ---------------------------------------------------------------------------
# Test 11: rule_key preserved when granularity == "rule"
# ---------------------------------------------------------------------------

def test_rule_key_preserved_for_rule_granularity():
    # Rule-level IAC: "170 IAC 4-1" (no section number)
    unit = _make_unit("Refer to 170 IAC 4-1.")
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert len(unit.citations) == 1
    entry = unit.citations[0]
    assert entry.parsed.granularity == "rule"
    assert entry.parsed.rule_key == "170 IAC 4-1"
    # rule-level IAC: code_section_id must be None
    assert entry.code_section_id is None


# ---------------------------------------------------------------------------
# Test 12: Multiple citations in one clause — all found
# ---------------------------------------------------------------------------

def test_multiple_citations_in_one_clause():
    text = "This rule is governed by 170 IAC 4-1-16, 170 IAC 4-1-17, and IC 8-1-2-121."
    unit = _make_unit(text)
    ctx = _make_ctx()
    enrich_citations([unit], ctx)
    assert len(unit.citations) == 3
    sources = [e.parsed.source_system for e in unit.citations]
    assert sources.count("iac") == 2
    assert sources.count("ic") == 1

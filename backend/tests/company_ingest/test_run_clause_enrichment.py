"""Tests for task 5.1.2: run_clause_enrichment runner."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from app.company_ingest.llm.run_clause_enrichment import run_clause_enrichment
from app.company_ingest.llm.schemas import CitationLink, ClauseEnrichment, SemanticParam
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_unit(
    text_raw: str = "The company shall comply with all applicable regulations.",
    role: str | None = None,
    clause_id: str = "DOC001:clause-1",
    local_id: str = "clause-1",
    parent_clause_id: str | None = None,
    citations: list | None = None,
) -> ClauseUnit:
    unit = ClauseUnit(
        version_id="ver-001",
        doc_id="DOC001",
        clause_id=clause_id,
        local_id=local_id,
        parent_clause_id=parent_clause_id,
        unit_kind="section",
        heading_path=["Scope"],
        section_kind="procedure",
        ordinal=1,
        char_start=0,
        char_end=len(text_raw),
        line_start=1,
        text_raw=text_raw,
        text_norm=text_raw.lower(),
        text_sha256=hashlib.sha256(text_raw.encode()).hexdigest(),
        role=role,
    )
    if citations is not None:
        unit.citations = citations
    return unit


def _make_ctx(**kwargs) -> RunContext:
    return RunContext(company_id="test_co", **kwargs)


@dataclass
class FakeParsedCitation:
    citation_raw: str


@dataclass
class FakeCitationEntry:
    parsed: FakeParsedCitation


def _enrichment(
    clause_role: str | None = None,
    normalized_statement: str | None = None,
    topic_terms: list[str] | None = None,
    parameters: list[SemanticParam] | None = None,
    citation_links: list[CitationLink] | None = None,
) -> ClauseEnrichment:
    return ClauseEnrichment(
        clause_role=clause_role,
        normalized_statement=normalized_statement,
        topic_terms=topic_terms or [],
        parameters=parameters or [],
        citation_links=citation_links or [],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


# 1. should_enrich=False → call_structured not called
async def test_should_enrich_false_skips_llm():
    unit = _make_unit(role="boilerplate")
    ctx = _make_ctx()
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
    ) as mock_cs:
        await run_clause_enrichment([unit], ctx)
    mock_cs.assert_not_called()


# 2. Verbatim param → added to unit.parameters with method="llm", verified=True
async def test_verbatim_param_added():
    text = "The company shall comply with all applicable regulations."
    unit = _make_unit(text_raw=text)
    ctx = _make_ctx()
    result = _enrichment(
        parameters=[SemanticParam(kind="applicability", name="scope", value_text="all applicable regulations")]
    )
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert len(unit.parameters) == 1
    p = unit.parameters[0]
    assert p.method == "llm"
    assert p.verified is True
    assert p.value_text == "all applicable regulations"


# 3. Non-verbatim param → dropped, issue recorded, NOT in unit.parameters
async def test_nonverbatim_param_dropped():
    text = "The company shall comply."
    unit = _make_unit(text_raw=text)
    ctx = _make_ctx()
    result = _enrichment(
        parameters=[SemanticParam(kind="party", name="party", value_text="NOT IN TEXT AT ALL XYZ")]
    )
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert len(unit.parameters) == 0
    issues = [i for i in ctx.issues if i.code == "param_not_verbatim"]
    assert len(issues) == 1
    assert issues[0].severity == "info"
    assert ctx.stats.get("params_dropped_not_verbatim", 0) == 1


# 4. regulatory_restatement + no citations → downgraded to internal_procedure, warning
async def test_restatement_without_citations_downgraded():
    unit = _make_unit(citations=[])
    ctx = _make_ctx()
    result = _enrichment(clause_role="regulatory_restatement")
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.role == "internal_procedure"
    warnings = [i for i in ctx.issues if i.code == "restatement_without_citation"]
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"


# 5. regulatory_restatement + citations present → role kept
async def test_restatement_with_citations_kept():
    citation = FakeCitationEntry(parsed=FakeParsedCitation(citation_raw="§ 12.3"))
    unit = _make_unit(citations=[citation])
    ctx = _make_ctx()
    result = _enrichment(clause_role="regulatory_restatement")
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.role == "regulatory_restatement"
    warnings = [i for i in ctx.issues if i.code == "restatement_without_citation"]
    assert len(warnings) == 0


# 6. role=None → LLM role assigned
async def test_role_none_assigned_by_llm():
    unit = _make_unit(role=None)
    ctx = _make_ctx()
    result = _enrichment(clause_role="internal_procedure")
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.role == "internal_procedure"


# 7. role already set (from 4.1.4) → LLM role NOT overwritten
async def test_existing_role_not_overwritten():
    unit = _make_unit(role="definition")
    ctx = _make_ctx()
    result = _enrichment(clause_role="boilerplate")
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.role == "definition"


# 8. role_method="llm" set when LLM assigns role
async def test_role_method_set_to_llm():
    unit = _make_unit(role=None)
    ctx = _make_ctx()
    result = _enrichment(clause_role="informational")
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.role_method == "llm"


# 9. citation_link_unmatched → binding dropped, issue recorded
async def test_citation_link_unmatched():
    unit = _make_unit(citations=[])
    ctx = _make_ctx()
    result = _enrichment(
        citation_links=[CitationLink(parameter_index=0, citation_raw="§ 99.99")]
    )
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    issues = [i for i in ctx.issues if i.code == "citation_link_unmatched"]
    assert len(issues) == 1
    assert issues[0].severity == "info"


# 10. no_llm=True: skips call, undecided with citation → regulatory_restatement
async def test_no_llm_with_citation_gives_restatement():
    citation = FakeCitationEntry(parsed=FakeParsedCitation(citation_raw="§ 5.1"))
    unit = _make_unit(role=None, citations=[citation])
    ctx = _make_ctx(no_llm=True)
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
    ) as mock_cs:
        await run_clause_enrichment([unit], ctx)
    mock_cs.assert_not_called()
    assert unit.role == "regulatory_restatement"


# 11. no_llm=True: undecided without citation → internal_procedure
async def test_no_llm_without_citation_gives_internal_procedure():
    unit = _make_unit(role=None, citations=[])
    ctx = _make_ctx(no_llm=True)
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.role == "internal_procedure"


# 12. no_llm=True: role_method="heuristic"
async def test_no_llm_role_method_heuristic():
    unit = _make_unit(role=None)
    ctx = _make_ctx(no_llm=True)
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.role_method == "heuristic"


# 13. assessable recomputed: boilerplate → False
async def test_assessable_boilerplate_false():
    unit = _make_unit(role=None)
    ctx = _make_ctx()
    result = _enrichment(clause_role="boilerplate")
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.assessable is False


# 14. assessable recomputed: internal_procedure → True
async def test_assessable_internal_procedure_true():
    unit = _make_unit(role=None)
    ctx = _make_ctx()
    result = _enrichment(clause_role="internal_procedure")
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit], ctx)

    assert unit.assessable is True


# 15. ctx.count("units_enriched_llm") incremented
async def test_units_enriched_llm_counted():
    unit1 = _make_unit(clause_id="DOC001:c1", local_id="c1")
    unit2 = _make_unit(clause_id="DOC001:c2", local_id="c2")
    ctx = _make_ctx()
    result = _enrichment()
    with patch(
        "app.company_ingest.llm.run_clause_enrichment.call_structured",
        new_callable=AsyncMock,
        return_value=result,
    ):
        await run_clause_enrichment([unit1, unit2], ctx)

    assert ctx.stats.get("units_enriched_llm", 0) == 2

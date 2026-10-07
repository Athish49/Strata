"""Tests for task 6.1.2 — find_restates_links.

All embed_texts calls are mocked so no real model is loaded.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from typing import Optional
from unittest.mock import patch

import pytest

from app.company_ingest.enrich.citation_entry import CitationEntry
from app.company_ingest.enrich.citations_grammar import ParsedCitation
from app.company_ingest.enrich.parameter_entry import ParameterEntry
from app.company_ingest.link.resolve_refs import ClauseLink
from app.company_ingest.link.restates import find_restates_links
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
    text_norm: str = "some clause text",
    role: str = "obligation",
    section_kind: str = "body",
    unit_kind: str = "section",
    heading_path: list[str] | None = None,
    parameters: list[ParameterEntry] | None = None,
    citations: list[CitationEntry] | None = None,
    assessable: bool | None = None,
    ordinal: int = 0,
) -> ClauseUnit:
    clause_id = f"{doc_id}:{local_id}"
    return ClauseUnit(
        version_id=_FAKE_VERSION,
        doc_id=doc_id,
        clause_id=clause_id,
        local_id=local_id,
        parent_clause_id=None,
        unit_kind=unit_kind,
        heading_path=heading_path or ["Section"],
        section_kind=section_kind,
        ordinal=ordinal,
        char_start=0,
        char_end=len(text_norm),
        line_start=0,
        text_raw=text_norm,
        text_norm=text_norm,
        text_sha256=_sha(text_norm),
        parameters=parameters or [],
        citations=citations or [],
        role=role,
        assessable=assessable,
    )


def _make_param(
    kind: str = "period",
    value_num: float = 30.0,
    unit: Optional[str] = "days",
    day_type: str = "business",
    qualifier: Optional[str] = None,
    verified: bool = True,
) -> ParameterEntry:
    return ParameterEntry(
        kind=kind,
        unit=unit,
        value_text="30 business days",
        value_num=value_num,
        value_source=None,
        qualifier=qualifier,
        day_type=day_type,
        span_start=0,
        span_end=16,
        method="regex",
        verified=verified,
    )


def _make_citation(normalized_key: str) -> CitationEntry:
    parsed = ParsedCitation(
        source_system="iac",
        title=170,
        article="4-1",
        rule="4-1-16",
        section=None,
        subsection_path="",
        granularity="rule",
        normalized_key=normalized_key,
        rule_key=normalized_key,
        citation_raw=normalized_key,
    )
    return CitationEntry(
        parsed=parsed,
        context="inline",
        span_start=0,
        span_end=10,
        resolution_status="resolved",
        code_section_id=None,
        in_knowledge_base=True,
    )


def _ctx() -> RunContext:
    return RunContext()


def _unit_vec(dim: int = 4) -> list[float]:
    """Return a unit vector [1/sqrt(dim), ...] of given dimension."""
    v = 1.0 / math.sqrt(dim)
    return [v] * dim


def _high_sim_vecs() -> list[list[float]]:
    """Two identical unit vectors — cosine = 1.0."""
    v = _unit_vec(4)
    return [v, v]


def _low_sim_vecs() -> list[list[float]]:
    """Two orthogonal unit vectors — cosine = 0.0."""
    return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]


def _sim_vecs(cosine: float) -> list[list[float]]:
    """Return two 2D unit vectors with the given cosine similarity."""
    import math
    # v1 = [1, 0], v2 = [cos, sin]
    sin_val = math.sqrt(max(0.0, 1.0 - cosine ** 2))
    return [[1.0, 0.0], [cosine, sin_val]]


# ---------------------------------------------------------------------------
# Test 1: Two units with same parameter signature → pair found
# ---------------------------------------------------------------------------

def test_same_signature_pair_found():
    param = _make_param()
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b], [], _ctx())

    assert len(links) == 2  # bidirectional
    from_ids = {lnk.from_clause_id for lnk in links}
    to_ids = {lnk.to_clause_id for lnk in links}
    assert "DOC-A:1" in from_ids or "DOC-A:1" in to_ids
    assert "DOC-B:1" in from_ids or "DOC-B:1" in to_ids


# ---------------------------------------------------------------------------
# Test 2: Units with different parameter signatures → not paired
# ---------------------------------------------------------------------------

def test_different_signatures_not_paired():
    param_a = _make_param(value_num=30.0)
    param_b = _make_param(value_num=60.0)
    a = _make_unit("DOC-A", "1", parameters=[param_a],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "1", parameters=[param_b],
                   citations=[_make_citation("170 IAC 4-1-16")])

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b], [], _ctx())

    assert links == []


# ---------------------------------------------------------------------------
# Test 3: Scope condition 1 — shared cited section → pass
# ---------------------------------------------------------------------------

def test_scope_shared_cited_section():
    param = _make_param()
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b], [], _ctx())

    assert len(links) == 2


# ---------------------------------------------------------------------------
# Test 4: Scope condition 2 — same document + one has no citations → pass
# ---------------------------------------------------------------------------

def test_scope_same_doc_no_citations():
    param = _make_param()
    # a has no citations; same doc
    a = _make_unit("DOC-A", "1", parameters=[param], citations=[])
    b = _make_unit("DOC-A", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b], [], _ctx())

    assert len(links) == 2


# ---------------------------------------------------------------------------
# Test 5: Scope condition fail — different docs, different citations, not connected
# ---------------------------------------------------------------------------

def test_scope_fail_different_docs_citations_not_connected():
    param = _make_param()
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 5-2-10")])

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b], [], _ctx())

    assert links == []


# ---------------------------------------------------------------------------
# Test 6: Cosine ≥ 0.6 → link created with confidence=cosine
# ---------------------------------------------------------------------------

def test_cosine_above_threshold_creates_link():
    param = _make_param()
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    vecs = _sim_vecs(0.75)
    with patch("app.company_ingest.link.restates.embed_texts", return_value=vecs):
        links = find_restates_links([a, b], [], _ctx())

    assert len(links) == 2
    for lnk in links:
        assert abs(lnk.confidence - 0.75) < 1e-6


# ---------------------------------------------------------------------------
# Test 7: Cosine < 0.6 → no link created
# ---------------------------------------------------------------------------

def test_cosine_below_threshold_no_link():
    param = _make_param()
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    vecs = _sim_vecs(0.55)
    with patch("app.company_ingest.link.restates.embed_texts", return_value=vecs):
        links = find_restates_links([a, b], [], _ctx())

    assert links == []


# ---------------------------------------------------------------------------
# Test 8: Two directed links per pair (A→B and B→A)
# ---------------------------------------------------------------------------

def test_two_directed_links_per_pair():
    param = _make_param()
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b], [], _ctx())

    assert len(links) == 2
    directions = {(lnk.from_clause_id, lnk.to_clause_id) for lnk in links}
    assert ("DOC-A:1", "DOC-B:2") in directions
    assert ("DOC-B:2", "DOC-A:1") in directions


# ---------------------------------------------------------------------------
# Test 9: link_type="restates", method="parameter_match"
# ---------------------------------------------------------------------------

def test_link_type_and_method():
    param = _make_param()
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b], [], _ctx())

    for lnk in links:
        assert lnk.link_type == "restates"
        assert lnk.method == "parameter_match"


# ---------------------------------------------------------------------------
# Test 10: Group > 200 members → skipped with issue
# ---------------------------------------------------------------------------

def test_group_too_large_skipped():
    param = _make_param()
    units = [
        _make_unit("DOC-A", str(i), parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")], ordinal=i)
        for i in range(201)
    ]
    ctx = _ctx()

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links(units, [], ctx)

    assert links == []
    assert ctx.stats.get("restates_groups_skipped", 0) == 1
    assert any(i.code == "restates_group_too_large" for i in ctx.issues)


# ---------------------------------------------------------------------------
# Test 11: Deduplication — same pair from multiple signatures → highest confidence kept
# ---------------------------------------------------------------------------

def test_deduplication_keeps_highest_confidence():
    param1 = _make_param(kind="period", value_num=30.0)
    param2 = _make_param(kind="amount", value_num=100.0)
    a = _make_unit("DOC-A", "1", parameters=[param1, param2],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param1, param2],
                   citations=[_make_citation("170 IAC 4-1-16")])

    call_count = 0

    def _mock_embed(texts):
        nonlocal call_count
        # Alternating: first call → 0.65, second call → 0.80
        call_count += 1
        if call_count == 1:
            return _sim_vecs(0.65)
        else:
            return _sim_vecs(0.80)

    with patch("app.company_ingest.link.restates.embed_texts", side_effect=_mock_embed):
        links = find_restates_links([a, b], [], _ctx())

    # Should have exactly 2 directed links (deduplicated)
    assert len(links) == 2
    for lnk in links:
        assert abs(lnk.confidence - 0.80) < 1e-6


# ---------------------------------------------------------------------------
# Test 12: build_embedded_text returns "" → pair skipped
# ---------------------------------------------------------------------------

def test_empty_embedded_text_skipped():
    param = _make_param()
    # role=boilerplate → build_embedded_text returns ""
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")],
                   role="boilerplate")
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()) as mock_embed:
        links = find_restates_links([a, b], [], _ctx())

    assert links == []
    mock_embed.assert_not_called()


# ---------------------------------------------------------------------------
# Test 13: ctx.count("restates_links") incremented
# ---------------------------------------------------------------------------

def test_ctx_count_restates_links():
    param = _make_param()
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])

    ctx = _ctx()
    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b], [], ctx)

    assert ctx.stats.get("restates_links", 0) == 2


# ---------------------------------------------------------------------------
# Test 14: existing_links used for scope condition 2 (connected by existing link)
# ---------------------------------------------------------------------------

def test_scope_connected_by_existing_link():
    param = _make_param()
    # Different docs, different citations (no shared section), but connected by existing link
    a = _make_unit("DOC-A", "1", parameters=[param],
                   citations=[_make_citation("170 IAC 4-1-16")])
    b = _make_unit("DOC-B", "2", parameters=[param],
                   citations=[_make_citation("170 IAC 5-2-10")])

    # No citations overlap, different docs, but b has no citations? No — let's make b have no citations
    # Actually: the spec says cond2 = (one side has no citations) AND (same_doc OR connected)
    # Here both have citations → cond2 fails unless connected
    # Let's remove citation from b and use connected=True
    b_no_cit = _make_unit("DOC-B", "2", parameters=[param], citations=[])

    existing = [
        ClauseLink(
            from_clause_id="DOC-A:1",
            to_clause_id="DOC-B:2",
            to_doc_id=None,
            link_type="references_clause",
            method="regex",
            evidence="link",
            confidence=1.0,
        )
    ]

    with patch("app.company_ingest.link.restates.embed_texts", return_value=_high_sim_vecs()):
        links = find_restates_links([a, b_no_cit], existing, _ctx())

    assert len(links) == 2

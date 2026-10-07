"""Tests for task 8.1.2 — store/snapshot.py and store/commit.py."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, call

import pytest

from app.company_ingest.enrich.citation_entry import CitationEntry
from app.company_ingest.enrich.citations_grammar import ParsedCitation
from app.company_ingest.enrich.parameter_entry import ParameterEntry
from app.company_ingest.enrich.ref_entry import RefEntry
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext
from app.company_ingest.store.commit import (
    build_run_report,
    compute_value_source,
    finalize_parameters,
    write_report,
)
from app.company_ingest.store.snapshot import (
    build_clause_snapshot,
    write_clause_snapshot,
)
from app.company_ingest.validate.checks import CheckOutcome


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_unit(
    clause_id: str = "DOC1:001",
    doc_id: str = "DOC1",
    role: str | None = None,
    citations=None,
    parameters=None,
    refs=None,
    **kwargs,
) -> ClauseUnit:
    defaults = dict(
        version_id="ver-uuid-001",
        doc_id=doc_id,
        clause_id=clause_id,
        local_id=clause_id.split(":")[-1],
        parent_clause_id=None,
        unit_kind="body",
        heading_path=["Section 1"],
        section_kind="body",
        ordinal=1,
        char_start=0,
        char_end=100,
        line_start=1,
        text_raw="Sample text.",
        text_norm="sample text.",
        text_sha256="abc123",
        role=role,
        role_method="heuristic",
        assessable=True,
        normalized_statement=None,
        topic_terms=[],
    )
    defaults.update(kwargs)
    unit = ClauseUnit(**defaults)
    if citations is not None:
        unit.citations = citations
    if parameters is not None:
        unit.parameters = parameters
    if refs is not None:
        unit.refs = refs
    return unit


def _make_parsed_citation() -> ParsedCitation:
    return ParsedCitation(
        source_system="iac",
        title=170,
        article="4-1",
        rule="4-1-16",
        section=None,
        subsection_path="",
        granularity="section",
        normalized_key="170 IAC 4-1-16",
        rule_key="170 IAC 4-1",
        citation_raw="170 IAC 4-1-16",
    )


def _make_citation_entry() -> CitationEntry:
    return CitationEntry(
        parsed=_make_parsed_citation(),
        context="inline",
        span_start=0,
        span_end=14,
        resolution_status="resolved",
        code_section_id="cs-001",
        in_knowledge_base=True,
    )


def _make_parameter_entry(value_source=None) -> ParameterEntry:
    return ParameterEntry(
        kind="period",
        unit="days",
        value_text="30 days",
        value_num=30.0,
        value_source=value_source,
        qualifier=None,
        day_type="business",
        span_start=0,
        span_end=7,
        method="regex",
        verified=True,
    )


def _make_ref_entry() -> RefEntry:
    return RefEntry(
        ref_type="references_doc",
        raw="Section 2",
        span_start=0,
        span_end=9,
        target_hint="DOC1:sec2",
    )


def _make_check_outcome(passed: bool, n: int = 1) -> CheckOutcome:
    return CheckOutcome(
        check_number=n,
        name=f"check_{n}",
        passed=passed,
        metric=f"metric_{n}",
        details={"key": "value"},
    )


# ---------------------------------------------------------------------------
# Tests: build_clause_snapshot
# ---------------------------------------------------------------------------


def test_build_clause_snapshot_sorted_by_clause_id():
    """build_clause_snapshot: sorted by clause_id."""
    u1 = _make_unit(clause_id="DOC1:003", ordinal=3)
    u2 = _make_unit(clause_id="DOC1:001", ordinal=1)
    u3 = _make_unit(clause_id="DOC1:002", ordinal=2)

    jsonl = build_clause_snapshot([u1, u2, u3])
    lines = jsonl.strip().split("\n")
    ids = [json.loads(line)["clause_id"] for line in lines]
    assert ids == ["DOC1:001", "DOC1:002", "DOC1:003"]


def test_build_clause_snapshot_each_line_is_valid_json():
    """build_clause_snapshot: each line is valid JSON."""
    u1 = _make_unit(clause_id="DOC1:001")
    u2 = _make_unit(clause_id="DOC1:002")
    jsonl = build_clause_snapshot([u1, u2])
    for line in jsonl.strip().split("\n"):
        obj = json.loads(line)
        assert isinstance(obj, dict)


def test_build_clause_snapshot_citations_serialized():
    """build_clause_snapshot: citations serialized correctly (check one field)."""
    citation = _make_citation_entry()
    unit = _make_unit(clause_id="DOC1:001", citations=[citation])
    jsonl = build_clause_snapshot([unit])
    obj = json.loads(jsonl)
    assert len(obj["citations"]) == 1
    c = obj["citations"][0]
    assert c["normalized_key"] == "170 IAC 4-1-16"
    assert c["resolution_status"] == "resolved"
    assert c["context"] == "inline"


def test_build_clause_snapshot_parameters_serialized():
    """build_clause_snapshot: parameters serialized."""
    param = _make_parameter_entry()
    unit = _make_unit(clause_id="DOC1:001", parameters=[param])
    jsonl = build_clause_snapshot([unit])
    obj = json.loads(jsonl)
    assert len(obj["parameters"]) == 1
    p = obj["parameters"][0]
    assert p["kind"] == "period"
    assert p["value_num"] == 30.0


def test_build_clause_snapshot_terms_not_in_output():
    """build_clause_snapshot: terms NOT in output."""
    unit = _make_unit(clause_id="DOC1:001")
    unit.terms = ["some_term"]
    jsonl = build_clause_snapshot([unit])
    obj = json.loads(jsonl)
    assert "terms" not in obj


def test_write_clause_snapshot_calls_put_bytes_with_correct_key():
    """write_clause_snapshot: calls r2.put_bytes with correct key."""
    from app.company_ingest.store.r2_keys import derived_clauses_key

    unit = _make_unit(clause_id="DOC1:001")
    ctx = RunContext(company_id="rpl")

    r2_mock = MagicMock()
    r2_mock.put_bytes.return_value = "ok"

    returned_key = write_clause_snapshot(
        units=[unit],
        doc_id="DOC1",
        version="v1",
        company_id="rpl",
        r2_client=r2_mock,
        ctx=ctx,
    )

    expected_key = derived_clauses_key("rpl", "DOC1", "v1")
    assert returned_key == expected_key
    r2_mock.put_bytes.assert_called_once()
    actual_key = r2_mock.put_bytes.call_args[0][0]
    assert actual_key == expected_key


# ---------------------------------------------------------------------------
# Tests: compute_value_source
# ---------------------------------------------------------------------------


def test_compute_value_source_regulatory_restatement_with_citations():
    """compute_value_source: regulatory_restatement with citations → 'regulatory'."""
    unit = _make_unit(role="regulatory_restatement", citations=[_make_citation_entry()])
    param = _make_parameter_entry()
    assert compute_value_source(unit, param) == "regulatory"


def test_compute_value_source_internal_target():
    """compute_value_source: internal_target → 'company'."""
    unit = _make_unit(role="internal_target")
    param = _make_parameter_entry()
    assert compute_value_source(unit, param) == "company"


def test_compute_value_source_template_field():
    """compute_value_source: template_field → 'template'."""
    unit = _make_unit(role="template_field")
    param = _make_parameter_entry()
    assert compute_value_source(unit, param) == "template"


def test_compute_value_source_no_role():
    """compute_value_source: no role (None) → 'company'."""
    unit = _make_unit(role=None)
    param = _make_parameter_entry()
    assert compute_value_source(unit, param) == "company"


# ---------------------------------------------------------------------------
# Tests: build_run_report
# ---------------------------------------------------------------------------


def test_build_run_report_includes_checks_array():
    """build_run_report: includes checks array."""
    ctx = RunContext(company_id="rpl")
    outcomes = [_make_check_outcome(True, 1), _make_check_outcome(True, 2)]
    report = build_run_report(ctx, outcomes, ["DOC1"], {"DOC1": 5})
    assert "checks" in report
    assert len(report["checks"]) == 2
    assert report["checks"][0]["check_number"] == 1


def test_build_run_report_passed_true_when_all_pass():
    """build_run_report: passed=True when all checks pass."""
    ctx = RunContext(company_id="rpl")
    outcomes = [_make_check_outcome(True, 1), _make_check_outcome(True, 2)]
    report = build_run_report(ctx, outcomes, ["DOC1"], {"DOC1": 5})
    assert report["passed"] is True


def test_build_run_report_passed_false_when_any_fails():
    """build_run_report: passed=False when any check fails."""
    ctx = RunContext(company_id="rpl")
    outcomes = [_make_check_outcome(True, 1), _make_check_outcome(False, 2)]
    report = build_run_report(ctx, outcomes, ["DOC1"], {"DOC1": 5})
    assert report["passed"] is False


def test_build_run_report_documents_section():
    """build_run_report: documents section has clause counts."""
    ctx = RunContext(company_id="rpl")
    outcomes = [_make_check_outcome(True, 1)]
    doc_ids = ["DOC1", "DOC2"]
    counts = {"DOC1": 10, "DOC2": 5}
    report = build_run_report(ctx, outcomes, doc_ids, counts)
    assert "documents" in report
    assert report["documents"]["DOC1"]["clause_count"] == 10
    assert report["documents"]["DOC2"]["clause_count"] == 5


# ---------------------------------------------------------------------------
# Tests: finalize_parameters
# ---------------------------------------------------------------------------


def test_finalize_parameters_sets_value_source_on_all():
    """finalize_parameters: sets value_source on all ParameterEntry objects."""
    p1 = _make_parameter_entry()
    p2 = _make_parameter_entry()
    u1 = _make_unit(clause_id="DOC1:001", role="internal_target", parameters=[p1])
    u2 = _make_unit(clause_id="DOC1:002", role="template_field", parameters=[p2])

    finalize_parameters([u1, u2])

    assert p1.value_source == "company"
    assert p2.value_source == "template"

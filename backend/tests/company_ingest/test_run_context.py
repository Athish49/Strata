"""Tests for task 1.1.2: RunContext and Issue."""
from __future__ import annotations

import uuid
from datetime import datetime

import pytest

from app.company_ingest.run_context import Issue, RunContext


# ---------------------------------------------------------------------------
# Issue model
# ---------------------------------------------------------------------------

def test_issue_required_fields():
    issue = Issue(severity="error", stage="parse", code="missing_field", message="Field X is missing")
    assert issue.severity == "error"
    assert issue.stage == "parse"
    assert issue.code == "missing_field"
    assert issue.message == "Field X is missing"
    assert issue.doc_id is None
    assert issue.clause_id is None
    assert issue.path is None
    assert issue.details == {}


def test_issue_optional_fields():
    issue = Issue(
        severity="warning",
        stage="validate",
        code="stale_doc",
        message="Document is older than 2 years",
        doc_id="doc-001",
        clause_id="clause-3",
        path="docs/procedure.md",
        details={"age_days": 730},
    )
    assert issue.doc_id == "doc-001"
    assert issue.clause_id == "clause-3"
    assert issue.path == "docs/procedure.md"
    assert issue.details == {"age_days": 730}


def test_issue_severity_literals():
    for sev in ("error", "warning", "info"):
        i = Issue(severity=sev, stage="s", code="c", message="m")
        assert i.severity == sev


def test_issue_invalid_severity():
    with pytest.raises(Exception):
        Issue(severity="critical", stage="s", code="c", message="m")


# ---------------------------------------------------------------------------
# RunContext defaults
# ---------------------------------------------------------------------------

def test_run_context_defaults():
    ctx = RunContext(company_id="acme")
    assert isinstance(ctx.run_id, uuid.UUID)
    assert ctx.run_id.version == 4
    assert ctx.company_id == "acme"
    assert isinstance(ctx.started_at, datetime)
    assert ctx.no_llm is False
    assert ctx.no_datasets is False
    assert ctx.rebuild is False
    assert ctx.stats == {}
    assert ctx.issues == []


def test_run_context_flags():
    ctx = RunContext(company_id="rpl", no_llm=True, no_datasets=True, rebuild=True)
    assert ctx.no_llm is True
    assert ctx.no_datasets is True
    assert ctx.rebuild is True


# ---------------------------------------------------------------------------
# ctx.issue()
# ---------------------------------------------------------------------------

def test_issue_recording_minimal():
    ctx = RunContext(company_id="x")
    ctx.issue("info", "collect", "file_found", "Found 3 files")
    assert len(ctx.issues) == 1
    i = ctx.issues[0]
    assert i.severity == "info"
    assert i.stage == "collect"
    assert i.code == "file_found"
    assert i.message == "Found 3 files"


def test_issue_recording_all_fields():
    ctx = RunContext(company_id="x")
    ctx.issue(
        "error",
        "parse",
        "bad_yaml",
        "YAML front-matter is invalid",
        doc_id="doc-99",
        clause_id="cls-5",
        path="corpus/docs/proc.md",
        details={"line": 12},
    )
    i = ctx.issues[0]
    assert i.doc_id == "doc-99"
    assert i.clause_id == "cls-5"
    assert i.path == "corpus/docs/proc.md"
    assert i.details == {"line": 12}


def test_issue_recording_multiple():
    ctx = RunContext(company_id="x")
    ctx.issue("info", "a", "c1", "m1")
    ctx.issue("warning", "b", "c2", "m2")
    ctx.issue("error", "c", "c3", "m3")
    assert len(ctx.issues) == 3
    assert [i.severity for i in ctx.issues] == ["info", "warning", "error"]


# ---------------------------------------------------------------------------
# ctx.count()
# ---------------------------------------------------------------------------

def test_count_new_key():
    ctx = RunContext(company_id="x")
    ctx.count("docs_parsed")
    assert ctx.stats["docs_parsed"] == 1


def test_count_accumulation():
    ctx = RunContext(company_id="x")
    ctx.count("docs_parsed")
    ctx.count("docs_parsed")
    ctx.count("docs_parsed")
    assert ctx.stats["docs_parsed"] == 3


def test_count_custom_n():
    ctx = RunContext(company_id="x")
    ctx.count("clauses", 5)
    ctx.count("clauses", 3)
    assert ctx.stats["clauses"] == 8


def test_count_independent_keys():
    ctx = RunContext(company_id="x")
    ctx.count("a", 2)
    ctx.count("b", 7)
    assert ctx.stats["a"] == 2
    assert ctx.stats["b"] == 7


# ---------------------------------------------------------------------------
# ctx.to_report()
# ---------------------------------------------------------------------------

def test_to_report_keys():
    ctx = RunContext(company_id="acme")
    report = ctx.to_report()
    expected_keys = {
        "run_id", "company_id", "started_at", "no_llm",
        "no_datasets", "rebuild", "stats", "issues", "finished_at",
    }
    assert set(report.keys()) == expected_keys


def test_to_report_run_id_is_str():
    ctx = RunContext(company_id="acme")
    report = ctx.to_report()
    assert isinstance(report["run_id"], str)
    # must be parseable back to a UUID
    parsed = uuid.UUID(report["run_id"])
    assert parsed == ctx.run_id


def test_to_report_started_at_is_iso():
    ctx = RunContext(company_id="acme")
    report = ctx.to_report()
    assert isinstance(report["started_at"], str)
    # must be parseable as a datetime
    datetime.fromisoformat(report["started_at"])


def test_to_report_finished_at_is_none():
    ctx = RunContext(company_id="acme")
    report = ctx.to_report()
    assert report["finished_at"] is None


def test_to_report_stats_copy():
    ctx = RunContext(company_id="acme")
    ctx.count("docs", 4)
    report = ctx.to_report()
    assert report["stats"] == {"docs": 4}


def test_to_report_issues_serialized():
    ctx = RunContext(company_id="acme")
    ctx.issue("warning", "validate", "old_doc", "Too old", doc_id="d1", details={"days": 800})
    report = ctx.to_report()
    assert isinstance(report["issues"], list)
    assert len(report["issues"]) == 1
    i = report["issues"][0]
    assert isinstance(i, dict)
    assert i["severity"] == "warning"
    assert i["stage"] == "validate"
    assert i["code"] == "old_doc"
    assert i["message"] == "Too old"
    assert i["doc_id"] == "d1"
    assert i["clause_id"] is None
    assert i["path"] is None
    assert i["details"] == {"days": 800}


def test_to_report_empty_issues():
    ctx = RunContext(company_id="acme")
    report = ctx.to_report()
    assert report["issues"] == []


def test_to_report_flags_preserved():
    ctx = RunContext(company_id="acme", no_llm=True, no_datasets=False, rebuild=True)
    report = ctx.to_report()
    assert report["no_llm"] is True
    assert report["no_datasets"] is False
    assert report["rebuild"] is True
    assert report["company_id"] == "acme"

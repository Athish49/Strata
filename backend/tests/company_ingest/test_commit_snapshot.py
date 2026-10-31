"""Tests for tasks 8.1.2 / 5.8 — store/snapshot.py, store/commit.py, ingest_runs lifecycle."""
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

    version_id = "11111111-1111-4111-8111-111111111111"
    returned_key = write_clause_snapshot(
        units=[unit],
        doc_id="DOC1",
        version_id=version_id,
        company_id="rpl",
        r2_client=r2_mock,
        ctx=ctx,
    )

    expected_key = derived_clauses_key("rpl", "DOC1", version_id)
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


# ===========================================================================
# Task 5.8 — store-layer defects
# ===========================================================================

import asyncio  # noqa: E402
import uuid  # noqa: E402

import boto3  # noqa: E402
from moto import mock_aws  # noqa: E402

import app.company_ingest.store.r2 as r2_mod  # noqa: E402
from app.company_ingest.store import neon as neon_mod  # noqa: E402
from app.company_ingest.store.commit import (  # noqa: E402
    finish_ingest_run,
    start_ingest_run,
)
from app.company_ingest.store.r2_keys import derived_clauses_key, report_key  # noqa: E402

_FAKE_BUCKET = "test-bucket"
_V1 = "aaaaaaaa-0000-4000-8000-000000000001"
_V2 = "aaaaaaaa-0000-4000-8000-000000000002"


def _moto_client():
    return boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="fake-key",
        aws_secret_access_key="fake-secret",
    )


@pytest.fixture()
def r2(monkeypatch):
    """The REAL r2 module (write-once guard included) against moto S3."""
    with mock_aws():
        _moto_client().create_bucket(Bucket=_FAKE_BUCKET)
        monkeypatch.setattr(r2_mod, "_get_client", lambda: _moto_client())
        monkeypatch.setattr(r2_mod.settings, "R2_BUCKET_NAME", _FAKE_BUCKET)
        yield r2_mod


class _FakeRunsDB:
    """company.ingest_runs only.  Writes become visible on commit() only, so a
    helper that forgets to commit (or a rolled-back session) leaves no row."""

    def __init__(self):
        self.rows: dict[str, dict] = {}
        self.commits = 0

    def factory(self):
        return _FakeRunsSession(self)


class _FakeRunsSession:
    def __init__(self, db: _FakeRunsDB):
        self.db = db
        self.pending: list[tuple[str, dict]] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        self.pending.clear()  # uncommitted work is discarded (rollback)
        return False

    async def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        assert sql.startswith("INSERT INTO company.ingest_runs"), sql
        self.pending.append((sql, dict(params)))

    async def commit(self):
        for sql, p in self.pending:
            run_id = p["run_id"]
            existing = self.db.rows.get(run_id)
            if "DO NOTHING" in sql:
                if existing is None:
                    self.db.rows[run_id] = {
                        **p, "finished_at": None, "report_r2_key": None,
                    }
            elif existing is None:
                self.db.rows[run_id] = p
            else:
                existing.update(
                    finished_at=p["finished_at"],
                    status=p["status"],
                    report_r2_key=p["report_r2_key"],
                )
        self.pending.clear()
        self.db.commits += 1

    async def rollback(self):
        self.pending.clear()


def _run(coro):
    return asyncio.run(coro)


# ---- (1) snapshot key + write-once guard ---------------------------------


def test_snapshot_two_versions_two_distinct_keys_neither_raises(r2):
    ctx = RunContext(company_id="rpl")
    k1 = write_clause_snapshot(
        [_make_unit(version_id=_V1)], "DOC1", _V1, "rpl", r2, ctx
    )
    k2 = write_clause_snapshot(
        [_make_unit(version_id=_V2, text_raw="changed")], "DOC1", _V2, "rpl", r2, ctx
    )
    assert k1 == derived_clauses_key("rpl", "DOC1", _V1)
    assert k2 == derived_clauses_key("rpl", "DOC1", _V2)
    assert k1 != k2
    assert _V1 in k1 and _V2 in k2 and "/v1/" not in k1
    assert r2.exists(k1) and r2.exists(k2)
    assert b"changed" not in r2.get_bytes(k1)
    assert b"changed" in r2.get_bytes(k2)


def test_snapshot_rewrite_same_version_changed_content_does_not_raise(r2):
    """The old landmine: a retry whose content changed hit the write-once
    ValueError and failed the run.  Default force=True overwrites."""
    ctx = RunContext(company_id="rpl")
    key = write_clause_snapshot([_make_unit(version_id=_V1)], "DOC1", _V1, "rpl", r2, ctx)
    key2 = write_clause_snapshot(
        [_make_unit(version_id=_V1, text_raw="after retry")], "DOC1", _V1, "rpl", r2, ctx
    )
    assert key == key2
    assert b"after retry" in r2.get_bytes(key)


def test_snapshot_force_false_conflict_is_an_issue_not_an_exception(r2):
    ctx = RunContext(company_id="rpl")
    key = write_clause_snapshot([_make_unit(version_id=_V1)], "DOC1", _V1, "rpl", r2, ctx)
    write_clause_snapshot(
        [_make_unit(version_id=_V1, text_raw="other")], "DOC1", _V1, "rpl", r2, ctx,
        force=False,
    )
    assert [i.code for i in ctx.issues] == ["snapshot_write_once_conflict"]
    assert b"other" not in r2.get_bytes(key)  # existing object kept


def test_snapshot_rejects_version_label_instead_of_version_id():
    with pytest.raises(ValueError, match="real version_id"):
        write_clause_snapshot(
            [_make_unit()], "DOC1", "v1", "rpl", MagicMock(), RunContext(company_id="rpl")
        )


# ---- (2) + (3) ingest_runs lifecycle and report.json -------------------------


def test_start_ingest_run_commits_running_row():
    db = _FakeRunsDB()
    ctx = RunContext(company_id="rpl")
    _run(start_ingest_run(ctx, session_factory=db.factory))
    row = db.rows[str(ctx.run_id)]
    assert row["status"] == "running"
    assert row["finished_at"] is None
    assert row["report_r2_key"] is None
    assert row["company_id"] == "rpl"
    # idempotent
    _run(start_ingest_run(ctx, session_factory=db.factory))
    assert len(db.rows) == 1


def test_finish_completed_writes_report_to_r2_and_sets_report_r2_key(r2):
    db = _FakeRunsDB()
    ctx = RunContext(company_id="rpl")
    ctx.count("clauses", 7)
    _run(start_ingest_run(ctx, session_factory=db.factory))

    key = _run(finish_ingest_run(
        ctx, "completed",
        doc_ids=["DOC1"], unit_counts_by_doc={"DOC1": 7},
        r2_client=r2, session_factory=db.factory,
    ))

    assert key == report_key("rpl", str(ctx.run_id))
    assert r2.exists(key)
    report = json.loads(r2.get_bytes(key))
    assert report["run_id"] == str(ctx.run_id)
    assert report["status"] == "completed"
    assert report["passed"] is True
    assert report["finished_at"] is not None
    assert report["documents"] == {"DOC1": {"clause_count": 7}}
    assert report["stats"]["clauses"] == 7

    row = db.rows[str(ctx.run_id)]
    assert row["status"] == "completed"
    assert row["report_r2_key"] == key
    assert row["finished_at"] is not None


def test_crashed_run_leaves_non_completed_row():
    """Start row is committed in its own session; the ingest transaction then
    blows up and is rolled back, and the process dies before finish."""
    db = _FakeRunsDB()
    ctx = RunContext(company_id="rpl")

    async def _job():
        await start_ingest_run(ctx, session_factory=db.factory)
        ingest_session = _FakeRunsSession(db)  # stands in for the ingest txn
        try:
            await neon_mod.insert_ingest_run(ingest_session, ctx, "completed", None)
            raise RuntimeError("segmenter exploded")
        except RuntimeError:
            await ingest_session.rollback()
            raise  # crash: finish_ingest_run is never reached

    with pytest.raises(RuntimeError):
        _run(_job())
    row = db.rows[str(ctx.run_id)]
    assert row["status"] == "running"
    assert row["status"] != "completed"
    assert row["finished_at"] is None


def test_handled_failure_marks_failed_and_still_writes_report(r2):
    db = _FakeRunsDB()
    ctx = RunContext(company_id="rpl")
    _run(start_ingest_run(ctx, session_factory=db.factory))
    key = _run(finish_ingest_run(
        ctx, "failed", error="CitationResolutionError('boom')",
        doc_ids=["DOC1"], r2_client=r2, session_factory=db.factory,
    ))
    row = db.rows[str(ctx.run_id)]
    assert row["status"] == "failed"
    assert row["report_r2_key"] == key and r2.exists(key)
    report = json.loads(r2.get_bytes(key))
    assert report["status"] == "failed"
    assert report["passed"] is False
    assert "boom" in report["error"]


def test_finish_still_sets_status_when_report_write_fails():
    db = _FakeRunsDB()
    ctx = RunContext(company_id="rpl")
    _run(start_ingest_run(ctx, session_factory=db.factory))
    broken = MagicMock()
    broken.put_bytes.side_effect = RuntimeError("R2 down")
    key = _run(finish_ingest_run(ctx, "completed", r2_client=broken, session_factory=db.factory))
    assert key is None
    row = db.rows[str(ctx.run_id)]
    assert row["status"] == "completed"
    assert row["report_r2_key"] is None


def test_finish_rejects_non_terminal_status():
    db = _FakeRunsDB()
    with pytest.raises(ValueError):
        _run(finish_ingest_run(
            RunContext(company_id="rpl"), "running",
            r2_client=MagicMock(), session_factory=db.factory,
        ))
    assert db.rows == {}


def test_commit_run_no_longer_writes_ingest_runs(monkeypatch):
    """The in-transaction 'completed' upsert is gone from commit_run."""
    from unittest.mock import AsyncMock

    for name in (
        "insert_company_documents", "insert_document_versions", "insert_clause_citations",
        "insert_clause_parameters", "insert_defined_terms", "insert_term_usages_with_map",
        "insert_clause_links", "insert_document_scope", "insert_table_columns",
    ):
        monkeypatch.setattr(neon_mod, name, AsyncMock())
    monkeypatch.setattr(neon_mod, "insert_clauses_bulk", AsyncMock(return_value={}))
    spy = AsyncMock()
    monkeypatch.setattr(neon_mod, "insert_ingest_run", spy)
    session = MagicMock()
    session.execute = AsyncMock()

    _run(neon_mod.commit_run(
        session=session, ctx=RunContext(company_id="rpl"), sources=[], register_entries=[],
        units=[_make_unit(version_id=_V1)], links=[], scope_rows=[], terms=[],
        term_usages=[], col_roles_map={}, report_r2_key=None,
        version_specs={"DOC1": neon_mod.DocumentVersionSpec(version_id=_V1, version_no=1)},
    ))
    spy.assert_not_called()
    for c in session.execute.call_args_list:
        assert "ingest_runs" not in str(c.args[0])

"""Tests for Task 7.2.3 — validate_checks."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from app.company_ingest.datasets.propose_checks import CheckProposal
from app.company_ingest.datasets.duckdb_runner import CheckResult
from app.company_ingest.enrich.parameter_entry import ParameterEntry
from app.company_ingest.run_context import RunContext
from app.company_ingest.datasets.validate_checks import validate_checks


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(
    value_num: float | None = 30.0,
    unit: str | None = None,
    value_text: str = "30",
    kind: str = "period",
) -> ParameterEntry:
    return ParameterEntry(
        kind=kind,
        unit=unit,
        value_text=value_text,
        value_num=value_num,
        value_source=None,
        qualifier=None,
        day_type="n_a",
        span_start=0,
        span_end=2,
        method="regex",
        verified=True,
    )


def make_proposal(
    sql_template: str = "SELECT * FROM tbl WHERE val > {threshold}",
    param_bindings: dict[str, str] | None = None,
    dataset_name: str = "tbl",
) -> CheckProposal:
    return CheckProposal(
        dataset_name=dataset_name,
        doc_id="doc1",
        purpose="Checks that values exceed threshold.",
        sql_template=sql_template,
        param_bindings=param_bindings if param_bindings is not None else {"threshold": "pk1"},
    )


def make_result(violation_count: int = 0, elapsed: float = 0.01, error: str | None = None) -> CheckResult:
    return CheckResult(
        violation_count=violation_count,
        affected_count=violation_count,
        sample_rows=[],
        elapsed_seconds=elapsed,
        error=error,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

MODULE = "app.company_ingest.datasets.validate_checks.run_check"


def test_validated_true_when_violation_count_zero():
    """Check with violation_count=0 → validated=True, s1_result set."""
    ctx = RunContext()
    proposal = make_proposal()
    parameter_map = {"pk1": make_entry(value_num=10.0, unit=None)}
    datasets = {"tbl": "/fake/path.parquet"}

    with patch(MODULE, return_value=make_result(violation_count=0, elapsed=0.05)) as mock_run:
        result = validate_checks([proposal], parameter_map, datasets, ctx)

    assert result[0].validated is True
    assert result[0].s1_result is not None
    assert result[0].s1_result["violation_count"] == 0
    assert result[0].s1_result["elapsed"] == pytest.approx(0.05)
    assert result[0].error is None


def test_validated_false_when_violation_count_nonzero():
    """Check with violation_count>0 → validated=False, error='violation_count_nonzero'."""
    ctx = RunContext()
    proposal = make_proposal()
    parameter_map = {"pk1": make_entry(value_num=10.0)}
    datasets = {"tbl": "/fake/path.parquet"}

    with patch(MODULE, return_value=make_result(violation_count=5)):
        result = validate_checks([proposal], parameter_map, datasets, ctx)

    assert result[0].validated is False
    assert result[0].error == "violation_count_nonzero"
    assert result[0].s1_result is None


def test_validated_false_when_run_check_errors():
    """Check with error='timeout' → validated=False, error='timeout'."""
    ctx = RunContext()
    proposal = make_proposal()
    parameter_map = {"pk1": make_entry(value_num=10.0)}
    datasets = {}

    with patch(MODULE, return_value=make_result(error="timeout")):
        result = validate_checks([proposal], parameter_map, datasets, ctx)

    assert result[0].validated is False
    assert result[0].error == "timeout"


def test_validated_false_when_parameter_pk_missing():
    """parameter_pk not in parameter_map → proposal.error set, validated=False."""
    ctx = RunContext()
    proposal = make_proposal(param_bindings={"threshold": "missing_pk"})
    parameter_map = {}  # empty — pk not found
    datasets = {}

    with patch(MODULE) as mock_run:
        result = validate_checks([proposal], parameter_map, datasets, ctx)

    mock_run.assert_not_called()
    assert result[0].validated is False
    assert "missing_pk" in result[0].error


def test_number_parameter_binding():
    """Number parameter → bound as kind='number' in run_check call."""
    ctx = RunContext()
    proposal = make_proposal()
    parameter_map = {"pk1": make_entry(value_num=42.0, unit="usd")}
    datasets = {}

    with patch(MODULE, return_value=make_result()) as mock_run:
        validate_checks([proposal], parameter_map, datasets, ctx)

    call_params = mock_run.call_args[0][1]  # second positional arg is params
    assert call_params["threshold"][1] == "number"
    assert call_params["threshold"][0] == pytest.approx(42.0)


def test_duration_parameter_binding():
    """Duration parameter (days) → bound as kind='duration' with unit."""
    ctx = RunContext()
    proposal = make_proposal(
        sql_template="SELECT * FROM tbl WHERE age > {max_age}",
        param_bindings={"max_age": "pk1"},
    )
    parameter_map = {"pk1": make_entry(value_num=30.0, unit="day")}
    datasets = {}

    with patch(MODULE, return_value=make_result()) as mock_run:
        validate_checks([proposal], parameter_map, datasets, ctx)

    call_params = mock_run.call_args[0][1]
    assert call_params["max_age"][1] == "duration"
    assert call_params["max_age"][0] == pytest.approx(30.0)
    assert call_params["max_age"][2] == "day"


def test_string_parameter_binding():
    """String parameter → bound as kind='string'."""
    ctx = RunContext()
    proposal = make_proposal(
        sql_template="SELECT * FROM tbl WHERE status = {status_val}",
        param_bindings={"status_val": "pk1"},
    )
    parameter_map = {"pk1": make_entry(value_num=None, unit=None, value_text="active")}
    datasets = {}

    with patch(MODULE, return_value=make_result()) as mock_run:
        validate_checks([proposal], parameter_map, datasets, ctx)

    call_params = mock_run.call_args[0][1]
    assert call_params["status_val"][1] == "string"
    assert call_params["status_val"][0] == "active"


def test_ctx_count_checks_validated():
    """ctx.count('checks_validated') incremented for validated proposals."""
    ctx = RunContext()
    proposal = make_proposal()
    parameter_map = {"pk1": make_entry(value_num=5.0)}
    datasets = {}

    with patch(MODULE, return_value=make_result(violation_count=0)):
        validate_checks([proposal], parameter_map, datasets, ctx)

    assert ctx.stats.get("checks_validated", 0) == 1
    assert ctx.stats.get("checks_failed_validation", 0) == 0


def test_ctx_count_checks_failed_validation():
    """ctx.count('checks_failed_validation') incremented for failed proposals."""
    ctx = RunContext()
    proposal = make_proposal()
    parameter_map = {"pk1": make_entry(value_num=5.0)}
    datasets = {}

    with patch(MODULE, return_value=make_result(violation_count=3)):
        validate_checks([proposal], parameter_map, datasets, ctx)

    assert ctx.stats.get("checks_failed_validation", 0) == 1
    assert ctx.stats.get("checks_validated", 0) == 0


def test_multiple_proposals_processed_independently():
    """Multiple proposals: each processed independently."""
    ctx = RunContext()
    p1 = make_proposal(param_bindings={"threshold": "pk1"})
    p2 = make_proposal(
        sql_template="SELECT * FROM tbl WHERE col < {limit}",
        param_bindings={"limit": "pk2"},
    )
    parameter_map = {
        "pk1": make_entry(value_num=10.0),
        "pk2": make_entry(value_num=100.0),
    }
    datasets = {}

    results_seq = [make_result(violation_count=0), make_result(violation_count=2)]

    with patch(MODULE, side_effect=results_seq):
        result = validate_checks([p1, p2], parameter_map, datasets, ctx)

    assert result[0].validated is True
    assert result[1].validated is False
    assert ctx.stats.get("checks_validated", 0) == 1
    assert ctx.stats.get("checks_failed_validation", 0) == 1


def test_s1_result_contains_violation_count_and_elapsed():
    """s1_result contains violation_count and elapsed."""
    ctx = RunContext()
    proposal = make_proposal()
    parameter_map = {"pk1": make_entry(value_num=1.0)}
    datasets = {}

    with patch(MODULE, return_value=make_result(violation_count=0, elapsed=0.123)):
        result = validate_checks([proposal], parameter_map, datasets, ctx)

    assert "violation_count" in result[0].s1_result
    assert "elapsed" in result[0].s1_result
    assert result[0].s1_result["violation_count"] == 0
    assert result[0].s1_result["elapsed"] == pytest.approx(0.123)

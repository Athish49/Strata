"""Tests for Task 7.2.2 — propose_checks (Stage 4c)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from app.company_ingest.datasets.profile import ColumnProfile, DatasetProfile
from app.company_ingest.datasets.propose_checks import (
    CheckProposal,
    DatasetEnrichment,
    ParameterBinding,
    ProposedCheck,
    _find_describing_clauses,
    propose_checks,
)
from app.company_ingest.enrich.parameter_entry import ParameterEntry
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.run_context import RunContext


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_profile(
    name: str = "test_dataset",
    doc_id: str | None = "DOC-001",
    row_count: int = 100,
    columns: list[ColumnProfile] | None = None,
) -> DatasetProfile:
    if columns is None:
        columns = [
            ColumnProfile(
                column_name="amount",
                dtype="float",
                null_rate=0.0,
                distinct_count=100,
                min_value="0",
                max_value="9999",
                top_values=None,
            )
        ]
    return DatasetProfile(
        name=name,
        doc_id=doc_id,
        row_count=row_count,
        file_sha256="abc123",
        r2_parquet_key="key/parquet",
        r2_source_key="key/source",
        primary_key=None,
        columns=columns,
    )


def _make_unit(
    doc_id: str = "DOC-001",
    clause_id: str = "DOC-001:c1",
    local_id: str = "c1",
    text_raw: str = "Some clause text",
    parameters: list[Any] | None = None,
    ordinal: int = 0,
) -> ClauseUnit:
    return ClauseUnit(
        version_id="v1",
        doc_id=doc_id,
        clause_id=clause_id,
        local_id=local_id,
        parent_clause_id=None,
        unit_kind="clause",
        heading_path=[],
        section_kind="body",
        ordinal=ordinal,
        char_start=0,
        char_end=len(text_raw),
        line_start=0,
        text_raw=text_raw,
        text_norm=text_raw,
        text_sha256="sha",
        parameters=parameters or [],
    )


def _make_param() -> ParameterEntry:
    return ParameterEntry(
        kind="amount",
        unit="USD",
        value_text="$1000",
        value_num=1000.0,
        value_source=None,
        qualifier=None,
        day_type="n_a",
        span_start=0,
        span_end=5,
        method="regex",
        verified=True,
    )


def _make_enrichment(
    description: str = "A test dataset.",
    checks: list[ProposedCheck] | None = None,
) -> DatasetEnrichment:
    return DatasetEnrichment(
        description=description,
        columns=[],
        checks=checks or [],
    )


# ---------------------------------------------------------------------------
# Tests: propose_checks — LLM interactions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_returns_valid_check_creates_proposal():
    """LLM returns a valid check → CheckProposal(validated=False, method='llm_proposed')."""
    profile = _make_profile()
    unit = _make_unit(
        text_raw="test_dataset contains amounts",
        parameters=[_make_param()],
    )
    ctx = RunContext()

    check = ProposedCheck(
        purpose="This check finds rows where amount exceeds the limit.",
        sql_template="SELECT * FROM test_dataset WHERE amount > {limit}",
        param_bindings=[
            ParameterBinding(placeholder="limit", parameter_pk="DOC-001:c1:0")
        ],
    )
    enrichment = _make_enrichment(checks=[check])

    with patch(
        "app.company_ingest.datasets.propose_checks.call_structured",
        new=AsyncMock(return_value=enrichment),
    ):
        description, proposals = await propose_checks(profile, [unit], [], ctx)

    assert description == "A test dataset."
    assert len(proposals) == 1
    p = proposals[0]
    assert isinstance(p, CheckProposal)
    assert p.validated is False
    assert p.method == "llm_proposed"
    assert p.dataset_name == "test_dataset"
    assert p.doc_id == "DOC-001"
    assert p.purpose == "This check finds rows where amount exceeds the limit."


@pytest.mark.asyncio
async def test_llm_returns_none_returns_empty():
    """LLM returns None → (None, [])."""
    profile = _make_profile()
    ctx = RunContext()

    with patch(
        "app.company_ingest.datasets.propose_checks.call_structured",
        new=AsyncMock(return_value=None),
    ):
        description, proposals = await propose_checks(profile, [], [], ctx)

    assert description is None
    assert proposals == []


@pytest.mark.asyncio
async def test_valid_placeholder_in_template_kept():
    """Placeholder in sql_template and binding → kept."""
    profile = _make_profile()
    unit = _make_unit(
        text_raw="test_dataset data",
        parameters=[_make_param()],
    )
    ctx = RunContext()

    check = ProposedCheck(
        purpose="This check validates that amount is within the threshold.",
        sql_template="SELECT * FROM t WHERE amount > {threshold}",
        param_bindings=[
            ParameterBinding(placeholder="threshold", parameter_pk="DOC-001:c1:0")
        ],
    )
    enrichment = _make_enrichment(checks=[check])

    with patch(
        "app.company_ingest.datasets.propose_checks.call_structured",
        new=AsyncMock(return_value=enrichment),
    ):
        description, proposals = await propose_checks(profile, [unit], [], ctx)

    assert len(proposals) == 1
    assert "threshold" in proposals[0].param_bindings


@pytest.mark.asyncio
async def test_placeholder_not_in_sql_template_dropped():
    """Placeholder in binding but NOT in sql_template → dropped + issue."""
    profile = _make_profile()
    unit = _make_unit(
        text_raw="test_dataset data",
        parameters=[_make_param()],
    )
    ctx = RunContext()

    check = ProposedCheck(
        purpose="This check validates data integrity for the dataset.",
        sql_template="SELECT * FROM t WHERE amount > 100",  # no {limit} here
        param_bindings=[
            ParameterBinding(placeholder="limit", parameter_pk="DOC-001:c1:0")
        ],
    )
    enrichment = _make_enrichment(checks=[check])

    with patch(
        "app.company_ingest.datasets.propose_checks.call_structured",
        new=AsyncMock(return_value=enrichment),
    ):
        description, proposals = await propose_checks(profile, [unit], [], ctx)

    # Proposal is still created (empty bindings)
    assert len(proposals) == 1
    assert "limit" not in proposals[0].param_bindings
    # Issue was recorded
    binding_issues = [i for i in ctx.issues if i.code == "check_binding_invalid"]
    assert len(binding_issues) >= 1


@pytest.mark.asyncio
async def test_parameter_pk_not_in_map_dropped():
    """parameter_pk not in parameter map → dropped + issue."""
    profile = _make_profile()
    unit = _make_unit(
        text_raw="test_dataset data",
        parameters=[_make_param()],
    )
    ctx = RunContext()

    check = ProposedCheck(
        purpose="This check validates that values are within the regulatory threshold.",
        sql_template="SELECT * FROM t WHERE amount > {limit}",
        param_bindings=[
            ParameterBinding(
                placeholder="limit",
                parameter_pk="NONEXISTENT:clause:999",  # not in map
            )
        ],
    )
    enrichment = _make_enrichment(checks=[check])

    with patch(
        "app.company_ingest.datasets.propose_checks.call_structured",
        new=AsyncMock(return_value=enrichment),
    ):
        description, proposals = await propose_checks(profile, [unit], [], ctx)

    assert len(proposals) == 1
    assert "limit" not in proposals[0].param_bindings
    binding_issues = [i for i in ctx.issues if i.code == "check_binding_invalid"]
    assert len(binding_issues) >= 1


@pytest.mark.asyncio
async def test_checks_proposed_counter_incremented():
    """ctx.count('checks_proposed') incremented per stored proposal."""
    profile = _make_profile()
    unit = _make_unit(
        text_raw="test_dataset data",
        parameters=[_make_param()],
    )
    ctx = RunContext()

    checks = [
        ProposedCheck(
            purpose=f"This check validates column {i} in the dataset.",
            sql_template=f"SELECT * FROM t WHERE amount > {{limit{i}}}",
            param_bindings=[
                ParameterBinding(placeholder=f"limit{i}", parameter_pk="DOC-001:c1:0")
            ],
        )
        for i in range(3)
    ]
    enrichment = _make_enrichment(checks=checks)

    with patch(
        "app.company_ingest.datasets.propose_checks.call_structured",
        new=AsyncMock(return_value=enrichment),
    ):
        description, proposals = await propose_checks(profile, [unit], [], ctx)

    assert len(proposals) == 3
    assert ctx.stats.get("checks_proposed", 0) == 3


# ---------------------------------------------------------------------------
# Tests: _find_describing_clauses
# ---------------------------------------------------------------------------


def test_find_describing_clauses_same_doc_matching_name():
    """_find_describing_clauses: same-doc unit with matching dataset name → included."""
    profile = _make_profile(name="my_dataset", doc_id="DOC-001")
    unit_match = _make_unit(
        doc_id="DOC-001",
        clause_id="DOC-001:c1",
        text_raw="The my_dataset table contains regulatory data.",
    )
    unit_other_doc = _make_unit(
        doc_id="DOC-999",
        clause_id="DOC-999:c1",
        text_raw="The my_dataset table in a different doc.",
    )
    unit_no_match = _make_unit(
        doc_id="DOC-001",
        clause_id="DOC-001:c2",
        text_raw="This clause does not mention the dataset.",
    )

    result = _find_describing_clauses(profile, [unit_match, unit_other_doc, unit_no_match], [])

    clause_ids = {u.clause_id for u in result}
    assert "DOC-001:c1" in clause_ids
    assert "DOC-999:c1" not in clause_ids
    assert "DOC-001:c2" not in clause_ids


def test_find_describing_clauses_units_with_parameters_sorted_first():
    """_find_describing_clauses: units with parameters sorted first."""
    profile = _make_profile(name="my_dataset", doc_id="DOC-001")

    unit_no_param = _make_unit(
        doc_id="DOC-001",
        clause_id="DOC-001:c1",
        text_raw="my_dataset is referenced here.",
        parameters=[],
        ordinal=0,
    )
    unit_with_param = _make_unit(
        doc_id="DOC-001",
        clause_id="DOC-001:c2",
        text_raw="my_dataset with $1000 threshold.",
        parameters=[_make_param()],
        ordinal=1,
    )

    result = _find_describing_clauses(profile, [unit_no_param, unit_with_param], [])

    assert len(result) == 2
    # unit with parameters should come first
    assert result[0].clause_id == "DOC-001:c2"
    assert result[1].clause_id == "DOC-001:c1"


def test_find_describing_clauses_capped_at_25():
    """_find_describing_clauses: capped at 25."""
    profile = _make_profile(name="my_dataset", doc_id="DOC-001")

    units = [
        _make_unit(
            doc_id="DOC-001",
            clause_id=f"DOC-001:c{i}",
            local_id=f"c{i}",
            text_raw=f"my_dataset entry number {i}.",
            ordinal=i,
        )
        for i in range(40)
    ]

    result = _find_describing_clauses(profile, units, [], max_clauses=25)

    assert len(result) == 25


# ---------------------------------------------------------------------------
# Tests: DatasetEnrichment model
# ---------------------------------------------------------------------------


def test_dataset_enrichment_caps_checks_at_5():
    """DatasetEnrichment: >5 checks → capped to 5."""
    checks = [
        ProposedCheck(
            purpose=f"This check validates condition number {i} in the dataset.",
            sql_template=f"SELECT * FROM t WHERE col > {{p{i}}}",
            param_bindings=[],
        )
        for i in range(8)
    ]
    enrichment = DatasetEnrichment(
        description="A dataset.",
        checks=checks,
    )
    assert len(enrichment.checks) == 5


def test_dataset_enrichment_zero_checks_valid():
    """DatasetEnrichment: 0 checks valid."""
    enrichment = DatasetEnrichment(description="A dataset with no checks.", checks=[])
    assert enrichment.checks == []


@pytest.mark.asyncio
async def test_description_returned_correctly():
    """description returned correctly."""
    profile = _make_profile()
    ctx = RunContext()

    enrichment = DatasetEnrichment(
        description="This dataset tracks regulatory compliance data for all entities.",
        checks=[],
    )

    with patch(
        "app.company_ingest.datasets.propose_checks.call_structured",
        new=AsyncMock(return_value=enrichment),
    ):
        description, proposals = await propose_checks(profile, [], [], ctx)

    assert description == "This dataset tracks regulatory compliance data for all entities."
    assert proposals == []

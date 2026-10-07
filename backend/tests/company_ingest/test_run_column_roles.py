"""Tests for task 5.2.1: run_column_roles — LLM-based column role classification."""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.company_ingest.constants import ColumnRole
from app.company_ingest.llm.run_column_roles import (
    ColumnRoleAssignment,
    ColumnRolesResponse,
    _build_user_message,
    run_column_roles,
)
from app.company_ingest.run_context import RunContext

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx() -> RunContext:
    return RunContext(company_id="test_co")


def _make_response(*pairs: tuple[str, ColumnRole]) -> ColumnRolesResponse:
    return ColumnRolesResponse(
        assignments=[ColumnRoleAssignment(column_name=col, role=role) for col, role in pairs]
    )


HEADERS = ["id_col", "citation_col", "mystery_col", "another_unknown"]
PROVISIONAL = {
    "id_col": ColumnRole.ID,
    "citation_col": ColumnRole.CITATION,
    "mystery_col": None,
    "another_unknown": None,
}
SAMPLE_ROWS = [
    {"id_col": "R001", "citation_col": "170 IAC 4-1-16", "mystery_col": "John Smith", "another_unknown": "active"},
    {"id_col": "R002", "citation_col": "170 IAC 4-1-17", "mystery_col": "Jane Doe", "another_unknown": "pending"},
]


# ---------------------------------------------------------------------------
# Test 1: No null roles → return unchanged, call_structured NOT called
# ---------------------------------------------------------------------------


async def test_no_null_roles_skips_llm():
    """When all provisional roles are assigned, LLM is not called."""
    provisional = {"col_a": ColumnRole.ID, "col_b": ColumnRole.CITATION}
    headers = ["col_a", "col_b"]
    ctx = _make_ctx()

    with patch(
        "app.company_ingest.llm.run_column_roles.call_structured", new_callable=AsyncMock
    ) as mock_cs:
        result = await run_column_roles("DOC1", headers, provisional, [], ctx)

    mock_cs.assert_not_called()
    assert result == provisional


# ---------------------------------------------------------------------------
# Test 2: One null column → call_structured called once with unit_id=doc_id
# ---------------------------------------------------------------------------


async def test_one_null_column_calls_llm_with_doc_id():
    """LLM is called once, with unit_id set to the doc_id."""
    provisional = {"col_a": ColumnRole.ID, "col_b": None}
    headers = ["col_a", "col_b"]
    ctx = _make_ctx()

    llm_response = _make_response(("col_b", ColumnRole.FREE_TEXT))

    with patch(
        "app.company_ingest.llm.run_column_roles.call_structured", new_callable=AsyncMock
    ) as mock_cs:
        mock_cs.return_value = llm_response
        result = await run_column_roles("MY_DOC", headers, provisional, [], ctx)

    mock_cs.assert_called_once()
    # Second positional arg is unit_id == doc_id
    assert mock_cs.call_args[0][1] == "MY_DOC"
    assert result["col_b"] == ColumnRole.FREE_TEXT


# ---------------------------------------------------------------------------
# Test 3: LLM assigns role → merged into result dict
# ---------------------------------------------------------------------------


async def test_llm_assigns_role_merged_into_result():
    """LLM result is correctly merged into the output dict."""
    ctx = _make_ctx()
    llm_response = _make_response(
        ("mystery_col", ColumnRole.OWNER_PERSON),
        ("another_unknown", ColumnRole.STATUS),
    )

    with patch(
        "app.company_ingest.llm.run_column_roles.call_structured", new_callable=AsyncMock,
        return_value=llm_response,
    ):
        result = await run_column_roles("DOC1", HEADERS, PROVISIONAL, SAMPLE_ROWS, ctx)

    assert result["id_col"] == ColumnRole.ID
    assert result["citation_col"] == ColumnRole.CITATION
    assert result["mystery_col"] == ColumnRole.OWNER_PERSON
    assert result["another_unknown"] == ColumnRole.STATUS


# ---------------------------------------------------------------------------
# Test 4: LLM returns None (failure) → null columns stay None
# ---------------------------------------------------------------------------


async def test_llm_failure_keeps_null_columns_as_none():
    """When LLM returns None, null columns remain None in output."""
    ctx = _make_ctx()

    with patch(
        "app.company_ingest.llm.run_column_roles.call_structured", new_callable=AsyncMock,
        return_value=None,
    ):
        result = await run_column_roles("DOC1", HEADERS, PROVISIONAL, SAMPLE_ROWS, ctx)

    assert result["mystery_col"] is None
    assert result["another_unknown"] is None
    # Non-null provisionals are preserved
    assert result["id_col"] == ColumnRole.ID
    assert result["citation_col"] == ColumnRole.CITATION


# ---------------------------------------------------------------------------
# Test 5: LLM covers only some null columns → others stay None
# ---------------------------------------------------------------------------


async def test_llm_partial_coverage_leaves_uncovered_as_none():
    """Columns not returned by LLM keep their None value."""
    ctx = _make_ctx()
    # LLM only classifies mystery_col, not another_unknown
    llm_response = _make_response(("mystery_col", ColumnRole.SUMMARY_TEXT))

    with patch(
        "app.company_ingest.llm.run_column_roles.call_structured", new_callable=AsyncMock,
        return_value=llm_response,
    ):
        result = await run_column_roles("DOC1", HEADERS, PROVISIONAL, SAMPLE_ROWS, ctx)

    assert result["mystery_col"] == ColumnRole.SUMMARY_TEXT
    assert result["another_unknown"] is None


# ---------------------------------------------------------------------------
# Test 6: Provisional roles preserved for non-null columns
# ---------------------------------------------------------------------------


async def test_provisional_roles_preserved_for_non_null_columns():
    """Non-null provisional roles are not overwritten by LLM output."""
    ctx = _make_ctx()
    llm_response = _make_response(
        ("mystery_col", ColumnRole.DATE),
        ("another_unknown", ColumnRole.ENUM),
    )

    with patch(
        "app.company_ingest.llm.run_column_roles.call_structured", new_callable=AsyncMock,
        return_value=llm_response,
    ):
        result = await run_column_roles("DOC1", HEADERS, PROVISIONAL, SAMPLE_ROWS, ctx)

    assert result["id_col"] == ColumnRole.ID
    assert result["citation_col"] == ColumnRole.CITATION


# ---------------------------------------------------------------------------
# Test 7: ctx.count("column_roles_llm_assigned") incremented per LLM-classified column
# ---------------------------------------------------------------------------


async def test_count_incremented_per_llm_classified_column():
    """ctx.count is called once per column the LLM classifies."""
    ctx = _make_ctx()
    llm_response = _make_response(
        ("mystery_col", ColumnRole.FREE_TEXT),
        ("another_unknown", ColumnRole.STATUS),
    )

    with patch(
        "app.company_ingest.llm.run_column_roles.call_structured", new_callable=AsyncMock,
        return_value=llm_response,
    ):
        await run_column_roles("DOC1", HEADERS, PROVISIONAL, SAMPLE_ROWS, ctx)

    assert ctx.stats.get("column_roles_llm_assigned", 0) == 2


# ---------------------------------------------------------------------------
# Test 8: ColumnRolesResponse round-trips through JSON
# ---------------------------------------------------------------------------


def test_column_roles_response_json_roundtrip():
    """ColumnRolesResponse serialises and deserialises correctly."""
    original = ColumnRolesResponse(
        assignments=[
            ColumnRoleAssignment(column_name="col_a", role=ColumnRole.CITATION),
            ColumnRoleAssignment(column_name="col_b", role=ColumnRole.DATE),
        ]
    )
    json_str = original.model_dump_json()
    restored = ColumnRolesResponse.model_validate_json(json_str)
    assert restored == original
    assert restored.assignments[0].role == ColumnRole.CITATION
    assert restored.assignments[1].column_name == "col_b"


# ---------------------------------------------------------------------------
# Test 9: All ColumnRole values accepted in ColumnRoleAssignment
# ---------------------------------------------------------------------------


def test_all_column_role_values_accepted():
    """Every ColumnRole value is valid in a ColumnRoleAssignment."""
    for role in ColumnRole:
        assignment = ColumnRoleAssignment(column_name="test_col", role=role)
        assert assignment.role == role


# ---------------------------------------------------------------------------
# Test 10: _build_user_message includes all null column names
# ---------------------------------------------------------------------------


def test_build_user_message_includes_null_columns():
    """The user message contains all null column names."""
    null_columns = ["mystery_col", "another_unknown"]
    msg = _build_user_message(
        doc_id="DOC1",
        headers=HEADERS,
        provisional_roles=PROVISIONAL,
        null_columns=null_columns,
        sample_rows=SAMPLE_ROWS,
    )

    # All null column names appear in the message
    for col in null_columns:
        assert col in msg

    # Document ID appears
    assert "DOC1" in msg

    # All headers appear
    for col in HEADERS:
        assert col in msg

"""Tests for task 1.3.3: LLM client with structured output and audit log."""
from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import BaseModel

from app.company_ingest.llm.client import call_structured
from app.company_ingest.run_context import RunContext

# All tests in this module are async.
pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class SimpleSchema(BaseModel):
    name: str
    value: int


def _make_ctx(**kwargs) -> RunContext:
    return RunContext(company_id="test_co", **kwargs)


def _valid_json() -> str:
    return json.dumps({"name": "hello", "value": 42})


def _invalid_json() -> str:
    # value is a string, not an int — pydantic will reject it
    return '{"name": "hello", "value": "not-an-int"}'


def _make_rate_limit_error():
    import anthropic

    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    resp = httpx.Response(429, request=req, text="rate limited")
    return anthropic.RateLimitError("rate limited", response=resp, body=None)


# ---------------------------------------------------------------------------
# Test 1: Successful call — returns parsed model instance, called once
# ---------------------------------------------------------------------------


async def test_successful_call(monkeypatch):
    ctx = _make_ctx()

    provider_mock = AsyncMock(return_value=_valid_json())
    monkeypatch.setattr("app.company_ingest.llm.client._call_provider", provider_mock)
    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", AsyncMock())

    result = await call_structured(
        stage="test_stage",
        unit_id="unit-1",
        system="You are a helper.",
        user="Give me a JSON object.",
        schema=SimpleSchema,
        ctx=ctx,
    )

    assert isinstance(result, SimpleSchema)
    assert result.name == "hello"
    assert result.value == 42
    assert len(ctx.issues) == 0
    provider_mock.assert_awaited_once()


# ---------------------------------------------------------------------------
# Test 2: Retry on validation error — first bad, second valid
# ---------------------------------------------------------------------------


async def test_retry_on_validation_error(monkeypatch):
    ctx = _make_ctx()

    call_args: list[tuple[str, str, str]] = []

    async def fake_provider(system: str, user: str, model: str) -> str:
        call_args.append((system, user, model))
        if len(call_args) == 1:
            return _invalid_json()
        return _valid_json()

    monkeypatch.setattr("app.company_ingest.llm.client._call_provider", fake_provider)
    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", AsyncMock())

    result = await call_structured(
        stage="test_stage",
        unit_id="unit-2",
        system="You are a helper.",
        user="Give me a JSON object.",
        schema=SimpleSchema,
        ctx=ctx,
    )

    assert len(call_args) == 2
    assert isinstance(result, SimpleSchema)
    assert result.name == "hello"
    assert result.value == 42
    assert len(ctx.issues) == 0

    # The second call's user prompt must contain the error message.
    _, second_user, _ = call_args[1]
    assert "Your previous response had this error" in second_user


# ---------------------------------------------------------------------------
# Test 3: Double failure — returns None, records issue, called twice
# ---------------------------------------------------------------------------


async def test_double_failure_returns_none(monkeypatch):
    ctx = _make_ctx()

    provider_mock = AsyncMock(return_value=_invalid_json())
    monkeypatch.setattr("app.company_ingest.llm.client._call_provider", provider_mock)
    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", AsyncMock())

    result = await call_structured(
        stage="test_stage",
        unit_id="unit-3",
        system="You are a helper.",
        user="Give me a JSON object.",
        schema=SimpleSchema,
        ctx=ctx,
    )

    assert result is None
    assert provider_mock.await_count == 2

    assert len(ctx.issues) == 1
    issue = ctx.issues[0]
    assert issue.severity == "warning"
    assert issue.code == "llm_validation_failed"
    assert issue.clause_id == "unit-3"


# ---------------------------------------------------------------------------
# Test 4: Replay cache hit — no API call when ctx.rebuild=True and cached
# ---------------------------------------------------------------------------


async def test_replay_cache_hit(monkeypatch):
    ctx = _make_ctx(rebuild=True)

    system = "You are a helper."
    user = "Give me a JSON object."
    prompt_sha256 = hashlib.sha256((system + user).encode()).hexdigest()
    cached_result = SimpleSchema(name="cached", value=99)
    ctx.llm_cache[("test_stage", "unit-4", prompt_sha256)] = cached_result

    provider_mock = AsyncMock()
    monkeypatch.setattr("app.company_ingest.llm.client._call_provider", provider_mock)
    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", AsyncMock())

    result = await call_structured(
        stage="test_stage",
        unit_id="unit-4",
        system=system,
        user=user,
        schema=SimpleSchema,
        ctx=ctx,
    )

    provider_mock.assert_not_called()
    assert isinstance(result, SimpleSchema)
    assert result.name == "cached"
    assert result.value == 99


# ---------------------------------------------------------------------------
# Test 5: Rate limit backoff — error twice then succeeds, correct delays
# ---------------------------------------------------------------------------


async def test_rate_limit_backoff(monkeypatch):
    ctx = _make_ctx()

    rate_limit_err = _make_rate_limit_error()
    call_count = 0

    async def fake_provider(system: str, user: str, model: str) -> str:
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            raise rate_limit_err
        return _valid_json()

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    monkeypatch.setattr("app.company_ingest.llm.client._call_provider", fake_provider)
    monkeypatch.setattr("app.company_ingest.llm.client._sleep", fake_sleep)
    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", AsyncMock())

    result = await call_structured(
        stage="test_stage",
        unit_id="unit-5",
        system="You are a helper.",
        user="Give me a JSON object.",
        schema=SimpleSchema,
        ctx=ctx,
    )

    assert call_count == 3
    # Attempt 0 → sleep 2^0=1s; attempt 1 → sleep 2^1=2s; attempt 2 succeeds.
    assert sleep_calls == [1, 2]
    assert isinstance(result, SimpleSchema)
    assert result.name == "hello"
    assert result.value == 42

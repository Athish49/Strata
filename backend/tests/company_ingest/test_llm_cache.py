"""Task 5.3 — persistent LLM cache in company.llm_extractions.

No database is touched. The migration that adds the cache columns
(f7b2c91d4a08) is NOT applied anywhere, and it TRUNCATEs, so these tests use a
FakeSession that honours the five-column unique key and ON CONFLICT DO NOTHING,
and they assert on the generated SQL.
"""
from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from app.company_ingest.llm.client import call_structured
from app.company_ingest.run_context import RunContext

pytestmark = pytest.mark.asyncio

CONTENT_SHA = "a" * 64
MODEL = "test-model-1"
KEY_COLUMNS = ("company_id", "stage", "content_sha256", "prompt_sha256", "model")


class SimpleSchema(BaseModel):
    name: str
    value: int


class EvolvedSchema(BaseModel):
    """Same stage, stricter shape — a row written for SimpleSchema fails here."""

    name: str
    value: int
    required_later: str


def _valid_json() -> str:
    return json.dumps({"name": "hello", "value": 42})


def _prompt_sha(system: str, user: str) -> str:
    return hashlib.sha256((system + user).encode()).hexdigest()


# ---------------------------------------------------------------------------
# FakeSession — a dict keyed by the five-column cache key
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class FakeSession:
    """Minimal AsyncSession stand-in: SELECT, INSERT ... ON CONFLICT, SAVEPOINT."""

    def __init__(self, *, fail_on: str | None = None):
        self.rows: dict[tuple, dict] = {}
        self.calls: list[tuple[str, dict]] = []
        self.savepoints = 0
        self.fail_on = fail_on  # "select" | "insert" | None

    # -- SAVEPOINT -----------------------------------------------------------
    @asynccontextmanager
    async def _nested(self):
        self.savepoints += 1
        yield self

    def begin_nested(self):
        return self._nested()

    # -- statement execution -------------------------------------------------
    async def execute(self, statement, params=None):
        sql = str(statement)
        params = params or {}
        self.calls.append((sql, params))
        key = tuple(params[c] for c in KEY_COLUMNS)

        if sql.lstrip().upper().startswith("SELECT"):
            if self.fail_on == "select":
                raise RuntimeError("boom: select")
            row = self.rows.get(key)
            return _FakeResult(None if row is None else (row["response"],))

        if self.fail_on == "insert":
            raise RuntimeError("boom: insert")
        # ON CONFLICT DO NOTHING
        self.rows.setdefault(key, dict(params))
        return _FakeResult(None)

    # -- helpers for tests ---------------------------------------------------
    def seed(self, response, *, stage="test_stage", prompt_sha256, company_id="test_co",
             content_sha256=CONTENT_SHA, model=MODEL):
        key = (company_id, stage, content_sha256, prompt_sha256, model)
        self.rows[key] = {"response": response}

    @property
    def selects(self):
        return [c for c in self.calls if c[0].lstrip().upper().startswith("SELECT")]

    @property
    def inserts(self):
        return [c for c in self.calls if "INSERT" in c[0].upper()]


@pytest.fixture
def provider(monkeypatch):
    """Patch the provider and the R2 audit write; return the provider mock."""
    mock = AsyncMock(return_value=_valid_json())
    monkeypatch.setattr("app.company_ingest.llm.client._call_provider", mock)
    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", AsyncMock())
    return mock


async def _call(ctx, session, *, system="sys", user="usr", model=MODEL,
                schema=SimpleSchema, content_sha256=CONTENT_SHA, stage="test_stage",
                unit_id="unit-1"):
    return await call_structured(
        stage, unit_id, system, user, schema, ctx, model=model,
        content_sha256=content_sha256, session=session,
    )


# ---------------------------------------------------------------------------
# Acceptance: one provider call across two different RunContexts
# ---------------------------------------------------------------------------


async def test_two_run_contexts_one_provider_call(provider):
    session = FakeSession()
    ctx_a = RunContext(company_id="test_co")
    ctx_b = RunContext(company_id="test_co")  # different run_id, fresh llm_cache

    first = await _call(ctx_a, session)
    second = await _call(ctx_b, session)

    assert provider.await_count == 1
    assert first == second == SimpleSchema(name="hello", value=42)
    assert ctx_a.stats.get("llm_cache_hit") is None
    assert ctx_a.stats.get("llm_cache_store") == 1
    assert ctx_b.stats.get("llm_cache_hit") == 1
    assert len(session.rows) == 1


async def test_changed_prompt_misses(provider):
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session, system="sys")
    await _call(RunContext(company_id="test_co"), session, system="sys-v2")

    assert provider.await_count == 2
    assert len(session.rows) == 2


async def test_changed_model_misses(provider):
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session, model="model-a")
    await _call(RunContext(company_id="test_co"), session, model="model-b")

    assert provider.await_count == 2
    assert len(session.rows) == 2


async def test_changed_content_sha_misses(provider):
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session, content_sha256="a" * 64)
    await _call(RunContext(company_id="test_co"), session, content_sha256="b" * 64)

    assert provider.await_count == 2
    assert len(session.rows) == 2


async def test_different_company_does_not_share_cache(provider):
    session = FakeSession()
    await _call(RunContext(company_id="co-a"), session)
    await _call(RunContext(company_id="co-b"), session)

    assert provider.await_count == 2
    assert len(session.rows) == 2


async def test_unit_id_is_not_part_of_the_key(provider):
    """Identical clause text under a different clause id still hits."""
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session, unit_id="unit-1")
    ctx = RunContext(company_id="test_co")
    await _call(ctx, session, unit_id="unit-99")

    assert provider.await_count == 1
    assert ctx.stats.get("llm_cache_hit") == 1


# ---------------------------------------------------------------------------
# Never cache errors
# ---------------------------------------------------------------------------


async def test_invalid_output_is_not_cached(monkeypatch):
    monkeypatch.setattr(
        "app.company_ingest.llm.client._call_provider",
        AsyncMock(return_value='{"name": "hello", "value": "not-an-int"}'),
    )
    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", AsyncMock())
    session = FakeSession()
    ctx = RunContext(company_id="test_co")

    assert await _call(ctx, session) is None
    assert session.inserts == []
    assert session.rows == {}
    assert ctx.stats.get("llm_cache_store") is None


async def test_provider_exception_is_not_cached(monkeypatch):
    monkeypatch.setattr(
        "app.company_ingest.llm.client._call_provider",
        AsyncMock(side_effect=RuntimeError("provider down")),
    )
    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", AsyncMock())
    session = FakeSession()

    with pytest.raises(RuntimeError):
        await _call(RunContext(company_id="test_co"), session)

    assert session.inserts == []
    assert session.rows == {}


# ---------------------------------------------------------------------------
# Stale rows are a miss
# ---------------------------------------------------------------------------


async def test_row_failing_schema_validation_is_a_miss(provider):
    session = FakeSession()
    sha = _prompt_sha("sys", "usr")
    session.seed({"name": "hello", "value": 42}, prompt_sha256=sha)
    ctx = RunContext(company_id="test_co")

    result = await _call(ctx, session, schema=EvolvedSchema)

    # The seeded row does not satisfy EvolvedSchema → miss → provider called.
    # The provider's reply is SimpleSchema-shaped, so it also fails EvolvedSchema
    # and the normal retry-once loop runs: two provider calls, no result, no row.
    assert provider.await_count == 2
    assert ctx.stats.get("llm_cache_stale") == 1
    assert ctx.stats.get("llm_cache_hit") is None
    assert result is None
    assert len(session.rows) == 1  # only the seeded row; nothing new cached


async def test_garbage_row_is_a_miss(provider):
    session = FakeSession()
    session.seed("not json at all", prompt_sha256=_prompt_sha("sys", "usr"))
    ctx = RunContext(company_id="test_co")

    assert await _call(ctx, session) == SimpleSchema(name="hello", value=42)
    assert provider.await_count == 1
    assert ctx.stats.get("llm_cache_stale") == 1


async def test_jsonb_returned_as_string_still_hits(provider):
    """Some drivers hand back jsonb as text rather than a dict."""
    session = FakeSession()
    session.seed(_valid_json(), prompt_sha256=_prompt_sha("sys", "usr"))
    ctx = RunContext(company_id="test_co")

    assert await _call(ctx, session) == SimpleSchema(name="hello", value=42)
    assert provider.await_count == 0
    assert ctx.stats.get("llm_cache_hit") == 1


# ---------------------------------------------------------------------------
# Degradation: no session, no hash, DB errors
# ---------------------------------------------------------------------------


async def test_session_none_works_and_touches_no_db(provider):
    ctx = RunContext(company_id="test_co")
    result = await call_structured(
        "test_stage", "unit-1", "sys", "usr", SimpleSchema, ctx,
        content_sha256=CONTENT_SHA, session=None,
    )
    assert result == SimpleSchema(name="hello", value=42)
    assert provider.await_count == 1


async def test_legacy_positional_call_still_works(provider):
    """Existing callers pass no content_sha256 and no session."""
    ctx = RunContext(company_id="test_co")
    result = await call_structured(
        "test_stage", "unit-1", "sys", "usr", SimpleSchema, ctx, MODEL
    )
    assert result == SimpleSchema(name="hello", value=42)


@pytest.mark.parametrize("sha", [None, "", "short", "Z" * 64, "A" * 64])
async def test_missing_or_malformed_content_sha_skips_db(provider, sha):
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session, content_sha256=sha)

    assert session.calls == []
    assert provider.await_count == 1


async def test_empty_company_id_skips_db(provider):
    """RunContext.company_id defaults to '' — never pool tenants under it."""
    session = FakeSession()
    await _call(RunContext(), session)

    assert session.calls == []
    assert provider.await_count == 1


async def test_select_failure_falls_back_to_provider(provider):
    session = FakeSession(fail_on="select")
    ctx = RunContext(company_id="test_co")

    assert await _call(ctx, session) == SimpleSchema(name="hello", value=42)
    assert provider.await_count == 1
    assert ctx.stats.get("llm_cache_error") == 1


async def test_insert_failure_does_not_fail_the_call(provider):
    session = FakeSession(fail_on="insert")
    ctx = RunContext(company_id="test_co")

    assert await _call(ctx, session) == SimpleSchema(name="hello", value=42)
    assert ctx.stats.get("llm_cache_error") == 1


async def test_db_work_runs_inside_a_savepoint(provider):
    """The caller owns the transaction; a cache error must not poison it."""
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session)
    assert session.savepoints == 2  # one SELECT, one INSERT


# ---------------------------------------------------------------------------
# In-memory tier still works and is consulted first
# ---------------------------------------------------------------------------


async def test_in_memory_tier_short_circuits_before_db(provider):
    session = FakeSession()
    ctx = RunContext(company_id="test_co", rebuild=True)
    cached = SimpleSchema(name="from-memory", value=1)
    ctx.llm_cache[("test_stage", "unit-1", _prompt_sha("sys", "usr"))] = cached

    assert await _call(ctx, session) is cached
    assert session.calls == []
    assert provider.await_count == 0


async def test_db_hit_populates_the_in_memory_tier(provider):
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session)
    ctx = RunContext(company_id="test_co")
    await _call(ctx, session)

    assert ctx.llm_cache[("test_stage", "unit-1", _prompt_sha("sys", "usr"))] == (
        SimpleSchema(name="hello", value=42)
    )


# ---------------------------------------------------------------------------
# SQL shape — built against the migration, not an older draft
# ---------------------------------------------------------------------------


async def test_sql_uses_response_column_and_all_five_key_columns(provider):
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session)

    select_sql, select_params = session.selects[0]
    insert_sql, insert_params = session.inserts[0]

    for col in KEY_COLUMNS:
        assert col in select_sql, col
        assert col in insert_sql, col

    # The cache payload lives in the pre-existing `response jsonb` column;
    # the migration deliberately does NOT add `output`.
    assert "SELECT response" in " ".join(select_sql.split())
    assert "response" in insert_sql
    assert "output" not in select_sql
    assert "output" not in insert_sql

    assert "ON CONFLICT" in insert_sql
    assert "DO NOTHING" in " ".join(insert_sql.split()).upper()
    # The conflict target must be the unique index, in its exact column order.
    assert (
        "ON CONFLICT (company_id, stage, content_sha256, prompt_sha256, model)"
        in " ".join(insert_sql.split())
    )
    # jsonb via CAST(... AS jsonb), not ::jsonb (which collides with binds).
    assert "CAST(:response AS jsonb)" in insert_sql
    assert "::jsonb" not in insert_sql


async def test_insert_supplies_every_not_null_column(provider):
    session = FakeSession()
    ctx = RunContext(company_id="test_co")
    await _call(ctx, session)

    _, params = session.inserts[0]
    # All five key columns are NOT NULL: Postgres treats NULLs as distinct in a
    # unique index, so a NULL here would make the cache miss on every lookup.
    for col in KEY_COLUMNS:
        assert params[col], col
    assert params["run_id"] == str(ctx.run_id)
    assert params["unit_id"] == "unit-1"
    assert params["extraction_pk"]
    assert json.loads(params["response"]) == {"name": "hello", "value": 42}
    assert json.loads(params["request"])["schema_name"] == "SimpleSchema"
    assert "valid" not in params  # written as a literal `true`


async def test_insert_marks_the_row_valid_with_no_error(provider):
    session = FakeSession()
    await _call(RunContext(company_id="test_co"), session)
    insert_sql = " ".join(session.inserts[0][0].split())
    assert "true, NULL, now()" in insert_sql


async def test_extraction_pk_is_deterministic_for_one_key(provider):
    session_a, session_b = FakeSession(), FakeSession()
    await _call(RunContext(company_id="test_co"), session_a)
    await _call(RunContext(company_id="test_co"), session_b)
    assert (
        session_a.inserts[0][1]["extraction_pk"]
        == session_b.inserts[0][1]["extraction_pk"]
    )


# ---------------------------------------------------------------------------
# Concurrency: one AsyncSession cannot run two statements at once
# ---------------------------------------------------------------------------


async def test_concurrent_calls_serialise_db_access(provider):
    import asyncio

    class StrictSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.in_flight = 0
            self.max_in_flight = 0

        async def execute(self, statement, params=None):
            self.in_flight += 1
            self.max_in_flight = max(self.max_in_flight, self.in_flight)
            try:
                await asyncio.sleep(0)
                return await super().execute(statement, params)
            finally:
                self.in_flight -= 1

    session = StrictSession()
    await asyncio.gather(*[
        _call(RunContext(company_id="test_co"), session,
              content_sha256=f"{i:064x}", unit_id=f"unit-{i}")
        for i in range(8)
    ])
    assert session.max_in_flight == 1
    assert len(session.rows) == 8


# ---------------------------------------------------------------------------
# Best-effort: failures outside execute() must not break the call either
# ---------------------------------------------------------------------------


async def test_savepoint_failure_does_not_fail_the_call(provider):
    """begin_nested() itself raising (closed/broken session) is a miss + lost write."""

    class BrokenSavepointSession(FakeSession):
        def begin_nested(self):
            raise RuntimeError("boom: savepoint")

    session = BrokenSavepointSession()
    ctx = RunContext(company_id="test_co")

    assert await _call(ctx, session) == SimpleSchema(name="hello", value=42)
    assert provider.await_count == 1
    assert ctx.stats.get("llm_cache_error") == 2  # lookup + store
    assert session.rows == {}


async def test_unusable_session_object_does_not_fail_the_call(provider):
    """A non-weakrefable, non-session object must degrade to no persistence."""
    ctx = RunContext(company_id="test_co")

    assert await _call(ctx, object()) == SimpleSchema(name="hello", value=42)
    assert provider.await_count == 1
    assert ctx.stats.get("llm_cache_error") == 2

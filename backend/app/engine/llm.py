"""Task 1.1.3 - cached, capped, concurrency-limited LLM calls (architecture 5.8).

Cache = engine.llm_calls: a hit is a row with valid=true and the same
(stage, model, prompt_sha256). Every real (miss) call is logged, valid or not.
Each DB operation uses its own short-lived AsyncSession unless one is passed.

Note: company_ingest.llm.client keeps its own global semaphore (8) around the
provider call, so radar concurrency above 8 is only effective if that is raised.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import text

from app.engine.config import LLM_CONCURRENCY, MAX_LLM_CALLS_KB, RADAR_CONCURRENCY

logger = logging.getLogger(__name__)


class LLMBudgetExceeded(RuntimeError):
    """Raised when a run would exceed its LLM call cap."""


@dataclass
class LLMBudget:
    max_calls: int = MAX_LLM_CALLS_KB
    used: int = 0

    def reserve(self) -> None:
        # No await between check and increment, so this is safe across tasks.
        if self.used >= self.max_calls:
            raise LLMBudgetExceeded(
                f"LLM call cap reached ({self.used}/{self.max_calls})"
            )
        self.used += 1


@dataclass
class LLMStats:
    calls_made: int = 0
    cache_hits: int = 0
    invalid: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"calls_made": self.calls_made, "cache_hits": self.cache_hits,
                "invalid": self.invalid}


@dataclass
class LLMContext:
    run_id: uuid.UUID | None = None
    budget: LLMBudget = field(default_factory=LLMBudget)
    stats: LLMStats = field(default_factory=LLMStats)
    _sems: dict[str, asyncio.Semaphore] = field(default_factory=dict, repr=False)

    def semaphore(self, stage: str) -> asyncio.Semaphore:
        if stage not in self._sems:
            n = RADAR_CONCURRENCY if stage == "radar" else LLM_CONCURRENCY
            self._sems[stage] = asyncio.Semaphore(n)
        return self._sems[stage]


# Patchable seams for tests.
async def _default_client(stage, unit_id, system, user, schema, ctx, model):
    from app.company_ingest.llm.client import call_structured

    return await call_structured(stage, unit_id, system, user, schema, ctx, model=model)


_client = _default_client


def _session_factory():
    from app.db import AsyncSessionLocal

    return AsyncSessionLocal


def prompt_sha256(system: str, user: str, schema: type[BaseModel]) -> str:
    schema_json = json.dumps(schema.model_json_schema(), sort_keys=True)
    return hashlib.sha256((system + user + schema_json).encode()).hexdigest()


async def _run_db(session, fn):
    """Run fn(session) on the given session, or on a fresh short-lived one."""
    if session is not None:
        return await fn(session)
    async with _session_factory()() as s:
        return await fn(s)


async def _lookup(session, stage: str, model: str, sha: str) -> dict | None:
    async def op(s):
        r = await s.execute(
            text(
                "SELECT response FROM engine.llm_calls "
                "WHERE stage=:stage AND model=:model AND prompt_sha256=:sha AND valid "
                "ORDER BY created_at DESC LIMIT 1"
            ),
            {"stage": stage, "model": model, "sha": sha},
        )
        row = r.first()
        return None if row is None else row[0]

    return await _run_db(session, op)


async def _log_call(session, **p: Any) -> None:
    async def op(s):
        await s.execute(
            text(
                "INSERT INTO engine.llm_calls (call_id, run_id, stage, model, "
                "prompt_sha256, request, response, valid, error, latency_ms) "
                "VALUES (:call_id, :run_id, :stage, :model, :sha, "
                "CAST(:request AS jsonb), CAST(:response AS jsonb), :valid, :error, :latency)"
            ),
            p,
        )
        await s.commit()

    try:
        await _run_db(session, op)
    except Exception as exc:  # noqa: BLE001 - logging must not kill the run
        logger.warning("engine.llm_calls insert failed: %s", exc)


async def call_cached(
    stage: str,
    model: str,
    system: str,
    user: str,
    schema: type[BaseModel],
    run_id: uuid.UUID | None,
    *,
    llm: LLMContext | None = None,
    session=None,
    unit_id: str = "",
) -> BaseModel | None:
    """Return a validated schema instance, or None if the model output was invalid
    (or the provider call failed); the invalid call is recorded either way.
    Raises LLMBudgetExceeded when the run's call cap is hit. Cache hits do not
    count against the cap."""
    llm = llm or LLMContext(run_id=run_id)
    sha = prompt_sha256(system, user, schema)

    cached = await _lookup(session, stage, model, sha)
    if cached is not None:
        try:
            result = schema.model_validate(cached)
            llm.stats.cache_hits += 1
            return result
        except ValidationError:
            logger.warning("cached llm response no longer validates; re-calling")

    llm.budget.reserve()

    from app.company_ingest.run_context import RunContext

    rc = RunContext(run_id=run_id or uuid.uuid4(), company_id="engine")
    result: BaseModel | None = None
    error: str | None = None
    t0 = time.monotonic()
    async with llm.semaphore(stage):
        try:
            result = await _client(stage, unit_id or sha[:12], system, user, schema, rc, model)
        except Exception as exc:  # noqa: BLE001 - recorded, caller handles None
            error = f"{type(exc).__name__}: {exc}"
    latency = int((time.monotonic() - t0) * 1000)

    llm.stats.calls_made += 1
    if result is None:
        llm.stats.invalid += 1
        if error is None:
            error = "; ".join(i.message for i in rc.issues) or "schema validation failed"

    await _log_call(
        session,
        call_id=str(uuid.uuid4()),
        run_id=str(run_id) if run_id else None,
        stage=stage,
        model=model,
        sha=sha,
        request=json.dumps({"system": system, "user": user, "schema_name": schema.__name__}),
        response=json.dumps(result.model_dump(mode="json")) if result is not None else None,
        valid=result is not None,
        error=error,
        latency=latency,
    )
    return result

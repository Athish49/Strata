"""
run.py — engine orchestrator (architecture.md sections 1 and 3).

Creates the ``engine.runs`` row, builds the inputs, runs Stage 1 and then every later stage
found in the stage registry.  Later stage modules are imported lazily; a missing module is
skipped with a log line, so new stages plug in without editing this file.  A stage module
exposes ``async def run_stage(state: RunState) -> None`` and may add to ``state.stats``.
"""
from __future__ import annotations

import importlib
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from sqlalchemy import text

from app.engine.config import MAX_LLM_CALLS_KB, MAX_LLM_CALLS_WHATIF, engine_settings
from app.engine.delta import Stage1Result, persist_stage1, run_stage1
from app.engine.footprint import Footprint, load_footprint
from app.engine.inputs import (
    build_baseline_inputs,
    build_kb_inputs,
    build_whatif_inputs,
    snapshot_pairs,
)
from app.engine.schemas import ChangeInput

logger = logging.getLogger(__name__)

StageFn = Callable[["RunState"], Awaitable[None]]

# (stage name, module path, only-if-flag); order is the pipeline order after Stage 1.
STAGE_MODULES: list[tuple[str, str, str | None]] = [
    ("characterize", "app.engine.characterize", None),
    ("candidates", "app.engine.candidates", None),
    ("rules", "app.engine.rules", None),
    ("judge", "app.engine.judge", None),
    ("ledger", "app.engine.ledger", None),
    ("radar", "app.engine.radar", "radar"),
]

# Populated lazily by load_stages(): the stage callables that are actually present.
STAGES: list[tuple[str, StageFn]] = []


@dataclass
class LlmContext:
    """Per-run LLM budget shared by the stages (architecture.md section 5, rule 7)."""
    max_calls: int
    calls_made: int = 0

    def reserve(self, n: int = 1) -> bool:
        """Take n calls from the budget; False when the cap would be exceeded."""
        if self.calls_made + n > self.max_calls:
            return False
        self.calls_made += n
        return True


@dataclass
class RunState:
    session_factory: Any
    run_id: str
    kind: str
    inputs: list[ChangeInput]
    footprint: Footprint
    stage1: Stage1Result
    llm: LlmContext
    stats: dict[str, Any] = field(default_factory=dict)
    radar: bool = False
    scenario_id: str | None = None


def load_stages(radar: bool = False) -> list[tuple[str, StageFn]]:
    """Import every later stage module that exists; skip the missing ones with a log line."""
    STAGES.clear()
    for name, module_path, flag in STAGE_MODULES:
        if flag == "radar" and not radar:
            continue
        try:
            mod = importlib.import_module(module_path)
        except ImportError as exc:
            if exc.name != module_path:
                raise  # the stage exists but one of its own imports is broken
            logger.info("stage %s skipped: module %s not available", name, module_path)
            continue
        fn = getattr(mod, "run_stage", None)
        if fn is None:
            logger.info("stage %s skipped: %s has no run_stage()", name, module_path)
            continue
        STAGES.append((name, fn))
    return list(STAGES)


def stage1_run_stats(stage1: Stage1Result) -> dict[str, Any]:
    """Funnel keys of data_model.md section 4 that Stage 1 can fill."""
    results = stage1.results
    by_class: dict[str, int] = {}
    in_fp: dict[str, int] = {}
    for r in results:
        by_class[r.change_class] = by_class.get(r.change_class, 0) + 1
        if r.in_footprint:
            in_fp[r.change_class] = in_fp.get(r.change_class, 0) + 1
    return {
        "raw_changed": len(results),
        "new_sections": by_class.get("new_section", 0),
        "repealed": by_class.get("repealed", 0),
        "by_class": by_class,
        "substantive": by_class.get("substantive", 0),
        "in_footprint": in_fp,
    }


_INSERT_RUN_SQL = text("""
    INSERT INTO engine.runs (run_id, kind, company_id, scenario_id, snapshots, status, models)
    VALUES (CAST(:run_id AS uuid), :kind, :company_id, CAST(:scenario_id AS uuid),
            CAST(:snapshots AS jsonb), 'running', CAST(:models AS jsonb))
""")

_FINISH_RUN_SQL = text("""
    UPDATE engine.runs
    SET status = :status, error = :error, stats = CAST(:stats AS jsonb), finished_at = now()
    WHERE run_id = CAST(:run_id AS uuid)
""")

_SCENARIO_SQL = text("""
    SELECT s1_section_id, edit_kind, edited_text
    FROM engine.whatif_scenarios WHERE scenario_id = CAST(:sid AS uuid)
""")


def _models() -> dict[str, str]:
    return {
        "characterize": engine_settings.ENGINE_CHARACTERIZE_MODEL,
        "judge": engine_settings.ENGINE_JUDGE_MODEL,
        "radar": engine_settings.ENGINE_RADAR_MODEL,
    }


async def _snapshots(session) -> dict[str, dict[str, str]]:
    """{source_system: {"s1": min date, "s2": max date}}; baseline compares S1 with S1."""
    rows = (await session.execute(text(
        "SELECT source_system, MIN(snapshot_date) AS s1, MAX(snapshot_date) AS s2 "
        "FROM public.code_sections GROUP BY source_system ORDER BY source_system"
    ))).mappings().all()
    return {r["source_system"]: {"s1": str(r["s1"]), "s2": str(r["s2"])} for r in rows}


async def run_engine(
    kind: str,
    scenario_id: str | None = None,
    *,
    radar: bool = False,
    run_id: str | None = None,
    session_factory: Any = None,
) -> str:
    """Run the engine once and return the run_id. Failures set status='failed' and re-raise."""
    if kind not in ("kb", "baseline", "whatif"):
        raise ValueError(f"unknown run kind: {kind!r}")
    if kind == "whatif" and not scenario_id:
        raise ValueError("whatif runs need a scenario_id")
    if session_factory is None:
        from app.db import AsyncSessionLocal
        session_factory = AsyncSessionLocal

    run_id = run_id or str(uuid.uuid4())
    t0 = time.monotonic()
    company_id = engine_settings.ENGINE_COMPANY_ID
    stats: dict[str, Any] = {}

    async with session_factory() as session:
        snaps = await _snapshots(session)
        if kind == "baseline":
            snaps = {k: {"s1": v["s1"], "s2": v["s1"]} for k, v in snaps.items()}
        await session.execute(_INSERT_RUN_SQL, {
            "run_id": run_id, "kind": kind, "company_id": company_id,
            "scenario_id": scenario_id, "snapshots": json.dumps(snaps),
            "models": json.dumps(_models()),
        })
        if kind == "whatif":
            await session.execute(text(
                "UPDATE engine.whatif_scenarios SET last_run_id = CAST(:run_id AS uuid) "
                "WHERE scenario_id = CAST(:sid AS uuid)"
            ), {"run_id": run_id, "sid": scenario_id})
        await session.commit()

    llm = LlmContext(MAX_LLM_CALLS_WHATIF if kind == "whatif" else MAX_LLM_CALLS_KB)
    try:
        async with session_factory() as session:
            if kind == "kb":
                inputs = await build_kb_inputs(session)
            elif kind == "baseline":
                inputs = build_baseline_inputs()
            else:
                sc = (await session.execute(_SCENARIO_SQL, {"sid": scenario_id})).mappings().first()
                if sc is None:
                    raise ValueError(f"scenario not found: {scenario_id}")
                inputs = await build_whatif_inputs(session, dict(sc))
            footprint = await load_footprint(session, company_id)
            stage1 = await run_stage1(session, run_id, inputs, footprint)
            await session.rollback()  # read-only so far; end the read transaction

        async with session_factory() as session:
            await persist_stage1(session, run_id, stage1)
            await session.commit()

        stats.update(stage1_run_stats(stage1))
        state = RunState(session_factory, run_id, kind, inputs, footprint, stage1, llm,
                         stats, radar, scenario_id)
        for name, fn in load_stages(radar):
            logger.info("running stage %s", name)
            await fn(state)

        stats["llm_calls"] = llm.calls_made
        stats["duration_s"] = round(time.monotonic() - t0, 2)
        status, error = "done", None
    except Exception as exc:
        logger.exception("engine run %s failed", run_id)
        stats["llm_calls"] = llm.calls_made
        stats["duration_s"] = round(time.monotonic() - t0, 2)
        status, error = "failed", f"{type(exc).__name__}: {exc}"
        await _finish(session_factory, run_id, status, error, stats)
        raise
    await _finish(session_factory, run_id, status, error, stats)
    return run_id


async def _finish(session_factory, run_id: str, status: str, error: str | None, stats: dict) -> None:
    async with session_factory() as session:
        await session.execute(_FINISH_RUN_SQL, {
            "run_id": run_id, "status": status, "error": error,
            "stats": json.dumps(stats, default=str),
        })
        await session.commit()

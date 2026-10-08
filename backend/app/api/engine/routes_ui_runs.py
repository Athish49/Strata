"""UI runs / scenarios / score / what-if section routes (ui_wiring_contract.md 3.1, 3.9-3.11).

Read-only. Mounted under /engine by routes.py. Never 409.
"""
import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.engine import routes_ui_common as ui
from app.api.engine.routes import _all, _j, _one, _uuid
from app.db import get_db
from app.engine import whatif

router = APIRouter(tags=["engine-ui-runs"])

_RUN_SQL = """SELECT r.run_id, r.kind, r.status, r.started_at, r.finished_at, r.scenario_id,
                     r.stats, r.error, s.title AS scenario_title
              FROM engine.runs r LEFT JOIN engine.whatif_scenarios s ON s.scenario_id = r.scenario_id"""

_NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _title(r: dict) -> str:
    if r["kind"] == "kb":
        return "Real wave · S1→S2"
    if r["kind"] == "baseline":
        return "Baseline · S1 vs S1"
    return r.get("scenario_title") or "What-if scenario"


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


async def _map_run(db: AsyncSession, r: dict) -> dict:
    status = ui.map_run_status(r["status"], r["started_at"], r["finished_at"])
    progress = await ui.build_progress(db, str(r["run_id"])) if status == "running" else None
    return {
        "run_id": str(r["run_id"]),
        "kind": r["kind"],
        "title": _title(r),
        "status": status,
        "started_at": r["started_at"],
        "finished_at": r["finished_at"],
        "scenario_id": str(r["scenario_id"]) if r.get("scenario_id") else None,
        "error": r.get("error"),
        "progress": progress,
        "stats": ui.map_stats(_j(r.get("stats"))),
    }


def _ts(r: dict):
    return r["started_at"]


def _collapse(rows: list[dict], preset_run_ids: set[str]) -> list[dict]:
    """rows are started_at DESC. See contract 3.1."""
    keep: list[dict] = []
    seen_done_kb = False
    seen_done_base = False
    latest_done_kb_started = None
    for r in rows:
        if r["kind"] == "kb" and r["status"] == "done":
            latest_done_kb_started = r["started_at"]
            break
    for r in rows:
        k, st = r["kind"], r["status"]
        if k == "kb":
            if st == "done":
                if not seen_done_kb:
                    seen_done_kb = True
                    keep.append(r)
            elif latest_done_kb_started is None or r["started_at"] > latest_done_kb_started:
                keep.append(r)  # running or failed and newer than the latest done kb run
        elif k == "baseline":
            if st == "done" and not seen_done_base:
                seen_done_base = True
                keep.append(r)
        else:
            if str(r["run_id"]) in preset_run_ids or st == "running":
                keep.append(r)
    return keep


@router.get("/ui/runs")
async def ui_list_runs(collapse: bool = Query(True), db: AsyncSession = Depends(get_db)):
    rows = await _all(db, _RUN_SQL + " ORDER BY r.started_at DESC, r.run_id")
    if collapse:
        sc = await _all(db, "SELECT last_run_id FROM engine.whatif_scenarios WHERE last_run_id IS NOT NULL")
        rows = _collapse(rows, {str(x["last_run_id"]) for x in sc})
    return [await _map_run(db, r) for r in rows]


@router.get("/ui/runs/{rid}")
async def ui_get_run(rid: str, db: AsyncSession = Depends(get_db)):
    row = await _one(db, _RUN_SQL + " WHERE r.run_id = CAST(:rid AS uuid)", rid=_uuid(rid))
    if not row:
        raise HTTPException(404, "run not found")
    return await _map_run(db, row)


def _target(targets: Any, key: str, fallback: float) -> float:
    for t in targets if isinstance(targets, list) else []:
        s = str(t.get("target", "")) if isinstance(t, dict) else ""
        if s.lower().startswith(key):
            m = _NUM_RE.search(s)
            if m:
                return float(m.group())
    return fallback


@router.get("/ui/runs/{rid}/score")
async def ui_get_score(rid: str, db: AsyncSession = Depends(get_db)):
    run = await _one(db, _RUN_SQL + " WHERE r.run_id = CAST(:rid AS uuid)", rid=_uuid(rid))
    if not run:
        raise HTTPException(404, "run not found")
    own = await _one(db, "SELECT metrics FROM engine.score_reports WHERE run_id = CAST(:r AS uuid)",
                     r=str(run["run_id"]))
    m = _j(own["metrics"]) if own else None
    if not isinstance(m, dict) or "precision" not in m:  # unscored (baseline reports carry no scorecard)
        return None
    stats = ui.map_stats(_j(run.get("stats")))
    base = await _one(db, """
        SELECT r.stats, s.metrics FROM engine.runs r
        LEFT JOIN engine.score_reports s ON s.run_id = r.run_id
        WHERE r.kind = 'baseline' AND r.status = 'done'
        ORDER BY r.finished_at DESC NULLS LAST, r.started_at DESC LIMIT 1""")
    baseline_findings: Optional[int] = None
    if base:
        bm = _j(base.get("metrics")) or {}
        if bm.get("baseline_check") == "PASS":
            baseline_findings = 0
        else:
            bf = ui.map_stats(_j(base.get("stats")))["findings_by_verdict"]
            baseline_findings = sum(v for k, v in bf.items() if k != "info")
    targets = m.get("targets")
    per_doc = m.get("per_doc")
    doc_agreement = None
    if isinstance(per_doc, list) and per_doc:
        docs = [d for d in per_doc if isinstance(d, dict)]
        doc_agreement = {"agree": sum(1 for d in docs if d.get("system") == d.get("expected")),
                         "total": len(docs)}
    return {
        "precision": _f(m.get("precision")),
        "recall": _f(m.get("recall")),
        "fp_rate_must_not_flag": _f(m.get("fp_rate_must_not_flag")),
        "routing_accuracy": _f(m.get("routing_accuracy")),
        "targets": {
            "precision": _target(targets, "precision", 0.80),
            "recall": _target(targets, "recall", 0.83),
            "fp_rate": _target(targets, "fp", 0.0),
            "routing": _target(targets, "routing", 0.80),
        },
        "baseline_findings": baseline_findings,
        "doc_agreement": doc_agreement,
        "decided_by": stats["decided_by"],
        "llm_calls": stats["llm_calls"],
    }


@router.get("/ui/scenarios")
async def ui_list_scenarios(db: AsyncSession = Depends(get_db)):
    rows = await _all(db, """
        SELECT scenario_id, title, citation, source_system, edit_kind, edited_text, is_preset, last_run_id
        FROM engine.whatif_scenarios ORDER BY is_preset DESC, created_at DESC, scenario_id""")
    return [{
        "scenario_id": str(r["scenario_id"]), "title": r["title"], "citation": r["citation"],
        "source_system": r["source_system"], "edit_kind": r["edit_kind"],
        "edited_text": r["edited_text"], "is_preset": bool(r["is_preset"]),
        "last_run_id": str(r["last_run_id"]) if r["last_run_id"] else None,
    } for r in rows]


@router.get("/ui/whatif/sections")
async def ui_whatif_sections(db: AsyncSession = Depends(get_db)):
    secs = await whatif.list_editable_sections(db)
    if not secs:
        return []
    ids = sorted({int(s["s1_section_id"]) for s in secs})
    ss = {r["id"]: r["source_system"] for r in await _all(
        db, "SELECT id, source_system FROM public.code_sections WHERE id = ANY(:ids)", ids=ids)}
    return [{
        "citation": s["citation"],
        "source_system": ss.get(s["s1_section_id"]) or ("cfr" if "CFR" in s["citation"] else "iac"),
        "heading": ui.clean_heading(s["citation"], s["heading"]),
        "cited_clause_count": int(s["cited_clause_count"]),
        "s1_section_id": int(s["s1_section_id"]),
    } for s in secs]


@router.get("/ui/whatif/sections/{s1_section_id}")
async def ui_whatif_section(s1_section_id: int, db: AsyncSession = Depends(get_db)):
    sec = await whatif.get_section(db, s1_section_id)
    if sec is None:
        raise HTTPException(404, "section not found")
    return {"citation": sec["citation"], "heading": ui.clean_heading(sec["citation"], sec["heading"]),
            "s1_text": sec["s1_text"]}

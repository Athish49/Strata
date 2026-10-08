"""Engine API (api_ui.md section 1), prefix /engine.

This module owns the run/result routes and exposes the aggregate `router`. The what-if,
radar and review/people routes live in their own router files (routes_whatif.py,
routes_radar.py, routes_reviews.py) and are mounted at the bottom when present.
engine.llm_calls is never exposed.
"""
import importlib
import json
import re
import uuid
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.engine.quotes import locate_quote
from app.engine.schemas import (
    ChangeDetail, DocumentDetail, DocumentRollup, EvidenceCard, LedgerRow,
    RunCreate, RunCreated, RunDetail, RunSummary, Scorecard,
)

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")  # same tokenization as engine.diffing

router = APIRouter(prefix="/engine", tags=["engine"])

VERDICT_GROUPS = ("action_required", "optional_relaxed", "update_citation", "review", "info")
_SEV_ORDER = "CASE f.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END"


# ---- helpers ----
async def _all(db: AsyncSession, sql: str, **params) -> list[dict]:
    res = await db.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


async def _one(db: AsyncSession, sql: str, **params) -> Optional[dict]:
    rows = await _all(db, sql, **params)
    return rows[0] if rows else None


def _j(v: Any) -> Any:
    """jsonb values normally arrive parsed; tolerate raw strings."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def _uuid(value: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except ValueError:
        raise HTTPException(404, "not found")


def _run_summary(r: dict) -> dict:
    return {
        "run_id": str(r["run_id"]), "kind": r["kind"], "status": r["status"],
        "started_at": r.get("started_at"), "finished_at": r.get("finished_at"),
        "scenario_title": r.get("scenario_title"),
    }


_RUN_SQL = """SELECT r.run_id, r.kind, r.status, r.started_at, r.finished_at, r.company_id,
                      r.stats, r.error, s.title AS scenario_title
              FROM engine.runs r LEFT JOIN engine.whatif_scenarios s ON s.scenario_id = r.scenario_id"""


async def _get_run(db: AsyncSession, run_id: Optional[str], *, require_done: bool = True) -> dict:
    """Resolve a run: omitted -> latest done kb run. 404 unknown, 409 still running."""
    if run_id is None:
        run = await _one(db, _RUN_SQL + " WHERE r.kind = 'kb' AND r.status = 'done' "
                                        "ORDER BY r.finished_at DESC NULLS LAST, r.started_at DESC LIMIT 1")
        if not run:
            raise HTTPException(404, "no completed kb run")
        return run
    run = await _one(db, _RUN_SQL + " WHERE r.run_id = CAST(:rid AS uuid)", rid=_uuid(run_id))
    if not run:
        raise HTTPException(404, "run not found")
    if require_done and run["status"] == "running":
        raise HTTPException(409, "run is still running")
    return run


async def _people(db: AsyncSession, company_id: str, ids: list[Optional[str]]) -> dict[str, dict]:
    ids = [i for i in set(ids) if i]
    if not ids:
        return {}
    rows = await _all(db, "SELECT person_id, name, title FROM company.people "
                          "WHERE company_id = :c AND person_id = ANY(:ids)", c=company_id, ids=ids)
    return {r["person_id"]: r for r in rows}


def _short(s: Optional[str], n: int = 220) -> str:
    s = " ".join((s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _span(quote: Any, text_: Optional[str]) -> Optional[tuple[int, int]]:
    if not isinstance(quote, str) or not text_:
        return None
    return locate_quote(quote, text_)


def _diff_span(quote: Any, text_: Optional[str]) -> Optional[tuple[int, int]]:
    """Quote span re-expressed in the coordinates of the diff view (tokens joined by single
    spaces, as in diff_segments), so the UI can map it straight onto the segments."""
    sp = _span(quote, text_)
    if not sp or not text_:
        return sp
    start = end = None
    off = 0
    for m in _TOKEN_RE.finditer(text_):
        t_start, t_end = off, off + len(m.group())
        if m.end() > sp[0] and m.start() < sp[1]:
            start = t_start if start is None else start
            end = t_end
        off = t_end + 1
    return (start, end) if start is not None else None


# ---- runs ----
async def _run_in_background(kind: str, run_id: str) -> None:
    mod = importlib.import_module("app.engine.run")  # lazy: module may not exist yet
    await mod.run_engine(kind=kind, run_id=run_id)


@router.post("/runs", response_model=RunCreated)
async def start_run(body: RunCreate, background: BackgroundTasks):
    try:
        importlib.import_module("app.engine.run")
    except ImportError:
        raise HTTPException(503, "engine runner unavailable")
    run_id = str(uuid.uuid4())
    background.add_task(_run_in_background, body.kind, run_id)
    return RunCreated(run_id=run_id)


@router.get("/runs", response_model=list[RunSummary])
async def list_runs(kind: Optional[str] = Query(None), db: AsyncSession = Depends(get_db)):
    rows = await _all(db, _RUN_SQL + " WHERE (CAST(:k AS text) IS NULL OR r.kind = :k) "
                                     "ORDER BY r.started_at DESC", k=kind)
    return [_run_summary(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await _get_run(db, run_id, require_done=False)  # status endpoint: usable while running
    return {"run": _run_summary(run), "stats": _j(run.get("stats")) or {}}


# ---- documents ----
@router.get("/runs/{run_id}/documents", response_model=list[DocumentRollup])
async def list_documents(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await _get_run(db, run_id)
    rows = await _all(db, """
        SELECT d.run_id, d.doc_id, d.status, d.counts, d.changes_considered, d.reason,
               cd.title, cd.vertical, p.name AS owner_name, v.approved_date,
               (SELECT count(DISTINCT f.finding_id) FROM engine.findings f
                 WHERE f.run_id = d.run_id AND f.doc_id = d.doc_id
                   AND EXISTS (SELECT 1 FROM engine.finding_reviews r WHERE r.finding_id = f.finding_id)) AS reviewed
        FROM engine.doc_rollups d
        LEFT JOIN company.company_documents cd ON cd.company_id = :c AND cd.doc_id = d.doc_id
        LEFT JOIN company.people p ON p.company_id = :c AND p.person_id = cd.owner_id
        LEFT JOIN company.document_versions v ON v.version_id = cd.current_version_id
        WHERE d.run_id = CAST(:rid AS uuid)
        ORDER BY (d.status = 'flagged') DESC, d.doc_id""", c=run["company_id"], rid=str(run["run_id"]))
    return [{**r, "run_id": str(r["run_id"]), "counts": _j(r["counts"]) or {},
             "changes_considered": _j(r["changes_considered"]) or []} for r in rows]


@router.get("/runs/{run_id}/documents/{doc_id}", response_model=DocumentDetail)
async def get_document(run_id: str, doc_id: str, db: AsyncSession = Depends(get_db)):
    run = await _get_run(db, run_id)
    rid = str(run["run_id"])
    rollup = await _one(db, "SELECT run_id, doc_id, status, counts, changes_considered, reason "
                            "FROM engine.doc_rollups WHERE run_id = CAST(:rid AS uuid) AND doc_id = :d",
                        rid=rid, d=doc_id)
    if not rollup:
        raise HTTPException(404, "document not in run")
    doc = await _one(db, """
        SELECT cd.doc_id, cd.title, cd.doc_class, cd.vertical, cd.owner_id, cd.reviewer_id, cd.approver_id,
               p.name AS owner_name, v.version, v.approved_date, v.effective_date
        FROM company.company_documents cd
        LEFT JOIN company.people p ON p.company_id = cd.company_id AND p.person_id = cd.owner_id
        LEFT JOIN company.document_versions v ON v.version_id = cd.current_version_id
        WHERE cd.company_id = :c AND cd.doc_id = :d""", c=run["company_id"], d=doc_id) or {"doc_id": doc_id}
    rollup = {**rollup, "run_id": str(rollup["run_id"]), "counts": _j(rollup["counts"]) or {},
              "changes_considered": _j(rollup["changes_considered"]) or [],
              "title": doc.get("title"), "vertical": doc.get("vertical"),
              "owner_name": doc.get("owner_name"), "approved_date": doc.get("approved_date")}
    frows = await _all(db, f"""
        SELECT f.finding_id, f.clause_id, f.citation, f.finding_type, f.verdict, f.severity, f.rationale,
               c.heading_path
        FROM engine.findings f LEFT JOIN company.clauses c ON c.clause_pk = f.clause_pk
        WHERE f.run_id = CAST(:rid AS uuid) AND f.doc_id = :d
        ORDER BY {_SEV_ORDER}, f.clause_id""", rid=rid, d=doc_id)
    groups: dict[str, list] = {g: [] for g in VERDICT_GROUPS}
    for r in frows:
        groups.setdefault(r["verdict"], []).append({
            "finding_id": str(r["finding_id"]), "clause_id": r["clause_id"],
            "heading_path": r["heading_path"], "citation": r["citation"],
            "finding_type": r["finding_type"], "verdict": r["verdict"], "severity": r["severity"],
            "short_rationale": _short(r["rationale"])})
    reviewed = await _one(db, """
        SELECT count(*) AS n FROM engine.findings f
        WHERE f.run_id = CAST(:rid AS uuid) AND f.doc_id = :d
          AND EXISTS (SELECT 1 FROM engine.finding_reviews r WHERE r.finding_id = f.finding_id)""",
                          rid=rid, d=doc_id)
    doc = {**doc, "reviewed": int(reviewed["n"]) if reviewed else 0}
    cleared = await _all(db, """
        SELECT k.clause_id, k.cited_citation AS citation, k.skip_reason, k.rationale, ch.change_class
        FROM engine.candidates k JOIN engine.change_records ch ON ch.change_id = k.change_id
        WHERE k.run_id = CAST(:rid AS uuid) AND k.doc_id = :d
          AND (k.skip_reason IS NOT NULL OR k.affected = false)
          AND NOT EXISTS (SELECT 1 FROM engine.findings f WHERE f.candidate_id = k.candidate_id)
        ORDER BY k.clause_id, ch.citation""", rid=rid, d=doc_id)
    return {"doc": doc, "rollup": rollup, "groups": groups, "cleared": cleared}


# ---- evidence card ----
@router.get("/findings/{finding_id}", response_model=EvidenceCard)
async def get_finding(finding_id: str, db: AsyncSession = Depends(get_db)):
    fid = _uuid(finding_id)
    f = await _one(db, "SELECT * FROM engine.findings WHERE finding_id = CAST(:f AS uuid)", f=fid)
    if not f:
        raise HTTPException(404, "finding not found")
    run = await _get_run(db, str(f["run_id"]))  # 409 while running
    ch = await _one(db, "SELECT * FROM engine.change_records WHERE change_id = :c", c=f["change_id"])
    if not ch:
        raise HTTPException(404, "change not found")
    cl = await _one(db, """
        SELECT c.clause_id, c.heading_path, c.text_raw, cd.title AS doc_title
        FROM company.clauses c
        LEFT JOIN company.company_documents cd ON cd.company_id = :co AND cd.doc_id = c.doc_id
        WHERE c.clause_pk = :pk""", co=run["company_id"], pk=f["clause_pk"]) or {
        "clause_id": f["clause_id"], "heading_path": None, "text_raw": "", "doc_title": None}
    cand = await _one(db, "SELECT path_detail FROM engine.candidates WHERE candidate_id = :c",
                      c=f["candidate_id"])
    quotes = _j(f["quotes"]) or {}
    people = await _people(db, run["company_id"], [f["route_owner"], f["route_reviewer"], f["route_approver"]])
    reviews = await _all(db, "SELECT action, note, person_id, created_at FROM engine.finding_reviews "
                             "WHERE finding_id = :f ORDER BY created_at", f=f["finding_id"])
    also = await _all(db, """
        SELECT finding_id, doc_id, clause_id, verdict FROM engine.findings
        WHERE change_id = :c AND finding_id <> :f ORDER BY doc_id, clause_id""",
                      c=f["change_id"], f=f["finding_id"])
    prop = None
    if f["propagated_from"]:
        prop = await _one(db, "SELECT finding_id, clause_id FROM engine.findings WHERE finding_id = :p",
                          p=f["propagated_from"])
    return {
        "finding": {
            "finding_id": str(f["finding_id"]), "clause_id": f["clause_id"], "doc_id": f["doc_id"],
            "citation": f["citation"], "finding_type": f["finding_type"], "verdict": f["verdict"],
            "severity": f["severity"], "needs_review": f["needs_review"],
            "required_change": _j(f["required_change"]),
            "rationale": f["rationale"],
            "confidence": float(f["confidence"]) if f["confidence"] is not None else None,
            "decided_by": f["decided_by"], "match_path": f["match_path"],
            "quotes_verified": f["quotes_verified"],
            "route": {"owner": people.get(f["route_owner"]), "reviewer": people.get(f["route_reviewer"]),
                      "approver": people.get(f["route_approver"])},
            "reviews": reviews},
        "change": {
            "change_id": str(ch["change_id"]), "citation": ch["citation"], "heading": ch["heading"],
            "change_class": ch["change_class"], "summary": ch["summary"], "direction": ch["direction"],
            "value_changes": _j(ch["value_changes"]), "published_date": ch["published_date"],
            "date_basis": ch["date_basis"], "din": ch["din"], "amendment_source": ch["amendment_source"],
            "origin": ch["origin"], "diff_segments": _j(ch["diff_segments"]),
            "s1_quote_span": _diff_span(quotes.get("s1"), ch["s1_text_norm"]),
            "s2_quote_span": _diff_span(quotes.get("s2"), ch["s2_text_norm"])},
        "clause": {
            "clause_id": cl["clause_id"], "doc_title": cl["doc_title"], "heading_path": cl["heading_path"],
            "text_raw": cl["text_raw"] or "", "quote_span": _span(quotes.get("clause"), cl["text_raw"])},
        "path": _j(cand["path_detail"]) if cand else [],
        "also_affected": [{**a, "finding_id": str(a["finding_id"])} for a in also],
        "propagated_from": ({"finding_id": str(prop["finding_id"]), "clause_id": prop["clause_id"]}
                            if prop else None),
    }


# ---- ledger / changes ----
@router.get("/runs/{run_id}/ledger", response_model=list[LedgerRow])
async def get_ledger(run_id: str, in_footprint: Optional[bool] = Query(None),
                     change_class: Optional[str] = Query(None), disposition: Optional[str] = Query(None),
                     db: AsyncSession = Depends(get_db)):
    run = await _get_run(db, run_id)
    rows = await _all(db, """
        SELECT ch.change_id, ch.citation, ch.heading, ch.change_class, ch.in_footprint,
               ch.cited_clause_count, ch.disposition, ch.disposition_reason, ch.published_date,
               (SELECT count(*) FROM engine.findings f WHERE f.change_id = ch.change_id) AS n_findings,
               (SELECT count(*) FROM engine.candidates k WHERE k.change_id = ch.change_id
                  AND (k.skip_reason IS NOT NULL OR k.affected = false)
                  AND NOT EXISTS (SELECT 1 FROM engine.findings f WHERE f.candidate_id = k.candidate_id)
               ) AS n_cleared
        FROM engine.change_records ch
        WHERE ch.run_id = CAST(:rid AS uuid)
          AND (CAST(:inf AS boolean) IS NULL OR ch.in_footprint = CAST(:inf AS boolean))
          AND (CAST(:cc AS text) IS NULL OR ch.change_class = :cc)
          AND (CAST(:disp AS text) IS NULL OR ch.disposition = :disp)
        ORDER BY ch.in_footprint DESC, (ch.change_class = 'substantive') DESC, ch.citation""",
                      rid=str(run["run_id"]), inf=in_footprint, cc=change_class, disp=disposition)
    return [{**r, "change_id": str(r["change_id"])} for r in rows]


@router.get("/changes/{change_id}", response_model=ChangeDetail)
async def get_change(change_id: str, db: AsyncSession = Depends(get_db)):
    ch = await _one(db, "SELECT * FROM engine.change_records WHERE change_id = CAST(:c AS uuid)",
                    c=_uuid(change_id))
    if not ch:
        raise HTTPException(404, "change not found")
    await _get_run(db, str(ch["run_id"]))  # 409 while running
    cands = await _all(db, """
        SELECT k.candidate_id, k.clause_id, k.doc_id, k.cited_citation, k.match_path, k.path_detail,
               k.judged_by, k.skip_reason, k.affected, k.rationale, f.finding_id, f.verdict
        FROM engine.candidates k LEFT JOIN engine.findings f ON f.candidate_id = k.candidate_id
        WHERE k.change_id = :c ORDER BY k.doc_id, k.clause_id""", c=ch["change_id"])
    return {
        "change_id": str(ch["change_id"]), "citation": ch["citation"], "heading": ch["heading"],
        "change_class": ch["change_class"], "diff_segments": _j(ch["diff_segments"]),
        "summary": ch["summary"], "value_changes": _j(ch["value_changes"]),
        "candidates": [{**k, "candidate_id": str(k["candidate_id"]), "path_detail": _j(k["path_detail"]) or [],
                        "finding_id": str(k["finding_id"]) if k["finding_id"] else None} for k in cands]}


# ---- scorecard ----
@router.get("/runs/{run_id}/scorecard", response_model=Scorecard)
async def get_scorecard(run_id: str, db: AsyncSession = Depends(get_db)):
    run = await _get_run(db, run_id)
    rid = str(run["run_id"])
    own = await _one(db, "SELECT metrics FROM engine.score_reports WHERE run_id = CAST(:r AS uuid)", r=rid)
    base = await _one(db, """
        SELECT s.metrics FROM engine.score_reports s JOIN engine.runs r ON r.run_id = s.run_id
        WHERE r.kind = 'baseline' AND r.status = 'done'
        ORDER BY r.finished_at DESC NULLS LAST, r.started_at DESC LIMIT 1""")
    return {"run_id": rid, "metrics": _j(own["metrics"]) if own else None,
            "baseline": _j(base["metrics"]) if base else None}


# ---- later waves: whatif / radar / reviews+people (separate router files) ----
for _name in ("routes_whatif", "routes_radar", "routes_reviews", "routes_ui_runs", "routes_ui_results", "routes_ui_kb"):
    try:
        router.include_router(importlib.import_module(f"app.api.engine.{_name}").router)
    except ModuleNotFoundError as _e:
        if _e.name != f"app.api.engine.{_name}":
            raise

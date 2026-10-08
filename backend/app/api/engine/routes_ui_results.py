"""Result endpoints for the UI (ui_wiring_contract.md sections 3.2-3.8): GET /engine/ui/...

Read-only. Response JSON mirrors the frontend zod schemas (changeRecord, candidate, finding,
docRollup, annotation, matrixCell, radarItem). Everything is fetched with joins / IN-lists and
assembled in Python (no N+1). Mounted under /engine by routes.py.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.engine.routes import _all, _j, _one, _uuid
from app.api.engine.routes_ui_common import (
    NOISE_CLASSES,
    VERDICT_RANK,
    build_path_nodes,
    clean_heading,
    cleared_reason_text,
    map_direction,
    resolve_run,
)
from app.db import get_db
from app.engine.quotes import locate_quote

router = APIRouter(tags=["engine-ui"])

_CLASS_ORDER = ("CASE ch.change_class WHEN 'substantive' THEN 0 WHEN 'repealed' THEN 1 "
                "WHEN 'renumbered' THEN 2 WHEN 'new_section' THEN 3 ELSE 4 END")
_SEV_ORDER = "CASE f.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END"
_ZERO_VERDICTS = {v: 0 for v in VERDICT_RANK}


# ------------------------------------------------------------------ small helpers
def _s(v: Any) -> str:
    return "" if v is None else str(v)


def _title_number(cs_title: Optional[str], citation: str) -> str:
    if cs_title:
        return str(cs_title)
    m = re.match(r"\s*(\d+)", citation or "")
    return m.group(1) if m else ""


def _characterization(r: dict) -> Optional[dict]:
    if r.get("direction") is None:
        return None
    vcs = []
    for vc in _j(r.get("value_changes")) or []:
        if not isinstance(vc, dict):
            continue
        old = vc.get("old_value_text")
        new = vc.get("new_value_text")
        if old is None and vc.get("old_value_num") is not None:
            old = vc.get("old_value_num")
        if new is None and vc.get("new_value_num") is not None:
            new = vc.get("new_value_num")
        vcs.append({"label": _s(vc.get("subject")), "old": _s(old), "new": _s(new), "unit": vc.get("unit")})
    return {"obligation_changed": bool(r.get("obligation_changed")),
            "direction": map_direction(r["direction"]), "summary": _s(r.get("summary")),
            "value_changes": vcs}


_CHANGE_COLS = """
    ch.change_id, ch.citation, ch.heading, ch.source_system, ch.rule_key, ch.change_class,
    ch.published_date, ch.date_basis, ch.din, ch.in_footprint, ch.cited_clause_count,
    ch.obligation_changed, ch.direction, ch.summary, ch.value_changes,
    ch.disposition, ch.disposition_reason,
    cs.agency_id, cs.title_number, c1.snapshot_date AS s1_date, c2.snapshot_date AS s2_date"""
_CHANGE_FROM = """
    FROM engine.change_records ch
    LEFT JOIN public.code_sections cs ON cs.id = COALESCE(ch.s2_section_id, ch.s1_section_id)
    LEFT JOIN public.code_sections c1 ON c1.id = ch.s1_section_id
    LEFT JOIN public.code_sections c2 ON c2.id = ch.s2_section_id"""


def _change_json(r: dict, snaps: dict, full: bool) -> dict:
    ss = r["source_system"]
    sn = snaps.get(ss) if isinstance(snaps.get(ss), dict) else {}
    diff: list = []
    s1 = s2 = ""
    if full:
        s1, s2 = _s(r.get("s1_text_norm")), _s(r.get("s2_text_norm"))
        diff = _j(r.get("diff_segments"))
        if not isinstance(diff, list):
            diff = []
        if not diff:
            if s2 and not s1:
                diff = [{"op": "insert", "text": s2}]
            elif s1 and not s2:
                diff = [{"op": "delete", "text": s1}]
    return {
        "change_id": str(r["change_id"]),
        "citation": r["citation"],
        "heading": clean_heading(r["citation"], r.get("heading")),
        "source_system": ss,
        "rule_key": _s(r.get("rule_key")),
        "agency_id": _s(r.get("agency_id")),
        "title_number": _title_number(r.get("title_number"), r["citation"]),
        "change_class": r["change_class"],
        "diff_segments": diff,
        "s1_text": s1,
        "s2_text": s2,
        "published_date": r.get("published_date"),
        "date_basis": r.get("date_basis"),
        "din": r.get("din"),
        "s1_snapshot": str(r["s1_date"]) if r.get("s1_date") else _s(sn.get("s1")),
        "s2_snapshot": str(r["s2_date"]) if r.get("s2_date") else _s(sn.get("s2")),
        "in_footprint": bool(r["in_footprint"]),
        "cited_clause_count": int(r.get("cited_clause_count") or 0),
        "characterization": _characterization(r),
        "disposition": r.get("disposition"),
        "disposition_reason": r.get("disposition_reason"),
    }


async def _run_snapshots(db: AsyncSession, run_id: str) -> dict:
    r = await _one(db, "SELECT snapshots FROM engine.runs WHERE run_id = CAST(:r AS uuid)", r=run_id)
    snaps = _j(r["snapshots"]) if r else None
    return snaps if isinstance(snaps, dict) else {}


async def _light_changes(db: AsyncSession, rid: str, where: str = "") -> list[dict]:
    rows = await _all(db, f"""
        SELECT {_CHANGE_COLS} {_CHANGE_FROM}
        WHERE ch.run_id = CAST(:rid AS uuid) {where}
        ORDER BY ch.in_footprint DESC, {_CLASS_ORDER}, ch.citation, ch.change_id""", rid=rid)
    snaps = await _run_snapshots(db, rid)
    return [_change_json(r, snaps, False) for r in rows]


# ------------------------------------------------------------------ changes
@router.get("/ui/runs/{rid}/changes")
async def ui_list_changes(rid: str, db: AsyncSession = Depends(get_db)):
    run = await resolve_run(db, rid)
    return await _light_changes(db, str(run["run_id"]))


@router.get("/ui/runs/{rid}/changes/{change_id}")
async def ui_get_change(rid: str, change_id: str, db: AsyncSession = Depends(get_db)):
    run = await resolve_run(db, rid)
    run_id = str(run["run_id"])
    r = await _one(db, f"""
        SELECT {_CHANGE_COLS}, ch.s1_text_norm, ch.s2_text_norm, ch.diff_segments {_CHANGE_FROM}
        WHERE ch.run_id = CAST(:rid AS uuid) AND ch.change_id = CAST(:cid AS uuid)""",
                   rid=run_id, cid=_uuid(change_id))
    if not r:
        raise HTTPException(404, "change not found")
    return _change_json(r, await _run_snapshots(db, run_id), True)


# ------------------------------------------------------------------ candidates
async def _via_rows(db: AsyncSession, company_id: str, details: list) -> dict[str, dict]:
    ids = set()
    for pd in details:
        for st in pd or []:
            if isinstance(st, dict) and st.get("via_clause_id"):
                ids.add(st["via_clause_id"])
    if not ids:
        return {}
    rows = await _all(db, """
        SELECT DISTINCT ON (clause_id) clause_id, doc_id, unit_kind FROM company.clauses
        WHERE company_id = :co AND clause_id = ANY(:ids) ORDER BY clause_id, ordinal""",
                      co=company_id, ids=list(ids))
    return {r["clause_id"]: r for r in rows}


def _path(r: dict, pd: Any, via: dict[str, dict]) -> list[dict]:
    steps = pd if isinstance(pd, list) else []
    mp = r.get("match_path")
    step = next((s for s in steps if isinstance(s, dict) and s.get("path") == mp),
                steps[0] if steps else None)
    vrow = via.get(step.get("via_clause_id")) if isinstance(step, dict) else None
    clause = {"clause_id": r["clause_id"], "doc_id": r["doc_id"], "heading_path": r.get("heading_path") or []}
    return build_path_nodes(steps, mp, r["citation"], r.get("heading"), clause, vrow)


@router.get("/ui/runs/{rid}/candidates")
async def ui_list_candidates(rid: str, change_id: Optional[str] = Query(None), doc_id: Optional[str] = Query(None),
                             db: AsyncSession = Depends(get_db)):
    run = await resolve_run(db, rid)
    run_id = str(run["run_id"])
    cid = _uuid(change_id) if change_id else None
    rows = await _all(db, """
        SELECT k.candidate_id, k.change_id, k.clause_id, k.doc_id, k.match_path, k.path_detail,
               k.skip_reason, k.rationale, ch.citation, ch.heading, cl.heading_path
        FROM engine.candidates k
        JOIN engine.change_records ch ON ch.change_id = k.change_id
        LEFT JOIN company.clauses cl ON cl.clause_pk = k.clause_pk
        WHERE k.run_id = CAST(:rid AS uuid)
          AND (CAST(:cid AS uuid) IS NULL OR k.change_id = CAST(:cid AS uuid))
          AND (CAST(:doc AS text) IS NULL OR k.doc_id = :doc)
        ORDER BY k.doc_id, k.clause_id, ch.citation, k.candidate_id""", rid=run_id, cid=cid, doc=doc_id)
    fmap = {r["candidate_id"]: str(r["finding_id"]) for r in await _all(db, """
        SELECT candidate_id, finding_id FROM engine.findings
        WHERE run_id = CAST(:rid AS uuid) AND candidate_id IS NOT NULL ORDER BY created_at DESC""", rid=run_id)}
    via = await _via_rows(db, run["company_id"], [_j(r["path_detail"]) for r in rows])
    out = []
    for r in rows:
        fid = fmap.get(r["candidate_id"])
        sr = r["skip_reason"]
        out.append({
            "candidate_id": str(r["candidate_id"]), "run_id": run_id, "change_id": str(r["change_id"]),
            "clause_id": r["clause_id"], "doc_id": r["doc_id"], "match_path": r["match_path"],
            "path_detail": _path(r, _j(r["path_detail"]), via),
            "outcome": "affected" if fid else "cleared",
            "skip_reason": None if (sr is None or sr.startswith("noise:")) else sr,
            "rationale": r["rationale"], "finding_id": fid})
    return out


# ------------------------------------------------------------------ findings
def _quote(q: Any, text_: Optional[str]) -> dict:
    if not isinstance(q, str) or not q:
        return {"text": "", "span": None}
    sp = locate_quote(q, text_ or "")
    return {"text": q, "span": list(sp) if sp else None}


async def _load_findings(db: AsyncSession, run: dict, where: str, params: dict) -> list[dict]:
    co = run["company_id"]
    rows = await _all(db, f"""
        SELECT f.finding_id, f.run_id, f.change_id, f.clause_id, f.doc_id, f.citation, f.finding_type,
               f.verdict, f.severity, f.confidence, f.decided_by, f.required_change, f.quotes,
               f.quotes_verified, f.rationale, f.match_path, f.propagated_from,
               f.route_owner, f.route_reviewer, f.route_approver,
               ch.heading, ch.s1_text_norm, ch.s2_text_norm, ch.published_date AS rule_pub,
               k.path_detail, cl.heading_path, cl.text_raw, v.approved_date
        FROM engine.findings f
        JOIN engine.change_records ch ON ch.change_id = f.change_id
        LEFT JOIN engine.candidates k ON k.candidate_id = f.candidate_id
        LEFT JOIN company.clauses cl ON cl.clause_pk = f.clause_pk
        LEFT JOIN company.company_documents cd ON cd.company_id = :co AND cd.doc_id = f.doc_id
        LEFT JOIN company.document_versions v ON v.version_id = cd.current_version_id
        WHERE {where}
        ORDER BY {_SEV_ORDER}, f.doc_id, f.clause_id, f.finding_id""", co=co, **params)
    if not rows:
        return []
    revrows = await _all(db, f"""
        SELECT r.finding_id, r.review_id, r.action, r.note, r.person_id, r.created_at FROM engine.finding_reviews r
        WHERE r.finding_id IN (SELECT f.finding_id FROM engine.findings f WHERE {where})
        ORDER BY r.created_at""", **params)
    pids = list({p for r in rows for p in (r["route_owner"], r["route_reviewer"], r["route_approver"]) if p}
                | {rv["person_id"] for rv in revrows if rv["person_id"]})
    people = {p["person_id"]: p for p in (await _all(db, """
        SELECT person_id, name, title, department, reports_to_id FROM company.people
        WHERE company_id = :co AND person_id = ANY(:ids)""", co=co, ids=pids))} if pids else {}
    revs: dict[str, list] = {}
    for rv in revrows:
        pp = people.get(rv["person_id"])
        revs.setdefault(str(rv["finding_id"]), []).append(
            {"review_id": str(rv["review_id"]), "decision": rv["action"], "note": rv["note"],
             "at": rv["created_at"], "by": _s(pp.get("name")) if pp else rv["person_id"]})
    via = await _via_rows(db, co, [_j(r["path_detail"]) for r in rows])

    def person(pid: Optional[str]) -> Optional[dict]:
        if not pid:
            return None
        p = people.get(pid) or {"person_id": pid, "name": pid}
        return {"person_id": p["person_id"], "name": _s(p.get("name")), "title": _s(p.get("title")),
                "department": _s(p.get("department")), "reports_to_id": p.get("reports_to_id")}

    out = []
    for r in rows:
        q = _j(r["quotes"]) or {}
        rc = _j(r["required_change"]) or {}
        owner = person(r["route_owner"]) or person(r["route_reviewer"])
        out.append({
            "finding_id": str(r["finding_id"]), "run_id": str(r["run_id"]), "change_id": str(r["change_id"]),
            "clause_id": r["clause_id"], "doc_id": r["doc_id"], "citation": r["citation"],
            "finding_type": r["finding_type"], "verdict": r["verdict"], "severity": r["severity"],
            "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
            "decided_by": "ai" if r["decided_by"] == "llm" else r["decided_by"],
            "required_change": {"from_text": _s(rc.get("from_text")), "to_text": _s(rc.get("to_text"))},
            "quotes": {"s1": _quote(q.get("s1"), r["s1_text_norm"]),
                       "s2": _quote(q.get("s2"), r["s2_text_norm"]),
                       "clause": _quote(q.get("clause"), r["text_raw"])},
            "quotes_verified": bool(r["quotes_verified"]),
            "rationale": _s(r["rationale"]), "match_path": r["match_path"],
            "path_detail": _path(r, _j(r["path_detail"]), via),
            "propagated_from": str(r["propagated_from"]) if r["propagated_from"] else None,
            "stale_at_approval": r["finding_type"] == "stale_at_approval",
            "doc_approved_date": r["approved_date"], "rule_published_date": r["rule_pub"],
            "route": {"owner": owner, "reviewer": person(r["route_reviewer"]) or owner,
                      "approver": person(r["route_approver"])},
            "reviews": revs.get(str(r["finding_id"]), []),
        })
    return out


@router.get("/ui/runs/{rid}/findings")
async def ui_list_findings(rid: str, doc_id: Optional[str] = Query(None), change_id: Optional[str] = Query(None),
                           db: AsyncSession = Depends(get_db)):
    run = await resolve_run(db, rid)
    where = ("f.run_id = CAST(:rid AS uuid) AND (CAST(:doc AS text) IS NULL OR f.doc_id = :doc) "
             "AND (CAST(:cid AS uuid) IS NULL OR f.change_id = CAST(:cid AS uuid))")
    return await _load_findings(db, run, where, {"rid": str(run["run_id"]), "doc": doc_id,
                                                  "cid": _uuid(change_id) if change_id else None})


@router.get("/ui/findings/{finding_id}")
async def ui_get_finding(finding_id: str, db: AsyncSession = Depends(get_db)):
    fid = _uuid(finding_id)
    f = await _one(db, "SELECT run_id FROM engine.findings WHERE finding_id = CAST(:f AS uuid)", f=fid)
    if not f:
        raise HTTPException(404, "finding not found")
    run = await resolve_run(db, str(f["run_id"]))  # 409 while running
    res = await _load_findings(db, run, "f.finding_id = CAST(:fid AS uuid)", {"fid": fid})
    if not res:
        raise HTTPException(404, "finding not found")
    return res[0]


# ------------------------------------------------------------------ rollups
@router.get("/ui/runs/{rid}/rollups")
async def ui_list_rollups(rid: str, db: AsyncSession = Depends(get_db)):
    run = await resolve_run(db, rid)
    run_id = str(run["run_id"])
    rows = await _all(db, """
        SELECT run_id, doc_id, status, counts, changes_considered, reason FROM engine.doc_rollups
        WHERE run_id = CAST(:rid AS uuid) ORDER BY (status = 'flagged') DESC, doc_id""", rid=run_id)
    reviewed = {r["doc_id"]: int(r["n"]) for r in await _all(db, """
        SELECT f.doc_id, COUNT(*) AS n FROM engine.findings f
        WHERE f.run_id = CAST(:rid AS uuid)
          AND EXISTS (SELECT 1 FROM engine.finding_reviews r WHERE r.finding_id = f.finding_id)
        GROUP BY f.doc_id""", rid=run_id)}
    out = []
    for r in rows:
        counts = _j(r["counts"]) or {}
        cbv = dict(_ZERO_VERDICTS)
        for k, v in counts.items():
            if k != "cleared_clauses":
                cbv[k] = int(v or 0)
        considered = _j(r["changes_considered"]) or []
        by_class: dict[str, int] = {}
        for c in considered:
            cc = c.get("change_class") if isinstance(c, dict) else None
            if cc:
                by_class[cc] = by_class.get(cc, 0) + 1
        out.append({"run_id": run_id, "doc_id": r["doc_id"], "status": r["status"],
                    "counts_by_verdict": cbv, "changes_considered": len(considered),
                    "considered_by_class": by_class, "cleared_reason": r["reason"],
                    "reviewed": reviewed.get(r["doc_id"], 0)})
    return out


# ------------------------------------------------------------------ annotations
@router.get("/ui/runs/{rid}/documents/{doc_id}/annotations")
async def ui_annotations(rid: str, doc_id: str, db: AsyncSession = Depends(get_db)):
    run = await resolve_run(db, rid)
    run_id = str(run["run_id"])
    out: list[dict] = []
    frows = await _all(db, f"""
        SELECT f.finding_id, f.change_id, f.clause_id, f.citation, f.verdict, f.rationale, f.quotes,
               cl.text_raw
        FROM engine.findings f LEFT JOIN company.clauses cl ON cl.clause_pk = f.clause_pk
        WHERE f.run_id = CAST(:rid AS uuid) AND f.doc_id = :d
        ORDER BY {_SEV_ORDER}, f.clause_id, f.finding_id""", rid=run_id, d=doc_id)
    for r in frows:
        q = (_j(r["quotes"]) or {}).get("clause")
        sp = locate_quote(q, r["text_raw"] or "") if isinstance(q, str) and q else None
        out.append({"clause_id": r["clause_id"], "kind": "finding", "verdict": r["verdict"],
                    "finding_id": str(r["finding_id"]), "change_id": str(r["change_id"]),
                    "citation": r["citation"], "quote_span": list(sp) if sp else None,
                    "reason": _s(r["rationale"])})
    crows = await _all(db, """
        SELECT k.clause_id, k.change_id, k.rationale, ch.citation, ch.change_class
        FROM engine.candidates k JOIN engine.change_records ch ON ch.change_id = k.change_id
        WHERE k.run_id = CAST(:rid AS uuid) AND k.doc_id = :d
          AND NOT EXISTS (SELECT 1 FROM engine.findings f WHERE f.candidate_id = k.candidate_id)
        ORDER BY k.clause_id, ch.citation, k.candidate_id""", rid=run_id, d=doc_id)
    for r in crows:
        reason = r["rationale"] if (r["rationale"] or "").strip() else \
            cleared_reason_text(r["change_class"], r["citation"])
        out.append({"clause_id": r["clause_id"], "kind": "cleared", "verdict": None, "finding_id": None,
                    "change_id": str(r["change_id"]), "citation": r["citation"], "quote_span": None,
                    "reason": reason})
    return out


# ------------------------------------------------------------------ matrix
@router.get("/ui/runs/{rid}/matrix")
async def ui_matrix(rid: str, include_noise: bool = Query(False), db: AsyncSession = Depends(get_db)):
    run = await resolve_run(db, rid)
    run_id = str(run["run_id"])
    where = "AND ch.in_footprint"
    if not include_noise:
        where += " AND ch.change_class NOT IN (" + ",".join(f"'{c}'" for c in NOISE_CLASSES) + ")"
    changes = await _light_changes(db, run_id, where)
    keep = {c["change_id"] for c in changes}
    rows = await _all(db, """
        SELECT k.doc_id, k.change_id, f.verdict
        FROM engine.candidates k
        LEFT JOIN engine.findings f ON f.candidate_id = k.candidate_id
        WHERE k.run_id = CAST(:rid AS uuid)""", rid=run_id)
    agg: dict[tuple[str, str], list] = {}
    for r in rows:
        cid = str(r["change_id"])
        if cid not in keep:
            continue
        a = agg.setdefault((r["doc_id"], cid), [0, 0, None])
        if r["verdict"]:
            a[0] += 1
            rank = VERDICT_RANK.index(r["verdict"]) if r["verdict"] in VERDICT_RANK else len(VERDICT_RANK)
            if a[2] is None or rank < a[2][0]:
                a[2] = (rank, r["verdict"])
        else:
            a[1] += 1
    cells = [{"doc_id": d, "change_id": c, "worst_verdict": a[2][1] if a[2] else "cleared",
              "n_findings": a[0], "n_cleared": a[1]} for (d, c), a in sorted(agg.items())]
    return {"changes": changes, "cells": cells}


# ------------------------------------------------------------------ radar
def _attr_value(r: dict) -> Any:
    if r["value_bool"] is not None:
        return bool(r["value_bool"])
    if r["value_num"] is not None:
        f = float(r["value_num"])
        return int(f) if f == int(f) else f
    if r["value_text"] is not None:
        return r["value_text"]
    return "not in profile"


@router.get("/ui/runs/{rid}/radar")
async def ui_radar(rid: str, db: AsyncSession = Depends(get_db)):
    run = await resolve_run(db, rid)
    run_id = str(run["run_id"])
    rows = await _all(db, """
        SELECT r.change_id, ch.citation, ch.heading, cs.agency_id, r.applicable, r.attribute_basis,
               r.affected_activity, r.reason, r.quote_s2, r.rule_covered_by_docs
        FROM engine.radar_items r
        JOIN engine.change_records ch ON ch.change_id = r.change_id
        LEFT JOIN public.code_sections cs ON cs.id = COALESCE(ch.s2_section_id, ch.s1_section_id)
        WHERE r.run_id = CAST(:rid AS uuid)
        ORDER BY CASE r.applicable WHEN 'yes' THEN 0 WHEN 'unclear' THEN 1 ELSE 2 END, ch.citation, r.change_id""",
                      rid=run_id)
    attrs = {a["key"]: _attr_value(a) for a in await _all(db, """
        SELECT key, value_text, value_num, value_bool FROM company.company_attributes
        WHERE company_id = :co""", co=run["company_id"])}
    return [{
        "radar_id": str(r["change_id"]), "run_id": run_id, "change_id": str(r["change_id"]),
        "citation": r["citation"], "heading": clean_heading(r["citation"], r["heading"]),
        "agency_id": _s(r["agency_id"]), "applicable": r["applicable"],
        "attribute_basis": [{"key": k, "value": attrs.get(k, "not in profile")}
                            for k in (r["attribute_basis"] or [])],
        "affected_activity": _s(r["affected_activity"]), "reason": _s(r["reason"]),
        "quote": _s(r["quote_s2"]), "docs_covering_same_rule": list(r["rule_covered_by_docs"] or []),
    } for r in rows]

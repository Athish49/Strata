"""Shared helpers for the /engine/ui/* routers (ui_wiring_contract.md section 7).

NOT a router: do not register it. Pure functions (no DB) except `resolve_run` and
`build_progress`, which only SELECT. Imports from `app.api.engine.routes` are lazy
(inside functions) so the pure helpers import without the DB layer and no circular
import can occur.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

STALE_RUN_MINUTES = 30

NOISE_CLASSES = ("cosmetic", "metadata_only", "punctuation_only", "cross_ref_only")
REAL_CLASSES = ("substantive", "repealed", "renumbered", "new_section")
VERDICT_RANK = ("action_required", "optional_relaxed", "update_citation", "review", "info")
CANDIDATE_PATHS = ("direct_section", "direct_rule", "value_echo", "register_hop")

CLASS_WORDS = {
    "cosmetic": "cosmetic",
    "metadata_only": "metadata-only",
    "punctuation_only": "punctuation-only",
    "cross_ref_only": "cross-reference-only",
}


# ---------------------------------------------------------------- headings / enums
def clean_heading(citation: str, heading: Optional[str]) -> str:
    """Strip a leading citation (case-insensitive) or leading '§ <token>', trim ' -:.'.
    Empty result keeps the original heading; None -> ''."""
    if heading is None:
        return ""
    orig = heading
    h = heading.strip()
    cit = (citation or "").strip()
    if cit and h.lower().startswith(cit.lower()):
        h = h[len(cit):]
    else:
        m = re.match(r"^§+\s*\S+", h)
        if m:
            h = h[m.end():]
    h = h.strip(" \t\n-–—:.")
    return h if h else orig


def map_direction(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    return "removed" if raw == "removed_requirement" else raw


def cleared_reason_text(change_class: Optional[str], citation: Optional[str]) -> str:
    """Fallback annotation reason for a cleared candidate with empty rationale (3.6)."""
    if not change_class:
        return "Checked: no impact."
    words = CLASS_WORDS.get(change_class, str(change_class).lower())
    cit = f" to {citation}" if citation else ""
    return f"Checked: no impact — {words} change{cit}."


# ---------------------------------------------------------------- run helpers
def _num(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def map_stats(stats: Optional[dict]) -> dict:
    s = stats if isinstance(stats, dict) else {}
    bc_raw = s.get("by_class") if isinstance(s.get("by_class"), dict) else {}
    bc = {k: _num(v) for k, v in bc_raw.items()}
    noise = sum(bc.get(k, 0) for k in NOISE_CLASSES)
    substantive = sum(bc.get(k, 0) for k in REAL_CLASSES)
    fp = s.get("in_footprint")
    in_footprint = sum(_num(v) for v in fp.values()) if isinstance(fp, dict) else _num(fp)
    # Real changes (REAL_CLASSES) among those in the footprint; the rest is noise. None when stats carry no per-class split.
    in_footprint_real = sum(_num(fp.get(k)) for k in REAL_CLASSES) if isinstance(fp, dict) else None
    cands = s.get("candidates") if isinstance(s.get("candidates"), dict) else {}
    finds = s.get("findings") if isinstance(s.get("findings"), dict) else {}
    radar = s.get("radar") if isinstance(s.get("radar"), dict) else {}
    out_cands = {p: _num(cands.get(p)) for p in CANDIDATE_PATHS}
    for k, v in cands.items():
        out_cands.setdefault(k, _num(v))
    out_finds = {v: _num(finds.get(v)) for v in VERDICT_RANK}
    for k, v in finds.items():
        out_finds.setdefault(k, _num(v))
    return {
        "changes_raw": _num(s.get("raw_changed")),
        "by_class": bc,
        "substantive": substantive,
        "noise": noise,
        "in_footprint": in_footprint,
        "in_footprint_real": in_footprint_real,
        "obligation_changed": _num(s.get("obligation_changed")),
        "candidates_by_path": out_cands,
        "findings_by_verdict": out_finds,
        "clauses_cleared": _num(s.get("clauses_cleared")),
        "docs_flagged": _num(s.get("docs_flagged")),
        "docs_cleared": _num(s.get("docs_cleared")),
        "radar": {"applicable": _num(radar.get("yes")), "screened_out": _num(radar.get("no")),
                  "unclear": _num(radar.get("unclear"))},
        "decided_by": {"rule": _num(s.get("judged_rule")), "ai": _num(s.get("judged_llm"))},
        "llm_calls": _num(s.get("llm_calls")),
    }


def map_run_status(status: Optional[str], started_at: Optional[datetime],
                   finished_at: Optional[datetime]) -> str:
    if status == "done":
        return "succeeded"
    if status == "running":
        if finished_at is None and isinstance(started_at, datetime):
            st = started_at if started_at.tzinfo else started_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - st > timedelta(minutes=STALE_RUN_MINUTES):
                return "failed"
        return "running"
    if status == "failed":
        return "failed"
    return status or "failed"


# ---------------------------------------------------------------- path_detail (3.3.1)
_VIA_KIND = {"register_row": "register_row", "form_field": "form_field", "tariff_subrule": "tariff_rule"}


def _local_id(clause_id: str) -> str:
    return clause_id.split(":", 1)[1] if ":" in clause_id else clause_id


def build_path_nodes(step_list: Optional[list], match_path: Optional[str], change_citation: str,
                     change_heading: Optional[str], clause_row: dict,
                     via_clause_row: Optional[dict] = None) -> list[dict]:
    """Ordered chain [{kind, ref, label}]. `clause_row` needs clause_id, doc_id, heading_path;
    `via_clause_row` (register_hop only) needs clause_id, doc_id, unit_kind."""
    steps = [s for s in (step_list or []) if isinstance(s, dict)]
    step = next((s for s in steps if s.get("path") == match_path), steps[0] if steps else None)
    path = (step or {}).get("path") or match_path

    heading = clean_heading(change_citation, change_heading)
    section = {"kind": "section", "ref": change_citation,
               "label": f"{change_citation} · {heading}" if heading else change_citation}
    hp = clause_row.get("heading_path") or []
    tail = hp[-1] if hp else _local_id(clause_row["clause_id"])
    clause = {"kind": "clause", "ref": clause_row["clause_id"],
              "label": f"{clause_row.get('doc_id', '')} · {tail}"}

    if path == "direct_rule":
        val = str((step or {}).get("value") or "")
        return [section, {"kind": "rule", "ref": val, "label": val}, clause]
    if path == "register_hop":
        via_id = (step or {}).get("via_clause_id")
        if via_id:
            v = via_clause_row or {}
            vdoc = v.get("doc_id") or (via_id.split(":", 1)[0] if ":" in via_id else "")
            via = {"kind": _VIA_KIND.get(v.get("unit_kind"), "clause"), "ref": via_id,
                   "label": f"{vdoc} · {_local_id(via_id)}"}
            return [section, via, clause]
    return [section, clause]


# ---------------------------------------------------------------- DB helpers (SELECT only)
async def resolve_run(db, rid: str, require_done: bool = True) -> dict:
    """Run row or HTTPException 404 (bad uuid/unknown) / 409 (running and require_done)."""
    from app.api.engine.routes import _get_run
    return await _get_run(db, rid, require_done=require_done)


async def build_progress(db, run_id: str) -> Optional[dict]:
    """Best-effort progress for a running run (3.1.1). Any exception -> None."""
    try:
        from app.api.engine.routes import _one

        def prog(stage, done, total, msg):
            return {"stage": stage, "done": int(done or 0), "total": int(total or 0), "message": msg}

        rid = str(run_id)
        r = await _one(db, """
            SELECT
              (SELECT count(*) FROM engine.doc_rollups WHERE run_id = CAST(:rid AS uuid)) AS rollups,
              (SELECT count(*) FROM company.company_documents) AS docs,
              (SELECT count(*) FROM engine.candidates WHERE run_id = CAST(:rid AS uuid)
                 AND skip_reason IS NULL) AS cand_total,
              (SELECT count(*) FROM engine.candidates WHERE run_id = CAST(:rid AS uuid)
                 AND skip_reason IS NULL AND judged_by IS NOT NULL) AS cand_judged,
              (SELECT count(*) FROM engine.candidates WHERE run_id = CAST(:rid AS uuid)
                 AND skip_reason IS NULL AND (judged_by IS NOT NULL OR affected IS NOT NULL)) AS cand_active,
              (SELECT count(*) FROM engine.findings WHERE run_id = CAST(:rid AS uuid)) AS finds,
              (SELECT count(*) FROM engine.change_records WHERE run_id = CAST(:rid AS uuid)) AS chg,
              (SELECT count(*) FROM engine.change_records WHERE run_id = CAST(:rid AS uuid)
                 AND obligation_changed IS NOT NULL) AS chg_char,
              (SELECT count(*) FROM engine.change_records WHERE run_id = CAST(:rid AS uuid)
                 AND change_class = 'substantive' AND in_footprint) AS sub_fp,
              (SELECT count(*) FROM engine.change_records WHERE run_id = CAST(:rid AS uuid)
                 AND change_class = 'substantive' AND in_footprint
                 AND obligation_changed IS NOT NULL) AS sub_fp_char
            """, rid=rid)
        if not r:
            return None
        if r["rollups"]:
            d, t = r["rollups"], r["docs"]
            return prog("ledger", d, t, f"{d} of {t} documents rolled up")
        if r["cand_active"] or r["finds"]:
            d, t = r["cand_judged"], r["cand_total"]
            return prog("judge", d, t, f"{d} of {t} candidate clauses judged")
        if r["cand_total"]:
            t = r["cand_total"]
            return prog("judge", 0, t, f"0 of {t} candidate clauses judged")
        if r["chg"] and r["chg_char"]:
            t = r["sub_fp"]
            return prog("candidates", t, t, f"{t} changes matched against clauses")
        if r["chg"]:
            d, t = r["sub_fp_char"], r["sub_fp"]
            return prog("characterize", d, t, f"{d} of {t} changes characterized")
        return prog("delta", 0, 0, "Comparing snapshots")
    except Exception:
        return None

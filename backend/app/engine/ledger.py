"""
ledger.py — Stage 5 (Ledger): propagation, routing, change dispositions, completeness check,
document rollups and run stats (engine_spec.md section 5).

Pure helpers (``decide_disposition``, ``compute_propagation``, ``check_completeness``,
``build_rollup``, ``cleared_reason``, ``build_stats``) work on plain dicts; the DB layer reads
the run's ``engine.*`` rows, calls them and writes ``engine.*`` only.
"""
from __future__ import annotations

import json
import logging
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import text

from app.engine.config import engine_settings

logger = logging.getLogger(__name__)

KEEP_DISPOSITIONS = {"excluded_noise", "not_in_footprint"}
VERDICTS = ("action_required", "optional_relaxed", "update_citation", "review", "info")


class LedgerCheckError(RuntimeError):
    """The completeness check failed; ``violations`` lists every problem found."""

    def __init__(self, violations: list[str]):
        self.violations = violations
        shown = "; ".join(violations[:10])
        more = f" (+{len(violations) - 10} more)" if len(violations) > 10 else ""
        super().__init__(f"ledger completeness check failed: {len(violations)} violation(s): {shown}{more}")


def is_non_info(f: dict) -> bool:
    return f["finding_type"] != "informational"


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def decide_disposition(change: dict, n_candidates: int, findings: list[dict]) -> tuple[str, str | None] | None:
    """(disposition, reason) for a change, or None when the existing disposition stays untouched."""
    current = change.get("disposition")
    if current in KEEP_DISPOSITIONS:
        return None
    if current == "needs_review" and change.get("change_class") == "new_section":
        return None
    non_info = [f for f in findings if is_non_info(f)]
    review = [f for f in findings if not is_non_info(f) and f.get("needs_review")]
    if not findings and current is not None:
        return None  # set earlier (e.g. by characterize) with its own reason
    if non_info:
        docs = len({f["doc_id"] for f in non_info})
        return ("findings_emitted",
                f"{len(non_info)} finding(s) across {docs} document(s)")
    if review:
        return ("needs_review", f"{len(review)} informational finding(s) need review")
    if n_candidates:
        return ("no_affected_clauses", f"{n_candidates} candidate(s) checked, none affected")
    return ("no_affected_clauses", "No candidate clauses to check")


def compute_propagation(findings: list[dict], path_details: dict[str, list[dict]]) -> dict[str, str]:
    """finding_id -> parent finding_id for register_hop findings whose via clause has a finding.

    ``path_details`` maps candidate_id -> its path_detail list.
    """
    by_key = {(f["change_id"], f["clause_id"]): f["finding_id"] for f in findings}
    out: dict[str, str] = {}
    for f in findings:
        if f["match_path"] != "register_hop":
            continue
        for e in path_details.get(f["candidate_id"], []):
            if e.get("path") != "register_hop" or not e.get("via_clause_id"):
                continue
            parent = by_key.get((f["change_id"], e["via_clause_id"]))
            if parent and parent != f["finding_id"]:
                out[f["finding_id"]] = parent
                break
    return out


def check_completeness(changes: list[dict], candidates: list[dict], findings: list[dict]) -> list[str]:
    """Violations of engine_spec 5.4 (empty list when complete)."""
    v: list[str] = []
    for c in changes:
        if not c.get("disposition"):
            v.append(f"change {c['change_id']} ({c.get('citation')}) has no disposition")
    for c in candidates:
        if not c.get("judged_by") and not c.get("skip_reason"):
            v.append(f"candidate {c['candidate_id']} ({c.get('clause_id')}) has neither judged_by nor skip_reason")
    for f in findings:
        if is_non_info(f) and not f.get("quotes_verified"):
            v.append(f"finding {f['finding_id']} ({f['finding_type']}) is non-informational with quotes_verified=false")
    return v


def outcome_label(cand: dict) -> str:
    """Why an unflagged candidate was cleared, as a short phrase."""
    skip = cand.get("skip_reason")
    if skip:
        return skip.split(":", 1)[-1].replace("_", " ")
    return "not affected"


def cleared_reason(outcomes: list[str]) -> str:
    """Templated reason for a cleared document from per-change outcome labels."""
    if not outcomes:
        return "No S2 change touches sections this document cites."
    n = len(outcomes)
    parts = ", ".join(f"{k} {lbl}" for lbl, k in sorted(Counter(outcomes).items(), key=lambda kv: (-kv[1], kv[0])))
    return f"{n} change{'s' if n != 1 else ''} considered: {parts}"


def build_rollup(doc_id: str, changes_by_id: dict[str, dict], candidates: list[dict],
                 findings: list[dict]) -> dict:
    """Rollup row for one document from its candidates and findings."""
    counts = {k: 0 for k in VERDICTS}
    for f in findings:
        counts[f["verdict"]] = counts.get(f["verdict"], 0) + 1
    flagged_clauses = {f["clause_pk"] for f in findings}
    cleared_clauses = {c["clause_pk"] for c in candidates} - flagged_clauses
    counts["cleared_clauses"] = len(cleared_clauses)

    flagged = any(is_non_info(f) for f in findings)
    fnd_by_change: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        fnd_by_change[f["change_id"]].append(f)
    cand_by_change: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        cand_by_change[c["change_id"]].append(c)

    considered, labels = [], []
    for cid in sorted(cand_by_change, key=lambda x: (changes_by_id[x]["citation"], x)):
        fs = fnd_by_change.get(cid, [])
        if any(is_non_info(f) for f in fs):
            outcome = "findings_emitted"
        elif any(f.get("needs_review") for f in fs):
            outcome = "needs_review"
        elif fs:
            outcome = "info"
        else:
            # most common cleared label among this change's candidates
            outcome = Counter(outcome_label(c) for c in cand_by_change[cid]).most_common(1)[0][0]
        labels.append(outcome)
        ch = changes_by_id[cid]
        considered.append({"change_id": cid, "citation": ch["citation"],
                           "change_class": ch["change_class"], "outcome": outcome})
    return {
        "doc_id": doc_id,
        "status": "flagged" if flagged else "cleared",
        "counts": counts,
        "changes_considered": considered,
        "reason": None if flagged else cleared_reason(labels),
    }


def build_stats(changes: list[dict], candidates: list[dict], findings: list[dict],
                rollups: list[dict], radar: dict[str, int] | None = None) -> dict[str, Any]:
    """Funnel keys of data_model.md section 4 that the ledger can compute."""
    flagged_clauses = {f["clause_pk"] for f in findings}
    stats: dict[str, Any] = {
        "obligation_changed": sum(1 for c in changes if c.get("obligation_changed")),
        "candidates": dict(Counter(c["match_path"] for c in candidates)),
        "judged_rule": sum(1 for c in candidates if c.get("judged_by") == "rule"),
        "judged_llm": sum(1 for c in candidates if c.get("judged_by") == "llm"),
        "findings": dict(Counter(f["verdict"] for f in findings)),
        "findings_non_info": sum(1 for f in findings if is_non_info(f)),
        "clauses_cleared": len({c["clause_pk"] for c in candidates} - flagged_clauses),
        "docs_flagged": sum(1 for r in rollups if r["status"] == "flagged"),
        "docs_cleared": sum(1 for r in rollups if r["status"] == "cleared"),
    }
    if radar:
        stats["radar"] = radar
    return stats


# ---------------------------------------------------------------------------
# DB layer
# ---------------------------------------------------------------------------

_CHANGES_SQL = text("""
    SELECT change_id::text AS change_id, citation, change_class, in_footprint, obligation_changed,
           disposition, disposition_reason
    FROM engine.change_records WHERE run_id = CAST(:rid AS uuid)
""")
_CANDS_SQL = text("""
    SELECT candidate_id::text AS candidate_id, change_id::text AS change_id, clause_pk::text AS clause_pk,
           clause_id, doc_id, match_path, path_detail, judged_by, skip_reason, affected
    FROM engine.candidates WHERE run_id = CAST(:rid AS uuid)
""")
_FINDINGS_SQL = text("""
    SELECT finding_id::text AS finding_id, change_id::text AS change_id, candidate_id::text AS candidate_id,
           clause_pk::text AS clause_pk, clause_id, doc_id, finding_type, verdict, needs_review,
           quotes_verified, match_path
    FROM engine.findings WHERE run_id = CAST(:rid AS uuid)
""")
_DOCS_SQL = text("SELECT doc_id FROM company.company_documents WHERE company_id = :cid ORDER BY doc_id")
_PROPAGATE_SQL = text("""
    UPDATE engine.findings SET propagated_from = CAST(:parent AS uuid) WHERE finding_id = CAST(:fid AS uuid)
""")
_ROUTE_SQL = text("""
    UPDATE engine.findings f
    SET route_owner = d.owner_id, route_reviewer = d.reviewer_id, route_approver = d.approver_id
    FROM company.company_documents d
    WHERE f.run_id = CAST(:rid AS uuid) AND d.company_id = :cid AND d.doc_id = f.doc_id
""")
_DISPOSITION_SQL = text("""
    UPDATE engine.change_records SET disposition = :disposition, disposition_reason = :reason
    WHERE change_id = CAST(:change_id AS uuid)
""")
_ROLLUP_SQL = text("""
    INSERT INTO engine.doc_rollups (run_id, doc_id, status, counts, changes_considered, reason)
    VALUES (CAST(:rid AS uuid), :doc_id, :status, CAST(:counts AS jsonb),
            CAST(:considered AS jsonb), :reason)
    ON CONFLICT (run_id, doc_id) DO UPDATE SET status = EXCLUDED.status, counts = EXCLUDED.counts,
        changes_considered = EXCLUDED.changes_considered, reason = EXCLUDED.reason
""")
_RADAR_SQL = text("""
    SELECT applicable, COUNT(*) AS n FROM engine.radar_items
    WHERE run_id = CAST(:rid AS uuid) GROUP BY applicable
""")
_STATS_SQL = text("""
    UPDATE engine.runs SET stats = COALESCE(stats, '{}'::jsonb) || CAST(:stats AS jsonb)
    WHERE run_id = CAST(:rid AS uuid)
""")


async def _rows(session, sql, **params) -> list[dict]:
    return [dict(r) for r in (await session.execute(sql, params)).mappings().all()]


async def run_ledger(session, run_id: str, company_id: str) -> dict[str, Any]:
    """Run Stage 5 for one run on an open session (commits); returns the stats it computed."""
    changes = await _rows(session, _CHANGES_SQL, rid=run_id)
    candidates = await _rows(session, _CANDS_SQL, rid=run_id)
    findings = await _rows(session, _FINDINGS_SQL, rid=run_id)

    # 1. propagation
    parents = compute_propagation(findings, {c["candidate_id"]: c["path_detail"] for c in candidates})
    if parents:
        await session.execute(_PROPAGATE_SQL, [{"fid": f, "parent": p} for f, p in parents.items()])
    # 2. routing
    await session.execute(_ROUTE_SQL, {"rid": run_id, "cid": company_id})

    # 3. dispositions
    n_cands = Counter(c["change_id"] for c in candidates)
    fnd_by_change: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        fnd_by_change[f["change_id"]].append(f)
    updates = []
    for ch in changes:
        decided = decide_disposition(ch, n_cands[ch["change_id"]], fnd_by_change.get(ch["change_id"], []))
        if decided is not None:
            ch["disposition"], ch["disposition_reason"] = decided
            updates.append({"change_id": ch["change_id"], "disposition": decided[0], "reason": decided[1]})
    if updates:
        await session.execute(_DISPOSITION_SQL, updates)
    await session.commit()

    # 4. completeness
    violations = check_completeness(changes, candidates, findings)
    if violations:
        raise LedgerCheckError(violations)

    # 5. doc rollups for every company document
    doc_ids = [r["doc_id"] for r in await _rows(session, _DOCS_SQL, cid=company_id)]
    doc_ids += sorted({c["doc_id"] for c in candidates} - set(doc_ids))
    changes_by_id = {c["change_id"]: c for c in changes}
    cands_by_doc: dict[str, list[dict]] = defaultdict(list)
    for c in candidates:
        cands_by_doc[c["doc_id"]].append(c)
    fnd_by_doc: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        fnd_by_doc[f["doc_id"]].append(f)
    rollups = [build_rollup(d, changes_by_id, cands_by_doc.get(d, []), fnd_by_doc.get(d, []))
               for d in doc_ids]
    await session.execute(_ROLLUP_SQL, [
        {"rid": run_id, "doc_id": r["doc_id"], "status": r["status"], "counts": json.dumps(r["counts"]),
         "considered": json.dumps(r["changes_considered"]), "reason": r["reason"]}
        for r in rollups
    ])

    # 6. stats
    radar = {r["applicable"]: r["n"] for r in await _rows(session, _RADAR_SQL, rid=run_id)
             if r["applicable"]}
    stats = build_stats(changes, candidates, findings, rollups, radar)
    await session.execute(_STATS_SQL, {"rid": run_id, "stats": json.dumps(stats)})
    await session.commit()
    return stats


async def run_stage(state) -> None:
    """Pipeline entry point (run.py): the ledger stage, after the judge."""
    async with state.session_factory() as session:
        stats = await run_ledger(session, state.run_id, engine_settings.ENGINE_COMPANY_ID)
    state.stats.update(stats)

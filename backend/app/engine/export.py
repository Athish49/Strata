"""
export.py — scoring export (engine_spec section 6, data_model section 6).

Builds the JSON consumed by the scoring script: every company document of the run's company,
flagged or cleared, with its findings (informational ones included).  What-if runs are never
exported.
"""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# one or more trailing subsection designators, e.g. "(a)(2)" or " (b)"
_SUBSECTION_TAIL = re.compile(r"(?:\s*\([^)]*\))+\s*$")


class ExportError(Exception):
    pass


def section_level(citation: str | None) -> str:
    """Strip subsection designators from a citation: '<rule> 4-1-16(a)(2)' -> '<rule> 4-1-16'."""
    return _SUBSECTION_TAIL.sub("", (citation or "").strip())


def _route(f: dict, doc: dict) -> dict[str, Any]:
    return {
        "owner": f.get("route_owner") or doc.get("owner_id"),
        "reviewer": f.get("route_reviewer") or doc.get("reviewer_id"),
        "approver": f.get("route_approver") or doc.get("approver_id") or None,
    }


def assemble_export(docs: list[dict], findings: list[dict], rollup_status: dict[str, str]) -> dict:
    """Pure assembly step (tested with fakes)."""
    by_doc: dict[str, list[dict]] = {}
    for f in findings:
        by_doc.setdefault(f["doc_id"], []).append(f)
    out_docs = []
    for d in sorted(docs, key=lambda x: x["doc_id"]):
        fl = by_doc.get(d["doc_id"], [])
        status = rollup_status.get(d["doc_id"])
        if status is None:
            status = "flagged" if any(f["finding_type"] != "informational" for f in fl) else "cleared"
        out_docs.append({
            "doc_id": d["doc_id"],
            "status": status,
            "findings": [
                {
                    "clause_id": f["clause_id"],
                    "citation": section_level(f["citation"]),
                    "finding_type": f["finding_type"],
                    "severity": f["severity"],
                    "route_to": _route(f, d),
                }
                for f in sorted(fl, key=lambda x: (x["clause_id"], x["citation"] or ""))
            ],
        })
    return {"documents": out_docs}


async def build_export(session: AsyncSession, run_id: str) -> dict:
    run = (await session.execute(
        text("SELECT kind, company_id FROM engine.runs WHERE run_id = CAST(:r AS uuid)"), {"r": str(run_id)}
    )).mappings().first()
    if run is None:
        raise ExportError(f"run {run_id} not found")
    if run["kind"] == "whatif":
        raise ExportError("what-if runs are never exported")

    docs = [dict(r) for r in (await session.execute(
        text("SELECT doc_id, owner_id, reviewer_id, approver_id FROM company.company_documents "
             "WHERE company_id = :c"), {"c": run["company_id"]}
    )).mappings()]
    findings = [dict(r) for r in (await session.execute(
        text("SELECT f.clause_id, f.doc_id, "
             # a rule-level clause citation can never be section-level; name the changed section instead
             "CASE WHEN f.match_path = 'direct_rule' THEN c.citation ELSE f.citation END AS citation, "
             "f.finding_type, f.severity, f.route_owner, f.route_reviewer, f.route_approver "
             "FROM engine.findings f JOIN engine.change_records c ON c.change_id = f.change_id "
             "WHERE f.run_id = CAST(:r AS uuid)"), {"r": str(run_id)}
    )).mappings()]
    rollup = {r["doc_id"]: r["status"] for r in (await session.execute(
        text("SELECT doc_id, status FROM engine.doc_rollups WHERE run_id = CAST(:r AS uuid)"), {"r": str(run_id)}
    )).mappings()}
    return assemble_export(docs, findings, rollup)

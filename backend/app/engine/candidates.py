"""Stage 3: candidate clauses for in-footprint changes still open after Stage 2 (engine_spec.md section 3).

Paths (priority order): direct_section, direct_rule, register_hop, value_echo.  Read-only on company.*;
``persist_candidates`` writes engine.candidates.  The company data is loaded once (``load_candidate_data``,
eligible clauses only, ~2k) and matched in memory, so the matching core is pure and unit-testable.
"""
from __future__ import annotations

import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.enrich.terms import _singularize
from app.engine.config import engine_settings
from app.engine.delta import CandidateSpec
from app.engine.footprint import rule_key
from app.engine.schemas import ValueChange



@dataclass
class CandidateRow(CandidateSpec):
    run_id: str = ""


PATH_PRIORITY = ["direct_section", "direct_rule", "register_hop", "value_echo"]
LINK_TYPES = (
    "references_clause", "references_obligation", "references_record_series",
    "references_tariff", "references_form",
)
_SECTION_ONLY = {"repealed", "renumbered"}
_OPEN_CLASSES = {"substantive", "repealed", "renumbered"}


@dataclass
class ChangeRow:
    change_id: str
    change_class: str
    s1_section_id: int | None
    citation: str
    rule_key: str | None
    value_changes: list[ValueChange] | list[dict] | None = None  # verified only
    origin: str = "kb"


@dataclass
class CandidateData:
    clauses: dict[str, dict] = field(default_factory=dict)            # clause_pk -> {clause_id, doc_id}
    citations: dict[str, list[dict]] = field(default_factory=dict)    # clause_pk -> [{status, section_id, raw, rule_key}]
    links: dict[str, list[tuple[str, str]]] = field(default_factory=dict)  # clause_pk -> [(other_pk, link_type)]
    params: list[dict] = field(default_factory=list)                  # eligible, non-fragment parameters
    by_section: dict[str, set[str]] = field(default_factory=dict)
    by_rule: dict[str, set[str]] = field(default_factory=dict)
    cited_rules: dict[str, set[str]] = field(default_factory=dict)    # clause_pk -> rule keys of any citation
    doc_clauses: dict[str, set[str]] = field(default_factory=dict)

    def index(self) -> "CandidateData":
        self.by_section, self.by_rule, self.cited_rules, self.doc_clauses = {}, {}, {}, {}
        for pk, c in self.clauses.items():
            self.doc_clauses.setdefault(c["doc_id"], set()).add(pk)
        for pk, cits in self.citations.items():
            if pk not in self.clauses:
                continue
            for c in cits:
                rk = c.get("rule_key") or rule_key(c["raw"])
                c["rule_key"] = rk
                if rk:
                    self.cited_rules.setdefault(pk, set()).add(rk)
                if c["status"] == "resolved" and c["section_id"] is not None:
                    self.by_section.setdefault(str(c["section_id"]), set()).add(pk)
                elif c["status"] == "resolved_rule" and rk:
                    self.by_rule.setdefault(rk, set()).add(pk)
        return self


_ELIGIBLE = """
    FROM company.clauses c
    JOIN company.company_documents d ON d.doc_id = c.doc_id AND d.company_id = :company_id
    WHERE c.company_id = :company_id AND c.assessable = true AND c.clause_role <> 'boilerplate'
"""
_CLAUSES_SQL = text("SELECT c.clause_pk::text AS clause_pk, c.clause_id, c.doc_id " + _ELIGIBLE)
_CITATIONS_SQL = text("""
    SELECT cc.clause_pk::text AS clause_pk, cc.resolution_status, cc.code_section_id, cc.citation_raw
    FROM company.clause_citations cc
    JOIN company.clauses c ON c.clause_pk = cc.clause_pk
    WHERE cc.resolution_status IN ('resolved', 'resolved_rule') AND c.company_id = :company_id
""")
_PARAMS_SQL = text("""
    SELECT p.clause_pk::text AS clause_pk, p.kind, p.value_text, p.value_num, p.unit, p.day_type
    FROM company.clause_parameters p
    JOIN company.clauses c ON c.clause_pk = p.clause_pk
    WHERE c.company_id = :company_id AND COALESCE(p.is_citation_fragment, false) = false
      AND (p.kind <> 'number' OR p.unit IS NOT NULL) AND p.value_num IS NOT NULL
""")
_LINKS_SQL = text("""
    SELECT l.from_clause_pk::text AS a, l.to_clause_pk::text AS b, l.link_type
    FROM company.clause_links l
    WHERE l.company_id = :company_id AND l.link_type = ANY(:types)
      AND l.from_clause_pk IS NOT NULL AND l.to_clause_pk IS NOT NULL
""")


async def load_candidate_data(session: AsyncSession, company_id: str | None = None) -> CandidateData:
    company_id = company_id or engine_settings.ENGINE_COMPANY_ID
    p = {"company_id": company_id}
    data = CandidateData()
    for r in (await session.execute(_CLAUSES_SQL, p)).mappings().all():
        data.clauses[r["clause_pk"]] = {"clause_id": r["clause_id"], "doc_id": r["doc_id"]}
    for r in (await session.execute(_CITATIONS_SQL, p)).mappings().all():
        if r["clause_pk"] not in data.clauses:
            continue
        data.citations.setdefault(r["clause_pk"], []).append({
            "status": r["resolution_status"],
            "section_id": r["code_section_id"],
            "raw": r["citation_raw"],
        })
    for r in (await session.execute(_PARAMS_SQL, p)).mappings().all():
        if r["clause_pk"] in data.clauses:
            data.params.append(dict(r))
    for r in (await session.execute(_LINKS_SQL, {**p, "types": list(LINK_TYPES)})).mappings().all():
        data.links.setdefault(r["a"], []).append((r["b"], r["link_type"]))
        data.links.setdefault(r["b"], []).append((r["a"], r["link_type"]))
    return data.index()


def _norm_unit(u: str | None) -> str | None:
    if not u:
        return None
    return _singularize(u.strip().lower())


def _vc_get(vc: Any, name: str) -> Any:
    return vc.get(name) if isinstance(vc, dict) else getattr(vc, name, None)


def _value_matches(vc: Any, p: dict) -> bool:
    old = _vc_get(vc, "old_value_num")
    if old is None or p["value_num"] is None:
        return False
    if abs(float(p["value_num"]) - float(old)) > 1e-9:
        return False
    if _norm_unit(_vc_get(vc, "unit")) != _norm_unit(p["unit"]):
        return False
    d1, d2 = _vc_get(vc, "day_type"), p.get("day_type")
    return not (d1 and d2 and d1 != d2)


def match_change(data: CandidateData, ch: ChangeRow) -> dict[str, dict]:
    """clause_pk -> {"entries": [path_detail...], "cited": str|None}; paths per engine_spec section 3.2."""
    found: dict[str, dict] = {}

    def add(pk: str, path: str, via: str | None = None, link: str | None = None,
            value: str | None = None, cited: str | None = None) -> None:
        slot = found.setdefault(pk, {"entries": [], "cited": None})
        slot["entries"].append({"path": path, "via_clause_id": via, "link_type": link, "value": value})
        if cited and slot["cited"] is None:
            slot["cited"] = cited

    direct: set[str] = set()
    if ch.s1_section_id is not None:
        for pk in sorted(data.by_section.get(str(ch.s1_section_id), ())):
            add(pk, "direct_section", value=ch.citation, cited=ch.citation)
            direct.add(pk)
    if ch.change_class in _SECTION_ONLY:
        return found

    if ch.rule_key:
        for pk in sorted(data.by_rule.get(ch.rule_key, ())):
            raw = next((c["raw"] for c in data.citations[pk]
                        if c["status"] == "resolved_rule" and c["rule_key"] == ch.rule_key), None)
            add(pk, "direct_rule", value=raw, cited=raw)
            direct.add(pk)

    for c in sorted(direct):
        for other, lt in data.links.get(c, ()):
            if other in data.clauses and other != c:
                add(other, "register_hop", via=data.clauses[c]["clause_id"], link=lt,
                    value=ch.citation, cited=ch.citation)

    vcs = ch.value_changes or []
    if vcs:
        direct_docs = {data.clauses[pk]["doc_id"] for pk in direct}
        for p in data.params:
            pk = p["clause_pk"]
            if pk not in data.clauses:
                continue
            if not (data.clauses[pk]["doc_id"] in direct_docs
                    or (ch.rule_key and ch.rule_key in data.cited_rules.get(pk, ()))):
                continue
            for vc in vcs:
                if _value_matches(vc, p):
                    add(pk, "value_echo", value=p["value_text"], cited=ch.citation)
    return found


def build_candidates_from_data(data: CandidateData, run_id: str, changes: list[ChangeRow]) -> list[CandidateRow]:
    rows: list[CandidateRow] = []
    for ch in changes:
        if ch.change_class not in _OPEN_CLASSES:
            continue
        for pk, slot in sorted(match_change(data, ch).items(), key=lambda kv: data.clauses[kv[0]]["clause_id"]):
            entries = slot["entries"]
            primary = min((e["path"] for e in entries), key=PATH_PRIORITY.index)
            entries.sort(key=lambda e: PATH_PRIORITY.index(e["path"]))
            c = data.clauses[pk]
            rows.append(CandidateRow(
                run_id=run_id, candidate_id=str(uuid.uuid4()), change_id=ch.change_id, clause_pk=pk,
                clause_id=c["clause_id"], doc_id=c["doc_id"], cited_citation=slot["cited"],
                match_path=primary, path_detail=entries, judged_by=None, skip_reason=None,
                affected=None, rationale=None,
            ))
    return rows


async def build_candidates(session: AsyncSession, run_id: str, changes: list[ChangeRow],
                           company_id: str | None = None) -> list[CandidateRow]:
    data = await load_candidate_data(session, company_id)
    return build_candidates_from_data(data, run_id, changes)


_INSERT_SQL = text("""
    INSERT INTO engine.candidates
        (candidate_id, run_id, change_id, clause_pk, clause_id, doc_id, cited_citation,
         match_path, path_detail, judged_by, skip_reason)
    VALUES
        (:candidate_id, :run_id, :change_id, CAST(:clause_pk AS uuid), :clause_id, :doc_id, :cited_citation,
         :match_path, CAST(:path_detail AS jsonb), NULL, NULL)
    ON CONFLICT (change_id, clause_pk) DO NOTHING
""")


async def persist_candidates(session: AsyncSession, rows: list[CandidateRow]) -> None:
    """Insert candidates (no commit). judged_by / skip_reason stay NULL until Stage 4."""
    if not rows:
        return
    await session.execute(_INSERT_SQL, [
        {"candidate_id": r.candidate_id, "run_id": r.run_id, "change_id": r.change_id,
         "clause_pk": r.clause_pk, "clause_id": r.clause_id, "doc_id": r.doc_id,
         "cited_citation": r.cited_citation, "match_path": r.match_path,
         "path_detail": json.dumps(r.path_detail)}
        for r in rows
    ])


# ---------------------------------------------------------------------------
# Stage runner
# ---------------------------------------------------------------------------

async def get_candidate_data(state, session: AsyncSession) -> CandidateData:
    """Company data is loaded once per run and shared by the stages."""
    data = getattr(state, "candidate_data", None)
    if data is None:
        data = state.candidate_data = await load_candidate_data(session)
    return data


async def run_stage(state) -> None:
    """Stage 3 over the in-footprint changes still open after Stage 2."""
    characterized = getattr(state, "characterized", {})
    changes: list[ChangeRow] = []
    for r in state.stage1.results:
        if not r.in_footprint or r.change_class not in _OPEN_CLASSES:
            continue
        v = characterized.get(r.change_id)
        if v is not None and v.obligation_changed is False:
            continue
        if r.disposition not in (None, "needs_review"):
            continue
        changes.append(ChangeRow(
            change_id=r.change_id, change_class=r.change_class, s1_section_id=r.s1_section_id,
            citation=r.citation, rule_key=r.rule_key,
            value_changes=list(v.value_changes) if v is not None else None, origin=r.origin,
        ))
    by_path: dict[str, int] = {}
    rows: list[CandidateRow] = []
    if changes:
        async with state.session_factory() as session:
            data = await get_candidate_data(state, session)
            rows = build_candidates_from_data(data, state.run_id, changes)
            await persist_candidates(session, rows)
            await session.commit()
    for row in rows:
        by_path[row.match_path] = by_path.get(row.match_path, 0) + 1
    state.stats["candidates"] = {"changes": len(changes), "total": len(rows), "by_path": by_path}

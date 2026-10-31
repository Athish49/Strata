"""Company footprint: which S1 sections / rules the company's eligible clauses cite (engine_spec.md section 1.5).

Read-only. Eligible clause = assessable, not boilerplate, belongs to a document of the company,
and scoped to that document's current version (task 7.1 — see VERSION_SCOPE below).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.company_ingest.enrich.citations_grammar import parse_citation

# federal form: "<title> <system> [Part] <part>[.<section>]..." -> "<title> <SYSTEM> <part>"
_FED_RE = re.compile(r"\b(\d{1,3})\s+(cfr)\s+(?:part\s+)?(\d+)(?![\d-])", re.IGNORECASE)


def rule_key(citation: str | None) -> str | None:
    """Rule-level key of a citation string, or None when it has no recognisable rule."""
    if not citation:
        return None
    m = _FED_RE.search(citation)
    if m:
        return f"{int(m.group(1))} {m.group(2).upper()} {int(m.group(3))}"
    for pc in parse_citation(citation):
        if pc.source_system == "iac" and pc.rule_key:
            return pc.rule_key
    return None


# Version scoping (task 7.1).  Every clause query in the engine and API embeds this one
# predicate (footprint.py, candidates.py, radar.py, delta.py, api/company/routes.py,
# api/engine/routes_ui_results.py); it requires the aliases `c` = company.clauses and
# `d` = company.company_documents.  tests/engine/test_version_scoping.py checks every site.
#
# A clause is in scope when it belongs to its document's current version. Full stop.
#
# Task 9.2 step 7 removed the legacy register-row exemption this predicate carried from
# task 7.1 through the v2 cutover: `(c.version_id = d.current_version_id OR (c.unit_kind =
# 'register_row' AND <orphan version_id, <= 1 document_versions row>))`. It existed because
# the pre-v2 register CSV path wrote clauses under a throwaway uuid5(company, doc, "v1")
# version_id with no company.document_versions row at all — the plain predicate would have
# dropped all 204 live register clauses and their 327 resolved citations. After the real
# cutover (task 9.1/9.2) every register CSV is ingested through the real pipeline, which
# creates its document_versions row before segmenting, so no orphan version ids exist any
# more — verified directly against production before removing this (zero register_row
# clauses with a version_id absent from company.document_versions). The exemption also had
# a known flaw worth not re-introducing: its "at most one version" guard switched off as
# soon as a document gained a second document_versions row, even an unapproved draft, which
# made its behaviour depend on unrelated history rather than on the clause itself.
VERSION_SCOPE = "c.version_id = d.current_version_id"

_ELIGIBLE_CTE = """
    WITH eligible AS (
        SELECT c.clause_pk
        FROM company.clauses c
        JOIN company.company_documents d ON d.company_id = c.company_id AND d.doc_id = c.doc_id
        WHERE c.company_id = :company_id AND c.assessable = true AND c.clause_role <> 'boilerplate'
          AND """ + VERSION_SCOPE + """
    )
"""

_CITATIONS_SQL = text(_ELIGIBLE_CTE + """
    SELECT cc.clause_pk::text AS clause_pk, cc.resolution_status, cc.code_section_id, cc.citation_raw
    FROM company.clause_citations cc
    JOIN eligible e ON e.clause_pk = cc.clause_pk
    WHERE cc.resolution_status IN ('resolved', 'resolved_rule')
""")

_ELIGIBLE_COUNT_SQL = text(_ELIGIBLE_CTE + "SELECT count(*) FROM eligible")

# document_scope carries version_id too (task 7.1): without this join v1's rule keys would
# persist in cited_rule_keys after a promotion.  Verified no-op today (285 rows, 0 mismatches).
_SCOPE_SQL = text("""
    SELECT DISTINCT s.scope_key
    FROM company.document_scope s
    JOIN company.company_documents d ON d.company_id = s.company_id AND d.doc_id = s.doc_id
    WHERE s.company_id = :company_id AND s.scope_level = 'rule'
      AND s.version_id = d.current_version_id
""")


@dataclass
class Footprint:
    eligible_clauses: int = 0
    cited_section_ids: set[int] = field(default_factory=set)
    cited_rule_keys: set[str] = field(default_factory=set)
    clauses_by_section: dict[int, set[str]] = field(default_factory=dict)
    clauses_by_rule_key: dict[str, set[str]] = field(default_factory=dict)

    @property
    def clause_count_by_section(self) -> dict[int, int]:
        return {k: len(v) for k, v in self.clauses_by_section.items()}

    @property
    def clause_count_by_rule_key(self) -> dict[str, int]:
        return {k: len(v) for k, v in self.clauses_by_rule_key.items()}

    def in_footprint(self, s1_section_id: int | None, citation: str | None) -> bool:
        if s1_section_id is not None and int(s1_section_id) in self.cited_section_ids:
            return True
        rk = rule_key(citation)
        return rk is not None and rk in self.cited_rule_keys

    def cited_clause_count(self, s1_section_id: int | None, citation: str | None) -> int:
        """Distinct eligible clauses citing the S1 section, or the rule via a rule-level citation."""
        clauses: set[str] = set()
        if s1_section_id is not None:
            clauses |= self.clauses_by_section.get(int(s1_section_id), set())
        rk = rule_key(citation)
        if rk is not None:
            clauses |= self.clauses_by_rule_key.get(rk, set())
        return len(clauses)


async def load_footprint(session: AsyncSession, company_id: str) -> Footprint:
    fp = Footprint()
    params = {"company_id": company_id}
    fp.eligible_clauses = int((await session.execute(_ELIGIBLE_COUNT_SQL, params)).scalar() or 0)

    for r in (await session.execute(_CITATIONS_SQL, params)).mappings().all():
        if r["resolution_status"] == "resolved":
            if r["code_section_id"] is None:
                continue
            sid = int(r["code_section_id"])
            fp.cited_section_ids.add(sid)
            fp.clauses_by_section.setdefault(sid, set()).add(r["clause_pk"])
        else:
            rk = rule_key(r["citation_raw"])
            if rk is not None:
                fp.cited_rule_keys.add(rk)
                fp.clauses_by_rule_key.setdefault(rk, set()).add(r["clause_pk"])

    for r in (await session.execute(_SCOPE_SQL, params)).mappings().all():
        rk = rule_key(r["scope_key"]) or r["scope_key"]
        if rk:
            fp.cited_rule_keys.add(rk)
    return fp

"""Company footprint: which S1 sections / rules the company's eligible clauses cite (engine_spec.md section 1.5).

Read-only. Eligible clause = assessable, not boilerplate, doc_id belongs to the company (section 3.1: no version_id filter).
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


_ELIGIBLE_CTE = """
    WITH eligible AS (
        SELECT c.clause_pk
        FROM company.clauses c
        JOIN company.company_documents d ON d.doc_id = c.doc_id AND d.company_id = :company_id
        WHERE c.company_id = :company_id AND c.assessable = true AND c.clause_role <> 'boilerplate'
    )
"""

_CITATIONS_SQL = text(_ELIGIBLE_CTE + """
    SELECT cc.clause_pk::text AS clause_pk, cc.resolution_status, cc.code_section_id, cc.citation_raw
    FROM company.clause_citations cc
    JOIN eligible e ON e.clause_pk = cc.clause_pk
    WHERE cc.resolution_status IN ('resolved', 'resolved_rule')
""")

_ELIGIBLE_COUNT_SQL = text(_ELIGIBLE_CTE + "SELECT count(*) FROM eligible")

_SCOPE_SQL = text("""
    SELECT DISTINCT scope_key
    FROM company.document_scope
    WHERE company_id = :company_id AND scope_level = 'rule'
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

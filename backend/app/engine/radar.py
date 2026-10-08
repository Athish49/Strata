"""Radar stage (engine_spec.md section 7): screen out-of-footprint changes against company attributes.

Reads the run's persisted change_records (disposition='not_in_footprint', class substantive /
repealed / new_section), makes one cheap LLM call per change and writes engine.radar_items.
Works on any run whose Stage 1 is persisted, so it can also be re-run on an existing run
(scripts/run_radar.py).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path

from sqlalchemy import text

from app.engine.config import engine_settings
from app.engine.footprint import rule_key
from app.engine.llm import LLMBudget, LLMBudgetExceeded, LLMContext, call_cached
from app.engine.quotes import verify_quote
from app.engine.schemas import RadarResult

logger = logging.getLogger(__name__)

STAGE = "radar"
_PROMPT_PATH = Path(__file__).parent / "prompts" / "radar.md"
RADAR_CLASSES = ("substantive", "repealed", "new_section")
MAX_TEXT_CHARS = 6000
NO_CHANGE_REASON = "no change in obligation"

_CHANGES_SQL = text("""
    SELECT ch.change_id::text AS change_id, ch.citation, ch.rule_key, ch.heading, ch.change_class,
           ch.s1_text_norm, ch.s2_text_norm, ch.diff_segments,
           COALESCE(a.name, cs.owning_agency) AS agency
    FROM engine.change_records ch
    LEFT JOIN public.code_sections cs ON cs.id = COALESCE(ch.s2_section_id, ch.s1_section_id)
    LEFT JOIN public.agencies a ON a.agency_id = cs.agency_id
    WHERE ch.run_id = CAST(:run_id AS uuid) AND ch.disposition = 'not_in_footprint'
      AND ch.change_class = ANY(:classes)
    ORDER BY ch.citation
""")

_ATTRS_SQL = text("""
    SELECT key, value_text FROM company.company_attributes WHERE company_id = :company_id ORDER BY key
""")

# Every citation (section-level or rule-level) of an eligible clause, with its document.
_DOC_CITATIONS_SQL = text("""
    SELECT DISTINCT c.doc_id, cc.resolution_status, cc.citation_raw, cs.citation AS section_citation
    FROM company.clause_citations cc
    JOIN company.clauses c ON c.clause_pk = cc.clause_pk AND c.company_id = :company_id
    JOIN company.company_documents d ON d.doc_id = c.doc_id AND d.company_id = :company_id
    LEFT JOIN public.code_sections cs ON cs.id::text = cc.code_section_id::text
    WHERE c.assessable = true AND c.clause_role <> 'boilerplate'
      AND cc.resolution_status IN ('resolved', 'resolved_rule')
""")

_DOC_SCOPE_SQL = text("""
    SELECT DISTINCT doc_id, scope_key FROM company.document_scope
    WHERE company_id = :company_id AND scope_level = 'rule'
""")

_INSERT_SQL = text("""
    INSERT INTO engine.radar_items (run_id, change_id, obligation_changed, applicable, attribute_basis,
        affected_activity, reason, quote_s2, quote_verified, rule_covered_by_docs)
    VALUES (CAST(:run_id AS uuid), CAST(:change_id AS uuid), :obligation_changed, :applicable,
        :attribute_basis, :affected_activity, :reason, :quote_s2, :quote_verified, :rule_covered_by_docs)
    ON CONFLICT (run_id, change_id) DO UPDATE SET
        obligation_changed = EXCLUDED.obligation_changed, applicable = EXCLUDED.applicable,
        attribute_basis = EXCLUDED.attribute_basis, affected_activity = EXCLUDED.affected_activity,
        reason = EXCLUDED.reason, quote_s2 = EXCLUDED.quote_s2, quote_verified = EXCLUDED.quote_verified,
        rule_covered_by_docs = EXCLUDED.rule_covered_by_docs
""")


def _cap(s: str, n: int = MAX_TEXT_CHARS) -> str:
    return s if len(s) <= n else s[:n] + " [...truncated]"


def render_diff(segments) -> str:
    """Compact word diff: equal text as is, deletions as [-x-], insertions as {+x+}."""
    out: list[str] = []
    for seg in segments or []:
        t = seg.get("text", "")
        op = seg.get("op")
        out.append(f"[-{t}-]" if op == "delete" else f"{{+{t}+}}" if op == "insert" else t)
    return " ".join(out)


def _diff_for_prompt(segments, limit: int = MAX_TEXT_CHARS) -> str:
    """Render the diff; for long sections keep changed segments with a little context."""
    full = render_diff(segments)
    if len(full) <= limit:
        return full
    keep: set[int] = set()
    segs = list(segments or [])
    for i, s in enumerate(segs):
        if s.get("op") != "equal":
            keep.update({i - 1, i, i + 1})
    parts, last = [], -2
    for i, s in enumerate(segs):
        if i not in keep:
            continue
        if i != last + 1:
            parts.append("[...]")
        t = s.get("text", "")
        if s.get("op") == "equal" and len(t) > 300:
            t = t[:150] + " ... " + t[-150:]
        parts.append(f"[-{t}-]" if s.get("op") == "delete" else f"{{+{t}+}}" if s.get("op") == "insert" else t)
        last = i
    return _cap(" ".join(parts), limit)


def build_user_prompt(ch: dict, attrs: list[tuple[str, str]]) -> str:
    cls = ch["change_class"]
    if cls == "new_section":
        body = "New section (full S2 text):\n" + _cap(ch.get("s2_text_norm") or "")
    elif cls == "repealed":
        body = ("Repealed section. S1 text (the section no longer exists in S2):\n"
                + _cap(ch.get("s1_text_norm") or ""))
    else:
        body = "Word diff (S1 -> S2):\n" + _diff_for_prompt(ch.get("diff_segments"))
    attr_lines = "\n".join(f"{k}={v}" for k, v in attrs)
    return (f"Citation: {ch['citation']}\nHeading: {ch.get('heading') or ''}\n"
            f"Agency: {ch.get('agency') or ''}\nChange class: {cls}\n\n{body}\n\n"
            f"Company attributes:\n{attr_lines}")


def apply_rules(res: RadarResult, attr_keys: set[str], s2_text: str | None) -> dict:
    """Code rules of engine_spec section 7 applied to the raw model output."""
    basis = [k for k in dict.fromkeys(res.attribute_basis) if k in attr_keys]
    applicable, reason = res.applicable, res.reason
    if not res.obligation_changed:
        applicable, reason = "no", NO_CHANGE_REASON
    elif applicable == "yes" and not basis:
        applicable = "unclear"
    quote = res.quote_s2.strip() if res.quote_s2 and res.quote_s2.strip() else None
    verified = None if quote is None else bool(s2_text and verify_quote(quote, s2_text))
    return {"obligation_changed": res.obligation_changed, "applicable": applicable,
            "attribute_basis": basis, "affected_activity": res.affected_activity, "reason": reason,
            "quote_s2": quote, "quote_verified": verified}


async def load_rule_docs(session, company_id: str) -> dict[str, list[str]]:
    """rule_key -> sorted doc_ids that cite the rule at section or rule level, or scope it."""
    docs: dict[str, set[str]] = {}
    params = {"company_id": company_id}
    for r in (await session.execute(_DOC_CITATIONS_SQL, params)).mappings().all():
        src = r["section_citation"] if r["resolution_status"] == "resolved" else r["citation_raw"]
        rk = rule_key(src) or rule_key(r["citation_raw"])
        if rk:
            docs.setdefault(rk, set()).add(r["doc_id"])
    for r in (await session.execute(_DOC_SCOPE_SQL, params)).mappings().all():
        rk = rule_key(r["scope_key"]) or r["scope_key"]
        if rk:
            docs.setdefault(rk, set()).add(r["doc_id"])
    return {k: sorted(v) for k, v in docs.items()}


async def _radar_one(ch: dict, attrs, attr_keys, system: str, llm: LLMContext) -> dict | None:
    try:
        res = await call_cached(
            STAGE, engine_settings.ENGINE_RADAR_MODEL, system, build_user_prompt(ch, attrs),
            RadarResult, llm.run_id, llm=llm, unit_id=ch["change_id"],
        )
    except LLMBudgetExceeded as exc:
        logger.warning("radar skipped %s: %s", ch["citation"], exc)
        return None
    if res is None:
        return None
    return apply_rules(res, attr_keys, ch.get("s2_text_norm"))


async def run_radar(session_factory, run_id: str, company_id: str, max_calls: int) -> tuple[dict, int]:
    """Screen the run's out-of-footprint changes. Returns ({yes,no,unclear}, llm calls made)."""
    async with session_factory() as session:
        changes = [dict(r) for r in (await session.execute(
            _CHANGES_SQL, {"run_id": run_id, "classes": list(RADAR_CLASSES)})).mappings().all()]
        attrs = [(r["key"], r["value_text"]) for r in (await session.execute(
            _ATTRS_SQL, {"company_id": company_id})).mappings().all()]
        rule_docs = await load_rule_docs(session, company_id)
    stats = {"yes": 0, "no": 0, "unclear": 0}
    if not changes:
        return stats, 0

    system = _PROMPT_PATH.read_text()
    attr_keys = {k for k, _ in attrs}
    llm = LLMContext(run_id=uuid.UUID(run_id), budget=LLMBudget(max_calls=max(0, max_calls)))
    results = await asyncio.gather(*(_radar_one(c, attrs, attr_keys, system, llm) for c in changes))

    async with session_factory() as session:
        for ch, item in zip(changes, results):
            if item is None:
                continue
            stats[item["applicable"]] += 1
            await session.execute(_INSERT_SQL, {
                "run_id": run_id, "change_id": ch["change_id"], **item,
                "rule_covered_by_docs": rule_docs.get(ch["rule_key"], []),
            })
        await session.commit()
    skipped = sum(1 for r in results if r is None)
    if skipped:
        logger.warning("radar: %d changes got no valid result", skipped)
    logger.info("radar: %s (calls=%d, cache_hits=%d)", stats, llm.stats.calls_made, llm.stats.cache_hits)
    return stats, llm.stats.calls_made


async def run_stage(state) -> None:
    remaining = state.llm.max_calls - state.llm.calls_made
    stats, calls = await run_radar(state.session_factory, state.run_id,
                                   engine_settings.ENGINE_COMPANY_ID, remaining)
    state.llm.calls_made += calls
    state.stats["radar"] = stats

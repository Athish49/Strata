"""Stage 2: characterize each in-footprint substantive change with one LLM call (engine_spec.md section 2).

Code hints (parameters only in S1 / only in S2) go into the prompt; the answer is verified against the
source texts (``verify_characterization``) before it is trusted.  Changes with ``obligation_changed=false``
are closed here with "cleared with proof" direct_section candidates; the rest continue to Stage 3.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import text

from app.engine.config import engine_settings
from app.engine.delta import CandidateSpec, DeltaResult, Stage1Result, persist_stage1
from app.engine.llm import LLMBudget, LLMBudgetExceeded, LLMContext, call_cached
from app.engine.params_text import extract_parameters_from_text, param_multiset_diff
from app.engine.quotes import verify_quote
from app.engine.schemas import Characterization, ValueChange

logger = logging.getLogger(__name__)

STAGE = "characterize"
_PROMPT_PATH = Path(__file__).parent / "prompts" / "characterize.md"
NO_OBLIGATION = "no_obligation_change"


@dataclass
class VerifiedChar:
    """Outcome of Stage 2 for one change; value_changes / quotes hold only verified items."""
    change_id: str
    obligation_changed: bool | None       # None: the LLM output was unusable
    direction: str | None = None
    summary: str | None = None
    value_changes: list[ValueChange] = field(default_factory=list)
    added_requirements: list[str] = field(default_factory=list)
    removed_requirements: list[str] = field(default_factory=list)
    quotes: dict = field(default_factory=dict)
    disposition: str | None = None         # 'needs_review' | 'no_affected_clauses' | None
    reason: str | None = None


def _hint_key(p: dict) -> dict:
    # The parameter kind depends on nearby wording ("within 30 days" vs "30-day period"), so the kind is
    # ignored: the diff is keyed on (unit, value_num, day_type) only.
    return {**p, "kind": ""}


def param_hints(s1: str, s2: str) -> tuple[list[dict], list[dict]]:
    a, b = param_multiset_diff(
        [_hint_key(p) for p in extract_parameters_from_text(s1)],
        [_hint_key(p) for p in extract_parameters_from_text(s2)],
    )
    return a, b


def _fmt_params(params: list[dict]) -> str:
    if not params:
        return "(none)"
    return "\n".join(
        f"- {p['value_text']} (value={p['value_num']}, unit={p['unit']}, day_type={p['day_type']})"
        for p in params
    )


def _fmt_diff(segments: list[dict] | None) -> str:
    if not segments:
        return "(not available)"
    out = []
    for s in segments:
        if s["op"] == "equal":
            continue
        out.append(("[-" if s["op"] == "delete" else "[+") + s["text"] + "]")
    return " ".join(out) or "(no word changes)"


def build_user_prompt(r: DeltaResult) -> str:
    s1, s2 = r.s1_text_norm or "", r.s2_text_norm or ""
    only1, only2 = param_hints(s1, s2)
    return (
        f"Citation: {r.citation}\nHeading: {r.heading or ''}\n\n"
        f"S1 text:\n{s1}\n\nS2 text:\n{s2}\n\n"
        f"Word diff (deleted [-...], inserted [+...]):\n{_fmt_diff(r.diff_segments)}\n\n"
        f"params_only_in_s1:\n{_fmt_params(only1)}\n\nparams_only_in_s2:\n{_fmt_params(only2)}\n"
    )


def verify_characterization(change_id: str, c: Characterization, s1: str, s2: str) -> VerifiedChar:
    """Section 2.3: keep only quotes / value changes that are substrings of their source text."""
    vcs = [v for v in c.value_changes
           if verify_quote(v.old_value_text, s1) and verify_quote(v.new_value_text, s2)]
    added = [q for q in c.added_requirements if verify_quote(q, s2)]
    removed = [q for q in c.removed_requirements if verify_quote(q, s1)]
    quotes = {}
    q1, q2 = (c.quotes or {}).get("s1"), (c.quotes or {}).get("s2")
    if isinstance(q1, str) and verify_quote(q1, s1):
        quotes["s1"] = q1
    if isinstance(q2, str) and verify_quote(q2, s2):
        quotes["s2"] = q2
    v = VerifiedChar(change_id, c.obligation_changed, c.direction, c.summary, vcs, added, removed, quotes)
    if not c.obligation_changed:
        v.disposition, v.reason = "no_affected_clauses", c.summary
    elif not (vcs or added or removed or quotes):
        v.disposition = "needs_review"
        v.reason = "Characterization had no verifiable quote or value change; the judge decides"
    return v


async def characterize_one(r: DeltaResult, llm: LLMContext, system: str) -> VerifiedChar:
    try:
        res = await call_cached(
            STAGE, engine_settings.ENGINE_CHARACTERIZE_MODEL, system, build_user_prompt(r),
            Characterization, llm.run_id, llm=llm, unit_id=r.change_id,
        )
    except LLMBudgetExceeded as exc:
        return VerifiedChar(r.change_id, None, disposition="needs_review",
                            reason=f"Characterization skipped: {exc}")
    if res is None:
        return VerifiedChar(r.change_id, None, disposition="needs_review",
                            reason="Characterization failed (invalid model output); judged without it")
    return verify_characterization(r.change_id, res, r.s1_text_norm or "", r.s2_text_norm or "")


_UPDATE_SQL = text("""
    UPDATE engine.change_records
    SET obligation_changed = :obligation_changed, direction = :direction, summary = :summary,
        value_changes = CAST(:value_changes AS jsonb), char_quotes = CAST(:char_quotes AS jsonb),
        disposition = COALESCE(:disposition, disposition),
        disposition_reason = CASE WHEN :disposition IS NULL THEN disposition_reason ELSE :reason END
    WHERE change_id = CAST(:change_id AS uuid)
""")


async def run_stage(state) -> None:
    from app.engine.candidates import ChangeRow, build_candidates_from_data, get_candidate_data

    todo = [r for r in state.stage1.results if r.change_class == "substantive" and r.in_footprint]
    state.characterized = {}
    stats = {"changes": len(todo), "obligation_changed": 0, "no_obligation_change": 0,
             "needs_review": 0, "invalid": 0}
    state.stats["characterize"] = stats
    if not todo:
        return

    system = _PROMPT_PATH.read_text()
    llm = LLMContext(run_id=uuid.UUID(state.run_id),
                     budget=LLMBudget(max_calls=max(0, state.llm.max_calls - state.llm.calls_made)))
    results = await asyncio.gather(*(characterize_one(r, llm, system) for r in todo))
    state.llm.calls_made += llm.stats.calls_made

    by_id = {r.change_id: r for r in todo}
    no_ob: list[DeltaResult] = []
    for v in results:
        state.characterized[v.change_id] = v
        r = by_id[v.change_id]
        if v.disposition:
            r.disposition, r.disposition_reason = v.disposition, v.reason
        if v.obligation_changed is None:
            stats["invalid"] += 1
        elif v.obligation_changed:
            stats["obligation_changed"] += 1
        else:
            stats["no_obligation_change"] += 1
            no_ob.append(r)
        if v.disposition == "needs_review":
            stats["needs_review"] += 1

    cand_specs: list[CandidateSpec] = []
    async with state.session_factory() as session:
        if no_ob:
            data = await get_candidate_data(state, session)
            rows = build_candidates_from_data(data, state.run_id, [
                ChangeRow(r.change_id, r.change_class, r.s1_section_id, r.citation, r.rule_key)
                for r in no_ob])
            summaries = {r.change_id: state.characterized[r.change_id].summary for r in no_ob}
            for c in rows:
                if c.match_path != "direct_section":
                    continue
                c.skip_reason, c.affected, c.rationale = NO_OBLIGATION, False, summaries[c.change_id]
                cand_specs.append(c)
            if cand_specs:
                await persist_stage1(session, state.run_id, Stage1Result([], cand_specs))
        for v in results:
            await session.execute(_UPDATE_SQL, {
                "change_id": v.change_id,
                "obligation_changed": v.obligation_changed,
                "direction": v.direction,
                "summary": v.summary,
                "value_changes": json.dumps([x.model_dump(mode="json") for x in v.value_changes]),
                "char_quotes": json.dumps(v.quotes),
                "disposition": v.disposition,
                "reason": v.reason,
            })
        await session.commit()
    stats["cleared_candidates"] = len(cand_specs)
    logger.info("characterize: %s", stats)

"""Stage 4: rules R1-R3 then the LLM judge with post-rules P1-P6 (engine_spec.md section 4).

Open candidates (judged_by and skip_reason both NULL) of the run are joined with their change
record and clause data.  ``apply_rules`` decides what it can; the rest go to the LLM judge
(stage 'judge').  Writes engine.candidates (judged_by, affected, rationale) and engine.findings.
Route_* and propagated_from are filled later by the ledger.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import text

from app.engine import llm as L
from app.engine.config import LLM_CONCURRENCY, engine_settings
from app.engine.diffing import changed_token_char_spans, changed_tokens
from app.engine.quotes import verify_quote
from app.engine.rules import (
    FindingDraft,
    RuleCandidate,
    RuleChange,
    RuleClause,
    apply_rules,
    map_verdict,
    severity_for,
)
from app.engine.schemas import JudgeResult, ValueChange
from app.engine.textnorm import strip_metadata

logger = logging.getLogger(__name__)

STAGE = "judge"
SYSTEM_PROMPT = (Path(__file__).parent / "prompts" / "judge.md").read_text(encoding="utf-8")
# Role guidance is appended to the system prompt ONLY for these clause roles, so the text sent for every
# other role stays byte-identical to the base prompt (LLM cache keys hash system+user text).
RESTATING_ROLES = frozenset({"regulatory_restatement", "definition"})
ROLE_GUIDANCE = """

## Clause role
When the user message gives a "Clause role" of `regulatory_restatement` or `definition`, the clause is meant to reproduce, summarize or define the cited rule. Compare its wording and values to the S2 text: a restatement or definition that no longer matches S2 IS affected (use the finding_type definitions above), even though it only restates the rule. If it still matches S2, set `affected=false`. All other rules, including verbatim quotes and never speculating, are unchanged."""
UNAVAILABLE = "LLM judgement unavailable"
STALE_ELIGIBLE = {"parameter_change", "required_content_change", "conflict", "new_requirement_gap"}
HUNK_SEP = "\n[...]\n"
MAX_EQUAL_CHARS = 240  # equal runs in the rendered word diff are trimmed to this many chars


# ---------------------------------------------------------------- data holders
@dataclass
class JudgeItem:
    """One open candidate with everything the judge needs."""
    candidate_id: str
    change_id: str
    clause_pk: str
    clause_id: str
    doc_id: str
    cited_citation: str | None
    match_path: str
    path_detail: list[dict]
    # change
    citation: str
    change_class: str
    origin: str
    source_system: str
    heading: str | None
    direction: str | None
    summary: str | None
    value_changes: list[ValueChange]
    char_quotes: dict | None
    s1_text_norm: str | None
    s2_text_norm: str | None
    diff_segments: list[dict] | None
    renumbered_from: str | None
    published_date: date | None
    # clause
    doc_title: str | None
    heading_path: list[str] | None
    unit_kind: str | None
    text_raw: str
    parameters: list[dict] = field(default_factory=list)
    approved_date: date | None = None
    clause_role: str | None = None


@dataclass
class Outcome:
    """What to persist for one candidate."""
    judged_by: str                      # 'rule' | 'llm'
    affected: bool | None
    rationale: str
    finding: FindingDraft | None = None
    needs_review: bool = False


# ---------------------------------------------------------------- prompt building
def render_diff(segments: list[dict] | None) -> str:
    """Word diff as text: [-deleted-] {+inserted+}; long equal runs keep only their edges."""
    if not segments:
        return "(no word diff)"
    parts: list[str] = []
    for seg in segments:
        t = seg.get("text", "")
        op = seg.get("op")
        if op == "delete":
            parts.append(f"[-{t}-]")
        elif op == "insert":
            parts.append(f"{{+{t}+}}")
        else:
            if len(t) > 2 * MAX_EQUAL_CHARS:
                t = t[:MAX_EQUAL_CHARS] + " ... " + t[-MAX_EQUAL_CHARS:]
            parts.append(t)
    return " ".join(parts)


def _merge(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for s, e in sorted(ranges):
        if out and s <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def window_texts(s1: str | None, s2: str | None, max_chars: int, window: int) -> tuple[str, str]:
    """Return the S1/S2 texts to send.  A text longer than max_chars is reduced to +-window
    char windows around the diff hunks (joined by a marker); shorter texts are sent whole."""
    s1, s2 = s1 or "", s2 or ""
    if len(s1) <= max_chars and len(s2) <= max_chars:
        return s1, s2
    ch = changed_tokens(s1, s2)

    def cut(txt: str, side: str) -> str:
        if len(txt) <= max_chars:
            return txt
        spans = changed_token_char_spans(txt, ch[side])
        if not spans:
            return txt[:max_chars]
        rngs = _merge([(max(0, s - window), min(len(txt), e + window)) for s, e in spans])
        pieces = [txt[a:b] for a, b in rngs]
        if rngs[0][0] > 0:
            pieces[0] = "..." + pieces[0]
        return HUNK_SEP.join(pieces)

    return cut(s1, "deleted"), cut(s2, "inserted")


def match_path_words(item: JudgeItem) -> str:
    """The way this clause was matched to the change, in plain words."""
    phrases: list[str] = []
    entries = item.path_detail or [{"path": item.match_path}]
    for e in entries:
        p = e.get("path")
        if p == "direct_section":
            phrases.append(f"the clause cites this section ({e.get('value') or item.citation})")
        elif p == "direct_rule":
            phrases.append(f"the clause cites the rule that contains this section ({e.get('value') or item.citation})")
        elif p == "register_hop":
            phrases.append(f"the clause is linked from clause {e.get('via_clause_id')} "
                           f"via {e.get('link_type')}, and that clause cites this section")
        elif p == "value_echo":
            phrases.append(f"the clause states the value {e.get('value')!r}, which equals a value that changed")
    return "; ".join(phrases) or item.match_path


def _upfirst(s: str) -> str:
    return s[:1].upper() + s[1:]


def _fmt_vc(vc: ValueChange) -> str:
    extra = f", {vc.day_type} days" if vc.day_type else ""
    unit = f" {vc.unit}" if vc.unit else ""
    return f"- {vc.subject}: '{vc.old_value_text}' -> '{vc.new_value_text}' ({vc.kind}{unit}{extra})"


def _fmt_param(p: dict) -> str:
    bits = [str(p.get("kind") or "")]
    if p.get("unit"):
        bits.append(str(p["unit"]))
    if p.get("day_type"):
        bits.append(str(p["day_type"]))
    return f"- '{p.get('value_text')}' ({', '.join(b for b in bits if b)})"


def system_prompt_for(item: JudgeItem) -> str:
    """Base system prompt, plus the role guidance only for restating/definition clauses."""
    return SYSTEM_PROMPT + ROLE_GUIDANCE if item.clause_role in RESTATING_ROLES else SYSTEM_PROMPT


def build_user_prompt(item: JudgeItem, max_chars: int | None = None, window: int | None = None) -> str:
    max_chars = engine_settings.ENGINE_JUDGE_MAX_SECTION_CHARS if max_chars is None else max_chars
    window = engine_settings.ENGINE_JUDGE_WINDOW_CHARS if window is None else window
    sys_ = item.source_system
    s1 = strip_metadata(item.s1_text_norm, sys_) if item.s1_text_norm else ""
    s2 = strip_metadata(item.s2_text_norm, sys_) if item.s2_text_norm else ""
    s1_send, s2_send = window_texts(s1, s2, max_chars, window)
    vcs = "\n".join(_fmt_vc(v) for v in item.value_changes) or "(none)"
    cq = item.char_quotes or {}
    core = "\n".join(f"- {k.upper()}: {v}" for k, v in cq.items() if isinstance(v, str) and v) or "(none)"
    params = "\n".join(_fmt_param(p) for p in item.parameters) or "(none)"
    heading_path = " > ".join(item.heading_path or []) or "(none)"
    renum = f"\nRenumbered from: {item.renumbered_from}" if item.renumbered_from else ""
    role_line = f"\nClause role: {item.clause_role}" if item.clause_role in RESTATING_ROLES else ""
    return f"""## The regulatory change
Citation: {item.citation}{renum}
Heading: {item.heading or '(none)'}
Change class: {item.change_class}
Direction: {item.direction or '(unknown)'}
Summary: {item.summary or '(none)'}

Value changes:
{vcs}

Core change quotes (from the characterization):
{core}

Word diff (S1 -> S2; [-deleted-], {{+inserted+}}):
{render_diff(item.diff_segments)}

### S1 text (old)
{s1_send or '(none: the section did not exist)'}

### S2 text (new)
{s2_send or '(none: the section was repealed)'}

## The company clause
Clause id: {item.clause_id}
Document: {item.doc_title or item.doc_id}
Heading path: {heading_path}
Unit kind: {item.unit_kind or '(unknown)'}{role_line}
Parameters in the clause:
{params}

Clause text:
{item.text_raw}

## How this clause was matched to the change
{_upfirst(match_path_words(item))}.
"""


# ---------------------------------------------------------------- post-rules
def _clean(q: Any) -> str | None:
    return q if isinstance(q, str) and q.strip() else None


def verify_result_quotes(res: JudgeResult, item: JudgeItem) -> list[str]:
    """P1 checks: [] when s1 in S1, s2 in S2, clause in text_raw (absent s1/s2 are skipped)."""
    q = res.quotes or {}
    errs: list[str] = []
    s1, s2, cl = _clean(q.get("s1")), _clean(q.get("s2")), _clean(q.get("clause"))
    if s1 and not verify_quote(s1, item.s1_text_norm or ""):
        errs.append("quotes.s1 is not a verbatim excerpt of the S1 text")
    if s2 and not verify_quote(s2, item.s2_text_norm or ""):
        errs.append("quotes.s2 is not a verbatim excerpt of the S2 text")
    if not cl:
        errs.append("quotes.clause is missing")
    elif not verify_quote(cl, item.text_raw or ""):
        errs.append("quotes.clause is not a verbatim excerpt of the clause text")
    return errs


def finalize(res: JudgeResult, item: JudgeItem, quotes_ok: bool) -> Outcome:
    """P2-P5 on an affected result whose P1 outcome is `quotes_ok`."""
    ft = res.finding_type
    needs_review = False
    if ft == "stale_at_approval":  # the LLM must not pick it; code assigns it in P3
        ft = "required_content_change"
    if not quotes_ok:  # P1
        ft, needs_review = "informational", True
    if res.confidence < engine_settings.ENGINE_MIN_CONFIDENCE:  # P2
        ft, needs_review = "informational", True
    if (item.origin == "kb" and item.published_date is not None  # P3
            and item.approved_date is not None
            and item.published_date <= item.approved_date and ft in STALE_ELIGIBLE):
        ft = "stale_at_approval"
    verdict = map_verdict(ft, item.direction, needs_review)  # P4
    severity = "low" if ft in ("stale_citation", "informational") else res.severity  # P5
    q = res.quotes or {}
    draft = FindingDraft(
        finding_type=ft, severity=severity, verdict=verdict,
        required_change=res.required_change or {},
        quotes={"s1": _clean(q.get("s1")), "s2": _clean(q.get("s2")), "clause": q.get("clause") or ""},
        quotes_verified=quotes_ok, rationale=res.rationale, confidence=res.confidence,
        decided_by="llm",
    )
    return Outcome("llm", True, res.rationale, draft, needs_review)


def unavailable(why: str = UNAVAILABLE) -> Outcome:
    draft = FindingDraft(
        finding_type="informational", severity="low",
        verdict=map_verdict("informational", None, True), required_change={},
        quotes={"s1": None, "s2": None, "clause": ""}, quotes_verified=False,
        rationale=why, confidence=None, decided_by="llm",
    )
    return Outcome("llm", None, why, draft, True)


async def judge_item(item: JudgeItem, run_id: str, llm_ctx: L.LLMContext, model: str) -> Outcome:
    """LLM judge + post-rules for one candidate."""
    user = build_user_prompt(item)
    prompt = user
    res: JudgeResult | None = None
    for attempt in (1, 2):
        try:
            res = await L.call_cached(STAGE, model, system_prompt_for(item), prompt, JudgeResult,
                                      uuid.UUID(run_id) if run_id else None,
                                      llm=llm_ctx, unit_id=item.candidate_id)
        except L.LLMBudgetExceeded:
            return unavailable(f"{UNAVAILABLE} (LLM call cap reached)")
        if res is None:
            return unavailable()
        if not res.affected:  # P6
            return Outcome("llm", False, res.rationale)
        errs = verify_result_quotes(res, item)  # P1
        if not errs:
            return finalize(res, item, True)
        if attempt == 1:
            prompt = (user + "\n\n## Correction needed\nYour previous answer failed quote verification: "
                      + "; ".join(errs) + ". Quote verbatim from the provided texts only.")
    return finalize(res, item, False)


# ---------------------------------------------------------------- rules bridge
def _rule_objs(item: JudgeItem) -> tuple[RuleChange, RuleClause, RuleCandidate]:
    ch = RuleChange(
        change_id=item.change_id, citation=item.citation, change_class=item.change_class,
        direction=item.direction, summary=item.summary, value_changes=item.value_changes,
        s1_text_norm=item.s1_text_norm, s2_text_norm=item.s2_text_norm,
        renumbered_from=item.renumbered_from, origin=item.origin,
        published_date=item.published_date,
    )
    cl = RuleClause(clause_pk=item.clause_pk, clause_id=item.clause_id, doc_id=item.doc_id,
                    text_raw=item.text_raw, parameters=item.parameters)
    cand = RuleCandidate(candidate_id=item.candidate_id, cited_citation=item.cited_citation,
                         match_path=item.match_path, skip_reason=None)
    return ch, cl, cand


def decide_by_rules(item: JudgeItem) -> Outcome | None:
    d = apply_rules(*_rule_objs(item))
    if d is None or not d.decided:
        return None
    if d.cleared or d.finding is None:
        return Outcome("rule", False, d.rationale)
    f = d.finding
    if not f.quotes_verified and f.finding_type != "informational":
        # unverified evidence never stands as a finding (architecture guardrail 3): downgrade for review
        f.finding_type = "informational"
        f.severity = severity_for("informational")
        f.verdict = map_verdict("informational", None, needs_review=True)
        return Outcome("rule", True, d.rationale, f, needs_review=True)
    return Outcome("rule", True, d.rationale, f, needs_review=False)


# ---------------------------------------------------------------- DB
_OPEN_SQL = text("""
    SELECT k.candidate_id::text AS candidate_id, k.change_id::text AS change_id,
           k.clause_pk::text AS clause_pk, k.clause_id, k.doc_id, k.cited_citation,
           k.match_path, k.path_detail,
           r.citation, r.change_class, r.origin, r.source_system, r.heading, r.direction,
           r.summary, r.value_changes, r.char_quotes, r.s1_text_norm, r.s2_text_norm,
           r.diff_segments, r.renumbered_from, r.published_date,
           d.title AS doc_title, c.heading_path, c.unit_kind, c.clause_role, c.text_raw, v.approved_date
    FROM engine.candidates k
    JOIN engine.change_records r ON r.change_id = k.change_id
    JOIN company.clauses c ON c.clause_pk = k.clause_pk
    LEFT JOIN company.company_documents d
           ON d.company_id = c.company_id AND d.doc_id = c.doc_id
    LEFT JOIN company.document_versions v ON v.version_id = d.current_version_id
    WHERE k.run_id = CAST(:run_id AS uuid) AND k.judged_by IS NULL AND k.skip_reason IS NULL
    ORDER BY k.change_id, k.clause_id
""")

_PARAMS_SQL = text("""
    SELECT clause_pk::text AS clause_pk, kind, value_text, value_num, unit, day_type,
           span_start, span_end, COALESCE(is_citation_fragment, false) AS is_citation_fragment
    FROM company.clause_parameters WHERE clause_pk = ANY(CAST(:pks AS uuid[]))
""")

_UPDATE_CAND_SQL = text("""
    UPDATE engine.candidates SET judged_by = :judged_by, affected = :affected, rationale = :rationale
    WHERE candidate_id = CAST(:candidate_id AS uuid)
""")

_INSERT_FINDING_SQL = text("""
    INSERT INTO engine.findings
        (finding_id, run_id, change_id, candidate_id, clause_pk, clause_id, doc_id, citation,
         finding_type, severity, verdict, needs_review, required_change, quotes, quotes_verified,
         rationale, confidence, decided_by, match_path)
    VALUES
        (CAST(:finding_id AS uuid), CAST(:run_id AS uuid), CAST(:change_id AS uuid),
         CAST(:candidate_id AS uuid), CAST(:clause_pk AS uuid), :clause_id, :doc_id, :citation,
         :finding_type, :severity, :verdict, :needs_review, CAST(:required_change AS jsonb),
         CAST(:quotes AS jsonb), :quotes_verified, :rationale, :confidence, :decided_by, :match_path)
""")


def _jsonish(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return None
    return v


async def load_open_items(session, run_id: str) -> list[JudgeItem]:
    rows = (await session.execute(_OPEN_SQL, {"run_id": run_id})).mappings().all()
    if not rows:
        return []
    pks = sorted({r["clause_pk"] for r in rows})
    params: dict[str, list[dict]] = {}
    for p in (await session.execute(_PARAMS_SQL, {"pks": pks})).mappings().all():
        d = dict(p)
        params.setdefault(d["clause_pk"], []).append(d)
    items: list[JudgeItem] = []
    for r in rows:
        r = dict(r)
        vcs = [ValueChange.model_validate(v) for v in (_jsonish(r["value_changes"]) or [])]
        cq = _jsonish(r["char_quotes"]) or None
        items.append(JudgeItem(
            candidate_id=r["candidate_id"], change_id=r["change_id"], clause_pk=r["clause_pk"],
            clause_id=r["clause_id"], doc_id=r["doc_id"], cited_citation=r["cited_citation"],
            match_path=r["match_path"], path_detail=_jsonish(r["path_detail"]) or [],
            citation=r["citation"], change_class=r["change_class"], origin=r["origin"],
            source_system=r["source_system"], heading=r["heading"], direction=r["direction"],
            summary=r["summary"], value_changes=vcs, char_quotes=cq,
            s1_text_norm=r["s1_text_norm"], s2_text_norm=r["s2_text_norm"],
            diff_segments=_jsonish(r["diff_segments"]), renumbered_from=r["renumbered_from"],
            published_date=r["published_date"], doc_title=r["doc_title"],
            heading_path=list(r["heading_path"] or []), unit_kind=r["unit_kind"],
            text_raw=r["text_raw"] or "", parameters=params.get(r["clause_pk"], []),
            approved_date=r["approved_date"], clause_role=r["clause_role"],
        ))
    return items


async def _persist(session_factory, run_id: str, item: JudgeItem, out: Outcome) -> None:
    async with session_factory() as session:
        await session.execute(_UPDATE_CAND_SQL, {
            "candidate_id": item.candidate_id, "judged_by": out.judged_by,
            "affected": out.affected, "rationale": out.rationale,
        })
        f = out.finding
        if f is not None:
            await session.execute(_INSERT_FINDING_SQL, {
                "finding_id": str(uuid.uuid4()), "run_id": run_id, "change_id": item.change_id,
                "candidate_id": item.candidate_id, "clause_pk": item.clause_pk,
                "clause_id": item.clause_id, "doc_id": item.doc_id,
                "citation": item.cited_citation or item.citation,
                "finding_type": f.finding_type, "severity": f.severity, "verdict": f.verdict,
                "needs_review": out.needs_review,
                "required_change": json.dumps(f.required_change) if f.required_change else None,
                "quotes": json.dumps(f.quotes), "quotes_verified": f.quotes_verified,
                "rationale": f.rationale, "confidence": f.confidence,
                "decided_by": f.decided_by, "match_path": item.match_path,
            })
        await session.commit()


async def run_stage(state) -> None:
    """Stage 4 entry point (run.py stage protocol)."""
    async with state.session_factory() as session:
        items = await load_open_items(session, state.run_id)

    stats = state.stats
    n_rule = n_llm = 0
    by_verdict: dict[str, int] = dict(stats.get("findings") or {})
    pending: list[JudgeItem] = []
    for it in items:
        out = decide_by_rules(it)
        if out is None:
            pending.append(it)
            continue
        await _persist(state.session_factory, state.run_id, it, out)
        n_rule += 1
        if out.finding:
            by_verdict[out.finding.verdict] = by_verdict.get(out.finding.verdict, 0) + 1

    # budget bridge: llm.py has its own context type; sync the call count back afterwards
    budget = L.LLMBudget(max_calls=state.llm.max_calls, used=state.llm.calls_made)
    llm_ctx = L.LLMContext(run_id=uuid.UUID(state.run_id), budget=budget)
    model = engine_settings.ENGINE_JUDGE_MODEL
    sem = asyncio.Semaphore(LLM_CONCURRENCY)

    async def work(it: JudgeItem) -> tuple[JudgeItem, Outcome]:
        async with sem:
            try:
                out = await judge_item(it, state.run_id, llm_ctx, model)
            except Exception as exc:  # noqa: BLE001 - one bad candidate must not kill the stage
                logger.exception("judge failed for candidate %s", it.candidate_id)
                out = unavailable(f"{UNAVAILABLE} ({type(exc).__name__})")
        await _persist(state.session_factory, state.run_id, it, out)
        return it, out

    for it, out in await asyncio.gather(*(work(i) for i in pending)):
        n_llm += 1
        if out.finding:
            by_verdict[out.finding.verdict] = by_verdict.get(out.finding.verdict, 0) + 1

    state.llm.calls_made = budget.used
    stats["judged_rule"] = stats.get("judged_rule", 0) + n_rule
    stats["judged_llm"] = stats.get("judged_llm", 0) + n_llm
    stats["findings"] = by_verdict
    logger.info("judge: %d by rule, %d by llm, findings=%s", n_rule, n_llm, by_verdict)

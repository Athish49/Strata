"""Stage 4 deterministic rules R1-R4 (engine_spec §4.1) and the P4/P5 mappings (§4.3).

Pure functions: no DB, no network. `apply_rules` returns None when the candidate
must be handed to the LLM judge.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.engine.quotes import verify_quote
from app.engine.schemas import ValueChange

R1_RATIONALE = "Cited section repealed in S2; confirm whether the obligation can be removed."
CONTEXT_CHARS = 80
_SENT_END = ".;!?\n"


@dataclass
class RuleChange:
    change_id: str
    citation: str
    change_class: str
    direction: str | None = None
    summary: str | None = None
    value_changes: list[ValueChange] = field(default_factory=list)
    s1_text_norm: str | None = None
    s2_text_norm: str | None = None
    renumbered_from: str | None = None
    origin: str = "kb"
    published_date: Any = None


@dataclass
class RuleClause:
    clause_pk: Any
    clause_id: str
    doc_id: str
    text_raw: str
    parameters: list[dict] = field(default_factory=list)


@dataclass
class RuleCandidate:
    candidate_id: Any
    cited_citation: str | None
    match_path: str
    skip_reason: str | None = None


@dataclass
class FindingDraft:
    finding_type: str
    severity: str
    verdict: str
    required_change: dict
    quotes: dict
    quotes_verified: bool
    rationale: str
    confidence: float | None = None
    decided_by: str = "rule"


@dataclass
class RuleDecision:
    decided: bool
    finding: FindingDraft | None = None
    cleared: bool = False
    rationale: str = ""


# ---- P4 / P5 (shared with judge.py) ----
def map_verdict(finding_type: str, direction: str | None, needs_review: bool = False) -> str:
    if finding_type == "informational":
        return "review" if needs_review else "info"
    if finding_type == "stale_citation":
        return "update_citation"
    if direction == "relaxed":
        return "optional_relaxed"
    return "action_required"


def severity_for(finding_type: str) -> str:
    return "low" if finding_type in ("stale_citation", "informational") else "high"


# ---- helpers ----
def _singular(unit: str | None) -> str | None:
    if unit is None:
        return None
    u = unit.strip().lower()
    if len(u) > 3 and u.endswith("ies"):
        return u[:-3] + "y"
    if len(u) > 1 and u.endswith("s") and not u.endswith("ss"):
        return u[:-1]
    return u


def _day_type_ok(a: str | None, b: str | None) -> bool:
    return a is None or b is None or a.lower() == b.lower()


def _eligible(p: dict) -> bool:
    if p.get("is_citation_fragment"):
        return False
    return p.get("kind") != "number" or p.get("unit") is not None


def _find_ci(text: str | None, needle: str) -> int:
    if not text or not needle:
        return -1
    return text.lower().find(needle.strip().lower())


def _window(text: str, start: int, end: int) -> str:
    """Text around [start, end) within +-CONTEXT_CHARS, trimmed to sentence bounds."""
    lo, hi = max(0, start - CONTEXT_CHARS), min(len(text), end + CONTEXT_CHARS)
    cut = max(text.rfind(c, lo, start) for c in _SENT_END)
    if cut >= 0:
        lo = cut + 1
    cuts = [i for i in (text.find(c, end, hi) for c in _SENT_END) if i >= 0]
    if cuts:
        hi = min(cuts) + 1
    return text[lo:hi].strip()


def _value_context(text: str | None, value_text: str) -> tuple[str, bool]:
    pos = _find_ci(text, value_text)
    if pos < 0:
        return "", False
    return _window(text, pos, pos + len(value_text.strip())), True


def _verified(vc: ValueChange, change: RuleChange) -> bool:
    """The characterization's old/new values must be present in the section texts."""
    if vc.old_value_num is None:
        return False
    return _find_ci(change.s1_text_norm, vc.old_value_text) >= 0 and \
        _find_ci(change.s2_text_norm, vc.new_value_text) >= 0


def _match_param(clause: RuleClause, vc: ValueChange) -> dict | None:
    for p in clause.parameters:
        if not _eligible(p) or p.get("value_num") is None:
            continue
        if float(p["value_num"]) != float(vc.old_value_num):
            continue
        if _singular(p.get("unit")) != _singular(vc.unit):
            continue
        if not _day_type_ok(p.get("day_type"), vc.day_type):
            continue
        return p
    return None


# ---- rules ----
def _stale(change: RuleChange, candidate: RuleCandidate, from_t: str, to_t: str, why: str) -> RuleDecision:
    ft = "stale_citation"
    draft = FindingDraft(
        finding_type=ft, severity=severity_for(ft),
        verdict=map_verdict(ft, change.direction),
        required_change={"from_text": from_t, "to_text": to_t},
        quotes={"s1": None, "s2": None, "clause": from_t},
        quotes_verified=True, rationale=why,
    )
    return RuleDecision(decided=True, finding=draft, rationale=why)


def _r3(change: RuleChange, clause: RuleClause) -> RuleDecision | None:
    for vc in change.value_changes or []:
        if not _verified(vc, change):
            continue
        p = _match_param(clause, vc)
        if p is None:
            continue
        s1q, ok1 = _value_context(change.s1_text_norm, vc.old_value_text)
        s2q, ok2 = _value_context(change.s2_text_norm, vc.new_value_text)
        cq = ""
        if p.get("span_start") is not None and p.get("span_end") is not None:
            cq = _window(clause.text_raw, p["span_start"], p["span_end"])
        if not cq or _find_ci(cq, p["value_text"]) < 0:
            # stored span does not index into this clause text: locate the value by text instead
            cq, _ = _value_context(clause.text_raw, p["value_text"])
        quotes = {"s1": s1q, "s2": s2q, "clause": cq}
        verified = (
            ok1 and ok2 and bool(cq)
            and verify_quote(s1q, change.s1_text_norm or "")
            and verify_quote(s2q, change.s2_text_norm or "")
            and verify_quote(cq, clause.text_raw or "")
        )
        ft = "parameter_change"
        why = (f"Clause states {p['value_text']}; {change.citation} now requires "
               f"{vc.new_value_text} ({vc.subject}).")
        draft = FindingDraft(
            finding_type=ft, severity=severity_for(ft),
            verdict=map_verdict(ft, change.direction),
            required_change={"from_text": p["value_text"], "to_text": vc.new_value_text},
            quotes=quotes, quotes_verified=verified, rationale=why,
        )
        return RuleDecision(decided=True, finding=draft, rationale=why)
    return None


def apply_rules(change: RuleChange, clause: RuleClause,
                candidate: RuleCandidate) -> RuleDecision | None:
    # R4
    if candidate.skip_reason:
        return RuleDecision(decided=True, cleared=True,
                            rationale=f"Skipped: {candidate.skip_reason}")
    direct = candidate.match_path == "direct_section"
    cited = candidate.cited_citation or change.citation
    # R1
    if change.change_class == "repealed" and direct:
        return _stale(change, candidate, cited, "(repealed)", R1_RATIONALE)
    # R2
    if change.change_class == "renumbered" and direct:
        old = change.renumbered_from or cited
        why = f"Cited section {old} was renumbered to {change.citation} in S2."
        return _stale(change, candidate, old, change.citation, why)
    # R3
    return _r3(change, clause)

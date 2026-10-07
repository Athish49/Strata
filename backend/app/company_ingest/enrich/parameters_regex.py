"""Task 4.1.2 — Numeric and unit parameter extraction (regex pass).

Public API
----------
    enrich_parameters(units, ctx) -> None

Appends ParameterEntry objects to unit.parameters for each ClauseUnit in
*units*.  This is a pure in-memory enrichment pass; it never writes to DB.

Design notes
------------
- Three passes per clause: (1) dollar-prefix amounts, (2) number+unit matches,
  (3) bare digit numbers (only when ≥1 citation is present).
- Forbidden spans are computed once per clause from exclusion patterns and
  citation spans found via find_citation_spans.
- Claimed spans are tracked across all three passes to avoid duplicate entries.
- Qualifier is found by tokenising the 6 words before the number.
- Kind is determined by context rules (RECORD_RETENTION and DEADLINE override
  the generic time-unit+qualifier → PERIOD rule, because "due within 5 days"
  is a deadline, not a period).
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from ..constants import DayType, ParameterKind
from ..parse.models import ClauseUnit
from ..parse.numbers import words_to_number
from ..parse.text import find_verbatim
from ..run_context import RunContext
from .citations_grammar import find_citation_spans
from .parameter_entry import ParameterEntry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Unit map  (regex pattern → canonical unit string)
# ---------------------------------------------------------------------------

UNIT_MAP: dict[str, str] = {
    r"business\s+days?": "business_day",
    r"calendar\s+days?": "calendar_day",
    r"working\s+days?": "working_day",
    r"days?": "day",
    r"hours?|hrs?": "hour",
    r"minutes?|mins?": "minute",
    r"months?": "month",
    r"years?|yr\b": "year",
    r"percent(?:age)?|%": "percent",
    r"gallons?|gal\b": "gallon",
    r"kva\b": "kva",
    r"kv\b": "kv",
    r"customers?": "customer",
    r"meters?": "meter",
    r"miles?": "mile",
    r"\$": "usd",
}

# ---------------------------------------------------------------------------
# Qualifier map  (regex pattern → Qualifier value string)
# ---------------------------------------------------------------------------

QUALIFIER_MAP: dict[str, str] = {
    r"not\s+less\s+than": "at_least",
    r"not\s+more\s+than": "not_more_than",
    r"no\s+later\s+than": "not_more_than",
    r"at\s+least": "at_least",
    r"prior\s+to": "prior_to",
    r"within\b": "within",
    r"after\b": "after",
    r"exactly\b": "exactly",
}

# ---------------------------------------------------------------------------
# Build compiled component patterns
# ---------------------------------------------------------------------------

# ones / teens / twenty (used as sub-patterns)
_ONES_PAT = (
    "zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    "eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
    "eighteen|nineteen|twenty"
)
# tens  (twenty included for bare-tens and compound patterns)
_TENS_PAT = "twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"

# Word number alternatives — longest first so the engine prefers them.
# \b … \b boundaries prevent matching inside other words.
_WORD_NUM_INNER = (
    # fractions
    r"one-half|one-quarter|three-quarters|one-third|two-thirds"
    # compound: thirty-five, twenty-one …
    rf"|(?:{_TENS_PAT})-(?:{_ONES_PAT})"
    # compound: thirty five …
    rf"|(?:{_TENS_PAT})\s+(?:{_ONES_PAT})"
    # X thousand / X hundred
    rf"|(?:{_ONES_PAT})\s+thousand"
    rf"|(?:{_ONES_PAT})\s+hundred"
    # bare magnitudes
    r"|thousand|hundred"
    # bare tens: thirty, forty …
    rf"|{_TENS_PAT}"
    # bare ones / teens / twenty
    rf"|{_ONES_PAT}"
)

_WORD_NUM = rf"\b(?:{_WORD_NUM_INNER})\b"

# Digit number with left boundary (no preceding digit / dot / comma / hyphen).
# Two alternatives: comma-formatted ("2,500") must come before plain ("2500").
_DIGIT_NUM = r"(?<![.\d,\-])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"

# Parenthetical forms:  "fourteen (14)"  or  "10 (10)"
_PAREN_WORD = rf"(?:{_WORD_NUM})\s*\(\d+\)"
_PAREN_DIGIT = rf"(?:(?<![.\d,\-])\d+)\s*\(\d+\)"

# Full number — parenthetical > digits > word  (try most-specific first)
_NUM_FULL = rf"(?:{_PAREN_WORD}|{_PAREN_DIGIT}|{_DIGIT_NUM}|{_WORD_NUM})"

# Unit alternation for main pattern — longer pattern strings first so that
# "business days" is tried before bare "days".
_UNIT_MAP_MAIN = {k: v for k, v in UNIT_MAP.items() if k != r"\$"}
_UNIT_PATS_SORTED = sorted(_UNIT_MAP_MAIN.keys(), key=len, reverse=True)
_UNIT_ALT = "|".join(rf"(?:{p})" for p in _UNIT_PATS_SORTED)

# ---------------------------------------------------------------------------
# Compiled regexes
# ---------------------------------------------------------------------------

# Main: number, optional separator (space/hyphen), unit, not followed by \w
_MAIN_RE = re.compile(
    rf"(?P<num>{_NUM_FULL})\s*-?\s*(?P<unit_str>{_UNIT_ALT})(?!\w)",
    re.IGNORECASE,
)

# Dollar prefix: $45.00  or  $ 1,200
_DOLLAR_RE = re.compile(
    r"(?<!\w)\$\s*(?P<num>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)",
    re.IGNORECASE,
)

# Bare digit: standalone integer not preceded/followed by digit/dot/comma/hyphen/slash
_BARE_DIGIT_RE = re.compile(
    r"(?<![.\d,\-/])(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?)(?![.\d,\-/])",
)

# ---------------------------------------------------------------------------
# Exclusion patterns
# ---------------------------------------------------------------------------

_EXCLUSION_COMPILED: list[re.Pattern] = [
    re.compile(r"\b1-800-\d{3}-\d{4}\b"),              # 800 numbers
    re.compile(r"\b\d{3}-\d{3}-\d{4}\b"),              # full phone numbers
    re.compile(r"\b\d{3}-\d{4}\b"),                    # phone suffix
    re.compile(r"\b[A-Z]{2,5}-\d{4}-?\d*\b"),          # OBL/EVT/RRS/CTL style IDs
    re.compile(r"\b[A-Z]{2,4}-F-\d{3}\b"),             # simple form IDs
    re.compile(r"\b[A-Z]{2,5}-[A-Z]{1,5}-[A-Z]-\d{3,}\b"),  # compound form IDs
    re.compile(r"\bSheet\s+(?:No\.?\s*)?\d+\b", re.IGNORECASE),
    re.compile(r"\bv\d+\.\d+\b"),                      # version strings
]

# ---------------------------------------------------------------------------
# Qualifier compiled patterns (longest/most-specific first)
# ---------------------------------------------------------------------------

_QUALIFIER_COMPILED: list[tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE), value)
    for pattern, value in QUALIFIER_MAP.items()
]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIME_UNITS = frozenset(
    {"day", "business_day", "calendar_day", "working_day", "hour", "minute", "month", "year"}
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _overlaps(a_start: int, a_end: int, spans: list[tuple[int, int]]) -> bool:
    """True if (a_start, a_end) overlaps any span in *spans*."""
    return any(a_start < e and a_end > s for s, e in spans)


def _get_forbidden_spans(text: str) -> list[tuple[int, int]]:
    """Return all exclusion-pattern and citation spans in *text*."""
    spans: list[tuple[int, int]] = []
    for pat in _EXCLUSION_COMPILED:
        for m in pat.finditer(text):
            spans.append((m.start(), m.end()))
    for start, end, _ in find_citation_spans(text):
        spans.append((start, end))
    return spans


def _canonicalize_unit(matched_str: str) -> Optional[str]:
    """Return the canonical unit name for a unit substring matched by _MAIN_RE."""
    for pattern, canonical in UNIT_MAP.items():
        if re.fullmatch(pattern, matched_str, re.IGNORECASE):
            return canonical
    return None


def _get_day_type(unit: Optional[str]) -> str:
    if unit == "business_day":
        return DayType.BUSINESS
    if unit == "calendar_day":
        return DayType.CALENDAR
    if unit == "working_day":
        return DayType.WORKING
    if unit in ("hour", "minute"):
        return DayType.HOURS
    return DayType.N_A


def _get_kind(unit: Optional[str], qualifier: Optional[str], context: str) -> str:
    """Determine ParameterKind from unit, qualifier, and surrounding context.

    Rule order (first match wins):
      1.  usd                             → amount
      2.  context: retain/keep            → record_retention
      3.  context: by/no later than/due   → deadline
      4.  context: every/per/annually/…   → frequency
      5.  context: or more/exceeds/…      → threshold
      6.  qualifier at_least/not_more_than + non-time unit → threshold
      7.  time unit + qualifier           → period
      8.  time unit (no qualifier)        → period
      9.  otherwise                       → number

    Note: rules 2–5 (context-based) intentionally precede rule 7 so that
    "due within 5 business days" resolves to deadline, not period.
    """
    ctx = context.lower()

    if unit == "usd":
        return ParameterKind.AMOUNT

    if re.search(r"\bretain\b|\bkeep\b", ctx):
        return ParameterKind.RECORD_RETENTION

    if re.search(r"\bby\b|no\s+later\s+than|\bdue\b", ctx):
        return ParameterKind.DEADLINE

    if re.search(r"\bor\s+more\b|\bexceeds?\b|\bgreater\s+than\b", ctx):
        return ParameterKind.THRESHOLD

    if re.search(r"\bevery\b|\bper\b|\bannually\b|\beach\s+year\b", ctx):
        return ParameterKind.FREQUENCY

    if qualifier in ("at_least", "not_more_than") and unit is not None and unit not in _TIME_UNITS:
        return ParameterKind.THRESHOLD

    if unit in _TIME_UNITS:
        return ParameterKind.PERIOD

    return ParameterKind.NUMBER


def _find_qualifier(text: str, num_start: int) -> Optional[str]:
    """Return the qualifier value from the 6 tokens immediately before *num_start*.

    The window is rebuilt from whole tokens so that a qualifier phrase split
    across the exact character boundary is not truncated.
    """
    prefix_tokens = text[:num_start].split()
    window = " ".join(prefix_tokens[-6:])

    best_match: Optional[str] = None
    best_end = -1
    for pat, value in _QUALIFIER_COMPILED:
        for m in pat.finditer(window):
            if m.end() > best_end:
                best_end = m.end()
                best_match = value
    return best_match


def _extract_value(num_str: str) -> tuple[Optional[float], str]:
    """Return (numeric_value, canonical_text) from a matched number substring.

    Parenthetical digit takes precedence: "fourteen (14)" → (14.0, "14").
    Strips commas from digit strings.  Falls back to words_to_number.
    """
    # Parenthetical: "fourteen (14)" or "10 (10)"
    paren = re.search(r"\((\d+)\)", num_str)
    if paren:
        return float(paren.group(1)), paren.group(1)

    cleaned = num_str.strip()

    # Digit with optional commas and/or decimal
    digit_m = re.match(r"^(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?$", cleaned)
    if digit_m:
        raw = (digit_m.group(1) + (digit_m.group(2) or "")).replace(",", "")
        return float(raw), raw

    # Word number
    wn = words_to_number(cleaned)
    if wn is not None:
        val = float(wn)
        canonical = str(int(wn)) if isinstance(wn, int) else str(wn)
        return val, canonical

    return None, cleaned


def _build_entry(
    unit_obj: ClauseUnit,
    text: str,
    value_text: str,
    value_num: Optional[float],
    unit_canonical: Optional[str],
    day_type: str,
    kind: str,
    qualifier: Optional[str],
    span_start: int,
    span_end: int,
    ctx: RunContext,
) -> ParameterEntry:
    """Build and verify a ParameterEntry."""
    spans = find_verbatim(text, value_text)
    verified = any(s == span_start and e == span_end for s, e in spans)

    if not verified:
        logger.warning(
            "Unverified regex parameter in %s: %r at %d-%d",
            unit_obj.clause_id,
            value_text,
            span_start,
            span_end,
        )
        ctx.issue(
            "warning",
            "4.1.2",
            "parameter_unverified",
            f"Regex parameter not confirmed by find_verbatim: {value_text!r}",
            clause_id=unit_obj.clause_id,
        )

    return ParameterEntry(
        kind=kind,
        value_text=value_text,
        value_num=value_num,
        unit=unit_canonical,
        day_type=day_type,
        qualifier=qualifier,
        span_start=span_start,
        span_end=span_end,
        method="regex",
        verified=verified,
        value_source=None,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def enrich_parameters(units: list[ClauseUnit], ctx: RunContext) -> None:
    """Append ParameterEntry objects to each unit's .parameters list.

    Three passes per clause:
    1. Dollar-prefix amounts  ($45.00)
    2. Number + unit  (10 business days, fourteen (14) calendar days, 10%)
    3. Bare digits  (only when unit.citations is non-empty)

    All candidates are checked against forbidden spans (exclusion patterns +
    citation spans) and against already-claimed spans from earlier passes.
    """
    for unit_obj in units:
        text = unit_obj.text_raw
        if not text:
            continue

        local_id = unit_obj.local_id
        forbidden = _get_forbidden_spans(text)
        claimed: list[tuple[int, int]] = []

        # -------------------------------------------------------------------
        # Pass 1: Dollar-prefix amounts
        # -------------------------------------------------------------------
        for m in _DOLLAR_RE.finditer(text):
            s, e = m.start(), m.end()
            if _overlaps(s, e, forbidden) or _overlaps(s, e, claimed):
                continue

            num_str = m.group("num")
            value_num, _ = _extract_value(num_str)
            if value_num is None:
                continue

            qualifier = _find_qualifier(text, s)
            entry = _build_entry(
                unit_obj, text, m.group(0), value_num, "usd",
                DayType.N_A, ParameterKind.AMOUNT, qualifier, s, e, ctx,
            )
            unit_obj.parameters.append(entry)
            claimed.append((s, e))
            ctx.count("parameters_found")
            if entry.verified:
                ctx.count("parameters_verified")

        # -------------------------------------------------------------------
        # Pass 2: Number + unit
        # -------------------------------------------------------------------
        for m in _MAIN_RE.finditer(text):
            s, e = m.start(), m.end()
            if _overlaps(s, e, forbidden) or _overlaps(s, e, claimed):
                continue

            matched_text = m.group(0)
            if matched_text.strip() == local_id:
                continue

            unit_str = m.group("unit_str")
            unit_canonical = _canonicalize_unit(unit_str)
            if unit_canonical is None:
                continue

            num_str = m.group("num")
            value_num, _ = _extract_value(num_str)
            if value_num is None:
                # Word-only fallback (e.g. word matched but _extract_value missed)
                wn = words_to_number(num_str.strip())
                if wn is None:
                    continue
                value_num = float(wn)

            qualifier = _find_qualifier(text, s)
            day_type = _get_day_type(unit_canonical)

            ctx_start = max(0, s - 100)
            ctx_end = min(len(text), e + 100)
            context = text[ctx_start:ctx_end]

            kind = _get_kind(unit_canonical, qualifier, context)

            entry = _build_entry(
                unit_obj, text, matched_text, value_num, unit_canonical,
                day_type, kind, qualifier, s, e, ctx,
            )
            unit_obj.parameters.append(entry)
            claimed.append((s, e))
            ctx.count("parameters_found")
            if entry.verified:
                ctx.count("parameters_verified")

        # -------------------------------------------------------------------
        # Pass 3: Bare digit numbers (only when citations are present)
        # -------------------------------------------------------------------
        if not unit_obj.citations:
            continue

        for m in _BARE_DIGIT_RE.finditer(text):
            s, e = m.start(), m.end()
            if _overlaps(s, e, claimed) or _overlaps(s, e, forbidden):
                continue

            num_str = m.group("num")
            if num_str == local_id:
                continue

            value_num, _ = _extract_value(num_str)
            if value_num is None:
                continue

            qualifier = _find_qualifier(text, s)
            context = text[max(0, s - 100): min(len(text), e + 100)]
            kind = _get_kind(None, qualifier, context)

            entry = _build_entry(
                unit_obj, text, num_str, value_num, None,
                DayType.N_A, kind, qualifier, s, e, ctx,
            )
            unit_obj.parameters.append(entry)
            claimed.append((s, e))
            ctx.count("parameters_found")
            if entry.verified:
                ctx.count("parameters_verified")

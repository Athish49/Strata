"""
Citation parser for regulatory citations found in company documents.

Supports:
  - Indiana Administrative Code (IAC): 170 IAC 4-1-16, with subsections,
    decimal sections, decimal articles, rule-level references, and ranges.
  - Indiana Code (IC): IC 8-1-2-121
  - Code of Federal Regulations (CFR): 40 CFR 112, 29 CFR 1910.269
  - United States Code (U.S.C.): 42 U.S.C. § 7401
  - External standards (ANSI, IEEE, ASTM, NFPA, NERC, ISO)

Public API
----------
    parse_citation(raw: str) -> list[ParsedCitation]
    find_citation_spans(text: str) -> list[tuple[int, int, str]]
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class ParsedCitation:
    """Structured representation of a single regulatory citation."""

    source_system: str        # iac | cfr | ic | usc | external_standard | unknown
    title: Optional[int]      # e.g. 170  (None for IC, external standards)
    article: Optional[str]    # e.g. "4-1"  (None for CFR/USC/unknown)
    rule: Optional[str]       # e.g. "4-1-16"  (None for rule-level IAC or non-IAC)
    section: Optional[Decimal]  # e.g. Decimal("16.5")  (None for rule-level)
    subsection_path: str      # e.g. "(b)(2)" or ""
    granularity: str          # rule | section | subsection
    normalized_key: str       # e.g. "170 IAC 4-1-16" or "170 IAC 4-1-16.5"
    rule_key: str             # e.g. "170 IAC 4-1"
    citation_raw: str         # original text as found


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _decimal(s: str) -> Optional[Decimal]:
    """Convert string to Decimal, returning None on failure."""
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _dec_str(d: Decimal) -> str:
    """Format Decimal for use in keys — strips trailing zeros but keeps decimals.

    Decimal("16") → "16", Decimal("100") → "100", Decimal("16.50") → "16.5".
    Uses fixed-point notation (no scientific notation).
    """
    # format(..., 'f') gives fixed-point, then strip trailing zeros after decimal
    s = format(d, "f")
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    return s


def _normalize_subsection(raw: Optional[str]) -> str:
    """Collapse whitespace inside a subsection path like ' (b) (2)' → '(b)(2)'."""
    if not raw:
        return ""
    return re.sub(r"\s+", "", raw.strip())


def _make_iac(
    title: int,
    article: str,
    section: Optional[Decimal],
    subsection_path: str,
    raw: str,
) -> ParsedCitation:
    """Build an IAC ParsedCitation from its components."""
    if section is None:
        granularity = "rule"
        rule = None
        normalized_key = f"{title} IAC {article}"
        rule_key = normalized_key
    else:
        sec_str = _dec_str(section)
        rule = f"{article}-{sec_str}"
        normalized_key = f"{title} IAC {rule}"
        rule_key = f"{title} IAC {article}"
        granularity = "subsection" if subsection_path else "section"

    return ParsedCitation(
        source_system="iac",
        title=title,
        article=article,
        rule=rule,
        section=section,
        subsection_path=subsection_path,
        granularity=granularity,
        normalized_key=normalized_key,
        rule_key=rule_key,
        citation_raw=raw,
    )


# ---------------------------------------------------------------------------
# IAC regex patterns
# ---------------------------------------------------------------------------

# Numeric part: integer or decimal (e.g. "4", "6.1", "16.5")
_NP = r"\d+(?:\.\d+)?"

# Subsection path: one or more parenthesised groups like (b)(2)
_SUBPATH = r"(?:\s*\([^)]+\))+"

# IAC range with "through": 170 IAC 4-1-4 through 4-1-14
_RE_IAC_RANGE_THROUGH = re.compile(
    rf"\b({_NP})\s+IAC\s+"
    rf"({_NP})-({_NP})-({_NP})"        # start  part1-part2-section
    rf"\s+through\s+"
    rf"({_NP})-({_NP})-({_NP})",       # end    part1-part2-section
    re.IGNORECASE,
)

# IAC range with "..": 170 IAC 4-1-4..4-1-14  (dots may have spaces around them)
_RE_IAC_RANGE_DOTDOT = re.compile(
    rf"\b({_NP})\s+IAC\s+"
    rf"({_NP})-({_NP})-({_NP})"
    rf"\s*\.\.\s*"
    rf"({_NP})-({_NP})-({_NP})",
)

# Standard IAC citation (3-part section or 2-part rule-level), optional subsection
_RE_IAC = re.compile(
    rf"\b({_NP})\s+IAC\s+"
    rf"({_NP})-({_NP})"                # part1-part2 (always present)
    rf"(?:-({_NP}))?"                  # optional -section
    rf"({_SUBPATH})?",                 # optional subsection path
)

# ---------------------------------------------------------------------------
# IC regex
# ---------------------------------------------------------------------------

_RE_IC = re.compile(
    rf"\bIC\s+({_NP})-({_NP})-({_NP})-({_NP})\b",
)

# ---------------------------------------------------------------------------
# CFR regex
# ---------------------------------------------------------------------------

# Matches both "40 CFR 112" and "29 CFR 1910.269"
_RE_CFR = re.compile(
    rf"\b(\d+)\s+CFR\s+({_NP})\b",
)

# ---------------------------------------------------------------------------
# U.S.C. regex
# ---------------------------------------------------------------------------

_RE_USC = re.compile(
    rf"\b(\d+)\s+U\.S\.C\.(?:\s*§\s*|\s+)({_NP})\b",
)

# ---------------------------------------------------------------------------
# External standard regex (ANSI/IEEE/ASTM/NFPA/NERC/ISO)
# ---------------------------------------------------------------------------

_RE_EXT_STANDARD = re.compile(
    r"\b(ANSI|IEEE|ASTM|NFPA|NERC|IEC|ISO)\b[\s/\-][\w\./\-]+",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Bracketed form: "Commission Rule 16 [170 IAC 4-1-16]"
# ---------------------------------------------------------------------------

_RE_BRACKETED = re.compile(r"\[([^\]]+)\]")

# ---------------------------------------------------------------------------
# Span-detection patterns (for find_citation_spans)
# These are combined into a single alternation, longest-match first.
# ---------------------------------------------------------------------------

_SPAN_PATTERNS = [
    # IAC range (through)
    rf"\b{_NP}\s+IAC\s+{_NP}-{_NP}-{_NP}\s+through\s+{_NP}-{_NP}-{_NP}",
    # IAC range (..)
    rf"\b{_NP}\s+IAC\s+{_NP}-{_NP}-{_NP}\s*\.\.\s*{_NP}-{_NP}-{_NP}",
    # IAC (section or rule-level) with optional subsection
    rf"\b{_NP}\s+IAC\s+{_NP}-{_NP}(?:-{_NP})?(?:{_SUBPATH})?",
    # IC
    rf"\bIC\s+{_NP}-{_NP}-{_NP}-{_NP}\b",
    # CFR
    rf"\b\d+\s+CFR\s+{_NP}\b",
    # U.S.C.
    rf"\b\d+\s+U\.S\.C\.(?:\s*§\s*|\s+){_NP}\b",
    # External standards
    r"\b(?:ANSI|IEEE|ASTM|NFPA|NERC|IEC|ISO)\b[\s/\-][\w\./\-]+",
]

_RE_SPAN = re.compile(
    "|".join(f"(?:{p})" for p in _SPAN_PATTERNS),
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Range expansion
# ---------------------------------------------------------------------------

def _expand_iac_range(
    title: int,
    part1: str,
    part2: str,
    sec_start: Decimal,
    sec_end: Decimal,
    raw: str,
) -> list[ParsedCitation]:
    """
    Expand an IAC range into individual ParsedCitations.

    Only integer sections are expanded (non-integer start/end yield a single
    citation from start to end with a note, falling back to start only).
    """
    article = f"{part1}-{part2}"

    # Only expand integer ranges
    try:
        start_int = int(sec_start)
        end_int = int(sec_end)
    except (ValueError, TypeError):
        # Decimal sections — just return start
        return [_make_iac(title, article, sec_start, "", raw)]

    if start_int > end_int:
        start_int, end_int = end_int, start_int

    result: list[ParsedCitation] = []
    for sec in range(start_int, end_int + 1):
        result.append(_make_iac(title, article, Decimal(str(sec)), "", raw))
    return result


# ---------------------------------------------------------------------------
# Parse IAC string
# ---------------------------------------------------------------------------

def _parse_iac_string(raw: str) -> list[ParsedCitation]:
    """
    Parse one IAC citation string (without surrounding text).
    Returns a list (>1 for ranges, 1 for single citations).
    """
    # Strip surrounding whitespace
    s = raw.strip()

    # Check for range forms first
    m = _RE_IAC_RANGE_THROUGH.search(s)
    if m:
        title = int(float(m.group(1)))
        part1_s, part2_s = m.group(2), m.group(3)
        sec_start = _decimal(m.group(4))
        # end groups: 5, 6, 7
        sec_end = _decimal(m.group(7))
        if sec_start is not None and sec_end is not None:
            return _expand_iac_range(title, part1_s, part2_s, sec_start, sec_end, raw)

    m = _RE_IAC_RANGE_DOTDOT.search(s)
    if m:
        title = int(float(m.group(1)))
        part1_s, part2_s = m.group(2), m.group(3)
        sec_start = _decimal(m.group(4))
        sec_end = _decimal(m.group(7))
        if sec_start is not None and sec_end is not None:
            return _expand_iac_range(title, part1_s, part2_s, sec_start, sec_end, raw)

    # Standard IAC citation
    m = _RE_IAC.search(s)
    if not m:
        return []

    title_str = m.group(1)
    part1 = m.group(2)
    part2 = m.group(3)
    part3 = m.group(4)  # may be None (rule-level)
    sub_raw = m.group(5)  # may be None

    title = int(float(title_str))
    article = f"{part1}-{part2}"
    section = _decimal(part3) if part3 is not None else None
    subsection_path = _normalize_subsection(sub_raw)

    return [_make_iac(title, article, section, subsection_path, raw)]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_citation(raw: str) -> list[ParsedCitation]:
    """
    Parse a citation string and return a list of ParsedCitation objects.

    Handles:
      - IAC single citations and ranges
      - Bracketed forms: Commission Rule 16 [170 IAC 4-1-16]
      - IC, CFR, U.S.C., external standards
      - Multiple citations in one string (returns all found)
    """
    results: list[ParsedCitation] = []
    s = raw.strip()

    # --- Bracketed form: extract text inside [...]
    bracket_matches = list(_RE_BRACKETED.finditer(s))
    if bracket_matches:
        for bm in bracket_matches:
            inner = bm.group(1).strip()
            inner_results = parse_citation(inner)
            for pc in inner_results:
                # Preserve the outer raw text
                results.append(
                    ParsedCitation(
                        source_system=pc.source_system,
                        title=pc.title,
                        article=pc.article,
                        rule=pc.rule,
                        section=pc.section,
                        subsection_path=pc.subsection_path,
                        granularity=pc.granularity,
                        normalized_key=pc.normalized_key,
                        rule_key=pc.rule_key,
                        citation_raw=raw,
                    )
                )
        if results:
            return results

    # --- IAC (try range first, then standard)
    iac_range_m = _RE_IAC_RANGE_THROUGH.search(s) or _RE_IAC_RANGE_DOTDOT.search(s)
    if iac_range_m:
        return _parse_iac_string(s)

    iac_m = _RE_IAC.search(s)
    if iac_m:
        return _parse_iac_string(s)

    # --- IC
    ic_m = _RE_IC.search(s)
    if ic_m:
        p1, p2, p3, p4 = ic_m.group(1), ic_m.group(2), ic_m.group(3), ic_m.group(4)
        article = f"{p1}-{p2}-{p3}"
        section = _decimal(p4)
        sec_str = _dec_str(section) if section is not None else p4
        nk = f"IC {article}-{sec_str}"
        rk = f"IC {article}"
        results.append(ParsedCitation(
            source_system="ic",
            title=None,
            article=article,
            rule=f"{article}-{sec_str}",
            section=section,
            subsection_path="",
            granularity="section",
            normalized_key=nk,
            rule_key=rk,
            citation_raw=raw,
        ))
        return results

    # --- CFR
    cfr_m = _RE_CFR.search(s)
    if cfr_m:
        title = int(cfr_m.group(1))
        sec_str = cfr_m.group(2)
        section = _decimal(sec_str)
        nk = f"{title} CFR {sec_str}"
        rk = f"{title} CFR"
        results.append(ParsedCitation(
            source_system="cfr",
            title=title,
            article=None,
            rule=None,
            section=section,
            subsection_path="",
            granularity="section",
            normalized_key=nk,
            rule_key=rk,
            citation_raw=raw,
        ))
        return results

    # --- U.S.C.
    usc_m = _RE_USC.search(s)
    if usc_m:
        title = int(usc_m.group(1))
        sec_str = usc_m.group(2)
        section = _decimal(sec_str)
        nk = f"{title} U.S.C. {sec_str}"
        rk = f"{title} U.S.C."
        results.append(ParsedCitation(
            source_system="usc",
            title=title,
            article=None,
            rule=None,
            section=section,
            subsection_path="",
            granularity="section",
            normalized_key=nk,
            rule_key=rk,
            citation_raw=raw,
        ))
        return results

    # --- External standard
    ext_m = _RE_EXT_STANDARD.search(s)
    if ext_m:
        results.append(ParsedCitation(
            source_system="external_standard",
            title=None,
            article=None,
            rule=None,
            section=None,
            subsection_path="",
            granularity="rule",
            normalized_key=ext_m.group(0).strip(),
            rule_key=ext_m.group(0).strip(),
            citation_raw=raw,
        ))
        return results

    # --- Unknown
    results.append(ParsedCitation(
        source_system="unknown",
        title=None,
        article=None,
        rule=None,
        section=None,
        subsection_path="",
        granularity="rule",
        normalized_key=s,
        rule_key=s,
        citation_raw=raw,
    ))
    return results


def find_citation_spans(text: str) -> list[tuple[int, int, str]]:
    """
    Find all citation-shaped strings in *text*.

    Returns a list of (start, end, raw_text) tuples where start/end are
    character offsets into *text*.  Overlapping matches are deduplicated
    (longest match wins).
    """
    matches: list[tuple[int, int, str]] = []
    for m in _RE_SPAN.finditer(text):
        raw = m.group(0)
        # Strip trailing whitespace that the pattern may have captured
        stripped = raw.rstrip()
        end = m.start() + len(stripped)
        matches.append((m.start(), end, stripped))

    # Deduplicate: if two spans overlap, keep the longer one
    if not matches:
        return []

    matches.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    deduped: list[tuple[int, int, str]] = []
    prev_end = -1
    for start, end, raw in matches:
        if start < prev_end:
            # Overlaps with previous; skip (previous was longer due to sort)
            continue
        deduped.append((start, end, raw))
        prev_end = end

    return deduped

"""Task 4.1.5 — Defined terms extraction and usage finding."""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.parse.text import normalize
from app.company_ingest.run_context import RunContext

# ---------------------------------------------------------------------------
# Exceptions for singularization (words ending in 's' that should NOT be
# singularized by stripping the trailing 's').
# ---------------------------------------------------------------------------
_NO_SINGULARIZE = frozenset({
    "status", "basis", "analysis", "hypothesis", "thesis", "crisis", "axis",
    "bonus", "campus", "census", "circus", "chorus", "exodus", "focus",
    "genus", "nexus", "nexus", "radius", "ramus", "sinus", "stylus",
    "syllabus", "torus", "virus", "caucus", "corpus", "hiatus", "impetus",
    "consensus", "apparatus", "prospectus", "stimulus", "calculus",
    "syllabus", "surplus",
    # common two-letter / short words
    "as", "is", "us", "has", "was",
})


def _singularize(word: str) -> str:
    """Apply a simple English singularization rule.

    Strips trailing 's' unless:
    - word ends in 'ss'  (e.g. "process" → stays)
    - word ends in 'us'  (e.g. "status" → stays)
    - word ends in 'is'  (e.g. "basis" → stays)
    - word is in the exception set
    - word does not end in 's'
    """
    lower = word.lower()
    if not lower.endswith("s"):
        return word
    if lower in _NO_SINGULARIZE:
        return word
    if lower.endswith("ss") or lower.endswith("us") or lower.endswith("is"):
        return word
    # Strip trailing 's'
    return word[:-1]


def _term_norm(term: str) -> str:
    """Return the canonical form of a term: normalize() then singularize last word."""
    normed = normalize(term).lower()
    # Singularize only the last word of the phrase
    parts = normed.split()
    if parts:
        parts[-1] = _singularize(parts[-1])
        normed = " ".join(parts)
    return normed


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TermEntry:
    term: str                           # exact text as written
    term_norm: str                      # normalize(term), lowercased, singular
    definition_clause_id: str           # full clause_id of the defining clause
    cites_regulatory_definition: bool   # True if the defining unit has ≥1 resolved IAC citation
    doc_id: str                         # doc_id of the defining clause


@dataclass
class TermUsage:
    term_norm: str
    clause_id: str      # full clause_id of the using clause
    occurrences: int    # count of times the term appears in that clause


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------

_BOLD_PATTERN = re.compile(r'^\*\*(.+?)\*\*\s+(means|is)\b')
_QUOTED_PATTERN = re.compile(r'^"(.+?)"\s+(means|is)\b')


def _extract_term_from_unit(unit: ClauseUnit) -> str | None:
    """Try all four patterns; return the raw term text or None."""
    # Pattern 1 — Table row
    if unit.unit_kind == "table_row" and unit.row_cells is not None:
        cells = unit.row_cells
        if cells:
            first_value = next(iter(cells.values()))
            if isinstance(first_value, str) and first_value.strip():
                return first_value.strip()

    text = unit.text_raw.lstrip()

    # Pattern 2 — Bold-term
    m = _BOLD_PATTERN.match(text)
    if m:
        return m.group(1)

    # Pattern 3 — Quoted-term
    m = _QUOTED_PATTERN.match(text)
    if m:
        return m.group(1)

    # Pattern 4 — Title-case heading (definitions section, heading itself is the term)
    if unit.section_kind == "definitions" and unit.heading_path:
        heading = unit.heading_path[-1]
        words = heading.split()
        # Single phrase, no verb keyword, ≤ 6 words
        if 1 <= len(words) <= 6 and not any(
            w.lower() in ("means", "is", "refers", "shall") for w in words
        ):
            return heading

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_terms(units: list[ClauseUnit], ctx: RunContext) -> list[TermEntry]:
    """Extract defined terms from definition-section units.

    Returns list of TermEntry objects.
    """
    entries: list[TermEntry] = []
    for unit in units:
        is_definition_unit = (
            unit.section_kind == "definitions" or unit.role == "definition"
        )
        if not is_definition_unit:
            continue

        raw_term = _extract_term_from_unit(unit)
        if raw_term is None:
            continue

        cites = len(unit.citations) > 0

        entry = TermEntry(
            term=raw_term,
            term_norm=_term_norm(raw_term),
            definition_clause_id=unit.clause_id,
            cites_regulatory_definition=cites,
            doc_id=unit.doc_id,
        )
        entries.append(entry)
        ctx.count("terms_extracted")

    return entries


def find_term_usages(
    terms: list[TermEntry],
    units: list[ClauseUnit],
    ctx: RunContext | None = None,
) -> list[TermUsage]:
    """Find usages of each term across all units.

    Terms are matched case-insensitively, whole-word.
    The defining clause itself is skipped.
    """
    usages: list[TermUsage] = []

    for term in terms:
        pattern = re.compile(
            r'\b' + re.escape(term.term_norm) + r's?\b', re.IGNORECASE
        )
        for unit in units:
            if unit.clause_id == term.definition_clause_id:
                continue
            count = len(pattern.findall(unit.text_norm))
            if count > 0:
                usage = TermUsage(
                    term_norm=term.term_norm,
                    clause_id=unit.clause_id,
                    occurrences=count,
                )
                usages.append(usage)
                unit.terms.append(term)
                if ctx is not None:
                    ctx.count("term_usages_found")

    return usages

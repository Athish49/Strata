"""
textnorm.py — Text functions for Stage 1 (engine_spec.md section 1.1).

``normalize`` wraps the existing change-detection normalizer;
``strip_metadata`` additionally removes non-obligation metadata (statute-reference
lines, source-history notes) from already-normalized text, so that the
``metadata_only`` class and the word diff look at wording only.

Both functions are pure and deterministic.
"""
from __future__ import annotations

import re

from app.regulatory.ingestion.normalize import normalize_for_diff


# ---------------------------------------------------------------------------
# State-code patterns (source_system "iac")
# ---------------------------------------------------------------------------

# One statute reference inside an Authority/Affected list: "IC 13-14-8", "IC 8-1-2.6-1.5".
_IAC_STATUTE_REF = r"[A-Za-z.]{1,6} \d[\d.\-]*"
_IAC_STATUTE_LIST = rf"{_IAC_STATUTE_REF}(?:\s*;\s*{_IAC_STATUTE_REF})*"

# The statute-reference block that precedes the rule text:
#   "Authority: IC a-b-c ; IC d-e Affected: IC f-g ; IC h"
_IAC_AUTHORITY = re.compile(
    rf"\bAuthority:\s*{_IAC_STATUTE_LIST}(?:\s*Affected:\s*{_IAC_STATUTE_LIST})?"
)
# An "Affected:" list on its own (when the Authority list is absent).
_IAC_AFFECTED = re.compile(rf"\bAffected:\s*{_IAC_STATUTE_LIST}")

# Document identification numbers: "20250618-IR-326250285ACA".
_IAC_DIN = re.compile(r"\b\d{8}-IR-\d+[A-Z]{2,3}\b")

# A source-history entry (readoption / errata / filing) that lost its opening
# parenthesis and is left dangling after the section text:
#   "; errata filed Jun 3, 2025, 1:59 p.m.: 20250618-IR-326250285ACA )"
_IAC_HISTORY_TAIL = re.compile(
    r";\s*(?:errata\s+|readopted\s+)?filed\b[^;()]{0,120}?:\s*"
    r"(?:\d{8}-IR-\d+[A-Z]{2,3}|\d+ IR \d+)\s*\)?",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Federal-code patterns (source_system "cfr")
# ---------------------------------------------------------------------------

# Bracketed Federal Register source note, anywhere in the text (not only at the end):
#   "[Order 91, 45 FR 46363, July 10, 1980]" / "[58 FR 3650, Jan. 11, 1993]"
_CFR_SOURCE_NOTE = re.compile(r"\[[^\[\]]*?\d+\s+FR\s+\d+[^\[\]]*\]", re.IGNORECASE)

# eCFR boilerplate that follows a source note.
_CFR_EDITORIAL_NOTE = re.compile(
    r"Editorial Note:\s*For Federal Register citations affecting[^,]*,\s*"
    r"see the List of \w+ Sections Affected,\s*which appears in the Finding Aids "
    r"section of the printed volume and at [\w./-]*\w\.?",
    re.IGNORECASE,
)


def normalize(text: str, source_system: str) -> str:
    """Normalized text for change detection (``normalize_for_diff``)."""
    return normalize_for_diff(text, source_system)


def strip_metadata(norm_text: str, source_system: str) -> str:
    """Remove non-obligation metadata from normalized text.

    Expects ``norm_text`` to be the output of :func:`normalize`.  Unknown
    ``source_system`` values return the text unchanged (stripped).
    """
    if not norm_text:
        return ""

    t = norm_text
    sys = (source_system or "").lower()

    if sys == "iac":
        t = _IAC_AUTHORITY.sub(" ", t)
        t = _IAC_AFFECTED.sub(" ", t)
        t = _IAC_HISTORY_TAIL.sub(" ", t)
        t = _IAC_DIN.sub(" ", t)
    elif sys == "cfr":
        t = _CFR_SOURCE_NOTE.sub(" ", t)
        t = _CFR_EDITORIAL_NOTE.sub(" ", t)
    else:
        return t.strip()

    return re.sub(r"\s+", " ", t).strip()

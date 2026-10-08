"""
normalize.py — Normalize regulatory text for change detection.

Strips cosmetic boilerplate (DIN prefixes, filing-history footers, edition
stamps, spurious whitespace) so that diff_hash reflects only substantive
content changes.

Usage::

    from app.regulatory.ingestion.normalize import normalize_for_diff
    import hashlib

    normalized = normalize_for_diff(section.body_text, section.source_system)
    diff_hash  = hashlib.sha256(normalized.encode()).hexdigest()
"""
from __future__ import annotations

import re


# ---------------------------------------------------------------------------
# IAC patterns
# ---------------------------------------------------------------------------

# "Sec. N." DIN section markers (e.g. "Sec. 18." / "Sec. 27.5."), at the start
# of a body or in front of each sub-section of a multi-section body.
_IAC_DIN_PREFIX = re.compile(r"(?<![\w.])Sec\.\s+\d+(?:\.\d+)*\.(?=\s|$)")

# Parenthetical filing-history entries, with at most one level of nesting:
#   (Agency Name; citation; filed …; readopted filed …; filed …: YYYYMMDD-IR-NNNNXXX )
# Any entry carrying an IR document code (or an old-style "NN IR NNNN" volume
# reference) is dropped wherever it appears, so appended readoption/errata
# entries do not register as changes.  "(Repealed by …)" entries are kept:
# a repeal is substantive.
_IAC_PAREN = re.compile(r"\((?:[^()]|\([^()]*\))*\)")
_IAC_FILING_MARK = re.compile(r"\d{8}-IR-\d+[A-Z]{2,3}|\b\d+ IR \d+", re.IGNORECASE)
_IAC_REPEALED = re.compile(r"^\(\s*Repealed\b", re.IGNORECASE)

# Spurious space inside an IR document reference code:
#   "20100623-IR- 170090792FRA" / "20101222- IR-675100251FRA" → no space
_IAC_IR_SPACE = re.compile(r"(\d{8})-\s*IR-\s*(\d+[A-Z]{2,3})")

# Spurious space inside Public Law references:
#   "P.L.101- 549" → "P.L.101-549"
_IAC_PL_SPACE = re.compile(r"(P\.L\.\d+-)\s+(\d+)")

# DIN line-break spacing around a hyphen between alphanumerics, in citations
# and compounds: "30-4- 40" → "30-4-40", "fifty- four" → "fifty-four",
# "A -3" → "A-3".
_HYPHEN_SPACE = re.compile(r"(?<=[A-Za-z0-9])\s*-\s*(?=[A-Za-z0-9])")


# ---------------------------------------------------------------------------
# CFR patterns
# ---------------------------------------------------------------------------

# Trailing Federal Register citation block:
#   [Order NNN, XX FR NNNNN, Month Day, Year; …]
_CFR_FR_FOOTER = re.compile(
    r"\s*\[[^\[\]]*?\d+\s+FR\s+\d+[^\[\]]*\]\s*$",
    re.DOTALL | re.IGNORECASE,
)

# Alternative inline FR amendment note at end of sections:
#   (XX FR NNNNN, Month Day, Year)
_CFR_FR_INLINE = re.compile(
    r"\s*\(\s*\d+\s+FR\s+\d+[^)]*\)\s*$",
    re.DOTALL | re.IGNORECASE,
)

# eCFR hyperlink note about a later amendment:
#   "Link to an amendment published at 91 FR 58997, Sept. 17, 2026."
_CFR_AMEND_LINK = re.compile(
    r"Link to an amendment published at\s+\d+\s+FR\s+\d+,\s*[A-Za-z]+\.?\s+\d{1,2},\s*\d{4}\.?",
    re.IGNORECASE,
)


def _drop_filing_history(m: re.Match) -> str:
    entry = m.group(0)
    if _IAC_REPEALED.match(entry) or not _IAC_FILING_MARK.search(entry):
        return entry
    return " "


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_for_diff(text: str, source_system: str) -> str:
    """Return normalized text for change detection, stripping cosmetic boilerplate.

    Parameters
    ----------
    text:
        Raw ``body_text`` of a ``CodeSection``.
    source_system:
        Value of ``CodeSection.source_system`` (e.g. ``"iac"``, ``"cfr"``).
        Comparison is case-insensitive.

    Returns
    -------
    str
        Normalized text suitable for hashing.  The original ``text`` is never
        modified in place; a new string is always returned.
    """
    if not text:
        return text or ""

    t = text
    sys = source_system.lower()

    if sys == "iac":
        # 1. Normalize spurious spaces inside document reference codes and
        #    Public Law references (before footer detection).
        t = _IAC_IR_SPACE.sub(r"\1-IR-\2", t)
        t = _IAC_PL_SPACE.sub(r"\1\2", t)

        # 2. Strip "Sec. N." DIN section markers.
        t = _IAC_DIN_PREFIX.sub(" ", t)

        # 3. Strip filing-history parentheticals (incl. appended readoptions).
        t = _IAC_PAREN.sub(_drop_filing_history, t)

        # 4. Normalize hyphen-space artifacts in citations and compounds.
        t = _HYPHEN_SPACE.sub("-", t)

    elif sys == "cfr":
        # 1. Strip trailing Federal Register citation block "[XX FR …]".
        t = _CFR_FR_FOOTER.sub("", t)

        # 2. Strip trailing inline FR amendment note "(XX FR …)".
        t = _CFR_FR_INLINE.sub("", t)

        # 3. Strip eCFR "Link to an amendment published at …" notes.
        t = _CFR_AMEND_LINK.sub(" ", t)

    # General: collapse internal runs of whitespace and trim ends.
    t = re.sub(r"\s+", " ", t).strip()

    return t

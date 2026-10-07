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

# "Sec. N." DIN prefix at start of a section body (e.g. "Sec. 18. (Repealed…)")
_IAC_DIN_PREFIX = re.compile(r"^\s*Sec\.\s+\d+(?:\.\d+)*\.\s*", re.MULTILINE)

# Trailing filing-history parenthetical:
#   (Agency Name; citation; filed …; readopted filed …; filed …: YYYYMMDD-IR-NNNNXXX )
# We match the LAST closing parenthesis that contains an IR-style document code.
_IAC_FOOTER = re.compile(
    r"\s*\([^()]*\d{8}-IR-\d+[A-Z]{2,3}[^()]*\)\s*$",
    re.DOTALL | re.IGNORECASE,
)

# Spurious space inside an IR document reference code:
#   "20100623-IR- 170090792FRA" → "20100623-IR-170090792FRA"
_IAC_IR_SPACE = re.compile(r"(\d{8}-IR-)\s+(\d+[A-Z]{2,3})")

# Spurious space inside Public Law references:
#   "P.L.101- 549" → "P.L.101-549"
_IAC_PL_SPACE = re.compile(r"(P\.L\.\d+-)\s+(\d+)")


# ---------------------------------------------------------------------------
# CFR patterns
# ---------------------------------------------------------------------------

# Trailing Federal Register citation block:
#   [Order NNN, XX FR NNNNN, Month Day, Year; …]
_CFR_FR_FOOTER = re.compile(
    r"\s*\[\s*\d+\s+FR\s+\d+[^\]]*\]\s*$",
    re.DOTALL | re.IGNORECASE,
)

# Alternative inline FR amendment note at end of sections:
#   (XX FR NNNNN, Month Day, Year)
_CFR_FR_INLINE = re.compile(
    r"\s*\(\s*\d+\s+FR\s+\d+[^)]*\)\s*$",
    re.DOTALL | re.IGNORECASE,
)


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
        # 1. Strip leading "Sec. N." section-number prefix (DIN line artifact).
        t = _IAC_DIN_PREFIX.sub("", t, count=1)

        # 2. Strip trailing filing-history parenthetical footer.
        t = _IAC_FOOTER.sub("", t)

        # 3. Normalize spurious spaces inside document reference codes.
        t = _IAC_IR_SPACE.sub(r"\1\2", t)

        # 4. Normalize spurious spaces inside Public Law references.
        t = _IAC_PL_SPACE.sub(r"\1\2", t)

    elif sys == "cfr":
        # 1. Strip trailing Federal Register citation block "[XX FR …]".
        t = _CFR_FR_FOOTER.sub("", t)

        # 2. Strip trailing inline FR amendment note "(XX FR …)".
        t = _CFR_FR_INLINE.sub("", t)

    # General: collapse internal runs of whitespace and trim ends.
    t = re.sub(r"\s+", " ", t).strip()

    return t

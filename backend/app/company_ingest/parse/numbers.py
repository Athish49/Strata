"""Numeric utilities: word-to-number conversion and numeral normalization."""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Lookup tables
# ---------------------------------------------------------------------------

_ONES: dict[str, int] = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

_TENS: dict[str, int] = {
    "twenty": 20,
    "thirty": 30,
    "forty": 40,
    "fifty": 50,
    "sixty": 60,
    "seventy": 70,
    "eighty": 80,
    "ninety": 90,
}

_FRACTIONS: dict[str, float] = {
    "one-half": 0.5,
    "one-quarter": 0.25,
    "three-quarters": 0.75,
    "one-third": 1 / 3,
    "two-thirds": 2 / 3,
}

# Pattern that captures a parenthetical digit group: "fourteen (14)"
_PAREN_DIGIT_RE = re.compile(r"\((\d+)\)")


def words_to_number(text: str) -> "int | float | None":
    """Convert a word-number phrase to an int (or float for fractions).

    Covers 0–1000.  When a parenthetical digit is present (e.g. "ten (10)")
    the parenthetical digit takes precedence.

    Returns None if the input is not recognized.
    """
    if not text:
        return None

    text = text.strip().lower()

    # Prefer parenthetical digit if present: "fourteen (14)" → 14
    m = _PAREN_DIGIT_RE.search(text)
    if m:
        return int(m.group(1))

    # Fraction shorthand
    if text in _FRACTIONS:
        return _FRACTIONS[text]

    # Direct ones/teens/twenty lookup
    if text in _ONES:
        return _ONES[text]

    # Bare tens word: "thirty", "forty", etc.
    if text in _TENS:
        return _TENS[text]

    # "hundred" alone → 100
    if text == "hundred":
        return 100

    # "thousand" alone → 1000
    if text == "thousand":
        return 1000

    # "X hundred" → X * 100  (e.g. "five hundred")
    hundred_match = re.fullmatch(r"(\w+)\s+hundred", text)
    if hundred_match:
        base_word = hundred_match.group(1)
        if base_word in _ONES:
            return _ONES[base_word] * 100

    # "X thousand" → X * 1000
    thousand_match = re.fullmatch(r"(\w+)\s+thousand", text)
    if thousand_match:
        base_word = thousand_match.group(1)
        if base_word in _ONES:
            return _ONES[base_word] * 1000

    # "thirty-five" style (tens-hyphen-ones)
    hyphen_match = re.fullmatch(r"(\w+)-(\w+)", text)
    if hyphen_match:
        tens_word, ones_word = hyphen_match.group(1), hyphen_match.group(2)
        if tens_word in _TENS and ones_word in _ONES:
            result = _TENS[tens_word] + _ONES[ones_word]
            return result

    # "thirty five" style (tens space ones)
    space_match = re.fullmatch(r"(\w+)\s+(\w+)", text)
    if space_match:
        tens_word, ones_word = space_match.group(1), space_match.group(2)
        if tens_word in _TENS and ones_word in _ONES:
            return _TENS[tens_word] + _ONES[ones_word]

    return None


# ---------------------------------------------------------------------------
# normalize_numeral
# ---------------------------------------------------------------------------

# Regex patterns used by normalize_numeral
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_CURRENCY_RE = re.compile(r"^[\$£€¥](\d[\d,]*(?:\.\d+)?)$")
_PLAIN_NUMBER_RE = re.compile(r"^(\d[\d,]*(?:\.\d+)?)$")
_SUFFIX_NUMBER_RE = re.compile(r"^(\d[\d,]*(?:\.\d+)?)-\w+")


def normalize_numeral(text: str) -> "tuple[float | None, str]":
    """Parse a raw text snippet into (numeric_value, canonical_text).

    Handles:
    - "30-day"          → (30.0, "30")
    - "$45.00"          → (45.0, "45.00")
    - "2,500"           → (2500.0, "2500")
    - "08:00"           → (None, "") — times are skipped
    - "ten (10) …"      → (10.0, "10")
    - Plain integers    → (float(n), str(n))

    Returns (None, "") when the input is not recognized or is a time.
    """
    stripped = text.strip()

    if not stripped:
        return (None, "")

    # Skip times
    if _TIME_RE.match(stripped):
        return (None, "")

    # Prefer parenthetical digit: "ten (10) business days"
    paren_m = _PAREN_DIGIT_RE.search(stripped)
    if paren_m:
        raw = paren_m.group(1)
        val = float(raw)
        return (val, raw)

    # Currency: "$45.00" → (45.0, "45.00")
    curr_m = _CURRENCY_RE.match(stripped)
    if curr_m:
        raw = curr_m.group(1).replace(",", "")
        val = float(raw)
        # canonical: remove trailing .00 only when value is whole
        if val == int(val) and "." in curr_m.group(1):
            # keep the decimal representation as given
            pass
        canonical = curr_m.group(1).replace(",", "")
        return (val, canonical)

    # "30-day" style: leading digits, then hyphen + non-digit suffix
    suffix_m = _SUFFIX_NUMBER_RE.match(stripped)
    if suffix_m:
        raw = suffix_m.group(1).replace(",", "")
        val = float(raw)
        canonical = suffix_m.group(1).replace(",", "")
        return (val, canonical)

    # Plain number with optional commas: "2,500" or "100"
    plain_m = _PLAIN_NUMBER_RE.match(stripped)
    if plain_m:
        raw = plain_m.group(1).replace(",", "")
        val = float(raw)
        canonical = raw
        return (val, canonical)

    # Word number (delegates to words_to_number)
    wn = words_to_number(stripped)
    if wn is not None:
        val = float(wn)
        canonical = str(int(wn)) if isinstance(wn, int) else str(wn)
        return (val, canonical)

    return (None, "")

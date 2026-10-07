"""Text utilities: normalization, hashing, and offset finding."""

import hashlib
import re
import unicodedata


def normalize(text: str) -> str:
    """Normalize text for downstream extraction and comparison.

    Steps (applied in order):
    1. NFKC Unicode normalization
    2. Lowercase
    3. Unify curly/smart quotes → straight quotes
    4. Unify en/em dashes → hyphen
    5. Non-breaking space (U+00A0) → regular space
    6. Keep § as-is
    7. Strip Markdown emphasis: **text** → text, *text* → text, _text_ → text
    8. Strip Markdown link syntax: [text](url) → text
    9. Collapse whitespace (multiple spaces/tabs/newlines → single space, strip)
    """
    # 1. NFKC Unicode normalization
    text = unicodedata.normalize("NFKC", text)

    # 2. Lowercase
    text = text.lower()

    # 3. Unify curly/smart quotes → straight quotes
    # Double quotes: " (U+201C) and " (U+201D) → "
    text = text.replace("“", '"').replace("”", '"')
    # Single quotes/apostrophes: ' (U+2018) and ' (U+2019) → '
    text = text.replace("‘", "'").replace("’", "'")

    # 4. Unify en/em dashes → hyphen
    # En dash (U+2013), em dash (U+2014) → -
    text = text.replace("–", "-").replace("—", "-")

    # 5. Non-breaking space (U+00A0) → regular space
    text = text.replace(" ", " ")

    # 6. § stays as-is (no action needed)

    # 7. Strip Markdown emphasis
    # **text** → text (bold, must come before single *)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # *text* → text (italic)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # _text_ → text (italic underscore)
    text = re.sub(r"_(.+?)_", r"\1", text)

    # 8. Strip Markdown link syntax: [text](url) → text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)

    # 9. Collapse whitespace
    text = re.sub(r"[ \t\n\r\f\v]+", " ", text)
    text = text.strip()

    return text


def sha256_text(text: str) -> str:
    """Return the SHA-256 hex digest of text encoded as UTF-8.

    Hashes the exact bytes with no normalization applied.
    """
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def find_verbatim(haystack: str, needle: str) -> list[tuple[int, int]]:
    """Return all (start, end) char offsets where needle appears in haystack.

    Performs an exact substring search.  Returns an empty list when needle is
    not found or when either argument is an empty string.
    """
    if not needle:
        return []

    results: list[tuple[int, int]] = []
    start = 0
    needle_len = len(needle)
    while True:
        pos = haystack.find(needle, start)
        if pos == -1:
            break
        results.append((pos, pos + needle_len))
        start = pos + 1
    return results

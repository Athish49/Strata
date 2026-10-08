"""Quote verification and location (engine_spec §4.3 P1, §2.3; api_ui §1.1).

Matching is a substring check on normalized text:
  - case-insensitive (lower-cased),
  - every whitespace run (spaces, tabs, newlines, NBSP...) collapses to one space,
    and leading/trailing whitespace is ignored,
  - unicode punctuation variants are treated as their ASCII equivalents: curly
    single/double quotes -> ' and ", all dash-like characters (hyphen, non-breaking
    hyphen, en/em dash, minus sign...) -> '-'; other compatibility forms go through
    NFKC (e.g. ellipsis -> "...", NBSP -> space).
Quotes shorter than MIN_QUOTE_LEN characters after normalization never verify.
"""
import unicodedata

MIN_QUOTE_LEN = 8

_PUNCT = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
    "―": "-", "−": "-", "­": "",
}


def _normalize(s: str) -> tuple[str, list[int]]:
    """Return (normalized, offsets) where offsets[i] is the index in `s` of the
    original character that produced normalized[i]."""
    out: list[str] = []
    idx: list[int] = []
    pending_space = False
    for i, ch in enumerate(s):
        ch = _PUNCT.get(ch, ch)
        for c in unicodedata.normalize("NFKC", ch).lower():
            c = _PUNCT.get(c, c)
            if c == "":
                continue
            if c.isspace():
                pending_space = True
                continue
            if pending_space and out:  # drop leading whitespace
                out.append(" ")
                idx.append(i)  # unused as an end offset; the span never ends on a space
            pending_space = False
            out.append(c)
            idx.append(i)
    return "".join(out), idx


def locate_quote(quote: str, text: str) -> tuple[int, int] | None:
    """Offsets (start inclusive, end exclusive) of the first match of `quote` in the
    original `text`, or None. text[start:end] is the matched span."""
    if not quote or not text:
        return None
    q, _ = _normalize(quote)
    if len(q) < MIN_QUOTE_LEN:
        return None
    t, idx = _normalize(text)
    pos = t.find(q)
    if pos < 0:
        return None
    return idx[pos], idx[pos + len(q) - 1] + 1


def verify_quote(quote: str, text: str) -> bool:
    return locate_quote(quote, text) is not None

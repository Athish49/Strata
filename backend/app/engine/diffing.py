"""Word-level diff helpers for the impact engine (engine_spec §1.3). Pure and deterministic."""
from __future__ import annotations

import difflib
import re

_TOKEN_RE = re.compile(r"\w+|[^\w\s]")
_WORD_CHAR_RE = re.compile(r"\w")


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)


def _opcodes(a_tok: list[str], b_tok: list[str]):
    return difflib.SequenceMatcher(None, a_tok, b_tok, autojunk=False).get_opcodes()


def diff_segments(a: str, b: str) -> list[dict]:
    """Equal/delete/insert runs, tokens joined with single spaces.

    A replace opcode becomes a delete segment followed by an insert segment.
    Adjacent same-op segments are merged.
    """
    a_tok, b_tok = tokenize(a), tokenize(b)
    segments: list[dict] = []

    def add(op: str, toks: list[str]) -> None:
        if not toks:
            return
        text = " ".join(toks)
        if segments and segments[-1]["op"] == op:
            segments[-1]["text"] += " " + text
        else:
            segments.append({"op": op, "text": text})

    for tag, i1, i2, j1, j2 in _opcodes(a_tok, b_tok):
        if tag == "equal":
            add("equal", a_tok[i1:i2])
        else:
            add("delete", a_tok[i1:i2])
            add("insert", b_tok[j1:j2])
    return segments


def changed_tokens(a: str, b: str) -> dict:
    """Changed tokens as {"deleted": [(index_in_a, token)], "inserted": [(index_in_b, token)]}."""
    a_tok, b_tok = tokenize(a), tokenize(b)
    deleted: list[tuple[int, str]] = []
    inserted: list[tuple[int, str]] = []
    for tag, i1, i2, j1, j2 in _opcodes(a_tok, b_tok):
        if tag == "equal":
            continue
        deleted.extend((i, a_tok[i]) for i in range(i1, i2))
        inserted.extend((j, b_tok[j]) for j in range(j1, j2))
    return {"deleted": deleted, "inserted": inserted}


def only_punct(changed: dict) -> bool:
    """True iff every changed token has no word characters (empty change -> True)."""
    for side in ("deleted", "inserted"):
        for _idx, tok in changed.get(side, []):
            if _WORD_CHAR_RE.search(tok):
                return False
    return True


def changed_token_char_spans(text: str, token_indexes) -> list[tuple[int, int]]:
    """Map token indexes (in tokenize(text) order) to (start, end) char spans in text."""
    wanted = {t[0] if isinstance(t, (tuple, list)) else t for t in token_indexes}
    if not wanted:
        return []
    out = []
    for i, m in enumerate(_TOKEN_RE.finditer(text)):
        if i in wanted:
            out.append((m.start(), m.end()))
    return out


def all_changed_inside_spans(changed_side_tokens, text: str, spans) -> bool:
    """True iff every changed token on one side lies fully inside one of *spans* in *text*.

    changed_side_tokens: the "deleted" or "inserted" list from changed_tokens (or bare indexes).
    spans: find_citation_spans() output ((start, end, raw) tuples) or (start, end) pairs.
    An empty side is vacuously True.
    """
    ranges = [(s[0], s[1]) for s in spans]
    for start, end in changed_token_char_spans(text, changed_side_tokens):
        if not any(rs <= start and end <= re_ for rs, re_ in ranges):
            return False
    return True

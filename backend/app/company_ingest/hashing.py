"""Document-level canonicalization and content hashing.

This module computes **the document hash** — the value stored in
``company_documents.current_content_hash`` and used for duplicate and change
detection. It is taken over the *canonically-extracted text* of a document,
not over the raw uploaded bytes, so that a DOCX re-saved from Word with
identical wording but different bytes is recognised as the same content
(``architecture.md`` §4).

Three distinct hashes exist in this system; conflating them is the main design
hazard in this area (``architecture.md`` §4):

===========================================  ==================================
Hash                                         Over
===========================================  ==================================
``company_documents.current_content_hash``   canonical extracted text (here)
``clauses.text_sha256``                      one clause's raw ``text_raw``
R2 object metadata ``sha256``                raw uploaded bytes
===========================================  ==================================

In particular, **do not** reuse ``parse/text.py:sha256_text`` here: it
deliberately hashes raw text with no normalization and is the clause-level LLM
cache key — a different concern.

This module is intentionally pure: standard library only, no configuration, no
database, no extractor imports.
"""

import hashlib
import re
import unicodedata

__all__ = ["canonicalize", "content_hash"]

_WS = re.compile(r"\s+")


def _strip_format_chars(text: str) -> str:
    """Drop Unicode format characters (general category Cf).

    These are zero-width and carry no meaning for a compliance document, but
    Word and PDF exporters insert them freely, and Python's ``\\s`` does *not*
    match them — so without this step a re-export differing only by invisible
    characters would hash differently, defeating the purpose of hashing text
    rather than bytes. Covers soft hyphen U+00AD (optional hyphenation),
    zero-width space U+200B, BOM / zero-width no-break space U+FEFF, the
    Mongolian vowel separator U+180E, and the bidi marks.
    """
    return "".join(c for c in text if unicodedata.category(c) != "Cf")


def canonicalize(text: str) -> str:
    """Normalize extracted text so cosmetically-different exports hash equal.

    Unicode NFC, then zero-width format characters removed, then every
    whitespace run (spaces, tabs, newlines, CR, and Unicode whitespace such as
    U+00A0) collapsed to a single space, then stripped.

    Collapsing *all* whitespace rather than only newlines is what makes a Word
    re-export with different line wrapping hash equal. Note the accepted
    consequence: because newlines are collapsed too, paragraph splits and list
    *nesting depth* become invisible to this hash (``"- a\\n  - b"`` and
    ``"- a\\n- b"`` hash equal). Heading changes are still caught, because the
    ``#`` markers survive.
    """
    t = unicodedata.normalize("NFC", text)
    t = _strip_format_chars(t)
    t = _WS.sub(" ", t)  # all whitespace runs -> single space
    return t.strip()


def content_hash(text: str) -> str:
    """SHA-256 hex digest of the canonical form. The document hash.

    SHA-256 rather than xxHash: it is already the repo-wide standard, and a
    collision would wrongly reject a customer's real document. Returns 64
    lowercase hex characters.
    """
    return hashlib.sha256(canonicalize(text).encode("utf-8")).hexdigest()

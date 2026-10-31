"""Tests for app.company_ingest.hashing — the document hash.

Every non-ASCII or whitespace character under test is written as an explicit
escape (``"\\u00e9"``, ``"\\u00a0"``) rather than a literal, and precondition
asserts guard against an editor or formatter silently normalizing this source
file and making the Unicode tests vacuous.
"""

import ast
import hashlib
import pathlib
import re
import unicodedata

from app.company_ingest.hashing import canonicalize, content_hash

HEX64 = re.compile(r"[0-9a-f]{64}")


# --------------------------------------------------------------------------
# Cosmetic differences must hash EQUAL
# --------------------------------------------------------------------------


def test_line_wrapping_differences_hash_equal():
    wrapped = "The operator shall maintain\nrecords for five years."
    one_line = "The operator shall maintain records for five years."
    assert content_hash(wrapped) == content_hash(one_line)


def test_indentation_differences_hash_equal():
    indented = "# Title\n\n    - item one\n    - item two\n"
    flat = "# Title\n- item one\n- item two"
    assert content_hash(indented) == content_hash(flat)


def test_trailing_whitespace_differences_hash_equal():
    a = "alpha   \nbeta\t\t\n\n\n"
    b = "alpha beta"
    assert content_hash(a) == content_hash(b)


def test_crlf_vs_lf_hash_equal():
    crlf = "line one\r\nline two\r\nline three"
    lf = "line one\nline two\nline three"
    cr = "line one\rline two\rline three"
    assert content_hash(crlf) == content_hash(lf) == content_hash(cr)


def test_tabs_and_nbsp_collapse_like_spaces():
    nbsp = " "
    assert nbsp != " "
    variants = [
        "a b",
        "a\tb",
        "a \t b",
        "a" + nbsp + "b",
        "a" + nbsp * 3 + "\n\tb",
        "a b",  # EM SPACE
        "a　b",  # IDEOGRAPHIC SPACE
    ]
    hashes = {content_hash(v) for v in variants}
    assert len(hashes) == 1, hashes


def test_mixed_line_endings_and_form_feeds_hash_equal():
    messy = "  Section 1\r\n\r\n\tBody text\x0c here.\v\r \n"
    clean = "Section 1 Body text here."
    assert content_hash(messy) == content_hash(clean)


def test_word_reexport_style_rewrap_hashes_equal():
    original = (
        "## 3.2 Recordkeeping\n\n"
        "The licensee shall retain all inspection records\n"
        "for a period of not less than five (5) years.\n"
    )
    reexport = (
        "## 3.2 Recordkeeping\r\n\r\n"
        "   The licensee shall retain all inspection\r\n"
        "   records for a period of not less than five (5) years.   \r\n\r\n"
    )
    assert content_hash(original) == content_hash(reexport)


# --------------------------------------------------------------------------
# Real content differences must hash DIFFERENTLY
# --------------------------------------------------------------------------


def test_one_word_difference_hashes_differently():
    a = "The operator shall maintain records."
    b = "The operator may maintain records."
    assert content_hash(a) != content_hash(b)


def test_single_character_difference_hashes_differently():
    assert content_hash("retain for 5 years") != content_hash("retain for 6 years")


def test_word_order_difference_hashes_differently():
    assert content_hash("alpha beta") != content_hash("beta alpha")


def test_heading_level_change_hashes_differently():
    assert content_hash("## Recordkeeping") != content_hash("### Recordkeeping")


def test_collapse_is_not_deletion():
    # Whitespace runs collapse to a *single space*, never to nothing, so token
    # boundaries survive. This is the core reason collapsing ALL whitespace
    # does not create word-level false duplicates.
    assert content_hash("rec ords") != content_hash("records")
    assert content_hash("5 000") != content_hash("5000")
    assert canonicalize("rec\nords") == "rec ords"


def test_known_false_duplicate_list_nesting():
    # ACCEPTED CONSEQUENCE, documented not desired: indentation-encoded list
    # depth is erased, so promoting a sub-item to a peer item hashes equal.
    assert content_hash("- a\n  - b") == content_hash("- a\n- b")


# --------------------------------------------------------------------------
# Empty / whitespace-only input
# --------------------------------------------------------------------------


def test_canonicalize_empty_string():
    assert canonicalize("") == ""


def test_canonicalize_whitespace_only():
    assert canonicalize("   \n\n ") == ""


def test_canonicalize_assorted_whitespace_only():
    assert canonicalize("\r\n\t  \x0b\x0c   ") == ""


def test_empty_and_whitespace_only_hash_equal():
    assert content_hash("") == content_hash("   \n\n ") == hashlib.sha256(b"").hexdigest()


# --------------------------------------------------------------------------
# Unicode: NFC vs NFD
# --------------------------------------------------------------------------


def test_nfc_and_nfd_hash_equal():
    composed = "é"  # é as a single code point
    decomposed = "é"  # e + COMBINING ACUTE ACCENT
    # Preconditions: guard against source-file normalization.
    assert composed != decomposed
    assert len(composed) == 1
    assert len(decomposed) == 2
    assert content_hash(composed) == content_hash(decomposed)
    assert canonicalize(decomposed) == composed


def test_nfc_and_nfd_hash_equal_in_sentence():
    composed = "Café résumé naïve"
    decomposed = "Café résumé naïve"
    assert composed != decomposed
    assert content_hash(composed) == content_hash(decomposed)


def test_hangul_nfd_hash_equal():
    composed = "한"  # HANGUL SYLLABLE HAN
    decomposed = "한"  # jamo sequence
    assert composed != decomposed
    assert content_hash(composed) == content_hash(decomposed)


# --------------------------------------------------------------------------
# Output shape
# --------------------------------------------------------------------------


def test_output_is_64_lowercase_hex_chars():
    for sample in ["", " ", "The operator shall.", "é", "a\tb\nc"]:
        h = content_hash(sample)
        assert len(h) == 64
        assert HEX64.fullmatch(h), h
        assert h == h.lower()


def test_hash_is_deterministic():
    text = "The operator shall maintain records for five years."
    assert content_hash(text) == content_hash(text)


# --------------------------------------------------------------------------
# Golden canonical form — these values are what Neon rows depend on
# --------------------------------------------------------------------------


def test_golden_canonical_form():
    assert canonicalize("  a\r\n\tb  ") == "a b"
    assert content_hash("  a\r\n\tb  ") == hashlib.sha256(b"a b").hexdigest()


def test_golden_known_sentence():
    text = "The operator shall maintain records."
    assert content_hash(text) == hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# This is NOT parse/text.py:normalize — pin the differences
#
# normalize() lowercases, folds smart quotes and dashes, applies NFKC and
# strips Markdown. Accidentally substituting it here would make genuinely
# different documents hash equal.
# --------------------------------------------------------------------------


def test_case_is_significant():
    assert content_hash("Shall") != content_hash("shall")


def test_smart_quotes_are_significant():
    assert content_hash("“x”") != content_hash('"x"')


def test_dashes_are_significant():
    assert content_hash("a—b") != content_hash("a-b")
    assert content_hash("a–b") != content_hash("a-b")


def test_nfkc_compatibility_folding_is_not_applied():
    ligature = "ﬁ"  # LATIN SMALL LIGATURE FI
    assert len(ligature) == 1
    assert content_hash(ligature) != content_hash("fi")


def test_markdown_emphasis_is_significant():
    assert content_hash("**x**") != content_hash("x")
    assert content_hash("[text](url)") != content_hash("text")


def test_zero_width_format_chars_are_removed():
    """Format characters (category Cf) are stripped, not collapsed.

    Python's ``\\s`` does not match these, so an earlier revision let them
    change the hash. Word and PDF exporters insert them freely, so a re-export
    differing only by invisible characters would have been treated as a new
    document — defeating the reason we hash text rather than bytes. They are
    now removed outright.
    """
    for ch in ["​", "﻿", "­", "᠎", "‎", "‏"]:
        assert unicodedata.category(ch) == "Cf", repr(ch)
        assert re.fullmatch(r"\s", ch) is None, repr(ch)
        assert content_hash("a" + ch + "b") == content_hash("ab"), repr(ch)


def test_soft_hyphen_reexport_matches():
    """The concrete Word case: optional hyphenation must not change the hash."""
    assert content_hash("The oper­ator shall com­ply.") == content_hash(
        "The operator shall comply."
    )


def test_real_hyphen_remains_significant():
    """A real hyphen is content, not formatting, and must stay distinguishing."""
    assert content_hash("compli-ance") != content_hash("compliance")


def test_ascii_control_separators_are_collapsed():
    # \x1c-\x1f and \x85 DO match Python's \s for str patterns.
    for c in ["\x1c", "\x1d", "\x1e", "\x1f", "\x85"]:
        assert re.fullmatch(r"\s", c), repr(c)
        assert content_hash("a" + c + "b") == content_hash("a b")


# --------------------------------------------------------------------------
# Module purity
# --------------------------------------------------------------------------


def test_module_imports_stdlib_only():
    path = pathlib.Path(__file__).resolve().parents[2] / "app" / "company_ingest" / "hashing.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module.split(".")[0])
    assert imported <= {"hashlib", "re", "unicodedata"}, imported

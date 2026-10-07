"""Task 1.3.1: Table-driven unit tests for text utilities and number parsing.

Covers:
- normalize()        – smart quotes, em/en dash, markdown stripping, whitespace
- sha256_text()      – stability and uniqueness
- words_to_number()  – word numbers, parenthetical digits, fractions
- normalize_numeral()– "30-day", "$45.00", "2,500", word+paren, times
- find_verbatim()    – multiple occurrences, absent needle, edge cases
"""

import pytest

from app.company_ingest.parse.text import find_verbatim, normalize, sha256_text
from app.company_ingest.parse.numbers import normalize_numeral, words_to_number


# ===========================================================================
# normalize()
# ===========================================================================

class TestNormalize:
    # --- smart quotes ---

    def test_double_smart_quotes_left(self):
        assert normalize("“hello”") == '"hello"'

    def test_double_smart_quotes_right(self):
        # already covered above but explicit about right quote alone
        assert normalize("”") == '"'

    def test_single_smart_quotes(self):
        assert normalize("‘it’s") == "'it's"

    def test_mixed_smart_quotes(self):
        assert normalize("“don’t”") == '"don\'t"'

    # --- dashes ---

    def test_en_dash(self):
        assert normalize("2020–2021") == "2020-2021"

    def test_em_dash(self):
        assert normalize("foo—bar") == "foo-bar"

    def test_multiple_dashes(self):
        assert normalize("a–b—c") == "a-b-c"

    # --- non-breaking space ---

    def test_nbsp_becomes_space(self):
        assert normalize("hello world") == "hello world"

    # --- section symbol preserved ---

    def test_section_symbol_preserved(self):
        result = normalize("see §1.2 for details")
        assert "§" in result

    # --- markdown emphasis ---

    def test_bold_double_asterisk(self):
        assert normalize("**important**") == "important"

    def test_italic_single_asterisk(self):
        assert normalize("*note*") == "note"

    def test_italic_underscore(self):
        assert normalize("_term_") == "term"

    def test_bold_in_sentence(self):
        assert normalize("the **fee** applies") == "the fee applies"

    def test_italic_in_sentence(self):
        assert normalize("a *soft* limit") == "a soft limit"

    def test_underscore_italic_in_sentence(self):
        assert normalize("an _optional_ clause") == "an optional clause"

    # --- markdown links ---

    def test_markdown_link(self):
        assert normalize("[click here](https://example.com)") == "click here"

    def test_markdown_link_in_sentence(self):
        result = normalize("see [docs](http://x.com) for more")
        assert result == "see docs for more"

    # --- whitespace collapse ---

    def test_multiple_spaces_collapsed(self):
        assert normalize("hello    world") == "hello world"

    def test_tabs_collapsed(self):
        assert normalize("hello\t\tworld") == "hello world"

    def test_newlines_collapsed(self):
        assert normalize("line1\n\nline2") == "line1 line2"

    def test_leading_trailing_whitespace_stripped(self):
        assert normalize("   hello   ") == "hello"

    def test_mixed_whitespace(self):
        assert normalize("  a  \t b \n c  ") == "a b c"

    # --- lowercase ---

    def test_lowercase_applied(self):
        assert normalize("Hello World") == "hello world"

    # --- NFKC normalization ---

    def test_nfkc_ligature(self):
        # ﬁ (U+FB01) → fi after NFKC
        result = normalize("ﬁle")
        assert result == "file"

    # --- combined ---

    def test_combined_smart_quote_and_dash(self):
        result = normalize("“foo” – bar")
        assert result == '"foo" - bar'

    def test_combined_bold_and_link(self):
        result = normalize("**[bold link](http://x.com)**")
        # bold strips outer **, link collapses to text
        assert "bold link" in result


# ===========================================================================
# sha256_text()
# ===========================================================================

class TestSha256Text:
    def test_returns_64_hex_chars(self):
        digest = sha256_text("hello")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_stable_across_calls(self):
        assert sha256_text("hello world") == sha256_text("hello world")

    def test_different_inputs_differ(self):
        assert sha256_text("abc") != sha256_text("ABC")

    def test_empty_string_hashes(self):
        # SHA-256 of empty string is well-known
        digest = sha256_text("")
        assert digest == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_no_normalization_applied(self):
        # Different case → different hash (normalization NOT applied)
        assert sha256_text("Hello") != sha256_text("hello")

    def test_unicode_stability(self):
        text = "café"
        assert sha256_text(text) == sha256_text(text)


# ===========================================================================
# words_to_number()
# ===========================================================================

class TestWordsToNumber:
    # --- parenthetical digit takes precedence ---

    def test_parenthetical_fourteen(self):
        assert words_to_number("fourteen (14)") == 14

    def test_parenthetical_ten(self):
        assert words_to_number("ten (10)") == 10

    def test_parenthetical_in_phrase(self):
        # extra trailing text should still match the paren
        assert words_to_number("thirty (30) days") == 30

    # --- basic ones and teens ---

    def test_zero(self):
        assert words_to_number("zero") == 0

    def test_one(self):
        assert words_to_number("one") == 1

    def test_twelve(self):
        assert words_to_number("twelve") == 12

    def test_nineteen(self):
        assert words_to_number("nineteen") == 19

    def test_twenty(self):
        assert words_to_number("twenty") == 20

    # --- tens ---

    def test_thirty(self):
        assert words_to_number("thirty") == 30

    def test_ninety(self):
        assert words_to_number("ninety") == 90

    # --- compound (tens + ones) ---

    def test_thirty_five_hyphen(self):
        assert words_to_number("thirty-five") == 35

    def test_forty_two_space(self):
        assert words_to_number("forty two") == 42

    def test_twenty_one(self):
        assert words_to_number("twenty-one") == 21

    # --- hundred / thousand ---

    def test_hundred(self):
        assert words_to_number("hundred") == 100

    def test_five_hundred(self):
        assert words_to_number("five hundred") == 500

    def test_thousand(self):
        assert words_to_number("thousand") == 1000

    def test_two_thousand(self):
        assert words_to_number("two thousand") == 2000

    # --- fractions ---

    def test_one_half(self):
        assert words_to_number("one-half") == 0.5

    # --- unrecognized → None ---

    def test_unrecognized_returns_none(self):
        assert words_to_number("banana") is None

    def test_empty_returns_none(self):
        assert words_to_number("") is None


# ===========================================================================
# normalize_numeral()
# ===========================================================================

class TestNormalizeNumeral:
    def test_30_day(self):
        val, canon = normalize_numeral("30-day")
        assert val == 30.0
        assert canon == "30"

    def test_currency_45_00(self):
        val, canon = normalize_numeral("$45.00")
        assert val == 45.0
        assert canon == "45.00"

    def test_comma_number_2500(self):
        val, canon = normalize_numeral("2,500")
        assert val == 2500.0
        assert canon == "2500"

    def test_time_skipped(self):
        val, canon = normalize_numeral("08:00")
        assert val is None

    def test_time_with_seconds_skipped(self):
        val, canon = normalize_numeral("12:30:00")
        assert val is None

    def test_word_paren_phrase(self):
        val, canon = normalize_numeral("ten (10) business days")
        assert val == 10.0
        assert canon == "10"

    def test_plain_integer(self):
        val, canon = normalize_numeral("42")
        assert val == 42.0
        assert canon == "42"

    def test_plain_float(self):
        val, canon = normalize_numeral("3.14")
        assert val == pytest.approx(3.14)

    def test_empty_string(self):
        val, canon = normalize_numeral("")
        assert val is None

    def test_90_day(self):
        val, canon = normalize_numeral("90-day")
        assert val == 90.0
        assert canon == "90"


# ===========================================================================
# find_verbatim()
# ===========================================================================

class TestFindVerbatim:
    def test_single_occurrence(self):
        result = find_verbatim("hello world", "world")
        assert result == [(6, 11)]

    def test_multiple_occurrences(self):
        result = find_verbatim("abcabc", "abc")
        assert result == [(0, 3), (3, 6)]

    def test_not_found_returns_empty(self):
        result = find_verbatim("hello world", "xyz")
        assert result == []

    def test_empty_needle_returns_empty(self):
        result = find_verbatim("hello", "")
        assert result == []

    def test_empty_haystack_not_found(self):
        result = find_verbatim("", "abc")
        assert result == []

    def test_overlapping_matches(self):
        # "aaa" in "aaaa": positions 0 and 1
        result = find_verbatim("aaaa", "aaa")
        assert result == [(0, 3), (1, 4)]

    def test_offsets_are_correct(self):
        haystack = "fee: $30, penalty: $30"
        results = find_verbatim(haystack, "$30")
        assert len(results) == 2
        for start, end in results:
            assert haystack[start:end] == "$30"

    def test_start_of_string(self):
        result = find_verbatim("abc", "a")
        assert result == [(0, 1)]

    def test_end_of_string(self):
        result = find_verbatim("abc", "c")
        assert result == [(2, 3)]

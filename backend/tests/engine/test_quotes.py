from app.engine.quotes import locate_quote, verify_quote

TEXT = "  The owner shall\nmaintain   records\tfor five (5) years.  The owner shall notify the agency."


def _slice(q, t):
    span = locate_quote(q, t)
    assert span is not None
    return t[span[0]:span[1]]


def test_exact():
    assert verify_quote("maintain   records", TEXT)
    assert _slice("The owner shall\nmaintain", TEXT) == "The owner shall\nmaintain"


def test_case():
    assert verify_quote("THE OWNER SHALL MAINTAIN", TEXT)
    assert _slice("THE OWNER SHALL MAINTAIN", TEXT) == "The owner shall\nmaintain"


def test_whitespace_differences():
    assert verify_quote("owner shall maintain records for five", TEXT)
    assert _slice("owner shall maintain records for five", TEXT) == "owner shall\nmaintain   records\tfor five"
    assert verify_quote("owner   shall\n\nmaintain", TEXT)
    assert verify_quote("  owner shall maintain  \n", TEXT)


def test_too_short_and_empty():
    assert not verify_quote("owner", TEXT)
    assert not verify_quote("a  b  c ", "a b c d e f g h")  # 5 chars normalized
    assert verify_quote("abcdefgh", "xx abcdefgh yy")
    assert not verify_quote("", TEXT)
    assert not verify_quote(None, TEXT)
    assert not verify_quote("owner shall", None)
    assert locate_quote("", TEXT) is None and locate_quote(None, None) is None


def test_not_found():
    assert not verify_quote("the owner shall destroy records", TEXT)
    assert locate_quote("the owner shall destroy records", TEXT) is None


def test_offsets_leading_whitespace_and_first_occurrence():
    start, end = locate_quote("the owner shall", TEXT)
    assert start == 2 and TEXT[start:end] == "The owner shall"
    # repeated phrase -> first occurrence
    assert start < TEXT.index("The owner shall notify")
    s2, e2 = locate_quote("The owner shall notify", TEXT)
    assert TEXT[s2:e2] == "The owner shall notify"


def test_trailing_text_not_included():
    q = "five (5) years."
    assert _slice(q, TEXT) == "five (5) years."


def test_unicode_punctuation():
    text = "The “responsible party” shall comply — within 30 days; it’s required."
    assert verify_quote('the "responsible party" shall comply - within 30 days', text)
    assert verify_quote("it's required", text)
    assert _slice("it's required", text) == "it’s required"
    assert verify_quote("comply – within", text)
    assert verify_quote("shall comply", text)


def test_agreement_and_round_trip():
    cases = [("owner shall notify", TEXT), ("nothing here at all", TEXT), ("short", TEXT)]
    for q, t in cases:
        assert verify_quote(q, t) == (locate_quote(q, t) is not None)
    s, e = locate_quote("owner shall notify the agency", TEXT)
    assert TEXT[s:e].split() == "owner shall notify the agency".split()

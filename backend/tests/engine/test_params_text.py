from app.engine.params_text import extract_parameters_from_text, param_multiset_diff


def _by_unit(ps, unit):
    return [p for p in ps if p["unit"] == unit]


def test_word_and_paren_business_days():
    ps = extract_parameters_from_text("The utility shall respond within ten (10) business days.")
    assert len(ps) == 1
    p = ps[0]
    assert p["value_num"] == 10.0 and p["unit"] == "business_day" and p["day_type"] == "business"
    assert p["kind"] == "period"
    s, e = p["span"]
    assert "The utility shall respond within ten (10) business days."[s:e] == p["value_text"]


def test_dollar_amount():
    ps = extract_parameters_from_text("A fee of $25.00 applies.")
    assert [(p["kind"], p["unit"], p["value_num"]) for p in ps] == [("amount", "usd", 25.0)]


def test_at_least_hours():
    ps = extract_parameters_from_text("Notice of at least 48 hours is required.")
    assert len(ps) == 1
    assert ps[0]["unit"] == "hour" and ps[0]["value_num"] == 48.0 and ps[0]["day_type"] == "hours"


def test_citation_fragments_dropped():
    ps = extract_parameters_from_text("170 IAC 4-1-16 requires 30 days")
    assert [(p["unit"], p["value_num"]) for p in ps] == [("day", 30.0)]


def test_sorted_and_deterministic():
    t = "Pay $5.00 within 3 days and keep for 2 years."
    a = extract_parameters_from_text(t)
    assert a == extract_parameters_from_text(t)
    starts = [p["span"][0] for p in a]
    assert starts == sorted(starts) and len(a) == 3


def test_empty():
    assert extract_parameters_from_text("") == []


def test_multiset_diff():
    a = extract_parameters_from_text("within 5 calendar days")
    b = extract_parameters_from_text("within 7 calendar days")
    only_a, only_b = param_multiset_diff(a, b)
    assert [p["value_num"] for p in only_a] == [5.0]
    assert [p["value_num"] for p in only_b] == [7.0]
    assert param_multiset_diff(a, a) == ([], [])


def test_multiset_counts_duplicates():
    a = extract_parameters_from_text("5 days or 5 days")
    b = extract_parameters_from_text("5 days")
    only_a, only_b = param_multiset_diff(a, b)
    assert len(only_a) == 1 and only_b == []

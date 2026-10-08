from app.company_ingest.enrich.citations_grammar import find_citation_spans
from app.engine.diffing import (
    all_changed_inside_spans,
    changed_token_char_spans,
    changed_tokens,
    diff_segments,
    only_punct,
    tokenize,
)


def _rebuild(segs, ops):
    return " ".join(s["text"] for s in segs if s["op"] in ops)


def test_tokenize():
    assert tokenize("a, b-c.") == ["a", ",", "b", "-", "c", "."]


def test_identical_single_equal():
    assert diff_segments("the quick fox", "the quick fox") == [{"op": "equal", "text": "the quick fox"}]
    assert only_punct(changed_tokens("x y", "x y"))


def test_pure_insert_delete_replace():
    assert diff_segments("a b", "a x b") == [
        {"op": "equal", "text": "a"}, {"op": "insert", "text": "x"}, {"op": "equal", "text": "b"}]
    assert diff_segments("a x b", "a b") == [
        {"op": "equal", "text": "a"}, {"op": "delete", "text": "x"}, {"op": "equal", "text": "b"}]
    assert diff_segments("a x b", "a y b") == [
        {"op": "equal", "text": "a"}, {"op": "delete", "text": "x"},
        {"op": "insert", "text": "y"}, {"op": "equal", "text": "b"}]


def test_adjacent_same_op_merged():
    segs = diff_segments("a b c d", "a x y d")
    assert [s["op"] for s in segs] == ["equal", "delete", "insert", "equal"]
    assert segs[1]["text"] == "b c" and segs[2]["text"] == "x y"


def test_punct_only():
    ch = changed_tokens("a, b", "a b")
    assert ch["deleted"] == [(1, ",")] and ch["inserted"] == []
    assert only_punct(ch)


def test_word_change_not_punct():
    assert not only_punct(changed_tokens("a, b", "a, c"))


def test_cross_ref_span_helper():
    a = "Comply with 170 IAC 4-1-16 at all times."
    b = "Comply with 170 IAC 4-1-17 at all times."
    ch = changed_tokens(a, b)
    assert ch["deleted"] and ch["inserted"]
    assert all_changed_inside_spans(ch["deleted"], a, find_citation_spans(a))
    assert all_changed_inside_spans(ch["inserted"], b, find_citation_spans(b))
    spans = changed_token_char_spans(b, ch["inserted"])
    assert all(b[s:e] in ("17",) for s, e in spans)

    c = "Comply with 170 IAC 4-1-17 at some times."
    ch2 = changed_tokens(b, c)
    assert not all_changed_inside_spans(ch2["inserted"], c, find_citation_spans(c))


def test_segment_rejoin():
    a = "The utility shall, within 30 days, file a report."
    b = "The utility must file the report within 45 days."
    segs = diff_segments(a, b)
    assert _rebuild(segs, {"equal", "delete"}) == " ".join(tokenize(a))
    assert _rebuild(segs, {"equal", "insert"}) == " ".join(tokenize(b))
    assert _rebuild(segs, {"equal", "delete"}).replace(" ", "") == a.replace(" ", "")

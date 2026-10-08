import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

from recompute_citation_fragments import is_citation_fragment, is_whole_token


@pytest.mark.parametrize("value", ["4", "16", "170", "1"])
def test_whole_tokens_in_citation(value):
    # "1" is the middle segment of 4-1-16, so it is whole too
    assert is_whole_token(value, "170 IAC 4-1-16")


@pytest.mark.parametrize("value,cite", [
    ("4", "170 IAC 14-1"),
    ("25.00", "40 CFR 125.001"),
    ("10", "40 CFR 100"),
    ("2", "326 IAC 12-7"),
    ("$25.00", "170 IAC 4-1-16"),
    ("ten (10)", "170 IAC 4-1-16"),
])
def test_not_whole_tokens(value, cite):
    assert not is_whole_token(value, cite)


@pytest.mark.parametrize("value,cite", [
    ("6", "170 IAC 4-1-16.6"),
    ("6", "327 IAC 2-6.1"),
    ("1", "327 IAC 2-6.1"),
    ("761", "40 CFR 761.180"),
    ("180", "40 CFR 761.180"),
    ("4", "10 CFR 4.5"),
])
def test_decimal_section_tokens_are_whole(value, cite):
    assert is_whole_token(value, cite)


def test_paren_and_dash_boundaries():
    assert is_whole_token("4", "326 IAC 2-7-4(a)(1)")
    assert is_whole_token("1", "326 IAC 2-7-4(a)(1)")
    assert is_whole_token("2", "326 IAC 2-7-4(a)(1)")


def test_empty_inputs():
    assert not is_whole_token("", "170 IAC 4")
    assert not is_whole_token(None, "170 IAC 4")
    assert not is_whole_token("4", None)


def test_fragment_requires_number_without_unit():
    cites = ["170 IAC 4-1-16"]
    assert is_citation_fragment("number", None, "4", cites)
    assert not is_citation_fragment("number", "days", "4", cites)
    assert not is_citation_fragment("duration", None, "4", cites)
    assert not is_citation_fragment("number", None, "$25.00", cites)
    assert not is_citation_fragment("number", None, "4", [])


def test_any_citation_matches():
    assert is_citation_fragment("number", None, "16", ["40 CFR 60", "170 IAC 4-1-16"])

"""Unit tests for the async per-version citation resolver.

The fake session below is deliberately more than a stub: it evaluates the
``snapshot_date <= :law_as_of`` predicate and the ``ORDER BY snapshot_date
DESC LIMIT 1`` ordering against a seeded section table, and it applies the
version / company / terminal-status filters of the row query.  Without that
the snapshot-window assertions would not test anything.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.company_ingest.enrich import resolve_citations as rc
from app.company_ingest.enrich.resolve_citations import resolve_citations_for_version

LAW_AS_OF = date(2024, 12, 31)
VERSION = "11111111-1111-5111-8111-111111111111"
OTHER_VERSION = "22222222-2222-5222-8222-222222222222"
COMPANY = "rpl"


# --------------------------------------------------------------------------- #
# Fake async session
# --------------------------------------------------------------------------- #

class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def mappings(self):
        return self

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        if not self._rows:
            return None
        row = self._rows[0]
        return row[0] if isinstance(row, tuple) else row


class _FakeSession:
    """Evaluates the resolver's queries against in-memory tables."""

    def __init__(self, sections, citations, fallback=LAW_AS_OF):
        self.sections = sections
        self.citations = citations
        self.fallback = fallback
        self.updates: list[dict] = []
        self.commits = 0

    async def commit(self):  # pragma: no cover - must never be called
        self.commits += 1

    async def execute(self, stmt, params=None):
        params = params or {}

        if stmt is rc._INGESTED_TITLES_SQL:
            return _Result(
                sorted({(s["source_system"], s["title_number"]) for s in self.sections})
            )

        if stmt is rc._FALLBACK_LAW_AS_OF_SQL:
            return _Result([(self.fallback,)])

        if stmt is rc._ROWS_SQL:
            terminal = set(params["terminal"])
            out = []
            for c in self.citations:
                if c["version_id"] != params["version_id"]:
                    continue
                if c["company_id"] != params["company_id"]:
                    continue
                status = c.get("resolution_status")
                if status is not None and status in terminal:
                    continue
                if c["source_system"] == "external_standard" and status == "external":
                    continue
                row = dict(c)
                row["law_as_of"] = c.get("law_as_of") or params["fallback_law_as_of"]
                out.append(row)
            return _Result(out)

        if stmt is rc._IAC_SECTION_SQL:
            hits = [
                s
                for s in self.sections
                if s["source_system"] == "iac"
                and s.get("citation") == params["key"]
                and s["snapshot_date"] <= params["law_as_of"]
            ]
            hits.sort(key=lambda s: s["snapshot_date"], reverse=True)
            return _Result([(hits[0]["id"],)] if hits else [])

        if stmt is rc._IAC_RULE_EXISTS_SQL:
            prefix = params["prefix"].rstrip("%")
            found = any(
                s["source_system"] == "iac"
                and (s.get("citation") or "").startswith(prefix)
                and s["snapshot_date"] <= params["law_as_of"]
                for s in self.sections
            )
            return _Result([(found,)])

        if stmt is rc._CFR_SECTION_SQL:
            hits = [
                s
                for s in self.sections
                if s["source_system"] == "cfr"
                and s.get("title_number") == params["title"]
                and s.get("part") == params["part"]
                and s.get("section_number") == params["section"]
                and s["snapshot_date"] <= params["law_as_of"]
            ]
            hits.sort(key=lambda s: s["snapshot_date"], reverse=True)
            return _Result([(hits[0]["id"],)] if hits else [])

        if stmt is rc._CFR_PART_EXISTS_SQL:
            found = any(
                s["source_system"] == "cfr"
                and s.get("title_number") == params["title"]
                and s.get("part") == params["part"]
                and s["snapshot_date"] <= params["law_as_of"]
                for s in self.sections
            )
            return _Result([(found,)])

        if stmt is rc._UPDATE_SQL:
            self.updates.extend(params if isinstance(params, list) else [params])
            return _Result([])

        raise AssertionError(f"unexpected statement: {stmt}")


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

def _sec(id_, source_system, snapshot_date, **kw):
    return {"id": id_, "source_system": source_system, "snapshot_date": snapshot_date, **kw}


SECTIONS = [
    # IAC 327 15-5-3: two snapshots at/before law_as_of plus one after it.
    _sec(1, "iac", date(2024, 6, 1), citation="327 IAC 15-5-3", title_number="327"),
    _sec(2, "iac", LAW_AS_OF, citation="327 IAC 15-5-3", title_number="327"),
    _sec(3, "iac", LAW_AS_OF + timedelta(days=5), citation="327 IAC 15-5-3", title_number="327"),
    # IAC rule-granularity sibling.
    _sec(4, "iac", LAW_AS_OF, citation="327 IAC 2-6.1-4", title_number="327"),
    # CFR inside the 14-day window.
    _sec(
        10, "cfr", LAW_AS_OF + timedelta(days=14),
        title_number="40", part="761", section_number="180",
    ),
    # CFR 30 days past law_as_of — outside the window.
    _sec(
        11, "cfr", LAW_AS_OF + timedelta(days=30),
        title_number="40", part="762", section_number="190",
    ),
    # CFR whole-part reference target, inside the window.
    _sec(
        12, "cfr", LAW_AS_OF + timedelta(days=14),
        title_number="18", part="35", section_number="1",
    ),
]


def _cit(pk, source_system, *, title=None, article=None, section=None,
         granularity=None, citation_raw=None, status=None,
         version_id=VERSION, company_id=COMPANY, law_as_of=LAW_AS_OF):
    return {
        "citation_pk": pk,
        "source_system": source_system,
        "title": title,
        "article": article,
        "rule": None,
        "section": section,
        "granularity": granularity,
        "citation_raw": citation_raw,
        "resolution_status": status,
        "version_id": version_id,
        "company_id": company_id,
        "law_as_of": law_as_of,
    }


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

async def test_iac_resolves_to_newest_snapshot_at_or_before_law_as_of():
    cits = [
        _cit("a", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="section", citation_raw="327 IAC 15-5-3"),
    ]
    s = _FakeSession(SECTIONS, cits)
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)

    assert counts == {"resolved": 1}
    # id 2 (snapshot == law_as_of), never id 3 (law_as_of + 5 days).
    assert s.updates == [
        {"status": "resolved", "in_kb": True, "code_section_id": "2", "citation_pk": "a"}
    ]
    assert s.commits == 0


async def test_cfr_fourteen_day_window_resolves_thirty_days_does_not():
    cits = [
        _cit("in", "cfr", granularity="section", citation_raw="40 CFR 761.180"),
        _cit("out", "cfr", granularity="section", citation_raw="40 CFR 762.190"),
    ]
    s = _FakeSession(SECTIONS, cits)
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)

    assert counts == {"resolved": 1, "not_in_kb": 1}
    by_pk = {u["citation_pk"]: u for u in s.updates}
    assert by_pk["in"]["code_section_id"] == "10"
    assert by_pk["out"] == {
        "status": "not_in_kb", "in_kb": True, "code_section_id": None,
        "citation_pk": "out",
    }


async def test_cfr_whole_part_reference_is_resolved_rule():
    cits = [_cit("p", "cfr", granularity="rule", citation_raw="18 CFR 35")]
    s = _FakeSession(SECTIONS, cits)
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)
    assert counts == {"resolved_rule": 1}
    assert s.updates[0]["in_kb"] is True


async def test_iac_rule_granularity_like_fallback():
    cits = [
        _cit("r", "iac", title=327, article="2-6.1", granularity="rule",
             citation_raw="327 IAC 2-6.1"),
        _cit("n", "iac", title=327, article="99-9", granularity="rule",
             citation_raw="327 IAC 99-9"),
    ]
    s = _FakeSession(SECTIONS, cits)
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)
    assert counts == {"resolved_rule": 1, "not_in_kb": 1}


async def test_out_of_scope_title_and_passthrough_statuses():
    cits = [
        _cit("t", "iac", title=999, article="1-1", section=Decimal("1"),
             granularity="section", citation_raw="999 IAC 1-1-1"),
        _cit("i", "ic", citation_raw="IC 13-11-2"),
        _cit("u", "usc", citation_raw="42 USC 6901"),
        _cit("e", "external_standard", citation_raw="NFPA 70E"),
        _cit("k", "unknown", citation_raw="???"),
        _cit("g", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="weird", citation_raw="327 IAC 15-5-3"),
    ]
    s = _FakeSession(SECTIONS, cits)
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)
    assert counts == {
        "out_of_scope_title": 1,
        "not_monitored": 2,
        "external": 1,
        "unparsed": 2,
    }
    by_pk = {u["citation_pk"]: u for u in s.updates}
    assert by_pk["e"]["status"] == "external" and by_pk["e"]["in_kb"] is False
    assert by_pk["t"]["in_kb"] is False


async def test_unparseable_cfr_is_unparsed():
    cits = [_cit("x", "cfr", granularity="section", citation_raw="CFR")]
    s = _FakeSession(SECTIONS, cits)
    assert await resolve_citations_for_version(s, COMPANY, VERSION) == {"unparsed": 1}


async def test_rerun_is_noop_for_terminal_statuses():
    terminal_rows = [
        _cit(f"t{i}", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="section", citation_raw="327 IAC 15-5-3", status=st)
        for i, st in enumerate(sorted(rc._TERMINAL - {"external"}))
    ]
    terminal_rows.append(
        _cit("ext", "external_standard", citation_raw="NFPA 70E", status="external")
    )
    s = _FakeSession(SECTIONS, terminal_rows)
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)
    assert counts == {}
    assert s.updates == []
    assert s.commits == 0


async def test_non_external_row_sitting_on_external_is_reprocessed():
    """'external' is excluded from the terminal set, as in the psycopg2 original."""
    cits = [
        _cit("mis", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="section", citation_raw="327 IAC 15-5-3", status="external"),
    ]
    s = _FakeSession(SECTIONS, cits)
    assert await resolve_citations_for_version(s, COMPANY, VERSION) == {"resolved": 1}


async def test_only_the_given_version_and_company_are_touched():
    cits = [
        _cit("mine", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="section", citation_raw="327 IAC 15-5-3"),
        _cit("other_version", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="section", citation_raw="327 IAC 15-5-3",
             version_id=OTHER_VERSION),
        _cit("other_company", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="section", citation_raw="327 IAC 15-5-3",
             company_id="other"),
    ]
    s = _FakeSession(SECTIONS, cits)
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)
    assert counts == {"resolved": 1}
    assert [u["citation_pk"] for u in s.updates] == ["mine"]


async def test_missing_version_row_uses_fallback_law_as_of():
    """A clause whose document_versions row is missing falls back to MIN(law_as_of)."""
    cits = [
        _cit("f", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="section", citation_raw="327 IAC 15-5-3", law_as_of=None),
    ]
    s = _FakeSession(SECTIONS, cits, fallback=date(2024, 7, 1))
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)
    # Only the 2024-06-01 snapshot is at or before the fallback date.
    assert counts == {"resolved": 1}
    assert s.updates[0]["code_section_id"] == "1"


async def test_fallback_defaults_to_2024_12_31_when_table_empty():
    cits = [
        _cit("f", "iac", title=327, article="15-5", section=Decimal("3"),
             granularity="section", citation_raw="327 IAC 15-5-3", law_as_of=None),
    ]
    s = _FakeSession(SECTIONS, cits, fallback=None)
    counts = await resolve_citations_for_version(s, COMPANY, VERSION)
    assert counts == {"resolved": 1}
    assert s.updates[0]["code_section_id"] == "2"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("40 CFR 761.180", ("40", "761", "180")),
        ("18 CFR 35", ("18", "35", None)),
        ("29 CFR 1910.269", ("29", "1910", "269")),
        ("40 CFR 761 (subpart F)", ("40", "761", None)),
        ("CFR", (None, None, None)),
    ],
)
def test_cfr_parser_contract(raw, expected):
    assert rc._parse_cfr_citation_raw(raw) == expected


def test_iac_key_strips_decimal_from_numeric_section():
    assert rc._iac_normalized_key(170, "4-1", Decimal("17")) == "170 IAC 4-1-17"
    assert rc._iac_normalized_key(170, "4-1", None) is None

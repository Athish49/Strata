import pytest

from app.engine.footprint import Footprint, load_footprint, rule_key


@pytest.mark.parametrize("cite,expected", [
    ("170 IAC 4-1-16", "170 IAC 4-1"),
    ("170 IAC 4-1-16(a)(2)", "170 IAC 4-1"),
    ("170 IAC 1-6-2 (Definitions)", "170 IAC 1-6"),
    ("Rule 16 [170 IAC 4-1-16]", "170 IAC 4-1"),
    ("170 IAC 4-1", "170 IAC 4-1"),
    ("18 CFR 35.28", "18 CFR 35"),
    ("18 CFR 35.28(a)(2)", "18 CFR 35"),
    ("18 CFR 35.28 (Market rules)", "18 CFR 35"),
    ("18 CFR Part 35", "18 CFR 35"),
    ("18 CFR 35", "18 CFR 35"),
    ("not a citation", None),
    ("", None),
    (None, None),
])
def test_rule_key(cite, expected):
    assert rule_key(cite) == expected


def _fp():
    return Footprint(
        eligible_clauses=5,
        cited_section_ids={10, 11},
        cited_rule_keys={"170 IAC 4-1", "18 CFR 35"},
        clauses_by_section={10: {"a", "b"}, 11: {"b", "c"}},
        clauses_by_rule_key={"170 IAC 4-1": {"c", "d"}},
    )


def test_in_footprint():
    fp = _fp()
    assert fp.in_footprint(10, "170 IAC 9-9-9")
    assert fp.in_footprint(99, "170 IAC 4-1-16")
    assert fp.in_footprint(None, "18 CFR 35.28")
    assert not fp.in_footprint(99, "170 IAC 9-9-9")
    assert not fp.in_footprint(99, None)


def test_counts_dedupe_union():
    fp = _fp()
    assert fp.clause_count_by_section == {10: 2, 11: 2}
    assert fp.clause_count_by_rule_key == {"170 IAC 4-1": 2}
    assert fp.cited_clause_count(10, "170 IAC 9-9-9") == 2
    assert fp.cited_clause_count(11, "170 IAC 4-1-16") == 3  # b, c, d (c deduped)
    assert fp.cited_clause_count(99, "170 IAC 4-1-3") == 2
    assert fp.cited_clause_count(99, "18 CFR 35.1") == 0
    assert fp.cited_clause_count(None, None) == 0


@pytest.mark.neon
async def test_live_footprint():
    from urllib.parse import urlparse, urlunparse

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    from app.config import settings

    if not settings.DATABASE_URL:
        pytest.skip("no DATABASE_URL")
    parsed = urlparse(settings.DATABASE_URL)
    url = urlunparse(parsed._replace(scheme="postgresql+asyncpg", query=""))
    eng = create_async_engine(url, connect_args={"ssl": "require"})
    try:
        async with AsyncSession(eng) as sess:
            cid = (await sess.execute(text("SELECT company_id FROM company.company_documents LIMIT 1"))).scalar()
            if cid is None:
                pytest.skip("no company data")
            fp = await load_footprint(sess, cid)
            print(f"\nELIGIBLE={fp.eligible_clauses} SECTIONS={len(fp.cited_section_ids)} "
                  f"RULE_KEYS={len(fp.cited_rule_keys)} RULE_CLAUSE_KEYS={len(fp.clauses_by_rule_key)}")
            rows = (await sess.execute(text(
                "SELECT id, citation FROM public.code_sections WHERE source_system='iac' "
                "AND snapshot_date=(SELECT min(snapshot_date) FROM public.code_sections WHERE source_system='iac') "
                "AND citation ~ '^170 IAC 1-6-[2-5]$' ORDER BY citation"))).all()
            for sid, cite in rows:
                print(f"COUNT {cite} id={sid} -> {fp.cited_clause_count(sid, cite)}")
            assert fp.eligible_clauses > 0
            assert fp.cited_section_ids
    except OSError as e:
        pytest.skip(f"db unusable: {e}")
    finally:
        await eng.dispose()

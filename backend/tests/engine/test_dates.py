from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.engine.dates import (
    compute_publication,
    extract_new_dins,
    lookup_fr_dates,
    lookup_fr_dates_batch,
)

S1 = "text (Filed Aug 8, 2012: 20120808-IR-170120114RFA ; readopted)"
S2 = S1 + " (Filed 2025: 20250115-IR-170240500FRA) 20241101-IR-170240100RFA"


def test_new_dins_max_date():
    assert extract_new_dins(S1, S2) == ("20250115-IR-170240500FRA", date(2025, 1, 15))


def test_none_when_no_new():
    assert extract_new_dins(S2, S2) is None
    assert extract_new_dins(None, "no dins here") is None


def test_s1_none_all_new_and_spacing():
    assert extract_new_dins(None, "x 20240102- IR- 170240001FRA") == (
        "20240102-IR-170240001FRA", date(2024, 1, 2))


def test_invalid_date_skipped():
    assert extract_new_dins("", "20241399-IR-1702400FRA") is None


def test_compute_publication():
    r = compute_publication("iac", S1, S2, None, None)
    assert r == {"published_date": date(2025, 1, 15), "date_basis": "din_publication",
                 "din": "20250115-IR-170240500FRA"}
    fr = {"2025-06941": (date(2025, 5, 1), "fr_effective")}
    r = compute_publication("cfr", "a", "b", "2025-06941", fr)
    assert r == {"published_date": date(2025, 5, 1), "date_basis": "fr_effective", "din": None}
    assert compute_publication("cfr", "a", "b", "missing", fr)["published_date"] is None
    assert compute_publication("cfr", "a", "b", None, fr)["date_basis"] is None


def _session(rows):
    s = MagicMock()
    res = MagicMock()
    res.all.return_value = rows
    s.execute = AsyncMock(return_value=res)
    return s


async def test_batch_mock():
    s = _session([("A", date(2025, 2, 1), date(2025, 1, 1)), ("B", None, date(2025, 3, 1)),
                  ("C", None, None)])
    out = await lookup_fr_dates_batch(s, ["A", "B", "C", "D", "A"])
    assert out == {"A": (date(2025, 2, 1), "fr_effective"), "B": (date(2025, 3, 1), "fr_published")}
    assert s.execute.await_count == 1
    assert await lookup_fr_dates_batch(s, []) == {}


async def test_single_mock():
    s = _session([("A", None, date(2025, 3, 1))])
    assert await lookup_fr_dates(s, "A") == (date(2025, 3, 1), "fr_published")
    assert await lookup_fr_dates(_session([]), "Z") is None
    assert await lookup_fr_dates(_session([]), None) is None


@pytest.mark.neon
async def test_live_fr_lookup():
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
            ids = [r[0] for r in (await sess.execute(text(
                "SELECT amendment_source FROM public.code_sections WHERE source_system='cfr' "
                "AND amendment_source IS NOT NULL LIMIT 5"))).all()]
            out = await lookup_fr_dates_batch(sess, ids)
            assert set(out) <= set(ids)
            assert await lookup_fr_dates(sess, "no-such-id") is None
    except OSError as e:
        pytest.skip(f"db unusable: {e}")
    finally:
        await eng.dispose()

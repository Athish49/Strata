"""Review write path against the real DB inside a transaction that is always rolled back (no permanent write)."""
import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

import app.api.engine.routes  # noqa: F401
from app.db import _clean_url, get_db
from app.main import app

UNKNOWN = "00000000-0000-0000-0000-000000000000"


@pytest.fixture
async def live():
    eng = create_async_engine(_clean_url, poolclass=NullPool, connect_args={"ssl": "require"})
    try:
        conn = await eng.connect()
    except Exception as e:  # no DB reachable
        await eng.dispose()
        pytest.skip(f"database unavailable: {e}")
    trans = await conn.begin()
    sess = AsyncSession(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)

    async def _dep():
        yield sess

    app.dependency_overrides[get_db] = _dep
    try:
        yield sess
    finally:
        app.dependency_overrides.pop(get_db, None)
        await sess.close()
        await trans.rollback()
        await conn.close()
        await eng.dispose()


async def _pick(sess):
    row = (await sess.execute(text(
        "SELECT f.finding_id, f.run_id, f.route_reviewer FROM engine.findings f "
        "JOIN engine.runs r ON r.run_id = f.run_id AND r.status = 'done' "
        "WHERE f.route_reviewer IS NOT NULL LIMIT 1"))).mappings().first()
    if not row:
        pytest.skip("no finding with a routed reviewer")
    return str(row["finding_id"]), row["route_reviewer"]


def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_accept_then_visible_and_reject_rules(live):
    fid, pid = await _pick(live)
    async with _client() as c:
        before = (await c.get(f"/engine/ui/findings/{fid}")).json()["reviews"]
        r = await c.post(f"/engine/findings/{fid}/reviews", json={"action": "accept", "person_id": pid})
        assert r.status_code == 200 and r.json()["action"] == "accept"
        got = (await c.get(f"/engine/ui/findings/{fid}")).json()["reviews"]
        assert len(got) == len(before) + 1 and got[-1]["decision"] == "accept" and got[-1]["by"]

        assert (await c.post(f"/engine/findings/{fid}/reviews", json={"action": "reject", "person_id": pid})).status_code == 422
        r = await c.post(f"/engine/findings/{fid}/reviews",
                         json={"action": "reject", "note": "Already updated.", "person_id": pid})
        assert r.status_code == 200 and r.json()["note"] == "Already updated."
        got = (await c.get(f"/engine/ui/findings/{fid}")).json()["reviews"]
        assert got[-1]["decision"] == "reject" and got[-1]["note"] == "Already updated."

        roll = (await c.get(f"/engine/ui/runs/{(await _run_of(live, fid))}/rollups")).json()
        assert all("reviewed" in d for d in roll) and sum(d["reviewed"] for d in roll) >= 1


async def _run_of(sess, fid):
    return (await sess.execute(text("SELECT run_id FROM engine.findings WHERE finding_id = CAST(:f AS uuid)"),
                               {"f": fid})).scalar_one()


async def test_unknown_finding_or_person_404(live):
    fid, pid = await _pick(live)
    async with _client() as c:
        assert (await c.post(f"/engine/findings/{UNKNOWN}/reviews",
                             json={"action": "accept", "person_id": pid})).status_code == 404
        assert (await c.post(f"/engine/findings/{fid}/reviews",
                             json={"action": "accept", "person_id": "no-such-person"})).status_code == 404

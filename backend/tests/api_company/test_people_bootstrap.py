"""First-administrator bootstrap on POST /company/people (task 9.1 part A), against a
throwaway local PostgreSQL cluster.

On an EMPTY company.people every write needs an existing acting person, so nobody could
ever be created. The one exception: when the company has zero people, a person may be
created with acting_person_id == their own person_id. These tests pin that it works,
that it is race-safe (advisory lock + re-count), and that nothing else is relaxed.

Same scratch-cluster pattern as tests/api_company/test_versions_jobs.py: initdb in a
pytest tmp dir, unix socket only, schema from tests/engine/fixtures/company_schema.sql.
Never connects to DATABASE_URL (get_db is overridden).
"""
from __future__ import annotations

import asyncio
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.company import org
from app.db import get_db
from app.main import app

pytestmark = pytest.mark.asyncio

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA_SQL = BACKEND / "tests" / "engine" / "fixtures" / "company_schema.sql"
CO = "co"


def _pg_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for cand in sorted(Path("/opt/homebrew/opt").glob("postgresql@*/bin/" + name), reverse=True):
        return str(cand)
    return None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def scratch_pg(tmp_path_factory):
    initdb, pg_ctl = _pg_bin("initdb"), _pg_bin("pg_ctl")
    if not (initdb and pg_ctl):
        pytest.skip("no local initdb/pg_ctl for a scratch PostgreSQL cluster")
    base = tmp_path_factory.mktemp("pg")
    data, sock = base / "data", Path(f"/tmp/strata-pg-{uuid.uuid4().hex[:8]}")
    sock.mkdir()
    port = _free_port()
    subprocess.run([initdb, "-D", str(data), "-A", "trust", "-U", "postgres", "--no-sync"],
                   check=True, capture_output=True)
    subprocess.run([pg_ctl, "start", "-D", str(data), "-w", "-l", str(base / "log"), "-o",
                    f"-p {port} -k {sock} -c listen_addresses='' -c fsync=off"],
                   check=True, capture_output=True)
    try:
        yield {"host": str(sock), "port": port,
               "url": f"postgresql+asyncpg://postgres@/postgres?host={sock}&port={port}"}
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sock, ignore_errors=True)


def _con(pg):
    import psycopg2

    con = psycopg2.connect(host=pg["host"], port=pg["port"], user="postgres", dbname="postgres")
    con.autocommit = True
    return con


def _rows(pg, sql, params=()):
    con = _con(pg)
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        con.close()


@pytest.fixture
def pg(scratch_pg):
    """Fresh schema per test with ZERO people (the fresh-install case)."""
    con = _con(scratch_pg)
    cur = con.cursor()
    cur.execute("DROP SCHEMA IF EXISTS company CASCADE")
    cur.execute(SCHEMA_SQL.read_text())
    con.close()
    return scratch_pg


@pytest.fixture
async def client(pg, monkeypatch):
    monkeypatch.setattr(org.engine_settings, "ENGINE_COMPANY_ID", CO)
    engine = create_async_engine(pg["url"], poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _db():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    try:
        yield httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()


def _person(pid, acting, **kw):
    return {"person_id": pid, "name": f"Person {pid}", "acting_person_id": acting, **kw}


def _people(pg):
    return sorted(r[0] for r in _rows(pg, "SELECT person_id FROM company.people WHERE company_id = %s", (CO,)))


async def test_first_person_can_self_register_on_an_empty_company(client, pg):
    async with client:
        res = await client.post("/company/people", json=_person("P01", "P01", title="President"))
        assert res.status_code == 201, res.text
        assert res.json()["person_id"] == "P01"
        # From here on the ordinary rule applies: P01 is a real actor.
        res2 = await client.post("/company/people", json=_person("P02", "P01"))
        assert res2.status_code == 201, res2.text
    assert _people(pg) == ["P01", "P02"]


async def test_unknown_actor_creating_someone_else_on_an_empty_company_is_404(client, pg):
    async with client:
        res = await client.post("/company/people", json=_person("P01", "GHOST"))
    assert res.status_code == 404
    assert "acting person not found: GHOST" in res.json()["detail"]
    assert _people(pg) == []


async def test_self_registration_is_refused_once_anyone_exists(client, pg):
    async with client:
        assert (await client.post("/company/people", json=_person("P01", "P01"))).status_code == 201
        res = await client.post("/company/people", json=_person("P99", "P99"))
        # And the bootstrapped person cannot be re-created either.
        dup = await client.post("/company/people", json=_person("P01", "P01"))
    assert res.status_code == 404 and "acting person not found: P99" in res.json()["detail"]
    assert dup.status_code == 409
    assert _people(pg) == ["P01"]


async def test_bootstrap_does_not_weaken_other_endpoints(client, pg):
    """With zero people, every OTHER write still requires an existing actor."""
    async with client:
        dep = await client.post("/company/departments",
                                json={"department_id": "D1", "name": "Ops", "acting_person_id": "P01"})
        prof = await client.patch("/company/profile", json={"name": "X", "acting_person_id": "P01"})
        attr = await client.put("/company/attributes/regulator",
                                json={"value": "IURC", "acting_person_id": "P01"})
        pol = await client.post("/company/approval-policies",
                                json={"name": "P", "acting_person_id": "P01"})
    assert [r.status_code for r in (dep, prof, attr, pol)] == [404, 404, 404, 404]
    assert _rows(pg, "SELECT count(*) FROM company.departments")[0][0] == 0
    assert _rows(pg, "SELECT count(*) FROM company.companies")[0][0] == 0


async def _race(client, monkeypatch, bodies):
    """Force both requests past the existence check before either takes the lock."""
    barrier = asyncio.Barrier(len(bodies))

    async def _wait():
        await asyncio.wait_for(barrier.wait(), timeout=10)

    monkeypatch.setattr(org, "_before_bootstrap_lock_hook", _wait)
    async with client:
        return await asyncio.gather(*(client.post("/company/people", json=b) for b in bodies))


async def test_concurrent_bootstraps_with_different_ids_admit_exactly_one(client, pg, monkeypatch):
    """Without the lock + re-count both would see zero rows and both would insert
    (different primary keys never collide), leaving two self-appointed admins."""
    results = await _race(client, monkeypatch, [_person("PA", "PA"), _person("PB", "PB")])
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 404], [r.text for r in results]
    assert len(_people(pg)) == 1


async def test_concurrent_bootstraps_with_the_same_id_create_one_row(client, pg, monkeypatch):
    results = await _race(client, monkeypatch, [_person("P01", "P01"), _person("P01", "P01")])
    codes = sorted(r.status_code for r in results)
    assert codes == [201, 409], [r.text for r in results]
    assert _people(pg) == ["P01"]


async def test_bootstrap_writes_every_person_column(client, pg):
    async with client:
        res = await client.post("/company/people", json=_person(
            "P01", "P01", title="President", department="Executive", department_id="executive",
            email="p01@x.test", alternate_person_id="P02"))
    assert res.status_code == 201
    row = _rows(pg, "SELECT title, department, department_id, email, alternate_person_id, is_active "
                    "FROM company.people WHERE person_id = 'P01'")[0]
    assert row == ("President", "Executive", "executive", "p01@x.test", "P02", True)

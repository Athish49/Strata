"""Review + people routes against a scripted fake session (no DB)."""
import uuid
from datetime import datetime

import httpx
import pytest

from app.db import get_db
from app.main import app

FID = str(uuid.uuid4())


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rules):
        self.rules, self.sql, self.committed = rules, [], False

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append((sql, params))
        for key, rows in self.rules:
            if key in sql:
                return _Res(rows(params) if callable(rows) else rows)
        return _Res([])

    async def commit(self):
        self.committed = True


def client_for(rules):
    sess = FakeSession(rules)

    async def _dep():
        yield sess

    app.dependency_overrides[get_db] = _dep
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t"), sess


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


def _insert(p):
    return [{"review_id": uuid.UUID(p["r"]), "finding_id": uuid.UUID(p["f"]), "action": p["a"],
             "note": p["n"], "person_id": p["p"], "created_at": datetime(2026, 1, 1)}]


RULES = [("FROM engine.findings", [{"finding_id": FID}]),
         ("FROM company.people", [{"person_id": "p1"}]),
         ("INSERT INTO engine.finding_reviews", _insert)]


async def test_reject_without_note_422():
    c, sess = client_for(RULES)
    async with c:
        r = await c.post(f"/engine/findings/{FID}/reviews", json={"action": "reject", "person_id": "p1"})
        assert r.status_code == 422
        r = await c.post(f"/engine/findings/{FID}/reviews",
                         json={"action": "reject", "note": "  ", "person_id": "p1"})
        assert r.status_code == 422
    assert not sess.committed


async def test_bad_action_422():
    c, _ = client_for(RULES)
    async with c:
        r = await c.post(f"/engine/findings/{FID}/reviews", json={"action": "maybe", "person_id": "p1"})
        assert r.status_code == 422


async def test_unknown_finding_and_person_404():
    c, _ = client_for([("INSERT", _insert), ("FROM company.people", [{"person_id": "p1"}])])
    async with c:
        body = {"action": "accept", "person_id": "p1"}
        assert (await c.post(f"/engine/findings/{FID}/reviews", json=body)).status_code == 404
        assert (await c.post("/engine/findings/nope/reviews", json=body)).status_code == 404
    c, _ = client_for([("FROM engine.findings", [{"finding_id": FID}]), ("INSERT", _insert)])
    async with c:
        r = await c.post(f"/engine/findings/{FID}/reviews", json={"action": "accept", "person_id": "zz"})
        assert r.status_code == 404


async def test_accept_and_reject_with_note_stored():
    c, sess = client_for(RULES)
    async with c:
        r = await c.post(f"/engine/findings/{FID}/reviews", json={"action": "accept", "person_id": "p1"})
        assert r.status_code == 200 and r.json()["action"] == "accept" and r.json()["note"] is None
        r = await c.post(f"/engine/findings/{FID}/reviews",
                         json={"action": "reject", "note": "not applicable", "person_id": "p1"})
        assert r.status_code == 200 and r.json()["note"] == "not applicable"
        assert r.json()["finding_id"] == FID
    assert sess.committed


async def test_people_list():
    c, _ = client_for([("FROM company.people", [{"person_id": "p1", "name": "A", "title": "T"}])])
    async with c:
        r = await c.get("/engine/people")
        assert r.json() == [{"person_id": "p1", "name": "A", "title": "T"}]

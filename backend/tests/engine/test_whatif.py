"""What-if: number replacement, preset selection, and route validation (fake session, no DB)."""
import uuid

import httpx
import pytest

from app.db import get_db
from app.engine import whatif
from app.main import app


# ---- number words ----
@pytest.mark.parametrize("n,w", [(1, "one"), (10, "ten"), (13, "thirteen"), (21, "twenty-one"),
                                 (45, "forty-five"), (100, "one hundred"), (101, "one hundred one")])
def test_number_words(n, w):
    assert whatif.number_to_words(n) == w
    assert whatif.words_to_number(w) == n


def test_number_words_out_of_range():
    assert whatif.number_to_words(0) is None and whatif.number_to_words(1000) is None


def test_changed_value():
    assert whatif.changed_value(10) == 15
    assert whatif.changed_value(1) == 2      # round(1.5)=2
    assert whatif.changed_value(3) == 4      # at least N+1
    assert whatif.changed_value(2) == 3


# ---- replacement ----
def test_replace_word_and_numeral():
    out = whatif.replace_value("file within ten (10) days", 10, 15)
    assert out == ("file within fifteen (15) days", "ten (10)", "fifteen (15)")


def test_replace_keeps_capitalization():
    out = whatif.replace_value("Seven (7) days after", 7, 10)
    assert out[0] == "Ten (10) days after"


def test_replace_bare_numeral_not_inside_other_numbers():
    out = whatif.replace_value("sections 3-10 and 10.5 apply; keep 10 days", 10, 15)
    assert out[0] == "sections 3-10 and 10.5 apply; keep 15 days"


def test_replace_bare_word():
    assert whatif.replace_value("within thirty days", 30, 45)[0] == "within forty-five days"


def test_replace_nearest_to_offset():
    t = "5 days now; later 5 days again"
    out = whatif.replace_value(t, 5, 8, near=t.rindex("5"))
    assert out[0] == "5 days now; later 8 days again"


def test_replace_missing():
    assert whatif.replace_value("no numbers here", 10, 15) is None


# ---- preset selection ----
def _c(sid, cit, val, clause, unit="days"):
    return {"s1_section_id": sid, "citation": cit, "value_num": val, "unit": unit, "clause_pk": clause}


def test_pick_distinct_rules_and_ranking():
    cands = [_c(1, "170 IAC 4-1-3", 3, "a"), _c(1, "170 IAC 4-1-3", 3, "b"), _c(1, "170 IAC 4-1-3", 5, "c"),
             _c(2, "170 IAC 4-1-9", 7, "d"),            # same rule as section 1 -> skipped
             _c(3, "170 IAC 16-1-5", 7, "e"), _c(3, "170 IAC 16-1-5", 7, "f"), _c(3, "170 IAC 16-1-5", 7, "f"),
             _c(4, "18 CFR 35.28", 30, "g")]
    got = whatif.pick_value_presets(cands, limit=3)
    assert [g["s1_section_id"] for g in got] == [1, 3, 4] or [g["s1_section_id"] for g in got] == [3, 1, 4]
    assert all(g["clause_count"] >= 1 for g in got)
    sec1 = next(g for g in got if g["s1_section_id"] == 1)
    assert sec1["value_num"] == 3 and sec1["clause_count"] == 2   # best token per section


def test_preset_title():
    assert whatif.preset_title("X 1-2", "day", "10", "15") == "X 1-2: day 10→15"


def test_validate_scenario():
    assert whatif.validate_scenario("text_edit", None)
    assert whatif.validate_scenario("text_edit", "  ")
    assert whatif.validate_scenario("text_edit", "new text") is None
    assert whatif.validate_scenario("repeal", None) is None
    assert whatif.validate_scenario("bogus", "x")


# ---- routes ----
class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    def __init__(self, rules):
        self.rules, self.sql, self.commits = rules, [], 0

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append(sql)
        for key, rows in self.rules:
            if key in sql:
                return _Res(rows)
        return _Res([])

    async def commit(self):
        self.commits += 1


def _client(rules, monkeypatch):
    sess = FakeSession(rules)
    started = []

    async def _fake_run(scenario_id, run_id=None):
        started.append((scenario_id, run_id))

    monkeypatch.setattr(whatif, "run_whatif", _fake_run)

    async def _dep():
        yield sess

    app.dependency_overrides[get_db] = _dep
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t"), sess, started


@pytest.fixture(autouse=True)
def _clear():
    yield
    app.dependency_overrides.clear()


SEC = {"source_system": "iac", "citation": "X 1-2", "heading": "H", "body_text": "T"}


async def test_text_edit_requires_text(monkeypatch):
    c, sess, started = _client([("FROM public.code_sections", [SEC])], monkeypatch)
    async with c:
        r = await c.post("/engine/whatif/scenarios", json={"s1_section_id": 1, "edit_kind": "text_edit", "title": "t"})
        assert r.status_code == 422
        r = await c.post("/engine/whatif/scenarios", json={"s1_section_id": 1, "edit_kind": "bogus", "title": "t"})
        assert r.status_code == 422
    assert not started and sess.commits == 0


async def test_create_unknown_section_404(monkeypatch):
    c, _, started = _client([], monkeypatch)
    async with c:
        r = await c.post("/engine/whatif/scenarios", json={"s1_section_id": 9, "edit_kind": "repeal", "title": "t"})
        assert r.status_code == 404
    assert not started


async def test_create_repeal_starts_run(monkeypatch):
    c, sess, started = _client([("FROM public.code_sections", [SEC])], monkeypatch)
    async with c:
        r = await c.post("/engine/whatif/scenarios", json={"s1_section_id": 1, "edit_kind": "repeal", "title": "t"})
        assert r.status_code == 200
        body = r.json()
    assert uuid.UUID(body["scenario_id"]) and uuid.UUID(body["run_id"])
    assert started == [(body["scenario_id"], body["run_id"])]
    assert sess.commits == 1


async def test_rerun_404_and_ok(monkeypatch):
    c, _, started = _client([], monkeypatch)
    async with c:
        assert (await c.post(f"/engine/whatif/scenarios/{uuid.uuid4()}/run")).status_code == 404
        assert (await c.post("/engine/whatif/scenarios/not-a-uuid/run")).status_code == 404
        assert (await c.get("/engine/whatif/sections/5")).status_code == 404
    assert not started
    sid = uuid.uuid4()
    row = {"scenario_id": sid, "title": "t", "s1_section_id": 1, "edit_kind": "repeal", "is_preset": False,
           "last_run_id": None, "status": None}
    c, _, started = _client([("engine.whatif_scenarios", [row])], monkeypatch)
    async with c:
        r = await c.post(f"/engine/whatif/scenarios/{sid}/run")
        assert r.status_code == 200
    assert started[0][0] == str(sid) and started[0][1] == r.json()["run_id"]


async def test_get_section_ok(monkeypatch):
    c, _, _ = _client([("FROM public.code_sections", [SEC])], monkeypatch)
    async with c:
        r = await c.get("/engine/whatif/sections/1")
    assert r.json() == {"citation": "X 1-2", "heading": "H", "s1_text": "T"}

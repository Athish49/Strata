import asyncio
import uuid

import pytest
from pydantic import BaseModel

from app.engine import llm as L


class Out(BaseModel):
    x: int


class FakeSession:
    """Stands in for AsyncSession against engine.llm_calls."""
    store: list

    def __init__(self, store):
        self.store = store

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if sql.startswith("SELECT"):
            rows = [(r["response"],) for r in self.store
                    if r["valid"] and (r["stage"], r["model"], r["sha"]) ==
                    (params["stage"], params["model"], params["sha"])]
            import json as _j
            rows = [(_j.loads(r[0]),) for r in rows]

            class R:
                def first(self_):
                    return rows[0] if rows else None
            return R()
        self.store.append(dict(params))

    async def commit(self):
        pass


@pytest.fixture
def client(monkeypatch):
    state = {"calls": 0, "inflight": 0, "max": 0, "result": Out(x=1)}

    async def fake(stage, unit_id, system, user, schema, ctx, model):
        state["calls"] += 1
        state["inflight"] += 1
        state["max"] = max(state["max"], state["inflight"])
        await asyncio.sleep(0.01)
        state["inflight"] -= 1
        state["model"] = model
        return state["result"]

    monkeypatch.setattr(L, "_client", fake)
    return state


async def test_cache_hit_skips_client(client):
    store = []
    s = FakeSession(store)
    llm = L.LLMContext()
    a = await L.call_cached("judge", "m", "sys", "usr", Out, None, llm=llm, session=s)
    b = await L.call_cached("judge", "m", "sys", "usr", Out, None, llm=llm, session=s)
    assert a == b == Out(x=1)
    assert client["calls"] == 1 and client["model"] == "m"
    assert (llm.stats.calls_made, llm.stats.cache_hits) == (1, 1)
    assert len(store) == 1 and store[0]["valid"]
    # different model -> miss
    await L.call_cached("judge", "m2", "sys", "usr", Out, None, llm=llm, session=s)
    assert client["calls"] == 2


async def test_cap_enforced(client):
    s = FakeSession([])
    llm = L.LLMContext(budget=L.LLMBudget(max_calls=2))
    for i in range(2):
        await L.call_cached("judge", "m", "s", f"u{i}", Out, None, llm=llm, session=s)
    with pytest.raises(L.LLMBudgetExceeded):
        await L.call_cached("judge", "m", "s", "u3", Out, None, llm=llm, session=s)
    # a cache hit still works at the cap
    assert await L.call_cached("judge", "m", "s", "u0", Out, None, llm=llm, session=s)


async def test_concurrency_limit(client, monkeypatch):
    monkeypatch.setattr(L, "LLM_CONCURRENCY", 3)
    s = FakeSession([])
    llm = L.LLMContext(budget=L.LLMBudget(max_calls=100))
    await asyncio.gather(*[
        L.call_cached("judge", "m", "s", f"u{i}", Out, None, llm=llm, session=s)
        for i in range(10)])
    assert client["max"] == 3


async def test_invalid_recorded_not_cached(client):
    client["result"] = None
    store = []
    s = FakeSession(store)
    llm = L.LLMContext()
    r = await L.call_cached("judge", "m", "s", "u", Out, uuid.uuid4(), llm=llm, session=s)
    assert r is None
    assert len(store) == 1 and store[0]["valid"] is False and store[0]["error"]
    await L.call_cached("judge", "m", "s", "u", Out, None, llm=llm, session=s)
    assert client["calls"] == 2  # invalid rows are not cache hits
    assert llm.stats.invalid == 2


async def test_live_smoke():
    from app.config import settings
    if not getattr(settings, "LLM_API_KEY", None):
        pytest.skip("no LLM_API_KEY")
    llm = L.LLMContext(budget=L.LLMBudget(max_calls=1))
    r = await L.call_cached("judge", settings.LLM_MODEL, "Reply with JSON.",
                            'Return {"x": 7}.', Out, None, llm=llm, session=FakeSession([]))
    assert r is not None and r.x == 7

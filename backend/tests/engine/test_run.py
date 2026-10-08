import pytest

from app.engine import run as run_mod
from app.engine.delta import Stage1Result
from app.engine.run import LlmContext, load_stages, stage1_run_stats


class _R:
    def __init__(self, cls, fp):
        self.change_class, self.in_footprint = cls, fp


def test_stage1_run_stats():
    s = Stage1Result([_R("cosmetic", True), _R("substantive", True), _R("substantive", False),
                      _R("new_section", False), _R("repealed", False)], [])
    st = stage1_run_stats(s)
    assert st["raw_changed"] == 5 and st["new_sections"] == 1 and st["repealed"] == 1
    assert st["substantive"] == 2 and st["in_footprint"] == {"cosmetic": 1, "substantive": 1}
    assert st["by_class"]["substantive"] == 2


def test_llm_context_cap():
    c = LlmContext(2)
    assert c.reserve() and c.reserve() and not c.reserve()
    assert c.calls_made == 2


def test_load_stages_skips_missing_and_respects_radar(monkeypatch):
    class Mod:
        async def _f(state):  # noqa
            pass
        run_stage = staticmethod(_f)

    def fake_import(path):
        if path.endswith("characterize"):
            return Mod
        if path.endswith("candidates"):
            return object()  # no run_stage
        raise ImportError(name=path)

    monkeypatch.setattr(run_mod.importlib, "import_module", fake_import)
    assert [n for n, _ in load_stages()] == ["characterize"]
    monkeypatch.setattr(run_mod, "STAGE_MODULES", run_mod.STAGE_MODULES + [("x", "app.engine.x", None)])
    assert [n for n, _ in load_stages(radar=True)] == ["characterize"]


def test_load_stages_reraises_broken_inner_import(monkeypatch):
    def fake_import(path):
        raise ImportError(name="some_missing_dependency")
    monkeypatch.setattr(run_mod.importlib, "import_module", fake_import)
    with pytest.raises(ImportError):
        load_stages()


class _Sess:
    def __init__(self, log):
        self.log = log

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, stmt, params=None):
        self.log.append((str(stmt), params))

        class R:
            def mappings(s):
                return s

            def all(s):
                return []
        return R()

    async def commit(self):
        pass

    async def rollback(self):
        pass


@pytest.mark.asyncio
async def test_failure_marks_run_failed_and_reraises(monkeypatch):
    log = []

    async def boom(*a, **k):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(run_mod, "build_kb_inputs", boom)
    with pytest.raises(RuntimeError):
        await run_mod.run_engine("kb", session_factory=lambda: _Sess(log), run_id="r1")
    last_sql, last_params = log[-1]
    assert "UPDATE engine.runs" in last_sql
    assert last_params["status"] == "failed" and "kaboom" in last_params["error"]


@pytest.mark.asyncio
async def test_stages_invoked_in_order_with_state(monkeypatch):
    log, seen = [], []

    async def inputs(s):
        return []

    async def fp(s, c):
        return run_mod.Footprint()

    async def s1(s, rid, i, f):
        return Stage1Result([], [])

    async def persist(s, rid, st):
        pass

    async def stage(state):
        seen.append(state)
        state.stats["marker"] = 1

    monkeypatch.setattr(run_mod, "build_kb_inputs", inputs)
    monkeypatch.setattr(run_mod, "load_footprint", fp)
    monkeypatch.setattr(run_mod, "run_stage1", s1)
    monkeypatch.setattr(run_mod, "persist_stage1", persist)
    monkeypatch.setattr(run_mod, "load_stages", lambda radar=False: [("a", stage)])
    rid = await run_mod.run_engine("kb", session_factory=lambda: _Sess(log), run_id="r2")
    assert rid == "r2" and len(seen) == 1 and seen[0].run_id == "r2"
    assert '"marker": 1' in log[-1][1]["stats"] and log[-1][1]["status"] == "done"


@pytest.mark.asyncio
async def test_bad_kind():
    with pytest.raises(ValueError):
        await run_mod.run_engine("nope")
    with pytest.raises(ValueError):
        await run_mod.run_engine("whatif")


@pytest.mark.neon
@pytest.mark.asyncio
async def test_baseline_run_all_zero():
    from sqlalchemy import text
    from app.db import AsyncSessionLocal
    try:
        async with AsyncSessionLocal() as s:
            await s.execute(text("select 1"))
    except Exception as exc:
        pytest.skip(f"DB unusable: {exc}")
    rid = await run_mod.run_engine("baseline")
    async with AsyncSessionLocal() as s:
        row = (await s.execute(text(
            "select status, stats from engine.runs where run_id = CAST(:r AS uuid)"), {"r": rid})).mappings().one()
        n = (await s.execute(text(
            "select count(*) from engine.change_records where run_id = CAST(:r AS uuid)"), {"r": rid})).scalar()
        await s.execute(text("delete from engine.runs where run_id = CAST(:r AS uuid)"), {"r": rid})
        await s.commit()
    assert row["status"] == "done" and n == 0
    st = row["stats"]
    assert st["raw_changed"] == st["substantive"] == st["new_sections"] == st["repealed"] == 0
    assert st["by_class"] == {} and st["in_footprint"] == {}

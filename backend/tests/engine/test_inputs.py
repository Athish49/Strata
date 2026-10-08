import datetime as dt

import pytest
from sqlalchemy import text

from app.engine.inputs import build_baseline_inputs, build_kb_inputs, build_whatif_inputs

D1, D2 = dt.date(2024, 1, 1), dt.date(2025, 1, 1)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class FakeSession:
    """Dispatches on the SQL text; rows are canned per query kind."""

    def __init__(self, snapshots=(), s2_rows=None, s1_rows=None):
        self.snapshots, self.s2_rows, self.s1_rows = snapshots, s2_rows or {}, s1_rows or {}

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        if "GROUP BY source_system" in sql:
            return _Result(self.snapshots)
        if "LEFT JOIN" in sql:
            return _Result(self.s2_rows[params["source_system"]])
        return _Result([self.s1_rows[params["id"]]] if params["id"] in self.s1_rows else [])


def _s2(i, cite, prior=None, s1_text=None, s1_date=D1):
    return dict(s2_id=i, s2_citation=cite, s2_text=f"new {cite}", s2_status="active",
                s2_heading=f"h {cite}", s2_amendment_source="src", prior_version_id=prior,
                s1_id=prior, s1_text=s1_text if prior else None,
                s1_status="active" if prior else None, s1_snapshot_date=s1_date if prior else None)


def _snap(ss):
    return dict(source_system=ss, s1_date=D1, s2_date=D2)


async def test_kb_pairs_new_and_ordering():
    sess = FakeSession(
        snapshots=[_snap("cfr"), _snap("iac")],
        s2_rows={
            "iac": [_s2(12, "B 2", prior=2, s1_text="old b"), _s2(11, "A 1")],
            "cfr": [_s2(21, "C 1", prior=1, s1_text="old c")],
        },
    )
    out = await build_kb_inputs(sess)
    assert [(c.source_system, c.citation) for c in out] == [("cfr", "C 1"), ("iac", "A 1"), ("iac", "B 2")]
    new = out[1]
    assert new.s1_section_id is None and new.s1_text is None and new.s1_status is None
    assert new.s2_section_id == 11 and new.origin == "kb" and new.amendment_source == "src"
    pair = out[2]
    assert pair.s1_section_id == 2 and pair.s1_text == "old b" and pair.s2_text == "new B 2"
    assert pair.heading == "h B 2"


async def test_kb_single_snapshot_system_skipped():
    sess = FakeSession(snapshots=[dict(source_system="iac", s1_date=D1, s2_date=D1)])
    assert await build_kb_inputs(sess) == []


async def test_kb_prior_in_wrong_snapshot_warns(caplog):
    sess = FakeSession(
        snapshots=[_snap("iac")],
        s2_rows={"iac": [_s2(5, "A 1", prior=3, s1_text="x", s1_date=dt.date(2023, 1, 1))]},
    )
    with caplog.at_level("WARNING"):
        out = await build_kb_inputs(sess)
    assert len(out) == 1 and "not S1" in caplog.text


def test_baseline_empty():
    assert build_baseline_inputs() == []


_S1 = {7: dict(id=7, source_system="iac", citation="A 1", heading="h", body_text="old",
               status="active", amendment_source=None)}


async def test_whatif_text_edit():
    sess = FakeSession(s1_rows=_S1)
    [c] = await build_whatif_inputs(
        sess, {"s1_section_id": 7, "edit_kind": "text_edit", "edited_text": "edited"})
    assert (c.origin, c.citation, c.s1_section_id, c.s2_section_id) == ("whatif", "A 1", 7, None)
    assert c.s1_text == "old" and c.s2_text == "edited" and c.s2_status == "active"


async def test_whatif_repeal():
    sess = FakeSession(s1_rows=_S1)
    [c] = await build_whatif_inputs(sess, {"s1_section_id": 7, "edit_kind": "repeal", "edited_text": None})
    assert c.s2_text is None and c.s2_status == "repealed" and c.s1_status == "active"


async def test_whatif_missing_section():
    with pytest.raises(ValueError):
        await build_whatif_inputs(FakeSession(), {"s1_section_id": 99, "edit_kind": "repeal"})


@pytest.fixture
async def live_session():
    try:
        from app.db import AsyncSessionLocal
        async with AsyncSessionLocal() as s:
            await s.execute(text("SELECT 1"))
            yield s
    except Exception as e:  # unusable DATABASE_URL / no network
        pytest.skip(f"live DB unavailable: {e}")


@pytest.mark.neon
async def test_kb_inputs_live(live_session):
    s = live_session
    rows = (await s.execute(text("""
        SELECT c.source_system, COUNT(*) AS n,
               COUNT(c.prior_version_id) AS pairs
        FROM public.code_sections c
        JOIN (SELECT source_system, MAX(snapshot_date) d FROM public.code_sections GROUP BY 1) m
          ON m.source_system = c.source_system AND m.d = c.snapshot_date
        GROUP BY 1"""))).mappings().all()
    expected = {r["source_system"]: (r["n"], r["pairs"]) for r in rows}
    out = await build_kb_inputs(s)
    assert len(out) == sum(n for n, _ in expected.values())
    for ss, (n, pairs) in expected.items():
        mine = [c for c in out if c.source_system == ss]
        assert len(mine) == n
        assert sum(c.s1_section_id is not None for c in mine) == pairs
        assert all(c.s2_section_id is not None for c in mine)
    # every prior_version_id points at the S1 snapshot
    bad = (await s.execute(text("""
        SELECT COUNT(*) FROM public.code_sections s2
        JOIN public.code_sections s1 ON s1.id = s2.prior_version_id
        JOIN (SELECT source_system, MIN(snapshot_date) d1, MAX(snapshot_date) d2
              FROM public.code_sections GROUP BY 1) m ON m.source_system = s2.source_system
        WHERE s2.snapshot_date = m.d2 AND s1.snapshot_date <> m.d1"""))).scalar()
    assert bad == 0
    print({ss: dict(total=n, pairs=p, new=n - p) for ss, (n, p) in expected.items()})

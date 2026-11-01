"""Task 5.6: promote_version / reindex_document (TDD §6, §6.1).

Postgres behaviour runs against a throwaway local cluster (initdb in a pytest tmp dir,
unix socket only, torn down afterwards) loaded from tests/engine/fixtures/company_schema.sql,
exactly like tests/engine/test_version_scoping.py. It never connects to DATABASE_URL.

Qdrant is an in-memory fake that applies upsert and delete-by-filter (``must`` and
``must_not``, with real Qdrant semantics: a point missing a ``must_not`` key does NOT
match it, so it is deleted) to a dict and logs every call. An autouse fixture makes the real client factory raise, so nothing here can
reach the Qdrant configured in backend/.env, and embeddings are stubbed so
sentence-transformers is never loaded.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import pytest

from app.company_ingest import promote
from app.company_ingest.ids import stable_uuid
from app.company_ingest.index import embed as embed_module
from app.company_ingest.index import qdrant_setup
from app.company_ingest.index import upsert as upsert_module
from app.company_ingest.promote import (
    PromotionConflict,
    PromotionHashUnavailable,
    PromotionNotReady,
    PromotionRetryableError,
    promote_version,
)

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "engine" / "fixtures" / "company_schema.sql"
CO = "co"
DOC = "DOC-000001"
U = lambda s: str(uuid.uuid5(uuid.NAMESPACE_URL, s))  # noqa: E731
V1, V2, V3 = U("v1"), U("v2"), U("v3")
H1, H2, H3 = "1" * 64, "2" * 64, "3" * 64

# clause_id -> (role, section_kind). One boilerplate and one front-matter unit per
# version, which build_embedded_text excludes, so "indexable" != "all clauses".
CLAUSES = {
    f"{DOC}:1": ("internal_procedure", "body"),
    f"{DOC}:2": ("internal_procedure", "body"),
    f"{DOC}:3": ("boilerplate", "body"),
    f"{DOC}:fm": ("internal_procedure", "front_matter"),
}
INDEXABLE = {f"{DOC}:1", f"{DOC}:2"}


# =========================================================================== fakes
class FakeQdrant:
    """Dict-backed stand-in for QdrantClient: applies deletes and upserts, logs calls."""

    def __init__(self, points: dict | None = None, *, fail_on: str | None = None):
        self.points: dict[str, dict] = dict(points or {})
        self.ops: list[tuple] = []
        self.fail_on = fail_on

    def delete(self, collection_name, points_selector, wait=False):
        flt = points_selector.filter
        conds = {c.key: c.match.value for c in (flt.must or [])}
        not_conds = {c.key: c.match.value for c in (flt.must_not or [])}
        self.ops.append(("delete", conds, wait, not_conds))
        if self.fail_on == "delete":
            raise ConnectionError("qdrant unreachable")

        def hit(p):
            return (all(p.get(k) == v for k, v in conds.items())
                    and not any(p.get(k) == v for k, v in not_conds.items()))

        self.points = {pid: p for pid, p in self.points.items() if not hit(p)}

    def upsert(self, collection_name, points, wait=False):
        self.ops.append(("upsert", [str(p.id) for p in points], wait))
        if self.fail_on == "upsert":
            raise ConnectionError("qdrant timed out")
        for p in points:
            self.points[str(p.id)] = p.payload


@pytest.fixture(autouse=True)
def _never_real_qdrant_or_model(monkeypatch):
    def _forbidden():
        raise AssertionError("test tried to build a real Qdrant client")

    monkeypatch.setattr(upsert_module, "_make_client", _forbidden)
    monkeypatch.setattr(upsert_module, "embed_texts", lambda texts: [[0.0] * 384 for _ in texts])
    monkeypatch.setattr(embed_module, "_get_model",
                        lambda: (_ for _ in ()).throw(AssertionError("model load")))


def _legacy_points() -> dict:
    """What a v1-era collection holds for DOC: the literal-"v1" ids plus a stale v1
    point from the real-id scheme, plus another document's point that must survive."""
    from app.config import settings

    base = {"project": settings.QDRANT_PROJECT_TAG, "company_id": CO, "doc_id": DOC}
    pts = {str(stable_uuid(CO, "v1", cid)): {**base, "version_id": "v1", "clause_id": cid,
                                            "is_current": True} for cid in INDEXABLE}
    pts[str(stable_uuid(CO, V1, f"{DOC}:1"))] = {**base, "version_id": V1, "clause_id": f"{DOC}:1"}
    pts["other-doc"] = {**base, "doc_id": "DOC-000099", "version_id": U("x"), "clause_id": "x"}
    return pts


# =========================================================================== scratch PG
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


def _sync_conn(pg):
    import psycopg2

    con = psycopg2.connect(host=pg["host"], port=pg["port"], user="postgres", dbname="postgres")
    con.autocommit = True
    return con


def _insert_version(cur, vid, no, status, ingest_status, *, is_current=False, with_clauses=True):
    cur.execute(
        "INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
        "status, ingest_status, is_current) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (vid, CO, DOC, no, status, ingest_status, is_current))
    if not with_clauses:
        return
    for i, (cid, (role, skind)) in enumerate(CLAUSES.items()):
        pk = U(f"pk/{vid}/{cid}")
        cur.execute(
            "INSERT INTO company.clauses (clause_pk, company_id, version_id, doc_id, clause_id, "
            "local_id, ordinal, unit_kind, heading_path, section_kind, text_raw, text_norm, "
            "text_sha256, clause_role, assessable) VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,'section',ARRAY['Sec','Sub'],%s,%s,%s,'x',%s,true)",
            (pk, CO, vid, DOC, cid, cid.split(":")[1], i, skind,
             f"text of {cid} in v{no}", f"text of {cid} in v{no}", role))
        if cid == f"{DOC}:1":
            cur.execute(
                "INSERT INTO company.clause_citations (citation_pk, clause_pk, citation_raw, "
                "span_start, source_system, title, article, rule, section, granularity, "
                "code_section_id, resolution_status) VALUES "
                "(%s,%s,'170 IAC 4-1-16',0,'iac',170,'4-1','4-1-16',16,'section','42','resolved')",
                (U(f"cit/{pk}"), pk))
            cur.execute(
                "INSERT INTO company.clause_parameters (parameter_pk, clause_pk, kind, "
                "value_text, span_start, value_num, unit) VALUES (%s,%s,'duration','10 days',0,10,'day')",
                (U(f"par/{pk}"), pk))
            tpk = U(f"term/{vid}")
            cur.execute("INSERT INTO company.defined_terms (term_pk, company_id, doc_id, version_id, "
                        "term, term_norm) VALUES (%s,%s,%s,%s,'Customer','customer')",
                        (tpk, CO, DOC, vid))
            cur.execute("INSERT INTO company.term_usages VALUES (%s,%s,1)", (tpk, pk))


@pytest.fixture
def pg(scratch_pg):
    """Fresh schema per test. Seed: DOC with v1 live (hash H1), v2 ingested and in
    review, v3 still ingesting (ingest_status='pending')."""
    assert "neon" not in scratch_pg["url"]
    assert os.environ.get("DATABASE_URL", "\0") not in scratch_pg["url"]
    con = _sync_conn(scratch_pg)
    cur = con.cursor()
    cur.execute("DROP SCHEMA IF EXISTS company CASCADE")
    cur.execute(SCHEMA_SQL.read_text())
    cur.execute("INSERT INTO company.companies (company_id) VALUES (%s)", (CO,))
    cur.execute("INSERT INTO company.company_documents (company_id, doc_id, title, "
                "current_version_id, current_content_hash, lifecycle_state) "
                "VALUES (%s,%s,'Policy',%s,%s,'active')", (CO, DOC, V1, H1))
    _insert_version(cur, V1, 1, "effective", "ingested", is_current=True)
    _insert_version(cur, V2, 2, "in_review", "ingested")
    _insert_version(cur, V3, 3, "in_review", "pending")
    con.close()
    return scratch_pg


def _rows(pg, sql, params=()):
    con = _sync_conn(pg)
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        con.close()


def _state(pg):
    """Every promotion-relevant column, read from a FRESH connection."""
    return (
        _rows(pg, "SELECT version_id::text, status, is_current, superseded_by::text, "
                  "supersedes_version_id::text, approved_date, pending_content_hash "
                  "FROM company.document_versions ORDER BY version_no"),
        _rows(pg, "SELECT current_version_id::text, current_content_hash, lifecycle_state, "
                  "updated_at FROM company.company_documents"),
    )


@pytest.fixture
async def make_session(pg):
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    engines = []

    def _make():
        eng = create_async_engine(pg["url"])
        engines.append(eng)
        return AsyncSession(eng)

    yield _make
    for eng in engines:
        await eng.dispose()


# =========================================================================== acceptance
async def test_promote_v2_makes_it_the_single_live_version(pg, make_session):
    qd = FakeQdrant(_legacy_points())
    async with make_session() as s:
        res = await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=qd)
        await s.commit()
    assert res.prior_version_id == V1 and res.content_hash == H2 and not res.already_current

    # document_versions_current_uq's predicate matches exactly one row: v2.
    assert _rows(pg, "SELECT version_id::text FROM company.document_versions "
                     "WHERE company_id = %s AND doc_id = %s AND is_current", (CO, DOC)) == [(V2,)]
    versions, docs = _state(pg)
    by_id = {v[0]: v for v in versions}
    assert by_id[V1][1:4] == ("superseded", False, V2)
    assert by_id[V2][1:3] == ("effective", True) and by_id[V2][4] == V1
    assert by_id[V2][5] is not None                       # approved_date moved here from org.py
    assert by_id[V3][1:3] == ("in_review", False)
    assert docs[0][:3] == (V2, H2, "active")
    # v1's clause graph is history, not deleted.
    assert _rows(pg, "SELECT count(*) FROM company.clauses WHERE version_id = %s", (V1,)) == [(4,)]


async def test_qdrant_upsert_v2_then_sweep_other_versions_of_the_doc(pg, make_session):
    """Task 3.2 order: upsert the new version FIRST, then delete this doc's points whose
    version_id differs. Not delete-then-upsert: that left v1 with no points whenever the
    upsert failed and Postgres rolled back to v1."""
    from app.config import settings

    qd = FakeQdrant(_legacy_points())
    async with make_session() as s:
        res = await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=qd)
        await s.commit()

    assert [op[0] for op in qd.ops] == ["upsert", "delete"]
    v2_ids = {str(stable_uuid(CO, V2, cid)) for cid in INDEXABLE}
    assert set(qd.ops[0][1]) == v2_ids and qd.ops[0][2] is True
    _, conds, wait, not_conds = qd.ops[1]
    # by doc + "not this version", NOT by a specific old version_id — that is what
    # sweeps the literal-"v1" orphans and any earlier version
    assert conds == {"project": settings.QDRANT_PROJECT_TAG, "company_id": CO, "doc_id": DOC}
    assert not_conds == {"version_id": V2}
    assert wait is True

    mine = {pid: p for pid, p in qd.points.items() if p["doc_id"] == DOC}
    assert set(mine) == v2_ids                              # v2 only
    assert len(mine) == res.points_indexed == len(INDEXABLE)  # indexable count, not all clauses
    assert {p["version_id"] for p in mine.values()} == {V2}
    forbidden = {str(stable_uuid(CO, v, cid)) for v in (V1, V3, "v1") for cid in CLAUSES}
    assert not forbidden & set(qd.points)                   # no v1, no pending v3
    assert "other-doc" in qd.points                         # other documents untouched

    p1 = qd.points[str(stable_uuid(CO, V2, f"{DOC}:1"))]
    assert p1["cited_sections"] == ["170 IAC 4-1-16"] and p1["cited_rules"] == ["170 IAC 4-1"]
    assert p1["param_kinds"] == ["duration"] and p1["param_units"] == ["day"]
    assert p1["terms_used"] == ["Customer"] and p1["heading_path"] == ["Sec", "Sub"]
    for p in mine.values():
        assert "is_current" not in p


async def test_pointer_and_hash_change_in_one_transaction(pg, make_session):
    """While promotion is mid-flight (blocked inside the Qdrant write) another connection
    still sees v1 + H1 everywhere; after commit it sees v2 + H2 together."""
    gate, inside = asyncio.Event(), asyncio.Event()

    class Gated(FakeQdrant):
        def upsert(self, *a, **kw):
            inside.set()
            return super().upsert(*a, **kw)

    qd = Gated()

    async def run():
        async with make_session() as s:
            orig = promote.reindex_document

            async def slow(*a, **kw):
                n = await orig(*a, **kw)
                await gate.wait()
                return n

            promote.reindex_document = slow
            try:
                await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=qd)
            finally:
                promote.reindex_document = orig
            await s.commit()

    task = asyncio.create_task(run())
    await asyncio.wait_for(inside.wait(), 10)
    versions, docs = _state(pg)
    assert docs[0][:2] == (V1, H1)
    assert [v[0] for v in versions if v[2]] == [V1]
    gate.set()
    await asyncio.wait_for(task, 10)
    versions, docs = _state(pg)
    assert docs[0][:2] == (V2, H2)
    assert [v[0] for v in versions if v[2]] == [V2]


def _set_pending(pg, vid, h):
    con = _sync_conn(pg)
    con.cursor().execute("UPDATE company.document_versions SET pending_content_hash = %s "
                         "WHERE version_id = %s", (h, vid))
    con.close()


@pytest.mark.parametrize("fail_on", ["delete", "upsert"])
async def test_qdrant_failure_leaves_postgres_unchanged_and_is_retryable(pg, make_session, fail_on):
    """The hash comes from v2's pending_content_hash (no argument), so "Postgres
    unchanged" also proves the rollback restored the pending hash.

    upsert fails -> nothing was deleted: live v1 (and every legacy point) still there.
    sweep fails  -> v1's points are still there, plus v2's extras; the retry sweeps them.
    """
    _set_pending(pg, V2, H2)
    before = _state(pg)
    legacy = _legacy_points()
    bad = FakeQdrant(legacy, fail_on=fail_on)
    async with make_session() as s:
        with pytest.raises(PromotionRetryableError) as ei:
            await promote_version(s, CO, DOC, V2, qdrant_client=bad)
        assert ei.value.retryable is True
        await s.commit()          # a caller that commits anyway must commit nothing
    assert _state(pg) == before
    assert {v[0]: v[6] for v in before[0]}[V2] == H2

    v1_live = str(stable_uuid(CO, V1, f"{DOC}:1"))
    assert v1_live in bad.points and bad.points[v1_live]["version_id"] == V1
    v2_ids = {str(stable_uuid(CO, V2, cid)) for cid in INDEXABLE}
    if fail_on == "upsert":
        assert bad.points == legacy                       # untouched, nothing missing
    else:
        assert set(legacy) <= set(bad.points)             # nothing live was lost...
        assert v2_ids <= set(bad.points)                  # ...extras are tolerated

    # Retry with Qdrant back: idempotent (deterministic ids, sweep by doc_id).
    good = FakeQdrant(bad.points)
    async with make_session() as s:
        await promote_version(s, CO, DOC, V2, qdrant_client=good)
        await s.commit()
    assert _state(pg)[1][0][:2] == (V2, H2)
    mine = {pid for pid, p in good.points.items() if p["doc_id"] == DOC}
    assert mine == v2_ids
    assert "other-doc" in good.points


async def test_concurrent_promotions_serialize_on_the_document_row(pg, make_session):
    """A promotes v2 and is held inside its Qdrant write; B (promoting v3) must block on
    SELECT … FOR UPDATE — it reaches Qdrant only after A commits — and then supersede
    v2, not v1."""
    _rows_exec = _sync_conn(pg)
    _rows_exec.cursor().execute(
        "UPDATE company.document_versions SET ingest_status = 'ingested' WHERE version_id = %s", (V3,))
    _rows_exec.close()

    gate, a_inside = asyncio.Event(), asyncio.Event()
    order: list[str] = []

    class GateA(FakeQdrant):
        def upsert(self, *a, **kw):
            order.append("A-qdrant")
            return super().upsert(*a, **kw)

    class SeenB(FakeQdrant):
        def upsert(self, *a, **kw):
            order.append("B-qdrant")
            return super().upsert(*a, **kw)

    orig = promote.reindex_document

    async def reindex(company_id, doc_id, version_id, units, ctx=None, *, client=None, **kw):
        n = await orig(company_id, doc_id, version_id, units, ctx, client=client, **kw)
        if version_id == V2:
            a_inside.set()
            await gate.wait()
        return n

    promote.reindex_document = reindex
    try:
        async def a():
            async with make_session() as s:
                await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=GateA())
                await s.commit()
                order.append("A-commit")

        async def b():
            async with make_session() as s:
                r = await promote_version(s, CO, DOC, V3, content_hash=H3, qdrant_client=SeenB())
                await s.commit()
                return r

        ta = asyncio.create_task(a())
        await asyncio.wait_for(a_inside.wait(), 10)
        tb = asyncio.create_task(b())
        await asyncio.sleep(0.5)
        assert "B-qdrant" not in order            # B is parked on the row lock
        gate.set()
        await asyncio.wait_for(ta, 10)
        rb = await asyncio.wait_for(tb, 10)
    finally:
        promote.reindex_document = orig

    assert order == ["A-qdrant", "A-commit", "B-qdrant"]
    assert rb.prior_version_id == V2              # B re-read the current pointer after the lock
    versions, docs = _state(pg)
    by_id = {v[0]: v for v in versions}
    assert [v for v in by_id if by_id[v][2]] == [V3]
    assert by_id[V1][3] == V2 and by_id[V2][1] == "superseded" and by_id[V2][3] == V3
    assert by_id[V3][4] == V2 and docs[0][:2] == (V3, H3)


# =========================================================================== guards
async def test_first_version_takes_the_reserved_hash(pg, make_session):
    con = _sync_conn(pg)
    cur = con.cursor()
    cur.execute("INSERT INTO company.company_documents (company_id, doc_id, title, "
                "current_content_hash, lifecycle_state) VALUES (%s,'DOC-000002','New',%s,'pending')",
                (CO, H3))
    nv = U("new/v1")
    cur.execute("INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
                "status, ingest_status) VALUES (%s,%s,'DOC-000002',1,'in_review','ingested')", (nv, CO))
    con.close()
    async with make_session() as s:
        res = await promote_version(s, CO, "DOC-000002", nv, qdrant_client=FakeQdrant())
        await s.commit()
    assert res.prior_version_id is None and res.content_hash == H3
    assert _rows(pg, "SELECT current_version_id::text, current_content_hash, lifecycle_state "
                     "FROM company.company_documents WHERE doc_id = 'DOC-000002'") == [(nv, H3, "active")]
    assert _rows(pg, "SELECT status, is_current, supersedes_version_id FROM company.document_versions "
                     "WHERE version_id = %s", (nv,)) == [("effective", True, None)]


async def test_later_version_without_a_hash_is_refused(pg, make_session):
    before = _state(pg)
    async with make_session() as s:
        with pytest.raises(PromotionHashUnavailable):
            await promote_version(s, CO, DOC, V2, qdrant_client=FakeQdrant())
        await s.commit()
    assert _state(pg) == before


@pytest.mark.parametrize("vid", [V3, V1, U("missing")])
async def test_not_ingested_current_or_unknown_versions_do_nothing(pg, make_session, vid):
    """v3 is still ingesting (promoting it would make an empty version current); v1 is
    already current (a no-op, not an error); an unknown id is refused."""
    before = _state(pg)
    qd = FakeQdrant()
    async with make_session() as s:
        if vid == V1:
            res = await promote_version(s, CO, DOC, V1, content_hash=H1, qdrant_client=qd)
            assert res.already_current
        else:
            with pytest.raises(PromotionNotReady):
                await promote_version(s, CO, DOC, vid, content_hash=H3, qdrant_client=qd)
        await s.commit()
    assert _state(pg) == before and qd.ops == []


async def test_hash_already_live_on_another_document_is_a_conflict(pg, make_session):
    con = _sync_conn(pg)
    con.cursor().execute("INSERT INTO company.company_documents (company_id, doc_id, title, "
                         "current_content_hash) VALUES (%s,'DOC-000009','Twin',%s)", (CO, H2))
    con.close()
    before = _state(pg)
    qd = FakeQdrant()
    async with make_session() as s:
        with pytest.raises(PromotionConflict):
            await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=qd)
    assert _state(pg) == before and qd.ops == []


async def test_superseded_version_cannot_be_repromoted(pg, make_session):
    async with make_session() as s:
        await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=FakeQdrant())
        await s.commit()
    before = _state(pg)
    qd = FakeQdrant()
    async with make_session() as s:
        with pytest.raises(PromotionNotReady, match="superseded"):
            await promote_version(s, CO, DOC, V1, content_hash=H1, qdrant_client=qd)
    assert _state(pg) == before and qd.ops == []


async def test_reused_clauses_are_reindexed_on_promotion(pg, make_session):
    """Task 5.2 constraint: promotion sweeps every other version's points for the doc, so
    clauses v2 reused from v1 (same text_sha256, enrichment inherited) MUST be re-embedded and
    re-inserted, or they would vanish from the live index. Make every v2 clause a
    byte-identical copy of v1's, then promote."""
    con = _sync_conn(pg)
    con.cursor().execute(
        "UPDATE company.clauses c2 SET text_raw = c1.text_raw, text_norm = c1.text_norm, "
        "text_sha256 = 'reused-' || c1.clause_id FROM company.clauses c1 "
        "WHERE c2.version_id = %s AND c1.version_id = %s AND c1.clause_id = c2.clause_id", (V2, V1))
    con.cursor().execute("UPDATE company.clauses SET text_sha256 = 'reused-' || clause_id "
                         "WHERE version_id = %s", (V1,))
    con.close()
    qd = FakeQdrant(_legacy_points())
    async with make_session() as s:
        res = await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=qd)
        await s.commit()
    upserted = [pid for op in qd.ops if op[0] == "upsert" for pid in op[1]]
    assert sorted(upserted) == sorted(str(stable_uuid(CO, V2, cid)) for cid in INDEXABLE)
    assert res.points_indexed == len(INDEXABLE)


async def test_reindex_ignores_the_in_memory_reused_flag():
    """Even units carrying 5.2's `_reused=True` are indexed: the flag means "skip the
    LLM", never "skip the index" — their old points belong to the old version_id and the
    sweep removes them."""
    from tests.company_ingest.test_index import make_unit

    units = [make_unit(clause_id=f"{DOC}:{i}", local_id=str(i), doc_id=DOC, heading_path=["S"],
                       text_norm=f"t{i}", role="internal_procedure") for i in range(3)]
    for u in units[:2]:
        u._reused = True
    qd = FakeQdrant()
    n = await promote.reindex_document(CO, DOC, V2, units, client=qd)
    assert qd.ops[0][0] == "upsert" and qd.ops[1][0] == "delete"
    assert n == 3 and len(qd.ops[0][1]) == 3


def test_is_current_is_gone_from_payload_indexes_and_api():
    from tests.company_ingest.test_index import make_unit

    payload = upsert_module._build_payload(make_unit(), "co", V2)
    assert "is_current" not in payload
    assert "is_current" not in qdrant_setup._BOOL_FIELDS + qdrant_setup._KEYWORD_FIELDS
    assert not hasattr(upsert_module, "mark_previous_versions_stale")


# =========================================================================== org.py wiring
async def test_final_approval_promotes_in_the_same_transaction(pg, make_session, monkeypatch):
    """End to end through the HTTP handler against the scratch DB: approving the last
    step closes the request AND promotes; a Qdrant failure records neither."""
    import httpx

    from app.api.company import org
    from app.db import get_db
    from app.main import app

    monkeypatch.setattr(org.engine_settings, "ENGINE_COMPANY_ID", CO)
    # A first version with no pending_content_hash, so the reserved hash is used.
    con = _sync_conn(pg)
    cur = con.cursor()
    nv, rid = U("org/v1"), U("org/req")
    cur.execute("INSERT INTO company.people (company_id, person_id, name) VALUES (%s,'P1','A')", (CO,))
    cur.execute("INSERT INTO company.company_documents (company_id, doc_id, title, "
                "current_content_hash, lifecycle_state) VALUES (%s,'DOC-000003','New',%s,'pending')",
                (CO, H3))
    cur.execute("INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
                "status, ingest_status) VALUES (%s,%s,'DOC-000003',1,'in_review','ingested')", (nv, CO))
    cur.execute("INSERT INTO company.approval_requests (request_id, company_id, version_id, state) "
                "VALUES (%s,%s,%s,'open')", (rid, CO, nv))
    cur.execute("INSERT INTO company.approval_steps (request_id, step_no, required_role, "
                "assignee_person_id) VALUES (%s,1,'approver','P1')", (rid,))
    con.close()

    qd = FakeQdrant(fail_on="delete")      # the version has no clauses, so no upsert happens
    monkeypatch.setattr(upsert_module, "_make_client", lambda: qd)

    async def _dep():
        async with make_session() as s:
            yield s

    app.dependency_overrides[get_db] = _dep
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            url = f"/company/approval-requests/{rid}/steps/1/decision"
            body = {"decision": "approved", "acting_person_id": "P1"}
            down = await c.post(url, json=body)
            assert down.status_code == 503
            assert _rows(pg, "SELECT state FROM company.approval_requests") == [("open",)]
            assert _rows(pg, "SELECT decision FROM company.approval_steps") == [(None,)]
            assert _rows(pg, "SELECT is_current FROM company.document_versions "
                             "WHERE version_id = %s", (nv,)) == [(False,)]

            qd.fail_on = None
            ok = await c.post(url, json=body)
            assert ok.status_code == 200 and ok.json()["request_state"] == "approved"
    finally:
        app.dependency_overrides.clear()

    assert _rows(pg, "SELECT state FROM company.approval_requests") == [("approved",)]
    assert _rows(pg, "SELECT status, is_current FROM company.document_versions "
                     "WHERE version_id = %s", (nv,)) == [("effective", True)]
    assert _rows(pg, "SELECT current_version_id::text, lifecycle_state FROM company.company_documents "
                     "WHERE doc_id = 'DOC-000003'") == [(nv, "active")]


# =========================================================================== task 3.2
async def test_v2_promotes_from_pending_content_hash_and_clears_it(pg, make_session):
    """No content_hash argument: the v2+ hash comes from document_versions.
    pending_content_hash, and is NULL afterwards (the only durable hash is
    company_documents.current_content_hash). A superseded version's pending hash is
    cleared too; an unrelated still-pending version keeps its own."""
    _set_pending(pg, V1, H1)        # a stray value on the version about to be superseded
    _set_pending(pg, V2, H2)
    _set_pending(pg, V3, H3)
    qd = FakeQdrant(_legacy_points())
    async with make_session() as s:
        res = await promote_version(s, CO, DOC, V2, qdrant_client=qd)
        await s.commit()
    assert res.content_hash == H2 and res.prior_version_id == V1
    versions, docs = _state(pg)
    by_id = {v[0]: v for v in versions}
    assert docs[0][:3] == (V2, H2, "active")
    assert by_id[V2][1:3] == ("effective", True) and by_id[V2][6] is None
    assert by_id[V1][1] == "superseded" and by_id[V1][6] is None
    assert by_id[V3][1] == "in_review" and by_id[V3][6] == H3


async def test_argument_beats_pending_hash(pg, make_session):
    _set_pending(pg, V2, H3)
    async with make_session() as s:
        res = await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=FakeQdrant())
        await s.commit()
    assert res.content_hash == H2
    assert _state(pg)[1][0][1] == H2
    assert _rows(pg, "SELECT pending_content_hash FROM company.document_versions "
                     "WHERE version_id = %s", (V2,)) == [(None,)]


async def test_malformed_pending_hash_is_refused(pg, make_session):
    _set_pending(pg, V2, "Z" * 64)
    before = _state(pg)
    qd = FakeQdrant()
    async with make_session() as s:
        with pytest.raises(PromotionHashUnavailable):
            await promote_version(s, CO, DOC, V2, qdrant_client=qd)
    assert _state(pg) == before and qd.ops == []


def _http_setup(pg, monkeypatch):
    from app.api.company import org

    monkeypatch.setattr(org.engine_settings, "ENGINE_COMPANY_ID", CO)
    con = _sync_conn(pg)
    con.cursor().execute("INSERT INTO company.people (company_id, person_id, name) "
                         "VALUES (%s,'P1','A')", (CO,))
    con.close()


async def _client(make_session):
    import httpx

    from app.db import get_db
    from app.main import app

    async def _dep():
        async with make_session() as s:
            yield s

    app.dependency_overrides[get_db] = _dep
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t"), app


async def test_v2_final_approval_promotes_via_pending_hash(pg, make_session, monkeypatch):
    """Task 3.2: before the addendum this 409'd (PromotionHashUnavailable) because a v2+
    version had nowhere to keep its hash. Now the decision handler promotes v2."""
    _http_setup(pg, monkeypatch)
    _set_pending(pg, V2, H2)
    rid = U("org/v2req")
    con = _sync_conn(pg)
    cur = con.cursor()
    cur.execute("INSERT INTO company.approval_requests (request_id, company_id, version_id, state) "
                "VALUES (%s,%s,%s,'open')", (rid, CO, V2))
    cur.execute("INSERT INTO company.approval_steps (request_id, step_no, required_role, "
                "assignee_person_id) VALUES (%s,1,'approver','P1')", (rid,))
    con.close()
    qd = FakeQdrant(_legacy_points())
    monkeypatch.setattr(upsert_module, "_make_client", lambda: qd)

    c, app = await _client(make_session)
    try:
        async with c:
            res = await c.post(f"/company/approval-requests/{rid}/steps/1/decision",
                               json={"decision": "approved", "acting_person_id": "P1"})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 200, res.text
    assert res.json()["request_state"] == "approved"
    assert res.json()["version_status"] == "effective"
    versions, docs = _state(pg)
    by_id = {v[0]: v for v in versions}
    assert docs[0][:3] == (V2, H2, "active")
    assert by_id[V2][1:3] == ("effective", True) and by_id[V2][6] is None
    assert {p["version_id"] for p in qd.points.values() if p["doc_id"] == DOC} == {V2}


async def test_open_approval_auto_approve_reports_post_promotion_status(pg, make_session, monkeypatch):
    """No policy -> auto-approve -> promotion. The response must say 'effective', not
    the 'in_review' read before promoting."""
    _http_setup(pg, monkeypatch)
    _set_pending(pg, V2, H2)
    monkeypatch.setattr(upsert_module, "_make_client", lambda: FakeQdrant())

    c, app = await _client(make_session)
    try:
        async with c:
            res = await c.post(f"/company/documents/{DOC}/versions/{V2}/approval",
                               json={"acting_person_id": "P1"})
    finally:
        app.dependency_overrides.clear()
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["auto_approved"] is True and body["state"] == "approved"
    assert body["version_status"] == "effective"
    assert _state(pg)[1][0][:2] == (V2, H2)


async def test_promotion_defaults_effective_date_but_keeps_an_earlier_one(pg, make_session):
    """A version takes effect when it becomes current.

    Promotion already defaulted `approved_date`; `effective_date` was left NULL, so every
    promoted version showed a blank effective date unless something patched it afterwards.
    A date set EARLIER (by extraction or the metadata PATCH) must survive, and a missing one
    is defaulted, for both columns."""
    from datetime import date

    con = _sync_conn(pg)
    cur = con.cursor()
    # v2 carries an explicit effective date and no approved date; v3 carries neither.
    cur.execute("UPDATE company.document_versions SET effective_date = DATE '2025-02-10' "
                "WHERE version_id = %s", (V2,))
    con.commit()
    con.close()

    qd = FakeQdrant(_legacy_points())
    async with make_session() as s:
        await promote_version(s, CO, DOC, V2, content_hash=H2, qdrant_client=qd)
        await s.commit()
    eff, appr = _rows(pg, "SELECT effective_date, approved_date FROM company.document_versions "
                          "WHERE version_id = %s", (V2,))[0]
    assert eff == date(2025, 2, 10), "an effective date set earlier must be kept"
    assert appr == date.today(), "a missing approved date is defaulted to today"

    # and when neither was set, both are defaulted
    con = _sync_conn(pg)
    cur = con.cursor()
    cur.execute("UPDATE company.document_versions SET effective_date = NULL, approved_date = NULL, "
                "pending_content_hash = %s WHERE version_id = %s", (H3, V3))
    cur.execute("UPDATE company.document_versions SET ingest_status = 'ingested' WHERE version_id = %s", (V3,))
    con.commit()
    con.close()
    async with make_session() as s:
        await promote_version(s, CO, DOC, V3, qdrant_client=FakeQdrant(_legacy_points()))
        await s.commit()
    eff3, appr3 = _rows(pg, "SELECT effective_date, approved_date FROM company.document_versions "
                            "WHERE version_id = %s", (V3,))[0]
    assert eff3 == date.today() and appr3 == date.today()

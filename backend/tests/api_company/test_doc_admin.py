"""PATCH /company/documents/{doc_id} (task 9.1 step 1a; app/api/company/doc_admin.py).

Two layers:
* FakeSession (no DB) for routing, validation and the exact SET clauses;
* a throwaway local PostgreSQL cluster (same scratch pattern as test_versions_jobs.py,
  schema from tests/engine/fixtures/company_schema.sql) proving the UPDATEs execute
  and that GET reflects them. It never connects to DATABASE_URL: get_db is
  overridden and every production client factory raises.
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import uuid
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.company_ingest.store.r2 as r2_mod
from app.api.company import doc_admin, org
from app.company_ingest import jobs
from app.company_ingest.constants import DocClass
from app.company_ingest.index import upsert as upsert_module
from app.db import get_db
from app.main import app

pytestmark = pytest.mark.asyncio

BACKEND = Path(__file__).resolve().parents[2]
SCHEMA_SQL = BACKEND / "tests" / "engine" / "fixtures" / "company_schema.sql"
CO = "co"
DOC = "DOC-000001"


def U(s: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, s))


V1, V2, V3 = U("v1"), U("v2"), U("v3")


@pytest.fixture(autouse=True)
def _isolation(monkeypatch):
    def _refuse(*a, **kw):
        raise AssertionError("test reached a production client")

    monkeypatch.setattr(jobs, "_default_session_factory", _refuse)
    monkeypatch.setattr(upsert_module, "_make_client", _refuse)
    monkeypatch.setattr(r2_mod, "get_bytes", _refuse)
    monkeypatch.setattr(org.engine_settings, "ENGINE_COMPANY_ID", CO)
    yield
    app.dependency_overrides.clear()


# =========================================================================== FakeSession
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
    """First (substring, rows) rule matching the SQL wins; records every statement."""

    def __init__(self, rules):
        self.rules = rules
        self.sql: list[tuple[str, dict]] = []
        self.committed = 0
        self.rolled_back = 0

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append((sql, params or {}))
        for key, rows in self.rules:
            if key in sql:
                return _Res(rows(params) if callable(rows) else rows)
        return _Res([])

    async def commit(self):
        self.committed += 1

    async def rollback(self):
        self.rolled_back += 1

    def find(self, needle):
        return [(s, p) for s, p in self.sql if needle in s]


PERSON = ("FROM company.people WHERE company_id = :c AND person_id = :p", [{"person_id": "P1"}])
DOC_LOCK = ("FROM company.company_documents WHERE company_id = :c AND doc_id = :d FOR UPDATE",
            [{"doc_id": DOC, "current_version_id": uuid.UUID(V1)}])
DOC_READ = ("SELECT cd.doc_id, cd.title", [{"doc_id": DOC, "title": "T", "vertical": "Environmental & Sustainability"}])
CUR_VERSION = ("AND version_id = CAST(:v AS uuid) FOR UPDATE",
               [{"version_id": uuid.UUID(V1), "status": "effective"}])
VER_UPDATE = ("UPDATE company.document_versions", [{"version_id": uuid.UUID(V1)}])


def fake_client(rules):
    sess = FakeSession(rules)

    async def _dep():
        yield sess

    app.dependency_overrides[get_db] = _dep
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t"), sess


async def test_fake_route_is_mounted_and_sets_only_sent_columns():
    c, sess = fake_client([PERSON, DOC_LOCK, CUR_VERSION, VER_UPDATE, DOC_READ])
    async with c:
        r = await c.patch(f"/company/documents/{DOC}", json={
            "acting_person_id": "P1", "vertical": "environmental-sustainability", "doc_class": "Procedure",
            "review_cycle": " Annual ", "next_review": "2026-03-01"})
    assert r.status_code == 200, r.text
    assert r.json()["doc_id"] == DOC and r.json()["vertical"] == "environmental-sustainability"
    (dsql, dp), = sess.find("UPDATE company.company_documents")
    assert "vertical = :d_vertical" in dsql and "doc_class = :d_doc_class" in dsql
    assert "review_cycle = :d_review_cycle" in dsql and "updated_at = now()" in dsql
    assert "title" not in dsql.split("WHERE")[0] and "doc_number" not in dsql
    assert (dp["d_vertical"], dp["d_doc_class"], dp["d_review_cycle"]) == ("Environmental & Sustainability", "procedure", "Annual")
    (vsql, vp), = sess.find("UPDATE company.document_versions")
    assert "next_review = :v_next_review" in vsql and "effective_date" not in vsql
    assert vp["v_next_review"] == date(2026, 3, 1) and vp["v"] == V1
    assert sess.committed == 1


async def test_fake_doc_only_patch_never_touches_versions():
    c, sess = fake_client([PERSON, DOC_LOCK, DOC_READ])
    async with c:
        r = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "title": "New"})
    assert r.status_code == 200, r.text
    assert sess.find("UPDATE company.document_versions") == []
    assert sess.find("SELECT version_id, status FROM company.document_versions") == []


async def test_fake_version_label_sets_only_the_version_column_of_the_current_version():
    c, sess = fake_client([PERSON, DOC_LOCK, CUR_VERSION, VER_UPDATE, DOC_READ])
    async with c:
        r = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "version": " 5.1 "})
    assert r.status_code == 200, r.text
    (vsql, vp), = sess.find("UPDATE company.document_versions")
    assert vsql.split("WHERE")[0].strip() == "UPDATE company.document_versions SET version = :v_version"
    assert vp["v_version"] == "5.1" and vp["v"] == V1, "stripped, applied to the current version"
    (dsql, dp), = sess.find("UPDATE company.company_documents")
    assert dsql.split("WHERE")[0].strip() == "UPDATE company.company_documents SET updated_at = now()"
    assert not [k for k in dp if k.startswith("d_")], "a version label is not a document column"
    assert sess.committed == 1


async def test_fake_version_label_null_clears_and_counts_as_a_version_level_field():
    c, sess = fake_client([PERSON, DOC_LOCK, CUR_VERSION, VER_UPDATE, DOC_READ])
    async with c:
        r = await c.patch(f"/company/documents/{DOC}",
                          json={"acting_person_id": "P1", "version_id": V1, "version": None})
    assert r.status_code == 200, r.text
    (vsql, vp), = sess.find("UPDATE company.document_versions")
    assert "version = :v_version" in vsql and vp["v_version"] is None


@pytest.mark.parametrize("body,needle", [
    ({}, None),                                                          # acting_person_id missing
    ({"acting_person_id": "P1"}, "Nothing to update"),
    ({"acting_person_id": "P1", "version_id": V1}, "Nothing to update"),
    ({"acting_person_id": "P1", "vertical": "unclassified"}, "Unknown vertical"),
    ({"acting_person_id": "P1", "vertical": "Mars"}, "Unknown vertical"),
    ({"acting_person_id": "P1", "vertical": None}, "vertical cannot be null"),
    ({"acting_person_id": "P1", "doc_class": "memo"}, "retention_schedule"),
    ({"acting_person_id": "P1", "next_review": "next tuesday"}, "ISO date"),
    ({"acting_person_id": "P1", "effective_date": ""}, "ISO date"),
    ({"acting_person_id": "P1", "approved_date": "2025-02-30"}, "ISO date"),
    ({"acting_person_id": "P1", "law_as_of": 0}, None),                  # not a string
    ({"acting_person_id": "P1", "title": None}, "title cannot be null"),
    ({"acting_person_id": "P1", "title": "   "}, "title cannot be blank"),
    ({"acting_person_id": "P1", "review_cycle": ""}, "send null to clear"),
    ({"acting_person_id": "P1", "version": ""}, "version cannot be blank; send null to clear"),
    ({"acting_person_id": "P1", "version": "   "}, "version cannot be blank; send null to clear"),
    ({"acting_person_id": "P1", "version": 5.1}, None),                 # not a string
    ({"acting_person_id": "P1", "doc_number": "X", "version_id": V1}, "no version-level field"),
    ({"acting_person_id": "P1", "status": "effective"}, None),           # immutable -> unknown key
    ({"acting_person_id": "P1", "lifecycle_state": "active"}, None),
    ({"acting_person_id": "P1", "version_no": 9}, None),
    ({"acting_person_id": "P1", "current_content_hash": "a" * 64}, None),
    ({"acting_person_id": "P1", "doc_id": "DOC-9"}, None),
])
async def test_fake_validation_is_422_and_writes_nothing(body, needle):
    c, sess = fake_client([PERSON, DOC_LOCK, CUR_VERSION, VER_UPDATE, DOC_READ])
    async with c:
        r = await c.patch(f"/company/documents/{DOC}", json=body)
    assert r.status_code == 422, r.text
    if needle:
        assert needle in str(r.json()["detail"])
    assert sess.find("UPDATE company.") == [] and sess.committed == 0


async def test_fake_doc_class_error_lists_allowed_values():
    c, _ = fake_client([PERSON, DOC_LOCK])
    async with c:
        r = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "doc_class": "x"})
    for v in DocClass:
        assert v.value in r.json()["detail"]


async def test_fake_unknown_person_and_unknown_doc_are_404():
    c, sess = fake_client([("FROM company.people", []), DOC_LOCK])
    async with c:
        r = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "GHOST", "title": "x"})
    assert r.status_code == 404 and "acting person not found" in r.json()["detail"]
    assert sess.find("UPDATE company.") == []
    c, sess = fake_client([PERSON])
    async with c:
        r = await c.patch("/company/documents/DOC-404", json={"acting_person_id": "P1", "title": "x"})
    assert r.status_code == 404 and r.json()["detail"] == "document not found"
    assert sess.find("UPDATE company.") == []


async def test_fake_malformed_version_id_is_404_before_any_sql_cast():
    c, sess = fake_client([PERSON, DOC_LOCK])
    async with c:
        r = await c.patch(f"/company/documents/{DOC}",
                          json={"acting_person_id": "P1", "version_id": "nope", "next_review": "2026-01-01"})
    assert r.status_code == 404
    assert sess.find("SELECT version_id, status FROM company.document_versions") == []


# =========================================================================== scratch PostgreSQL
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


def _sync(pg):
    import psycopg2

    con = psycopg2.connect(host=pg["host"], port=pg["port"], user="postgres", dbname="postgres")
    con.autocommit = True
    return con


def _exec(pg, sql, params=()):
    con = _sync(pg)
    try:
        con.cursor().execute(sql, params)
    finally:
        con.close()


def _rows(pg, sql, params=()):
    con = _sync(pg)
    try:
        cur = con.cursor()
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        con.close()


@pytest.fixture
def pg(scratch_pg):
    con = _sync(scratch_pg)
    cur = con.cursor()
    cur.execute("DROP SCHEMA IF EXISTS company CASCADE")
    cur.execute(SCHEMA_SQL.read_text())
    # GET's _CITED_SQL joins the regulatory KB table.
    cur.execute("CREATE TABLE IF NOT EXISTS public.code_sections (id int PRIMARY KEY, citation text)")
    cur.execute("INSERT INTO company.companies (company_id) VALUES (%s)", (CO,))
    cur.execute("INSERT INTO company.people (company_id, person_id, name) VALUES (%s,'P1','A')", (CO,))
    con.close()
    return scratch_pg


@pytest.fixture
async def factory(pg):
    engine = create_async_engine(pg["url"], poolclass=NullPool)
    yield async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def client(factory):
    async def _db():
        async with factory() as s:
            yield s

    app.dependency_overrides[get_db] = _db
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


def _doc(pg, doc_id=DOC, *, current=None, state="active", title="Policy", doc_class="plan",
         vertical="Compliance & Ethics", doc_number="RPL-X-001", review_cycle="Biennial"):
    _exec(pg, "INSERT INTO company.company_documents (company_id, doc_id, title, doc_class, vertical, "
              "doc_number, review_cycle, current_version_id, lifecycle_state, updated_at) "
              "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s, now() - interval '1 day')",
          (CO, doc_id, title, doc_class, vertical, doc_number, review_cycle, current, state))


def _version(pg, vid, no, status, *, doc_id=DOC, is_current=False, ingest="ingested"):
    _exec(pg, "INSERT INTO company.document_versions (version_id, company_id, doc_id, version_no, "
              "version, status, is_current, ingest_status, effective_date, approved_date, law_as_of, "
              "next_review) VALUES (%s,%s,%s,%s,%s,%s,%s,%s, DATE '2020-01-01', DATE '2020-01-02', "
              "DATE '2020-01-03', DATE '2020-01-04')",
          (vid, CO, doc_id, no, f"v{no}.0", status, is_current, ingest))


_DOC_COLS = "SELECT title, doc_class, vertical, doc_number, review_cycle FROM company.company_documents WHERE doc_id = %s"
_VER_COLS = ("SELECT effective_date, approved_date, law_as_of, next_review FROM company.document_versions "
             "WHERE version_id = %s")
OLD_DATES = (date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3), date(2020, 1, 4))


async def test_pg_sets_doc_fields_and_current_version_dates_and_get_reflects(pg, client):
    _doc(pg, current=V1, doc_class=None, vertical=None, review_cycle=None, doc_number=None)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review")
    body = {"acting_person_id": "P1", "title": "Retention Schedule", "doc_class": "retention_schedule",
            "vertical": "workforce-employment", "doc_number": "RPL-RRS-001", "review_cycle": "Annual",
            "next_review": "2026-06-30", "effective_date": "2025-01-15",
            "approved_date": "2025-01-14", "law_as_of": "2024-12-31"}
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}", json=body)
        got = await c.get(f"/company/documents/{DOC}")
    assert r.status_code == 200, r.text
    assert _rows(pg, _DOC_COLS, (DOC,)) == [
        ("Retention Schedule", "retention_schedule", "Workforce & Employment", "RPL-RRS-001", "Annual")]
    assert _rows(pg, _VER_COLS, (V1,)) == [
        (date(2025, 1, 15), date(2025, 1, 14), date(2024, 12, 31), date(2026, 6, 30))]
    assert _rows(pg, _VER_COLS, (V2,)) == [OLD_DATES], "only the current version changes"
    assert _rows(pg, "SELECT updated_at > now() - interval '1 minute' FROM company.company_documents") == [(True,)]
    # nothing immutable moved
    assert _rows(pg, "SELECT version_no, status, is_current FROM company.document_versions ORDER BY version_no") \
        == [(1, "effective", True), (2, "in_review", False)]
    assert r.json() == got.json(), "PATCH returns the GET payload"
    g = got.json()
    assert (g["title"], g["doc_type"], g["vertical"], g["vertical_name"]) == (
        "Retention Schedule", "Retention Schedule", "workforce-employment", "Workforce & Employment")
    assert (g["doc_number"], g["review_cycle"], g["next_review"]) == ("RPL-RRS-001", "Annual", "2026-06-30")
    assert (g["effective_date"], g["approved_date"], g["law_as_of"]) == ("2025-01-15", "2025-01-14", "2024-12-31")


async def test_pg_vertical_accepts_lowercase_name_and_slug_for_all_14(pg, client):
    from app.api.company.routes import VERTICAL_SLUGS

    _doc(pg, current=None)
    async with client as c:
        for name, slug in VERTICAL_SLUGS.items():
            for value in (name, slug):
                r = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "vertical": value})
                assert r.status_code == 200, (value, r.text)
                assert r.json()["vertical"] == slug
                assert _rows(pg, "SELECT vertical FROM company.company_documents") == [(name.title(),)]


async def test_pg_verticals_table_enforces_fk_on_old_and_invalid_names(pg):
    """company.verticals (added by migration 9c1e4b7a2f05) is a real FK target in
    the test fixture now, not just an app-layer check. A raw INSERT of an
    old-taxonomy or otherwise unknown vertical string directly against
    company_documents.vertical or approval_policies.applies_to_vertical must be
    rejected by Postgres itself with a foreign-key violation -- proving the
    fixture (tests/engine/fixtures/company_schema.sql) actually has the FK, not
    just the app's own validation in front of it."""
    import psycopg2

    _doc(pg, doc_id="DOC-FK-1", current=None, vertical=None)

    # old (pre-retaxonomy) and nonsense values are both rejected on INSERT.
    for bad in ("Policy & Governance", "Mars"):
        with pytest.raises(psycopg2.errors.ForeignKeyViolation):
            _exec(
                pg,
                "UPDATE company.company_documents SET vertical = %s WHERE doc_id = %s",
                (bad, "DOC-FK-1"),
            )

    # same FK on approval_policies.applies_to_vertical.
    policy_id = str(uuid.uuid4())
    with pytest.raises(psycopg2.errors.ForeignKeyViolation):
        _exec(
            pg,
            "INSERT INTO company.approval_policies (company_id, policy_id, name, applies_to_vertical) "
            "VALUES (%s, %s, %s, %s)",
            (CO, policy_id, "bad policy", "Policy & Governance"),
        )

    # a canonical new-taxonomy name, and NULL (unclassified), both still work.
    _exec(
        pg,
        "UPDATE company.company_documents SET vertical = %s WHERE doc_id = %s",
        ("Compliance & Ethics", "DOC-FK-1"),
    )
    _exec(
        pg,
        "UPDATE company.company_documents SET vertical = NULL WHERE doc_id = %s",
        ("DOC-FK-1",),
    )
    _exec(
        pg,
        "INSERT INTO company.approval_policies (company_id, policy_id, name, applies_to_vertical) "
        "VALUES (%s, %s, %s, %s)",
        (CO, policy_id, "good policy", "Risk & Resilience"),
    )
    assert _rows(pg, "SELECT applies_to_vertical FROM company.approval_policies WHERE policy_id = %s",
                 (policy_id,)) == [("Risk & Resilience",)]

    # the seeded lookup table matches the migration's 14-row NEW_VERTICALS exactly.
    assert _rows(pg, "SELECT count(*) FROM company.verticals") == [(14,)]
    assert _rows(pg, "SELECT name, slug FROM company.verticals WHERE name = %s",
                 ("Corporate Governance & Board",)) == [("Corporate Governance & Board", "corporate-governance-board")]


async def test_pg_no_current_version_updates_newest_non_retired(pg, client):
    _doc(pg, current=None, state="pending")
    _version(pg, V1, 1, "in_review")
    _version(pg, V2, 2, "in_review")
    _version(pg, V3, 3, "retired")
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}",
                          json={"acting_person_id": "P1", "next_review": "2027-01-01"})
        got = await c.get(f"/company/documents/{DOC}")
    assert r.status_code == 200, r.text
    assert _rows(pg, "SELECT version_no, next_review FROM company.document_versions ORDER BY version_no") == [
        (1, date(2020, 1, 4)), (2, date(2027, 1, 1)), (3, date(2020, 1, 4))]
    # GET reads dates from the current version only, which does not exist yet
    assert got.json()["has_current_version"] is False and got.json()["next_review"] is None


async def test_pg_explicit_version_id_selects_that_version(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review")
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}",
                          json={"acting_person_id": "P1", "version_id": V2, "effective_date": "2026-02-02"})
    assert r.status_code == 200, r.text
    assert _rows(pg, _VER_COLS, (V1,)) == [OLD_DATES]
    assert _rows(pg, "SELECT effective_date FROM company.document_versions WHERE version_id = %s", (V2,)) \
        == [(date(2026, 2, 2),)]


async def test_pg_explicit_null_clears_and_omitted_fields_untouched(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}", json={
            "acting_person_id": "P1", "doc_class": None, "review_cycle": None, "next_review": None})
        got = await c.get(f"/company/documents/{DOC}")
    assert r.status_code == 200, r.text
    assert _rows(pg, _DOC_COLS, (DOC,)) == [("Policy", None, "Compliance & Ethics", "RPL-X-001", None)]
    assert _rows(pg, _VER_COLS, (V1,)) == [(date(2020, 1, 1), date(2020, 1, 2), date(2020, 1, 3), None)]
    g = got.json()
    assert (g["doc_type"], g["review_cycle"], g["next_review"]) == ("Document", None, None)
    assert (g["vertical"], g["doc_number"], g["effective_date"]) == ("compliance-ethics", "RPL-X-001", "2020-01-01")


async def test_pg_doc_only_patch_works_with_no_versions_at_all(pg, client):
    _doc(pg, current=None, state="pending")
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "doc_number": "RPL-Z-9"})
    assert r.status_code == 200, r.text
    assert r.json()["doc_number"] == "RPL-Z-9"


async def test_pg_version_field_with_no_editable_version_is_409(pg, client):
    _doc(pg, current=None, state="retired")
    _version(pg, V1, 1, "retired")
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}",
                          json={"acting_person_id": "P1", "title": "T2", "next_review": "2027-01-01"})
    assert r.status_code == 409, r.text
    assert _rows(pg, _DOC_COLS, (DOC,))[0][0] == "Policy", "the doc-level part is not applied either"


async def test_pg_retired_version_is_409_and_unchanged(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "retired")
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}", json={
            "acting_person_id": "P1", "version_id": V2, "next_review": "2027-01-01", "title": "T2"})
    assert r.status_code == 409 and "retired" in r.json()["detail"]
    assert _rows(pg, _VER_COLS, (V2,)) == [OLD_DATES]
    assert _rows(pg, _DOC_COLS, (DOC,))[0][0] == "Policy"


async def test_pg_version_of_another_document_or_unknown_or_malformed_is_404(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _doc(pg, "DOC-000002", current=V2)
    _version(pg, V2, 1, "effective", doc_id="DOC-000002", is_current=True)
    async with client as c:
        other = await c.patch(f"/company/documents/{DOC}",
                              json={"acting_person_id": "P1", "version_id": V2, "next_review": "2027-01-01"})
        unknown = await c.patch(f"/company/documents/{DOC}", json={
            "acting_person_id": "P1", "version_id": str(uuid.uuid4()), "next_review": "2027-01-01"})
        bad = await c.patch(f"/company/documents/{DOC}",
                            json={"acting_person_id": "P1", "version_id": "nope", "next_review": "2027-01-01"})
    assert (other.status_code, unknown.status_code, bad.status_code) == (404, 404, 404)
    assert _rows(pg, _VER_COLS, (V2,)) == [OLD_DATES]


async def test_pg_unknown_person_unknown_doc_and_bad_input(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    async with client as c:
        ghost = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "GHOST", "title": "x"})
        missing = await c.patch("/company/documents/DOC-404", json={"acting_person_id": "P1", "title": "x"})
        empty = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1"})
        no_body = await c.patch(f"/company/documents/{DOC}", json={})
        bad_v = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "vertical": "unclassified"})
        bad_c = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "doc_class": "memo"})
        bad_d = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "law_as_of": "31/12/2024"})
        status = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "status": "retired"})
    assert ghost.status_code == 404 and missing.status_code == 404
    assert [x.status_code for x in (empty, no_body, bad_v, bad_c, bad_d, status)] == [422] * 6
    assert _rows(pg, _DOC_COLS, (DOC,)) == [("Policy", "plan", "Compliance & Ethics", "RPL-X-001", "Biennial")]
    assert _rows(pg, _VER_COLS, (V1,)) == [OLD_DATES]
    assert _rows(pg, "SELECT status FROM company.document_versions") == [("effective",)]
    assert _rows(pg, "SELECT updated_at < now() - interval '1 hour' FROM company.company_documents") == [(True,)]


_LABEL = "SELECT version FROM company.document_versions WHERE version_id = %s"


async def test_pg_version_label_set_on_current_version_only_and_get_reflects(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review")
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "version": "  5.1 "})
        got = await c.get(f"/company/documents/{DOC}")
    assert r.status_code == 200, r.text
    assert _rows(pg, _LABEL, (V1,)) == [("5.1",)]
    assert _rows(pg, _LABEL, (V2,)) == [("v2.0",)], "only the current version changes"
    assert _rows(pg, _VER_COLS, (V1,)) == [OLD_DATES], "the dates are untouched"
    assert _rows(pg, _DOC_COLS, (DOC,)) == [("Policy", "plan", "Compliance & Ethics", "RPL-X-001", "Biennial")]
    assert _rows(pg, "SELECT version_no, status, is_current FROM company.document_versions ORDER BY version_no") \
        == [(1, "effective", True), (2, "in_review", False)]
    assert r.json()["version"] == "5.1" and got.json()["version"] == "5.1"


async def test_pg_version_label_explicit_version_id_and_null_clear(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "in_review")
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}", json={
            "acting_person_id": "P1", "version_id": V2, "version": "Sheets as revised through 2024-06-01"})
        assert r.status_code == 200, r.text
        assert _rows(pg, _LABEL, (V1,)) == [("v1.0",)]
        assert _rows(pg, _LABEL, (V2,)) == [("Sheets as revised through 2024-06-01",)]
        r = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "version": None})
        assert r.status_code == 200, r.text
    assert _rows(pg, _LABEL, (V1,)) == [(None,)]
    assert r.json()["version"] == "", "GET renders a NULL label as an empty string"


async def test_pg_version_label_on_retired_version_is_409_and_unchanged(pg, client):
    _doc(pg, current=V1)
    _version(pg, V1, 1, "effective", is_current=True)
    _version(pg, V2, 2, "retired")
    async with client as c:
        r = await c.patch(f"/company/documents/{DOC}",
                          json={"acting_person_id": "P1", "version_id": V2, "version": "9.9"})
        blank = await c.patch(f"/company/documents/{DOC}", json={"acting_person_id": "P1", "version": " "})
    assert r.status_code == 409 and blank.status_code == 422
    assert _rows(pg, _LABEL, (V2,)) == [("v2.0",)] and _rows(pg, _LABEL, (V1,)) == [("v1.0",)]


async def test_doc_classes_mirror_the_enum():
    assert set(doc_admin.DOC_CLASSES) == {c.value for c in DocClass}

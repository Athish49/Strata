"""Task 7.1: every engine/API clause query is scoped to the document's current version.

Runs each real query path against a throwaway local PostgreSQL cluster (initdb in a pytest
tmp dir, unix socket only, torn down afterwards). It never connects to DATABASE_URL. The
module is skipped when no ``initdb``/``pg_ctl`` binary is available, except for the
static check, which always runs.

Fixture data, company ``co``:

* ``POL``: a prose document with two live versions. V1 is old, V2 is current. Both
  versions carry a clause with clause_id ``POL-1`` and their own citations and scope rows.
  Exactly V2 must surface.
* ``REG``: a document with one document_versions row, whose ``register_row`` clause sits
  under a *different*, orphan version_id (no company.document_versions row of its own —
  the shape the pre-v2 register CSV path used to write). Task 9.2 step 7 removed the
  exemption that used to keep this clause in scope regardless; it must now drop out, the
  same as REG2's.
* ``REG2``: the same shape — an orphan register row on a document that has also gained a
  second, current version. Kept as a second, independent case: before task 9.2 step 7 this
  was the one where the old exemption's "at most one version" guard switched off; now it
  behaves identically to REG, which is the point — there is no longer a special case.
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import uuid
from pathlib import Path

import pytest

import app.api.engine.routes  # noqa: F401  (import order: routes registers routes_ui_results)
from app.api.company import routes as company_routes
from app.api.engine import routes_ui_results
from app.engine import candidates, delta, footprint, radar
from app.engine.footprint import VERSION_SCOPE

CO = "co"
U = lambda s: str(uuid.uuid5(uuid.NAMESPACE_URL, s))  # noqa: E731

V1, V2 = U("POL/v1"), U("POL/v2")
VR, VO = U("REG/real"), U("REG/orphan")
VA, VB, VX = U("REG2/a"), U("REG2/b"), U("REG2/orphan")
P1, P2 = U("pk/P1"), U("pk/P2")          # POL v1 (stale), POL v2 (current)
R1, R2 = U("pk/R1"), U("pk/R2")          # REG current prose, REG legacy register row
X1, X2 = U("pk/X1"), U("pk/X2")          # REG2 orphan register row (stale), REG2 current
ALL_PKS = [P1, P2, R1, R2, X1, X2]
IN_SCOPE = {P2, R1, X2}  # R2 (REG's orphan register row) no longer kept (task 9.2 step 7)

# Minimal company.* DDL for the scratch cluster (formerly app/company_ingest/store/schema.sql,
# moved here by task 2.3; the real schema is owned by the alembic migrations).
SCHEMA_SQL = Path(__file__).resolve().parent / "fixtures" / "company_schema.sql"


# --------------------------------------------------------------------------- static check
def test_every_site_embeds_version_scope():
    """Every clause query path carries the shared predicate and a `d` documents join."""
    join = "JOIN company.company_documents d ON d.company_id = c.company_id AND d.doc_id = c.doc_id"
    sites = {
        "footprint._ELIGIBLE_CTE": footprint._ELIGIBLE_CTE,
        "candidates._ELIGIBLE": candidates._ELIGIBLE,
        "radar._DOC_CITATIONS_SQL": str(radar._DOC_CITATIONS_SQL),
        "delta._CLAUSE_IDS_SQL": str(delta._CLAUSE_IDS_SQL),
        "company._CITED_SQL": company_routes._CITED_SQL,
    }
    for name, sql in sites.items():
        assert VERSION_SCOPE in sql, name
        assert join in sql, name
    for name, sql in {"footprint._SCOPE_SQL": str(footprint._SCOPE_SQL),
                      "radar._DOC_SCOPE_SQL": str(radar._DOC_SCOPE_SQL)}.items():
        assert "s.version_id = d.current_version_id" in sql, name
    import inspect
    for fn in (company_routes.list_clauses, routes_ui_results._via_rows):
        src = inspect.getsource(fn)
        assert "VERSION_SCOPE" in src and join in src, fn.__name__


# --------------------------------------------------------------------------- scratch cluster
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
    import psycopg2

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
        con = psycopg2.connect(host=str(sock), port=port, user="postgres", dbname="postgres")
        con.autocommit = True
        cur = con.cursor()
        cur.execute(SCHEMA_SQL.read_text())
        cur.execute("ALTER TABLE company.clause_parameters ADD COLUMN IF NOT EXISTS is_citation_fragment boolean")
        cur.execute("CREATE TABLE public.code_sections (id int PRIMARY KEY, citation text)")
        _seed(cur)
        con.close()
        yield f"postgresql+asyncpg://postgres@/postgres?host={sock}&port={port}"
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sock, ignore_errors=True)


def _seed(cur) -> None:
    sections = {100: "170 IAC 1-1-1", 200: "170 IAC 2-1-1", 300: "170 IAC 3-1-1",
                400: "170 IAC 4-1-1", 500: "170 IAC 5-1-1", 600: "170 IAC 6-1-1"}
    for sid, cite in sections.items():
        cur.execute("INSERT INTO public.code_sections VALUES (%s, %s)", (sid, cite))
    cur.execute("INSERT INTO company.companies (company_id) VALUES (%s)", (CO,))
    for doc, cur_v in (("POL", V2), ("REG", VR), ("REG2", VB)):
        cur.execute("INSERT INTO company.company_documents (company_id, doc_id, title, current_version_id) "
                    "VALUES (%s, %s, %s, %s)", (CO, doc, doc, cur_v))
    for vid, doc in ((V1, "POL"), (V2, "POL"), (VR, "REG"), (VA, "REG2"), (VB, "REG2")):
        cur.execute("INSERT INTO company.document_versions (version_id, company_id, doc_id) VALUES (%s, %s, %s)",
                    (vid, CO, doc))
    # pk, version, doc, clause_id, ordinal, unit_kind
    clauses = [
        (P1, V1, "POL", "POL-1", 1, "table_row"),   # stale; lower ordinal so DISTINCT ON would pick it
        (P2, V2, "POL", "POL-1", 2, "section"),
        (R1, VR, "REG", "REG-1", 1, "section"),
        (R2, VO, "REG", "REG-row-1", 2, "register_row"),
        (X1, VX, "REG2", "REG2-row-1", 1, "register_row"),
        (X2, VB, "REG2", "REG2-1", 2, "section"),
    ]
    for pk, vid, doc, cid, ordn, kind in clauses:
        cur.execute("""INSERT INTO company.clauses (clause_pk, company_id, version_id, doc_id, clause_id,
                       ordinal, unit_kind, heading_path, text_raw, clause_role, assessable)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, ARRAY['h'], %s, 'operative', true)""",
                    (pk, CO, vid, doc, cid, ordn, kind, f"text of {cid}@{vid[:4]}"))
    # pk -> (status, code_section_id, raw)
    cites = [
        (P1, "resolved", "100", "170 IAC 1-1-1"),
        (P1, "resolved_rule", None, "170 IAC 7-1"),
        (P2, "resolved", "200", "170 IAC 2-1-1"),
        (R2, "resolved", "300", "170 IAC 3-1-1"),
        (X1, "resolved", "400", "170 IAC 4-1-1"),
        (R1, "resolved", "500", "170 IAC 5-1-1"),
        (X2, "resolved", "600", "170 IAC 6-1-1"),
    ]
    for pk, status, sid, raw in cites:
        cur.execute("INSERT INTO company.clause_citations (citation_pk, clause_pk, citation_raw, code_section_id, "
                    "resolution_status) VALUES (%s, %s, %s, %s, %s)", (str(uuid.uuid4()), pk, raw, sid, status))
    for doc, vid, key in (("POL", V1, "170 IAC 8-1"), ("POL", V2, "170 IAC 9-1")):
        cur.execute("INSERT INTO company.document_scope (company_id, doc_id, version_id, scope_level, scope_key) "
                    "VALUES (%s, %s, %s, 'rule', %s)", (CO, doc, vid, key))
    for pk in (P1, P2):
        cur.execute("INSERT INTO company.clause_parameters (parameter_pk, clause_pk, kind, value_text, value_num, "
                    "unit) VALUES (%s, %s, 'duration', '10 days', 10, 'day')", (str(uuid.uuid4()), pk))


@pytest.fixture
async def session(scratch_pg):
    assert "neon" not in scratch_pg and os.environ.get("DATABASE_URL", "\0") not in scratch_pg
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    eng = create_async_engine(scratch_pg)
    try:
        async with AsyncSession(eng) as s:
            yield s
    finally:
        await eng.dispose()


# --------------------------------------------------------------------------- path tests
async def test_fixture_really_has_two_live_versions(session):
    """Control: the unscoped doc_id join (the pre-7.1 shape) sees both POL versions."""
    from sqlalchemy import text
    rows = (await session.execute(text(
        "SELECT c.clause_pk::text FROM company.clauses c JOIN company.company_documents d "
        "ON d.doc_id = c.doc_id AND d.company_id = :co WHERE c.doc_id = 'POL'"), {"co": CO})).scalars().all()
    assert set(rows) == {P1, P2}


async def test_footprint(session):
    fp = await footprint.load_footprint(session, CO)
    assert fp.eligible_clauses == len(IN_SCOPE)
    assert fp.cited_section_ids == {200, 500, 600}              # not 100 (POL v1), 300 (REG orphan) nor 400 (REG2 orphan)
    assert set().union(*fp.clauses_by_section.values()) == IN_SCOPE
    assert fp.cited_rule_keys == {"170 IAC 9-1"}                # not v1's rule cite / v1's scope row


async def test_candidates(session):
    data = await candidates.load_candidate_data(session, CO)
    assert set(data.clauses) == IN_SCOPE
    assert data.doc_clauses["POL"] == {P2}
    assert {p["clause_pk"] for p in data.params} == {P2}
    assert set(data.citations) <= IN_SCOPE


async def test_radar_rule_docs(session):
    rows = (await session.execute(radar._DOC_CITATIONS_SQL, {"company_id": CO})).mappings().all()
    assert {r["section_citation"] for r in rows} == {"170 IAC 2-1-1", "170 IAC 5-1-1", "170 IAC 6-1-1"}
    docs = await radar.load_rule_docs(session, CO)
    assert "170 IAC 1-1" not in docs and "170 IAC 7-1" not in docs and "170 IAC 8-1" not in docs
    assert "170 IAC 4-1" not in docs
    assert "170 IAC 3-1" not in docs    # REG's orphan register row (R2) is no longer in scope
    assert docs["170 IAC 2-1"] == ["POL"] and docs["170 IAC 9-1"] == ["POL"]
    assert docs["170 IAC 5-1"] == ["REG"]


async def test_delta_clause_ids(session):
    rows = (await session.execute(delta._CLAUSE_IDS_SQL, {"pks": ALL_PKS})).mappings().all()
    assert {r["clause_pk"] for r in rows} == IN_SCOPE
    assert [r["clause_id"] for r in rows if r["doc_id"] == "POL"] == ["POL-1"]


async def test_company_cited_sql(session):
    from sqlalchemy import text
    rows = (await session.execute(text(company_routes._CITED_SQL.format(extra="")), {"cid": CO})).mappings().all()
    by_doc: dict[str, set[str]] = {}
    for r in rows:
        by_doc.setdefault(r["doc_id"], set()).add(r["citation"])
    assert by_doc == {"POL": {"170 IAC 2-1-1"}, "REG": {"170 IAC 5-1-1"},
                      "REG2": {"170 IAC 6-1-1"}}


async def test_company_list_clauses(session, monkeypatch):
    monkeypatch.setattr(company_routes.engine_settings, "ENGINE_COMPANY_ID", CO)
    pol = await company_routes.list_clauses("POL", db=session)
    assert [(c["clause_id"], c["ordinal"], c["unit_kind"]) for c in pol] == [("POL-1", 1, "section")]
    assert pol[0]["text_raw"].endswith(V2[:4])
    reg = await company_routes.list_clauses("REG", db=session)
    assert [c["clause_id"] for c in reg] == ["REG-1"]                    # orphan register row dropped
    reg2 = await company_routes.list_clauses("REG2", db=session)
    assert [c["clause_id"] for c in reg2] == ["REG2-1"]                  # orphan dropped here too


async def test_ui_via_rows(session):
    details = [[{"via_clause_id": "POL-1"}], [{"via_clause_id": "REG-row-1"}], [{"via_clause_id": "REG2-row-1"}]]
    via = await routes_ui_results._via_rows(session, CO, details)
    assert set(via) == {"POL-1"}    # REG-row-1 and REG2-row-1 (both orphans) are out of scope
    assert via["POL-1"]["unit_kind"] == "section"                        # v2's row, not v1's lower ordinal

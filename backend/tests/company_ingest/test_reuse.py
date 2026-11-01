"""Task 5.2 — ``reuse_from_prior_version`` (TDD §4.2).

Unit tests use a tiny in-memory session.  ``test_real_postgres_*`` runs the
two SELECTs against a throwaway local PostgreSQL cluster (``initdb`` in a
pytest tmp dir, unix socket only), built from
``tests/engine/fixtures/company_schema.sql`` — it never connects to
``DATABASE_URL``; skipped when no ``initdb`` / ``pg_ctl`` is available.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

from app.company_ingest.enrich.parameter_entry import ParameterEntry
from app.company_ingest.ids import stable_uuid
from app.company_ingest.parse.models import ClauseUnit
from app.company_ingest.parse.text import sha256_text
from app.company_ingest.reuse import (
    is_reused,
    reuse_from_prior_version,
    units_needing_embedding,
)
from app.company_ingest.run_context import RunContext

pytestmark = pytest.mark.asyncio

CO, DOC = "co", "DOC-000001"
V1 = str(uuid.uuid5(uuid.NAMESPACE_URL, "reuse/v1"))
V2 = str(uuid.uuid5(uuid.NAMESPACE_URL, "reuse/v2"))


def _unit(local: str, text: str, ordinal: int, *, version_id: str = V2,
          unit_kind: str = "paragraph", section_kind: str = "body") -> ClauseUnit:
    return ClauseUnit(
        version_id=version_id, doc_id=DOC, clause_id=f"{DOC}:{local}", local_id=local,
        parent_clause_id=None, unit_kind=unit_kind, heading_path=["H"],
        section_kind=section_kind, ordinal=ordinal, char_start=0, char_end=len(text),
        line_start=1, text_raw=text, text_norm=text, text_sha256=sha256_text(text),
    )


def _row(local: str, text: str, ordinal: int, *, role="internal_procedure", method="llm",
         stmt="stmt", topics=("t",), assessable=True, unit_kind="paragraph",
         section_kind="body") -> dict:
    return {
        "clause_pk": str(stable_uuid(CO, V1, f"{DOC}:{local}")), "clause_id": f"{DOC}:{local}",
        "ordinal": ordinal, "text_sha256": sha256_text(text), "unit_kind": unit_kind,
        "section_kind": section_kind, "clause_role": role, "role_method": method,
        "assessable": assessable, "normalized_statement": stmt,
        "topic_terms": list(topics) if topics is not None else None,
    }


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        rows = self._rows

        class _M:
            def all(self_inner):
                return list(rows)

        return _M()


class MiniSession:
    def __init__(self, clauses: list[dict], params: list[dict] | None = None):
        self.clauses, self.params, self.calls = clauses, params or [], []

    async def execute(self, stmt, params=None):
        sql = " ".join(str(stmt).split())
        self.calls.append((sql, params))
        if "FROM company.clauses" in sql:
            assert params["version_id"] == V1 and params["company_id"] == CO
            return _Res(sorted(self.clauses, key=lambda r: (r["ordinal"], r["clause_id"])))
        if "FROM company.clause_parameters" in sql:
            assert "method = 'llm'" in sql
            return _Res([p for p in self.params if p["clause_pk"] in params["clause_pks"]])
        raise AssertionError(sql)


# ---------------------------------------------------------------------------


async def test_first_version_reuses_nothing_and_issues_no_sql():
    s = MiniSession([])
    units = [_unit("1", "A.", 1)]
    assert await reuse_from_prior_version(s, CO, DOC, None, units) == 0
    assert s.calls == [] and not is_reused(units[0])


async def test_reingesting_the_prior_version_itself_is_a_noop():
    s = MiniSession([_row("1", "A.", 1)])
    units = [_unit("1", "A.", 1, version_id=V1)]
    assert await reuse_from_prior_version(s, CO, DOC, V1, units) == 0
    assert s.calls == []


async def test_matches_on_text_hash_and_inherits_llm_fields_only():
    s = MiniSession(
        [_row("1", "Same.", 1, role="company_position", stmt="S1", topics=["a", "b"],
              assessable=False),
         _row("2", "Old.", 2)],
        [{"clause_pk": str(stable_uuid(CO, V1, f"{DOC}:1")), "kind": "period",
          "value_text": "Same", "value_num": None, "unit": None, "qualifier": None,
          "day_type": "n_a", "span_start": 0, "span_end": 4, "verified": True}],
    )
    ctx = RunContext(company_id=CO)
    same, new = _unit("1", "Same.", 1), _unit("2", "New.", 2)
    assert await reuse_from_prior_version(s, CO, DOC, V1, [same, new], ctx) == 1

    assert is_reused(same) and not is_reused(new)
    assert (same.role, same.role_method, same.assessable) == ("company_position", "llm", False)
    assert same.normalized_statement == "S1" and same.topic_terms == ["a", "b"]
    # citations are left to stage 4; only the LLM-derived parameter is inherited
    assert same.citations == []
    assert [(p.value_text, p.method, p.value_source) for p in same.parameters] == [
        ("Same", "llm", None)]
    assert isinstance(same.parameters[0], ParameterEntry)
    assert new.role is None and new.normalized_statement is None and new.parameters == []
    assert ctx.stats["clauses_reused"] == 1
    assert units_needing_embedding([same, new]) == [new]
    assert same._reused_from == str(stable_uuid(CO, V1, f"{DOC}:1"))


async def test_deterministic_role_is_not_inherited():
    """marker/grammar/heuristic roles are recomputed by stage 4 (enrich_roles
    skips units whose role is already set, so inheriting would freeze them)."""
    s = MiniSession([_row("1", "Same.", 1, role="definition", method="grammar", stmt="S")])
    u = _unit("1", "Same.", 1)
    assert await reuse_from_prior_version(s, CO, DOC, V1, [u]) == 1
    assert u.role is None and u.role_method is None and u.assessable is None
    assert u.normalized_statement == "S"


async def test_prior_without_llm_output_is_not_reused():
    """A prior ingested with no_llm must not lock its clauses out of the LLM."""
    s = MiniSession([_row("1", "Same.", 1, role="internal_procedure", method="heuristic",
                          stmt=None, topics=None)])
    u = _unit("1", "Same.", 1)
    assert await reuse_from_prior_version(s, CO, DOC, V1, [u]) == 0
    assert not is_reused(u) and u.role is None


async def test_structural_change_is_not_reused():
    s = MiniSession([_row("1", "Same.", 1, section_kind="body")])
    u = _unit("1", "Same.", 1, section_kind="definitions")
    assert await reuse_from_prior_version(s, CO, DOC, V1, [u]) == 0
    assert not is_reused(u)


async def test_duplicate_text_picks_first_prior_by_ordinal():
    boiler = "This page intentionally left blank."
    s = MiniSession([
        _row("9", boiler, 9, stmt="LATE"),
        _row("3", boiler, 3, stmt="FIRST"),
        _row("5", boiler, 5, stmt="MIDDLE"),
    ])
    units = [_unit("a", boiler, 1), _unit("b", boiler, 2), _unit("c", "Other.", 3)]
    assert await reuse_from_prior_version(s, CO, DOC, V1, units) == 2
    assert [u.normalized_statement for u in units] == ["FIRST", "FIRST", None]
    assert {u._reused_from for u in units[:2]} == {str(stable_uuid(CO, V1, f"{DOC}:3"))}


async def test_ordinal_tie_broken_by_clause_id():
    s = MiniSession([_row("b", "X.", 1, stmt="B"), _row("a", "X.", 1, stmt="A")])
    u = _unit("z", "X.", 1)
    await reuse_from_prior_version(s, CO, DOC, V1, [u])
    assert u.normalized_statement == "A"


# ---------------------------------------------------------------------------
# Real SQL against a throwaway local PostgreSQL
# ---------------------------------------------------------------------------

SCHEMA_SQL = Path(__file__).resolve().parents[1] / "engine" / "fixtures" / "company_schema.sql"


def _pg_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for cand in sorted(Path("/opt/homebrew/opt").glob("postgresql@*/bin/" + name), reverse=True):
        return str(cand)
    return None


@pytest.fixture(scope="module")
def scratch_pg(tmp_path_factory):
    initdb, pg_ctl = _pg_bin("initdb"), _pg_bin("pg_ctl")
    if not (initdb and pg_ctl):
        pytest.skip("no local initdb/pg_ctl for a scratch PostgreSQL cluster")
    import socket

    import psycopg2

    base = tmp_path_factory.mktemp("pg")
    data, sock = base / "data", Path(f"/tmp/strata-pg-{uuid.uuid4().hex[:8]}")
    sock.mkdir()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
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
        rows = [
            # local, text, ordinal, version, stmt
            ("1", "Kept.", 2, V1, "KEPT-LATE"),
            ("0", "Kept.", 1, V1, "KEPT-FIRST"),
            ("2", "Changed old.", 3, V1, "OLD"),
            ("1", "Kept.", 1, V2, "WRONG-VERSION"),       # same doc, other version
        ]
        for local, txt, ordn, vid, stmt in rows:
            cur.execute(
                """INSERT INTO company.clauses (clause_pk, company_id, version_id, doc_id,
                       clause_id, ordinal, unit_kind, section_kind, text_raw, text_sha256,
                       clause_role, role_method, assessable, normalized_statement, topic_terms)
                   VALUES (%s, %s, %s, %s, %s, %s, 'paragraph', 'body', %s, %s,
                           'company_position', 'llm', false, %s, ARRAY['x'])""",
                (str(stable_uuid(CO, vid, f"{DOC}:{local}")), CO, vid, DOC, f"{DOC}:{local}",
                 ordn, txt, sha256_text(txt), stmt))
        # another company's identical clause under the same version id must not leak
        cur.execute(
            """INSERT INTO company.clauses (clause_pk, company_id, version_id, doc_id, clause_id,
                   ordinal, unit_kind, section_kind, text_raw, text_sha256, role_method,
                   normalized_statement)
               VALUES (%s, 'other', %s, %s, 'x', 0, 'paragraph', 'body', 'Kept.', %s, 'llm',
                       'LEAK')""",
            (str(uuid.uuid4()), V1, DOC, sha256_text("Kept.")))
        first_pk = str(stable_uuid(CO, V1, f"{DOC}:0"))
        for pk, method, vt in ((first_pk, "llm", "Kept"), (first_pk, "regex", "Kept.")):
            cur.execute(
                """INSERT INTO company.clause_parameters (parameter_pk, clause_pk, kind, value_text,
                       span_start, span_end, value_num, day_type, method, verified)
                   VALUES (%s, %s, 'period', %s, 0, 4, 1.5, 'n_a', %s, true)""",
                (str(uuid.uuid4()), pk, vt, method))
        con.close()
        yield f"postgresql+asyncpg://postgres@/postgres?host={sock}&port={port}"
    finally:
        subprocess.run([pg_ctl, "-D", str(data), "-m", "immediate", "stop"], capture_output=True)
        shutil.rmtree(sock, ignore_errors=True)


async def test_real_postgres_reuse_queries(scratch_pg):
    assert "neon" not in scratch_pg and os.environ.get("DATABASE_URL", "\0") not in scratch_pg
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    eng = create_async_engine(scratch_pg)
    try:
        async with AsyncSession(eng) as s:
            v3 = str(uuid.uuid5(uuid.NAMESPACE_URL, "reuse/v3"))
            kept = _unit("1", "Kept.", 1, version_id=v3)
            changed = _unit("2", "Changed new.", 2, version_id=v3)
            n = await reuse_from_prior_version(s, CO, DOC, V1, [kept, changed])
            assert n == 1
            assert kept.normalized_statement == "KEPT-FIRST"
            assert (kept.role, kept.assessable, kept.topic_terms) == (
                "company_position", False, ["x"])
            assert [(p.value_text, p.method, p.value_num) for p in kept.parameters] == [
                ("Kept", "llm", 1.5)]
            assert not is_reused(changed)
            assert await reuse_from_prior_version(s, CO, DOC, None, [changed]) == 0
            await s.rollback()
    finally:
        await eng.dispose()

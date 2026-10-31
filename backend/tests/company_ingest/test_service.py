"""Task 5.1 — the per-document ingest service.

No database, no network, no Anthropic, no Qdrant, no R2:

* ``FakeDB`` is an in-memory stand-in for the caller's ``AsyncSession``.  It
  dispatches on SQL text and models every table ``commit_run`` writes as an
  upsert keyed by that table's conflict target, so row sets can be compared
  across runs (idempotency) and the LLM cache is honoured across sessions.
* ``resolve_citations_for_version`` is replaced by a fake that resolves IAC
  rows in ``FakeDB`` (only non-terminal rows, like the real one).
* The LLM provider is mocked with a call counter; the R2 audit write, the
  embedding model and the R2 snapshot client are stubbed.
"""
from __future__ import annotations

import builtins
import csv
import io
import json
import pathlib
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest

from app.company_ingest import service as service_mod
from app.company_ingest.extract import DocxExtractor
from app.company_ingest.register_spec import RegisterSpec, validate_register_spec
from app.company_ingest.run_context import RunContext
from app.company_ingest.service import (
    CitationResolutionError,
    IngestResult,
    ingest_document,
)
from app.company_ingest.store.neon import DocumentVersionSpec

pytestmark = pytest.mark.asyncio

BACKEND = Path(__file__).resolve().parents[2]
# A test-owned, byte-identical copy of a seeded corpus render, so these tests keep
# running when backend/synthetic/ is deleted (task 9.4 deletability gate).
DOCX_FIXTURE = BACKEND / "tests" / "fixtures" / "docx" / "RPL-CS-PRO-004_v5.1.docx"

COMPANY = "rpl"
DOC_ID = "DOC-000123"

PROSE_MD = """\
# Disconnection Procedure

## 1 Purpose

This procedure implements 170 IAC 4-1-16 for residential disconnection.

## 2 Notice

The utility shall give written notice at least 14 days before disconnection,
as required by 170 IAC 4-1-16.5.

## 3 Records

Records are retained for 3 years.
"""


# ---------------------------------------------------------------------------
# FakeDB — in-memory AsyncSession stand-in
# ---------------------------------------------------------------------------


class _Result:
    def __init__(self, rows: list[tuple] | None = None, mapping_rows: list[dict] | None = None,
                 scalar: Any = None):
        self._rows = rows or []
        self._maps = mapping_rows or []
        self._scalar = scalar

    def first(self):
        return self._rows[0] if self._rows else None

    def all(self):
        return list(self._rows)

    def scalar(self):
        return self._scalar

    def mappings(self):
        maps = self._maps

        class _M:
            def first(self_inner):
                return maps[0] if maps else None

            def all(self_inner):
                return list(maps)

        return _M()


# conflict target per table (mirrors store/neon.py ON CONFLICT clauses)
_KEYS = {
    "document_versions": ("version_id",),
    "clauses": ("version_id", "clause_id"),
    "clause_citations": ("citation_pk",),
    "clause_parameters": ("parameter_pk",),
    "defined_terms": ("term_pk",),
    "term_usages": ("term_pk", "clause_pk"),
    "clause_links": ("link_pk",),
    "document_scope": ("version_id", "scope_level", "scope_key"),
    "table_columns": ("company_id", "doc_id", "table_name", "column_name"),
    "ingest_runs": ("run_id",),
    "company_documents": ("company_id", "doc_id"),
}
_DO_NOTHING = {"clause_citations", "clause_links"}
_LLM_KEY = ("company_id", "stage", "content_sha256", "prompt_sha256", "model")


class FakeDB:
    """One persistent 'database'; ``session()`` hands out session objects."""

    def __init__(self):
        self.tables: dict[str, dict[tuple, dict]] = {t: {} for t in _KEYS}
        self.llm: dict[tuple, dict] = {}
        self.statements: list[str] = []
        #: (source_system, title_number) pairs public.code_sections holds a snapshot of
        #: at the lookup date (the must-resolve guard's KB-coverage probe).
        self.kb_titles: set[tuple[str, str]] = set()
        self.kb_probes: list[dict] = []

    def session(self) -> "FakeSession":
        return FakeSession(self)

    def snapshot(self, *, exclude: tuple[str, ...] = ("ingest_runs",)) -> dict:
        """Row sets with volatile columns stripped, for idempotency checks."""
        volatile = {"ingested_at", "ingest_run_id", "run_id", "started_at", "finished_at"}
        out = {}
        for t, rows in self.tables.items():
            if t in exclude:
                continue
            out[t] = {
                k: {c: v for c, v in r.items() if c not in volatile} for k, r in rows.items()
            }
        return out


class FakeSession:
    def __init__(self, db: FakeDB):
        self.db = db

    @asynccontextmanager
    async def _nested(self):
        yield self

    def begin_nested(self):
        return self._nested()

    async def commit(self):  # pragma: no cover - the service must never call it
        raise AssertionError("ingest_document must not commit the caller's session")

    async def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.db.statements.append(sql)
        if isinstance(params, list):
            for p in params:
                await self.execute(statement, p)
            return _Result()
        p = dict(params or {})

        # ---- llm cache --------------------------------------------------
        if "company.llm_extractions" in sql:
            key = tuple(p[c] for c in _LLM_KEY)
            if sql.startswith("SELECT"):
                row = self.db.llm.get(key)
                return _Result(rows=[(json.loads(row["response"]),)] if row else [])
            self.db.llm.setdefault(key, p)
            return _Result()

        # ---- service reads ----------------------------------------------
        if sql.startswith("SELECT company_id, doc_id, version, version_no"):
            row = self.db.tables["document_versions"].get((p["version_id"],))
            return _Result(mapping_rows=[row] if row else [])
        if "COALESCE(MAX(version_no), 0) + 1" in sql:
            nos = [r["version_no"] for r in self.db.tables["document_versions"].values()
                   if r["company_id"] == p["company_id"] and r["doc_id"] == p["doc_id"]]
            return _Result(scalar=max(nos, default=0) + 1)
        if sql.startswith("SELECT current_version_id"):
            row = self.db.tables["company_documents"].get((p["company_id"], p["doc_id"]))
            return _Result(scalar=row.get("current_version_id") if row else None)
        if sql.startswith("SELECT cc.citation_pk, cc.resolution_status"):
            return _Result(rows=self._citations_for(p["version_id"], p["company_id"]))

        if "FROM public.code_sections" in sql:
            self.db.kb_probes.append(p)
            return _Result(scalar=(p["source_system"], p["title"]) in self.db.kb_titles)

        if sql.startswith("UPDATE company.document_versions SET law_as_of"):
            row = self.db.tables["document_versions"].get((p["version_id"],))
            if row is not None and row.get("law_as_of") is None:
                row["law_as_of"] = p["law_as_of"]
            return _Result()

        # ---- inserts ------------------------------------------------------
        if sql.startswith("INSERT INTO company."):
            table = sql[len("INSERT INTO company."):].split()[0]
            key = tuple(p[c] for c in _KEYS[table])
            rows = self.db.tables[table]
            if key in rows and table in _DO_NOTHING:
                return _Result()
            if key in rows and table == "document_versions":
                # status / is_current are never in the update list
                for c in ("ingest_status", "ingested_at", "ingest_run_id", "source_r2_key",
                          "extraction_r2_key", "extraction_method"):
                    rows[key][c] = p.get(c)
                return _Result()
            if table == "document_versions":
                p.setdefault("is_current", False)
            rows[key] = {**rows.get(key, {}), **p}
            return _Result()

        # ---- task 5.2 reuse reads (app/company_ingest/reuse.py) ---------------
        if sql.startswith("SELECT CAST(clause_pk AS text) AS clause_pk, clause_id, ordinal"):
            rows = [
                {"topic_terms": None, **r} for r in self.db.tables["clauses"].values()
                if r["company_id"] == p["company_id"] and r["doc_id"] == p["doc_id"]
                and r["version_id"] == p["version_id"]
            ]
            rows.sort(key=lambda r: (r["ordinal"], r["clause_id"]))
            return _Result(mapping_rows=rows)
        if sql.startswith("SELECT CAST(clause_pk AS text) AS clause_pk, kind"):
            pks = set(p["clause_pks"])
            rows = [r for r in self.db.tables["clause_parameters"].values()
                    if r["clause_pk"] in pks and r["method"] == "llm"]
            rows.sort(key=lambda r: (r["clause_pk"], r["span_start"], r["span_end"],
                                     r["value_text"]))
            return _Result(mapping_rows=rows)

        raise AssertionError(f"FakeSession: unexpected SQL: {sql[:120]}")

    def _citations_for(self, version_id: str, company_id: str) -> list[tuple]:
        clause_pks = {
            r["clause_pk"] for r in self.db.tables["clauses"].values()
            if r["version_id"] == version_id and r["company_id"] == company_id
        }
        return [
            (r["citation_pk"], r["resolution_status"], r["code_section_id"], r["in_knowledge_base"])
            for r in self.db.tables["clause_citations"].values()
            if r["clause_pk"] in clause_pks
        ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_TERMINAL = {"resolved", "resolved_rule", "not_in_kb", "not_monitored", "external",
             "out_of_scope_title", "unparsed"}


class FakeResolver:
    """Stands in for enrich/resolve_citations.resolve_citations_for_version."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []

    async def __call__(self, session, company_id, version_id):
        self.calls.append((company_id, version_id))
        clause_pks = {
            r["clause_pk"] for r in session.db.tables["clauses"].values()
            if r["version_id"] == version_id and r["company_id"] == company_id
        }
        counts: dict[str, int] = {}
        for r in session.db.tables["clause_citations"].values():
            if r["clause_pk"] not in clause_pks or r["resolution_status"] in _TERMINAL:
                continue
            if r["source_system"] == "iac":
                r["resolution_status"] = "resolved"
                r["code_section_id"] = f"cs::{r['citation_raw']}"
                r["in_knowledge_base"] = True
            else:
                r["resolution_status"] = "not_monitored"
            counts[r["resolution_status"]] = counts.get(r["resolution_status"], 0) + 1
        return counts


class FakeR2:
    def __init__(self):
        self.puts: dict[str, bytes] = {}

    def put_bytes(self, key, data, metadata, content_type="application/octet-stream",
                  force=False):
        self.puts[key] = data
        return "ok"


class Provider:
    """Mock LLM provider with a call counter."""

    def __init__(self):
        self.calls = 0

    async def __call__(self, system: str, user: str, model: str) -> str:
        self.calls += 1
        if "classifying columns" in system:
            cols = user.split("Columns needing classification:")[1].split("Sample rows")[0]
            names = [c.strip() for c in cols.strip().splitlines() if c.strip()]
            return json.dumps({"assignments": [
                {"column_name": n, "role": "free_text"} for n in names]})
        return json.dumps({
            "clause_role": "internal_procedure",
            "normalized_statement": "The utility gives notice.",
            "topic_terms": ["notice"],
            "parameters": [],
            "citation_links": [],
        })


@pytest.fixture
def env(monkeypatch):
    provider = Provider()
    resolver = FakeResolver()
    qdrant_calls: list[str] = []

    monkeypatch.setattr("app.company_ingest.llm.client._call_provider", provider)

    async def _no_audit(*a, **k):
        return None

    monkeypatch.setattr("app.company_ingest.llm.client._write_audit", _no_audit)
    monkeypatch.setattr(
        "app.company_ingest.link.restates.embed_texts",
        lambda texts: [[1.0, 0.0] for _ in texts],
    )
    monkeypatch.setattr(service_mod, "resolve_citations_for_version", resolver)

    # Any Qdrant touch is recorded (and would fail anyway).
    import app.company_ingest.index.upsert as upsert_mod

    for name in dir(upsert_mod):
        obj = getattr(upsert_mod, name)
        if callable(obj) and not name.startswith("__") and getattr(obj, "__module__", "") == upsert_mod.__name__:
            monkeypatch.setattr(
                upsert_mod, name,
                lambda *a, _n=name, **k: qdrant_calls.append(_n),
            )
    try:
        import qdrant_client

        def _boom(*a, **k):
            qdrant_calls.append("QdrantClient")
            raise AssertionError("Qdrant must not be touched by ingest")

        monkeypatch.setattr(qdrant_client, "QdrantClient", _boom)
        monkeypatch.setattr(qdrant_client, "AsyncQdrantClient", _boom, raising=False)
    except ImportError:  # pragma: no cover
        pass

    return {"provider": provider, "resolver": resolver, "qdrant": qdrant_calls}


def _vid() -> str:
    return str(uuid.uuid4())


async def _ingest(db: FakeDB, markdown: str, version_id: str, *, register_spec=None,
                  doc_id: str = DOC_ID, ctx: RunContext | None = None, r2=None,
                  **kw) -> IngestResult:
    return await ingest_document(
        company_id=COMPANY,
        doc_id=doc_id,
        version_id=version_id,
        markdown=markdown,
        register_spec=register_spec,
        session=db.session(),
        ctx=ctx or RunContext(company_id=COMPANY),
        r2_client=r2 or FakeR2(),
        **kw,
    )


# ---------------------------------------------------------------------------
# Prose
# ---------------------------------------------------------------------------


async def test_docx_derived_markdown_for_system_doc_id_yields_clauses(env):
    markdown = DocxExtractor().extract(DOCX_FIXTURE.read_bytes(), DOCX_FIXTURE.name).markdown
    db = FakeDB()
    vid = _vid()
    r2 = FakeR2()

    result = await _ingest(db, markdown, vid, r2=r2)

    assert result.clause_count > 0
    assert result.version_id == vid
    clauses = db.tables["clauses"].values()
    assert len(clauses) == result.clause_count
    assert all(c["version_id"] == vid and c["company_id"] == COMPANY for c in clauses)
    assert all(c["clause_id"].startswith(f"{DOC_ID}:") for c in clauses)
    # citations written and resolved via the (mocked) resolver
    assert result.citations_total > 0
    assert result.citations_resolved > 0
    assert env["resolver"].calls == [(COMPANY, vid)]
    assert db.tables["document_scope"]
    # every clause version has a document_versions row (no orphans)
    assert {c["version_id"] for c in clauses} <= {k[0] for k in db.tables["document_versions"]}
    # LLM ran (and was counted) on a cold cache
    assert result.llm_calls == env["provider"].calls > 0
    assert result.llm_cache_hits == 0
    # snapshot keyed by the REAL version_id, not "v1"
    (key,) = r2.puts
    assert f"/{vid}/" in key and "/v1/" not in key
    assert result.snapshot_r2_key == key
    snap = [json.loads(line) for line in r2.puts[key].decode().splitlines()]
    assert any(c["resolution_status"] == "resolved" and c["code_section_id"]
               for row in snap for c in row["citations"])
    # zero Qdrant calls
    assert env["qdrant"] == []


async def test_version_row_inserted_in_review_before_segmenting(env, monkeypatch):
    db = FakeDB()
    vid = _vid()
    seen_rows_at_segment: list[int] = []
    real_segment = service_mod.segment_with_ctx

    def _spy(*a, **k):
        seen_rows_at_segment.append(len(db.tables["document_versions"]))
        return real_segment(*a, **k)

    monkeypatch.setattr(service_mod, "segment_with_ctx", _spy)
    result = await _ingest(db, PROSE_MD, vid)

    assert seen_rows_at_segment == [1]
    row = db.tables["document_versions"][(vid,)]
    assert row["status"] == "in_review"
    assert row["is_current"] is False
    assert row["version_no"] == result.version_no == 1
    # promotion-owned fields are never written
    for sql in db.statements:
        assert "current_version_id =" not in sql and "current_content_hash" not in sql
    assert "UPDATE company.document_versions" not in " ".join(db.statements)


async def test_existing_version_row_is_reused_not_clobbered(env):
    db = FakeDB()
    vid = _vid()
    db.tables["document_versions"][(vid,)] = {
        "version_id": vid, "company_id": COMPANY, "doc_id": DOC_ID, "version": "v5.1",
        "version_no": 3, "status": "in_review", "is_current": False,
        "source_r2_key": "company/rpl/raw/DOC-000123/x.docx", "next_review": None,
        "effective_date": None, "approved_date": None, "law_as_of": None,
        "classification": "internal", "regulatory_basis": [], "render_r2_keys": [],
        "extraction_r2_key": "company/rpl/extract/x.md", "extraction_method": "python-docx/1.1",
        "supersedes_version_id": None, "created_by_person_id": "P01", "change_reason": "edit",
    }
    result = await _ingest(db, PROSE_MD, vid)
    row = db.tables["document_versions"][(vid,)]
    assert result.version_no == 3
    assert row["source_r2_key"] == "company/rpl/raw/DOC-000123/x.docx"
    assert row["extraction_method"] == "python-docx/1.1"


async def test_law_as_of_filled_on_pre_existing_row_with_null(env):
    from datetime import date

    db = FakeDB()
    vid = _vid()
    db.tables["document_versions"][(vid,)] = {
        "version_id": vid, "company_id": COMPANY, "doc_id": DOC_ID, "version": None,
        "version_no": 1, "status": "in_review", "is_current": False, "source_r2_key": None,
        "next_review": None, "effective_date": None, "approved_date": None, "law_as_of": None,
        "classification": "internal", "regulatory_basis": [], "render_r2_keys": [],
        "extraction_r2_key": None, "extraction_method": None, "supersedes_version_id": None,
        "created_by_person_id": None, "change_reason": None,
    }
    await _ingest(db, PROSE_MD, vid, law_as_of=date(2024, 12, 31))
    assert db.tables["document_versions"][(vid,)]["law_as_of"] == date(2024, 12, 31)


async def test_missing_law_as_of_is_surfaced_as_issue(env):
    ctx = RunContext(company_id=COMPANY)
    await _ingest(FakeDB(), PROSE_MD, _vid(), ctx=ctx)
    assert any(i.code == "law_as_of_missing" for i in ctx.issues)


async def test_out_of_scope_titles_do_not_fail_the_guard(env, monkeypatch):
    async def _all_out_of_scope(session, company_id, version_id):
        for r in session.db.tables["clause_citations"].values():
            r["resolution_status"] = "out_of_scope_title"
        return {}

    monkeypatch.setattr(service_mod, "resolve_citations_for_version", _all_out_of_scope)
    result = await _ingest(FakeDB(), PROSE_MD, _vid())
    assert result.citations_resolved == 0
    assert result.citation_status_counts == {"out_of_scope_title": result.citations_total}


async def test_duplicate_clause_ids_are_reported(env, monkeypatch):
    # The segmenter de-duplicates today (``1`` -> ``1_T1_2``); this guard is
    # defensive, so inject a collision directly.
    import dataclasses

    real_segment = service_mod.segment_with_ctx

    def _dup(*a, **k):
        units = real_segment(*a, **k)
        return units + [dataclasses.replace(units[-1], ordinal=units[-1].ordinal + 1)]

    monkeypatch.setattr(service_mod, "segment_with_ctx", _dup)
    ctx = RunContext(company_id=COMPANY)
    result = await _ingest(FakeDB(), PROSE_MD, _vid(), ctx=ctx)
    assert result.duplicate_clause_ids >= 1
    assert any(i.code == "duplicate_clause_id" for i in ctx.issues)


async def test_second_version_gets_next_version_no(env):
    db = FakeDB()
    await _ingest(db, PROSE_MD, _vid())
    result = await _ingest(db, PROSE_MD + "\n## 4 Extra\n\nMore text.\n", _vid())
    assert result.version_no == 2


async def test_idempotent_for_same_version_id(env):
    db = FakeDB()
    vid = _vid()
    first = await _ingest(db, PROSE_MD, vid)
    snap1 = db.snapshot()
    second = await _ingest(db, PROSE_MD, vid)
    snap2 = db.snapshot()

    assert snap1 == snap2
    assert first.clause_count == second.clause_count
    # resolver returns {} on the re-run (rows terminal) but totals are stable
    assert second.citations_resolved == first.citations_resolved > 0
    assert len(db.tables["document_versions"]) == 1


async def test_second_ingest_of_identical_markdown_makes_zero_provider_calls(env):
    """Proves the persistent LLM cache is wired (content_sha256 + session)."""
    db = FakeDB()
    first = await _ingest(db, PROSE_MD, _vid(), ctx=RunContext(company_id=COMPANY))
    calls_after_first = env["provider"].calls
    assert calls_after_first > 0
    assert first.llm_calls == calls_after_first
    assert db.llm, "results must be stored in company.llm_extractions"

    # fresh RunContext (empty in-memory tier), new session, NEW version_id
    second = await _ingest(db, PROSE_MD, _vid(), ctx=RunContext(company_id=COMPANY))
    assert env["provider"].calls == calls_after_first  # ZERO new provider calls
    assert second.llm_calls == 0
    assert second.llm_cache_hits == first.llm_calls


async def test_company_id_mismatch_between_ctx_and_arg_fails_loudly(env):
    with pytest.raises(ValueError, match="company_id"):
        await _ingest(FakeDB(), PROSE_MD, _vid(), ctx=RunContext(company_id="RPL"))
    with pytest.raises(ValueError, match="company_id"):
        await _ingest(FakeDB(), PROSE_MD, _vid(), ctx=RunContext())


async def test_unresolved_iac_citations_fail_loudly(env, monkeypatch):
    async def _resolves_nothing(session, company_id, version_id):
        return {}

    monkeypatch.setattr(service_mod, "resolve_citations_for_version", _resolves_nothing)
    with pytest.raises(CitationResolutionError):
        await _ingest(FakeDB(), PROSE_MD, _vid())


def _all_not_in_kb(monkeypatch):
    async def _resolver(session, company_id, version_id):
        for r in session.db.tables["clause_citations"].values():
            r["resolution_status"] = "not_in_kb"
        return {}

    monkeypatch.setattr(service_mod, "resolve_citations_for_version", _resolver)


async def test_zero_resolved_against_a_covered_title_is_a_warning_not_a_failure(env, monkeypatch):
    """Task 9.1 rehearsal: RPL-ENV-PRO-005 cites only ``327 IAC 2-6.1``. Title 327 is in
    the KB at law_as_of, rule 2-6.1 is not, so every lookup ran against real data and
    found nothing: a correct 0, which v1 ingested. It must not fail the upload."""
    from datetime import date

    _all_not_in_kb(monkeypatch)
    db = FakeDB()
    db.kb_titles = {("iac", "170")}
    ctx = RunContext(company_id=COMPANY)
    result = await _ingest(db, PROSE_MD, _vid(), ctx=ctx, law_as_of=date(2024, 12, 31))
    assert result.citations_resolved == 0
    assert result.citation_status_counts == {"not_in_kb": result.citations_total}
    assert any(i.code == "citations_none_resolved" for i in ctx.issues)
    assert db.kb_probes and db.kb_probes[0]["law_as_of"] == date(2024, 12, 31)
    assert db.kb_probes[0]["window_days"] == 0  # IAC: no window (CFR gets 14)


async def test_zero_resolved_with_no_kb_snapshot_at_law_as_of_still_fails(env, monkeypatch):
    """A law_as_of that predates every snapshot of the cited title (or a KB missing the
    snapshot) yields not_in_kb everywhere too; that IS the fault the guard exists for."""
    _all_not_in_kb(monkeypatch)
    db = FakeDB()  # kb_titles empty: no snapshot of title 170 at the lookup date
    with pytest.raises(CitationResolutionError, match="0 resolved"):
        await _ingest(db, PROSE_MD, _vid())
    assert {(p["source_system"], p["title"]) for p in db.kb_probes} == {("iac", "170")}


async def test_unprocessed_citations_fail_without_consulting_the_kb(env, monkeypatch):
    """Rows the resolver never classified (status NULL) are not ``not_in_kb``: the
    coverage probe must not even run, so it cannot excuse them."""
    async def _resolves_nothing(session, company_id, version_id):
        return {}

    monkeypatch.setattr(service_mod, "resolve_citations_for_version", _resolves_nothing)
    db = FakeDB()
    db.kb_titles = {("iac", "170")}
    with pytest.raises(CitationResolutionError):
        await _ingest(db, PROSE_MD, _vid())
    assert db.kb_probes == []


async def test_explicit_version_spec_must_match(env):
    with pytest.raises(ValueError):
        await _ingest(
            FakeDB(), PROSE_MD, _vid(),
            version_spec=DocumentVersionSpec(version_id=_vid(), version_no=1),
        )


async def test_no_filesystem_corpus_access(env, monkeypatch):
    opened: list[str] = []
    real_open = builtins.open
    real_path_open = pathlib.Path.open

    def _open(file, *a, **k):
        opened.append(str(file))
        return real_open(file, *a, **k)

    def _path_open(self, *a, **k):
        opened.append(str(self))
        return real_path_open(self, *a, **k)

    monkeypatch.setattr(builtins, "open", _open)
    monkeypatch.setattr(pathlib.Path, "open", _path_open)
    monkeypatch.delenv("CORPUS_ROOT", raising=False)

    await _ingest(FakeDB(), PROSE_MD, _vid())
    assert not [p for p in opened if "corpus" in p or "synthetic" in p], opened

    src = Path(service_mod.__file__).read_text()
    for forbidden in ("CORPUS_ROOT", "company_ingest.collect", "company_ingest.datasets",
                      "company_ingest.constants", "company_ingest.cli", "company_ingest.index",
                      "qdrant", ".commit()"):
        assert forbidden not in src, forbidden


# ---------------------------------------------------------------------------
# Registers
# ---------------------------------------------------------------------------


def _register_csv() -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["title", "obligation_id", "regulatory_authority", "notes"])
    w.writerow(["Disconnection notice", "OBL-001", "170 IAC 4-1-16", "n1"])
    w.writerow(["Deposit rules", "OBL-002", "170 IAC 4-1-15", "n2"])
    w.writerow(["", "", "", ""])  # trailing spreadsheet artefact
    return "﻿" + buf.getvalue()


async def test_register_with_non_first_id_column_gets_correct_clause_ids(env):
    raw = _register_csv()
    spec = RegisterSpec(register_type="obligation", id_column="obligation_id",
                        citation_columns=["regulatory_authority"])
    validate_register_spec(spec, raw.encode("utf-8"))
    db = FakeDB()
    vid = _vid()

    result = await _ingest(db, raw, vid, register_spec=spec, doc_id="DOC-000200")

    clause_ids = sorted(r["clause_id"] for r in db.tables["clauses"].values())
    assert clause_ids == ["DOC-000200:OBL-001", "DOC-000200:OBL-002"]  # blank row skipped
    assert result.clause_count == 2
    # BOM never reaches the header
    first = next(iter(db.tables["clauses"].values()))
    assert "title" in json.loads(first["row_cells"])
    # declared citation column was scanned and resolved, under a real version row
    assert result.citations_total == 2
    assert result.citations_resolved == 2
    assert (vid,) in db.tables["document_versions"]
    roles = {r["column_name"]: r["column_role"] for r in db.tables["table_columns"].values()}
    assert roles["obligation_id"] == "id"
    assert roles["regulatory_authority"] == "citation"
    assert roles["title"] != "id"
    assert env["qdrant"] == []


async def test_register_column_roles_are_cache_backed(env):
    spec = RegisterSpec(register_type="obligation", id_column="obligation_id",
                        citation_columns=["regulatory_authority"])
    db = FakeDB()
    await _ingest(db, _register_csv(), _vid(), register_spec=spec, doc_id="DOC-000200")
    calls = env["provider"].calls
    assert calls > 0
    second = await _ingest(db, _register_csv(), _vid(), register_spec=spec, doc_id="DOC-000200")
    assert env["provider"].calls == calls
    assert second.llm_calls == 0


# ---------------------------------------------------------------------------
# Task 5.2 — clause-level reuse through the service
# ---------------------------------------------------------------------------

PROSE_MD_V2 = PROSE_MD.replace("Records are retained for 3 years.",
                               "Records are retained for 5 years.")


def _rows_for(db: FakeDB, table: str, version_id: str) -> dict[str, list[dict]]:
    """{clause_id: [child rows]} for one version (clauses or a child table)."""
    clauses = {r["clause_pk"]: r for r in db.tables["clauses"].values()
               if r["version_id"] == version_id}
    if table == "clauses":
        return {r["clause_id"]: [r] for r in clauses.values()}
    out: dict[str, list[dict]] = {r["clause_id"]: [] for r in clauses.values()}
    for r in db.tables[table].values():
        if r["clause_pk"] in clauses:
            out[clauses[r["clause_pk"]]["clause_id"]].append(r)
    return out


async def _v1_then_promote(db: FakeDB) -> tuple[str, IngestResult]:
    v1 = _vid()
    first = await _ingest(db, PROSE_MD, v1)
    # Promotion (task 5.6) is the only writer of current_version_id; simulate it
    # so the next version's supersedes_version_id = v1.
    db.tables["company_documents"][(COMPANY, DOC_ID)] = {
        "company_id": COMPANY, "doc_id": DOC_ID, "current_version_id": v1}
    return v1, first


async def test_v2_with_one_changed_clause_makes_exactly_one_provider_call(env):
    db = FakeDB()
    v1, first = await _v1_then_promote(db)
    assert first.reused_clauses == 0
    # Clear the persistent LLM cache: otherwise it alone (keyed on text_sha256)
    # would make unchanged clauses free and this test would not prove reuse.
    db.llm.clear()
    calls_before = env["provider"].calls

    ctx = RunContext(company_id=COMPANY)
    second = await _ingest(db, PROSE_MD_V2, _vid(), ctx=ctx)

    assert env["provider"].calls - calls_before == 1
    assert second.llm_calls == 1 and second.llm_cache_hits == 0
    assert second.stats["units_enriched_llm"] == 1
    assert second.reused_clauses == second.clause_count - 1 > 0
    assert ctx.stats["clauses_reused"] == second.reused_clauses


async def test_reused_clauses_carry_v1_enrichment_and_new_keys(env):
    db = FakeDB()
    v1, _ = await _v1_then_promote(db)
    # Make v1's LLM output observable: a sentinel the provider never returns,
    # plus an LLM-derived parameter (stage 4 can never regenerate those).
    v1_rows = _rows_for(db, "clauses", v1)
    notice = next(cid for cid, (r,) in v1_rows.items() if "14 days" in r["text_raw"])
    for (r,) in v1_rows.values():
        r.update(normalized_statement=f"V1::{r['clause_id']}", topic_terms=["v1-topic"],
                 clause_role="company_position", role_method="llm", assessable=False)
    notice_pk = v1_rows[notice][0]["clause_pk"]
    db.tables["clause_parameters"][("llm-param-v1",)] = {
        "parameter_pk": "llm-param-v1", "clause_pk": notice_pk, "kind": "period",
        "name": None, "value_text": "written notice", "span_start": 4, "span_end": 18,
        "value_num": None, "unit": None, "qualifier": None, "day_type": "n_a",
        "supported_by_citation_pk": None, "value_source": "company", "method": "llm",
        "verified": True}
    db.llm.clear()

    v2 = _vid()
    await _ingest(db, PROSE_MD_V2, v2)

    v2_rows = _rows_for(db, "clauses", v2)
    changed = [cid for cid, (r,) in v2_rows.items() if "5 years" in r["text_raw"]]
    assert len(changed) == 1
    for cid, (r,) in v2_rows.items():
        if cid in changed:
            assert r["normalized_statement"] == "The utility gives notice."  # fresh LLM output
            continue
        assert r["normalized_statement"] == f"V1::{cid}"
        assert r["topic_terms"] == ["v1-topic"]
        assert (r["clause_role"], r["role_method"], r["assessable"]) == (
            "company_position", "llm", False)
    # inherited LLM parameter re-keyed under v2 (never the old primary key)
    v2_params = _rows_for(db, "clause_parameters", v2)[notice]
    llm = [p for p in v2_params if p["method"] == "llm"]
    assert [p["value_text"] for p in llm] == ["written notice"]
    assert llm[0]["parameter_pk"] != "llm-param-v1"
    assert llm[0]["clause_pk"] == v2_rows[notice][0]["clause_pk"]


async def test_reuse_does_not_double_append_citations_or_parameters(env):
    db = FakeDB()
    v1, _ = await _v1_then_promote(db)
    v2 = _vid()
    second = await _ingest(db, PROSE_MD, v2)  # identical text: every LLM'd clause reused
    assert second.reused_clauses > 0

    for table, pk in (("clause_citations", "citation_pk"), ("clause_parameters", "parameter_pk")):
        a, b = _rows_for(db, table, v1), _rows_for(db, table, v2)
        assert {k: len(v) for k, v in a.items()} == {k: len(v) for k, v in b.items()}, table
        assert sum(len(v) for v in b.values()) > 0, table
        assert {r[pk] for v in a.values() for r in v}.isdisjoint(
            {r[pk] for v in b.values() for r in v}), table
        # no duplicate (raw, span) within one clause
        for rows in b.values():
            sig = [(r.get("citation_raw") or r.get("value_text"), r["span_start"]) for r in rows]
            assert len(sig) == len(set(sig)), table
    assert second.citations_resolved > 0


async def test_reused_clauses_are_excluded_from_embedding_input(env, monkeypatch):
    from app.company_ingest.reuse import units_needing_embedding

    db = FakeDB()
    await _v1_then_promote(db)
    seen: list = []
    real = service_mod.write_clause_snapshot

    def _spy(units, *a, **k):
        seen.extend(units)
        return real(units, *a, **k)

    monkeypatch.setattr(service_mod, "write_clause_snapshot", _spy)
    db.llm.clear()
    second = await _ingest(db, PROSE_MD_V2, _vid())

    to_embed = units_needing_embedding(seen)
    assert len(seen) - len(to_embed) == second.reused_clauses > 0
    assert [u.text_raw.strip() for u in to_embed if "years" in u.text_raw] == [
        "Records are retained for 5 years."]
    assert all(not getattr(u, "_reused", False) for u in to_embed)
    assert all(getattr(u, "_reused_from", None) for u in seen if u not in to_embed)


async def test_first_version_reuses_nothing(env):
    db = FakeDB()
    result = await _ingest(db, PROSE_MD, _vid())
    assert result.reused_clauses == 0
    assert not any("company.clause_parameters WHERE" in s or s.startswith("SELECT CAST(clause_pk")
                   for s in db.statements)

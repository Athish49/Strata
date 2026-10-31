"""Task 5.5 — version-scoped child primary keys in store/neon.py.

The bug being locked out: ``citation_pk``, ``parameter_pk``, ``term_pk`` and
``link_pk`` were derived without ``version_id`` and inserted
``ON CONFLICT DO NOTHING``, so writing v2 of a document silently discarded its
own citations, parameters, terms and links.

A plain recording fake would not catch that, so ``ConflictSession`` below
actually *emulates* the conflict clauses: it parses the target table out of the
SQL, keys each row by that table's primary key, and drops a duplicate exactly
the way Postgres would.  Row counts therefore mean what they mean in the DB.

No database is touched.
"""
from __future__ import annotations

import re
import uuid
from datetime import date

import pytest

from app.company_ingest.enrich.terms import TermEntry, TermUsage
from app.company_ingest.link.document_scope import DocumentScopeRow
from app.company_ingest.link.resolve_refs import ClauseLink
from app.company_ingest.run_context import RunContext
from app.company_ingest.store import neon
from app.company_ingest.store.neon import DocumentVersionSpec, commit_run

COMPANY = "demo-co"
DOC = "DOC-000123"

# Primary key (or unique key) per table, mirroring the migration.
_PK_COLUMNS = {
    "company.company_documents": ("company_id", "doc_id"),
    "company.document_versions": ("version_id",),
    "company.clauses": ("version_id", "clause_id"),
    "company.clause_citations": ("citation_pk",),
    "company.clause_parameters": ("parameter_pk",),
    "company.defined_terms": ("term_pk",),
    "company.term_usages": ("term_pk", "clause_pk"),
    "company.clause_links": ("link_pk",),
    "company.document_scope": ("version_id", "scope_level", "scope_key"),
    "company.table_columns": ("company_id", "doc_id", "table_name", "column_name"),
    "company.ingest_runs": ("run_id",),
}

_INSERT_RE = re.compile(r"INSERT\s+INTO\s+([a-z_]+\.[a-z_]+)", re.IGNORECASE)


class _Res:
    def mappings(self):
        return self

    def all(self):
        return []

    def first(self):
        return None

    def scalar(self):
        return None


class ConflictSession:
    """A fake AsyncSession that stores rows keyed by primary key."""

    def __init__(self) -> None:
        self.tables: dict[str, dict[tuple, dict]] = {}
        self.sql: list[tuple[str, dict | None]] = []

    async def execute(self, stmt, params=None):
        sql = str(stmt)
        self.sql.append((sql, params))
        m = _INSERT_RE.search(sql)
        if m and params is not None:
            table = m.group(1).lower()
            cols = _PK_COLUMNS[table]
            key = tuple(params.get(c) for c in cols)
            rows = self.tables.setdefault(table, {})
            if key in rows:
                # Both DO NOTHING and DO UPDATE leave the row count unchanged.
                rows[key] = {**rows[key], **params}
            else:
                rows[key] = dict(params)
        return _Res()

    def count(self, table: str) -> int:
        return len(self.tables.get(table, {}))

    def rows(self, table: str) -> list[dict]:
        return list(self.tables.get(table, {}).values())

    def all_sql(self) -> str:
        return "\n".join(s for s, _ in self.sql)


# ---------------------------------------------------------------------------
# Minimal pipeline-output fixtures
# ---------------------------------------------------------------------------


class _Parsed:
    def __init__(self, raw: str) -> None:
        self.citation_raw = raw
        self.source_system = "IAC"
        self.title = "199"
        self.article = "20"
        self.rule = "20.2"
        self.section = 20.2
        self.subsection_path = None
        self.granularity = "rule"


class _Citation:
    def __init__(self, raw: str) -> None:
        self.parsed = _Parsed(raw)
        self.span_start = 0
        self.span_end = 10
        self.in_knowledge_base = True
        self.code_section_id = "IAC-199-20.2"
        self.resolution_status = "resolved"
        self.context = "ctx"


class _Param:
    def __init__(self, value_text: str) -> None:
        self.kind = "duration"
        self.name = "deadline"
        self.value_text = value_text
        self.span_start = 0
        self.span_end = 5
        self.value_num = 30.0
        self.unit = "days"
        self.qualifier = None
        self.day_type = "calendar"
        self.value_source = "regex"
        self.method = "regex"
        self.verified = False


class _Unit:
    """Stand-in for parse.models.ClauseUnit with just the fields neon reads."""

    def __init__(self, version_id: str, local_id: str, n_children: int = 2) -> None:
        self.version_id = version_id
        self.doc_id = DOC
        self.clause_id = f"{DOC}:{local_id}"
        self.local_id = local_id
        self.parent_clause_id = None
        self.ordinal = 1
        self.unit_kind = "clause"
        self.heading_path = ["1", "1.1"]
        self.section_kind = "body"
        self.sheet_no = None
        self.table_id = None
        self.row_cells = None
        self.text_raw = f"text {local_id}"
        self.text_norm = f"text {local_id}"
        self.text_sha256 = "0" * 64
        self.char_start = 0
        self.char_end = 10
        self.line_start = 1
        self.role = "obligation"
        self.role_method = "llm"
        self.assessable = True
        self.normalized_statement = "stmt"
        self.topic_terms = ["a"]
        self.citations = [_Citation(f"199 IAC 20.{i}") for i in range(n_children)]
        self.parameters = [_Param(f"{30 + i} days") for i in range(n_children)]


def _version_fixtures(version_id: str):
    units = [_Unit(version_id, "s1"), _Unit(version_id, "s2")]
    terms = [
        TermEntry(
            term="Customer",
            term_norm="customer",
            definition_clause_id=f"{DOC}:s1",
            cites_regulatory_definition=True,
            doc_id=DOC,
        )
    ]
    usages = [TermUsage(term_norm="customer", clause_id=f"{DOC}:s2", occurrences=3)]
    links = [
        ClauseLink(
            from_clause_id=f"{DOC}:s1",
            to_clause_id=f"{DOC}:s2",
            to_doc_id=None,
            link_type="references_clause",
            method="regex",
            evidence="see s2",
            confidence=1.0,
        )
    ]
    scope = [
        DocumentScopeRow(
            doc_id=DOC,
            version_id=version_id,
            scope_key="IAC-199-20.2",
            scope_level="rule",
            sources=["IAC"],
            clause_count=2,
        )
    ]
    return units, terms, usages, links, scope


class _Source:
    doc_id = DOC
    doc_class = "procedure"


class _Reg:
    doc_id = DOC
    title = "Disconnection Procedure"
    version = "v1"
    owner_id = "p1"
    reviewer_id = "p2"
    approver_id = "p3"
    status = "Approved"
    effective_date = "2026-01-01"
    approved_date = "2025-12-01"
    law_as_of = "2025-12-01"
    regulatory_basis_sections = "199 IAC 20.2"


async def _write_version(session, version_id: str, version_no: int) -> RunContext:
    units, terms, usages, links, scope = _version_fixtures(version_id)
    ctx = RunContext(company_id=COMPANY)
    spec = DocumentVersionSpec(
        version_id=version_id,
        version_no=version_no,
        version=f"v{version_no}.0",
        source_r2_key=f"company/{DOC}/{version_no}/source.docx",
        next_review=date(2027, 1, 1),
        effective_date=date(2026, 1, 1),
        extraction_r2_key=f"company/{DOC}/{version_no}/extract.md",
        extraction_method="docx",
    )
    await commit_run(
        session=session,
        ctx=ctx,
        sources=[_Source()],
        register_entries=[_Reg()],
        units=units,
        links=links,
        scope_rows=scope,
        terms=terms,
        term_usages=usages,
        col_roles_map={DOC: {"colA": "key"}},
        report_r2_key=None,
        version_specs={DOC: spec},
    )
    return ctx


V1 = str(uuid.uuid4())
V2 = str(uuid.uuid4())

_CHILD_TABLES = [
    "company.clauses",
    "company.clause_citations",
    "company.clause_parameters",
    "company.defined_terms",
    "company.term_usages",
    "company.clause_links",
]


@pytest.mark.asyncio
async def test_second_version_children_are_not_discarded():
    """The headline bug: counts must scale with the number of versions."""
    sess = ConflictSession()
    await _write_version(sess, V1, 1)
    after_v1 = {t: sess.count(t) for t in _CHILD_TABLES}
    assert all(v > 0 for v in after_v1.values()), after_v1

    await _write_version(sess, V2, 2)
    for table in _CHILD_TABLES:
        assert sess.count(table) == 2 * after_v1[table], (
            f"{table}: {sess.count(table)} rows after two versions, "
            f"expected {2 * after_v1[table]} — v2 rows were dropped"
        )

    assert sess.count("company.document_versions") == 2
    # One document, not two.
    assert sess.count("company.company_documents") == 1


@pytest.mark.asyncio
async def test_rewriting_the_same_version_is_idempotent():
    sess = ConflictSession()
    await _write_version(sess, V1, 1)
    first = {t: set(sess.tables[t]) for t in _CHILD_TABLES}
    await _write_version(sess, V1, 1)
    for table in _CHILD_TABLES:
        assert set(sess.tables[table]) == first[table], f"{table} keys changed"


@pytest.mark.asyncio
async def test_term_usages_reference_a_real_term_row():
    """_term_pk must be derived identically in both writers."""
    sess = ConflictSession()
    await _write_version(sess, V1, 1)
    await _write_version(sess, V2, 2)
    term_pks = {r["term_pk"] for r in sess.rows("company.defined_terms")}
    usage_pks = {r["term_pk"] for r in sess.rows("company.term_usages")}
    assert usage_pks, "no term_usages written"
    assert usage_pks <= term_pks, usage_pks - term_pks


@pytest.mark.asyncio
async def test_defined_terms_carry_their_version_id():
    sess = ConflictSession()
    await _write_version(sess, V1, 1)
    rows = sess.rows("company.defined_terms")
    assert rows and all(r["version_id"] == V1 for r in rows), rows


@pytest.mark.asyncio
async def test_no_insert_references_a_dropped_column_or_table():
    sess = ConflictSession()
    await _write_version(sess, V1, 1)
    sql = sess.all_sql()
    assert "file_sha256" not in sql
    assert "company.datasets" not in sql
    assert "dataset_columns" not in sql
    assert "parameter_checks" not in sql
    # `supersedes` the dropped version *string*, but not `supersedes_version_id`.
    assert re.search(r"\bsupersedes\b(?!_)", sql) is None
    # company_documents must not claim the new version as current.
    assert "current_version_id" not in sql


@pytest.mark.asyncio
async def test_document_version_row_satisfies_the_new_schema():
    sess = ConflictSession()
    await _write_version(sess, V1, 1)
    row = sess.rows("company.document_versions")[0]
    assert row["version_no"] == 1
    assert row["source_r2_key"] is not None
    assert row["next_review"] == date(2027, 1, 1)
    assert row["status"] == "in_review"
    assert row["status"] in {
        "draft", "in_review", "approved", "effective", "superseded", "retired",
    }
    assert row["extraction_r2_key"] is not None
    # is_current is a literal false in the SQL, never a parameter.
    ddl = next(s for s, _ in sess.sql if "company.document_versions" in s)
    assert "is_current" in ddl and ":is_current" not in ddl
    # A re-ingest must not be able to demote a promoted version.
    update_clause = ddl.split("DO UPDATE SET", 1)[1]
    assert re.search(r"(?<!ingest_)\bstatus\b", update_clause) is None
    assert "is_current" not in update_clause


@pytest.mark.asyncio
async def test_commit_run_requires_version_specs():
    sess = ConflictSession()
    units, terms, usages, links, scope = _version_fixtures(V1)
    with pytest.raises(ValueError, match="version_specs"):
        await commit_run(
            session=sess,
            ctx=RunContext(company_id=COMPANY),
            sources=[_Source()],
            register_entries=[_Reg()],
            units=units,
            links=links,
            scope_rows=scope,
            terms=terms,
            term_usages=usages,
            col_roles_map={},
            report_r2_key=None,
        )


def test_mixing_two_versions_of_one_document_is_rejected():
    """clause_pk_map is keyed by bare clause_id, so this must not be allowed."""
    units = [_Unit(V1, "s1"), _Unit(V2, "s1")]
    with pytest.raises(ValueError, match="two version_ids"):
        neon.build_clause_version_map(units)


def test_child_keys_actually_differ_between_versions():
    """Direct assertion on the key derivation, independent of the fake session."""
    from app.company_ingest.ids import stable_uuid

    cid = f"{DOC}:s1"
    assert stable_uuid(COMPANY, V1, cid, "0", "199 IAC 20.0") != stable_uuid(
        COMPANY, V2, cid, "0", "199 IAC 20.0"
    )
    assert stable_uuid(COMPANY, V1, cid, "0", "30 days") != stable_uuid(
        COMPANY, V2, cid, "0", "30 days"
    )
    assert neon._term_pk(COMPANY, V1, "customer") != neon._term_pk(
        COMPANY, V2, "customer"
    )
    assert stable_uuid(COMPANY, V1, cid, f"{DOC}:s2", "references_clause") != stable_uuid(
        COMPANY, V2, cid, f"{DOC}:s2", "references_clause"
    )

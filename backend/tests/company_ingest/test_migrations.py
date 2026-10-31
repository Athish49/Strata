"""
Migration content tests. Static — these parse the migration files as text/AST
and never open a database connection.

Two groups:
  * the original `c3d4e5f6a7b8` company-schema assertions (v1 baseline);
  * the `f7b2c91d4a08` v2 document-versioning assertions (TDD §1.0-§1.6, §6.3).
"""
import ast
import pathlib

import pytest

VERSIONS_DIR = (
    pathlib.Path(__file__).parent.parent.parent / "migrations" / "versions"
)

MIGRATION_PATH = VERSIONS_DIR / "c3d4e5f6a7b8_company_schema.py"
V2_MIGRATION_PATH = VERSIONS_DIR / "f7b2c91d4a08_v2_document_versioning.py"

V2_REVISION = "f7b2c91d4a08"
V2_DOWN_REVISION = "e5a1c7d9b304"

EXPECTED_TABLES = [
    "companies",
    "company_attributes",
    "people",
    "company_documents",
    "document_versions",
    "clauses",
    "clause_citations",
    "clause_parameters",
    "defined_terms",
    "term_usages",
    "clause_links",
    "document_scope",
    "table_columns",
    "datasets",
    "dataset_columns",
    "parameter_checks",
    "llm_extractions",
    "ingest_runs",
]

# TDD §1.5 + §6.3 — tables created by the v2 migration.
V2_NEW_TABLES = [
    "departments",
    "document_role_assignments",
    "approval_policies",
    "approval_policy_steps",
    "approval_requests",
    "approval_steps",
    "ingest_jobs",
]

# TDD §1.6 — dropped. `table_columns` is deliberately NOT in this list.
V2_DROPPED_TABLES = ["parameter_checks", "datasets", "dataset_columns"]

# TDD §1.1/§1.2/§1.4/§1.5/§6.3 — every named index the v2 migration creates.
V2_INDEXES = [
    "company_documents_content_hash_uq",
    "document_versions_no_uq",
    "document_versions_current_uq",
    "document_versions_doc_idx",
    "llm_extractions_cache_uq",
    "approval_requests_open_uq",
    "ingest_jobs_state_idx",
]

V2_NEW_COLUMNS = {
    "company.company_documents": [
        "current_content_hash",
        "doc_number",
        "lifecycle_state",
        "created_at",
        "updated_at",
    ],
    "company.document_versions": [
        "version_no",
        "is_current",
        "superseded_by",
        "supersedes_version_id",
        "created_at",
        "created_by_person_id",
        "change_reason",
        "extraction_r2_key",
        "extraction_method",
        # Task 3.2: hash of an in-flight version, read by promote_version.
        "pending_content_hash",
    ],
    # No `output` column: the cache payload reuses the existing `response jsonb`
    # rather than adding a second result column beside it.
    "company.llm_extractions": ["company_id", "content_sha256"],
    "company.people": ["department_id", "is_active"],
}


def _function_source(path: pathlib.Path, name: str) -> str:
    source = path.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            lines = source.splitlines()
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"{name}() function not found in {path.name}")


def _get_upgrade_source() -> str:
    return _function_source(MIGRATION_PATH, "upgrade")


def _v2_upgrade() -> str:
    return _function_source(V2_MIGRATION_PATH, "upgrade")


def _v2_downgrade() -> str:
    return _function_source(V2_MIGRATION_PATH, "downgrade")


def _sql_statements(path: pathlib.Path, func: str) -> list[str]:
    """The SQL string literals passed to op.execute() inside `func`.

    Works from the AST, so Python comments and docstrings cannot influence any
    assertion made against the result.
    """
    tree = ast.parse(path.read_text())
    target = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func:
            target = node
            break
    assert target is not None, f"{func}() not found in {path.name}"

    stmts: list[str] = []
    for node in ast.walk(target):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "execute"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            stmts.append(node.args[0].value)
    return stmts


def _v2_upgrade_sql() -> list[str]:
    return _sql_statements(V2_MIGRATION_PATH, "upgrade")


def _v2_downgrade_sql() -> list[str]:
    return _sql_statements(V2_MIGRATION_PATH, "downgrade")


# ---------------------------------------------------------------------------
# c3d4e5f6a7b8 — company schema baseline
# ---------------------------------------------------------------------------


def test_migration_file_exists():
    assert MIGRATION_PATH.exists(), f"Migration file not found: {MIGRATION_PATH}"


def test_migration_is_valid_python():
    ast.parse(MIGRATION_PATH.read_text())


def test_migration_revision_metadata():
    source = MIGRATION_PATH.read_text()
    assert "revision: str = 'c3d4e5f6a7b8'" in source
    assert "down_revision" in source
    assert "b1c2d3e4f5a6" in source


def test_upgrade_creates_company_schema():
    assert "CREATE SCHEMA IF NOT EXISTS company" in _get_upgrade_source()


def test_upgrade_contains_all_expected_tables():
    upgrade_src = _get_upgrade_source()
    missing = [
        f"company.{t}" for t in EXPECTED_TABLES if f"company.{t}" not in upgrade_src
    ]
    assert not missing, f"Tables missing from upgrade(): {missing}"


def test_downgrade_drops_schema():
    assert "DROP SCHEMA IF EXISTS company CASCADE" in _function_source(
        MIGRATION_PATH, "downgrade"
    )


def test_upgrade_contains_indexes():
    upgrade_src = _get_upgrade_source()
    expected_indexes = [
        "company.clauses (doc_id)",
        "company.clauses (clause_id)",
        "company.clause_citations (code_section_id)",
        "company.clause_citations (clause_pk)",
        "company.clause_parameters (clause_pk)",
        "company.clause_links (from_clause_pk)",
        "company.clause_links (to_clause_pk)",
        "company.document_scope (scope_key)",
    ]
    missing = [idx for idx in expected_indexes if idx not in upgrade_src]
    assert not missing, f"Indexes missing from upgrade(): {missing}"


# ---------------------------------------------------------------------------
# f7b2c91d4a08 — v2 document versioning
# ---------------------------------------------------------------------------


def test_v2_migration_file_exists():
    assert V2_MIGRATION_PATH.exists(), f"Migration not found: {V2_MIGRATION_PATH}"


def test_v2_migration_is_valid_python():
    ast.parse(V2_MIGRATION_PATH.read_text())


def test_v2_revision_metadata():
    source = V2_MIGRATION_PATH.read_text()
    assert f"revision: str = '{V2_REVISION}'" in source
    assert f"down_revision: Union[str, None] = '{V2_DOWN_REVISION}'" in source


def test_v2_is_the_single_head():
    """Exactly one Alembic head, and it is the v2 migration."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    ini = pathlib.Path(__file__).parent.parent.parent / "alembic.ini"
    cfg = Config(str(ini))
    # alembic.ini carries a relative script_location; make it cwd-independent.
    cfg.set_main_option("script_location", str(VERSIONS_DIR.parent))
    script = ScriptDirectory.from_config(cfg)
    heads = list(script.get_heads())
    assert len(heads) == 1, f"Expected exactly one Alembic head, got {heads}"
    # ... and the v2 migration must be reachable from it.
    assert V2_REVISION in {r.revision for r in script.walk_revisions("base", heads[0])}


def test_v2_truncates_before_altering():
    """TDD §1.0 — the TRUNCATE must come first, or the ALTERs fail on live rows."""
    stmts = _v2_upgrade_sql()
    first_truncate = next(
        i for i, s in enumerate(stmts) if s.upper().lstrip().startswith("TRUNCATE")
    )
    first_other = next(
        i
        for i, s in enumerate(stmts)
        if not s.upper().lstrip().startswith("TRUNCATE")
    )
    assert first_truncate < first_other, (
        "the TRUNCATE preamble must be the first statement(s) of upgrade()"
    )

    upgrade_src = " ".join(stmts)
    for table in [
        "company.clauses",
        "company.clause_citations",
        "company.clause_parameters",
        "company.clause_links",
        "company.defined_terms",
        "company.term_usages",
        "company.document_scope",
        "company.document_versions",
        "company.company_documents",
        "company.table_columns",
        "company.llm_extractions",
        "company.ingest_runs",
        "engine.runs",
        "engine.findings",
        "engine.finding_reviews",
        "engine.doc_rollups",
        "engine.score_reports",
    ]:
        assert table in upgrade_src, f"{table} missing from the truncation preamble"


def test_v2_never_truncates_code_sections():
    """The regulatory KB is real, externally-sourced data and can never be wiped."""
    for func in ("upgrade", "downgrade"):
        for stmt in _sql_statements(V2_MIGRATION_PATH, func):
            upper = stmt.upper()
            if any(
                kw in upper for kw in ("TRUNCATE", "DROP TABLE", "DELETE FROM", "UPDATE ")
            ):
                assert "CODE_SECTIONS" not in upper, (
                    f"public.code_sections appears in a destructive {func}() "
                    f"statement: {stmt[:200]}"
                )


def test_v2_preserves_org_identity_tables():
    """companies / company_attributes / people keep their rows (TDD §1.0)."""
    truncates = " ".join(
        s for s in _v2_upgrade_sql() if s.upper().lstrip().startswith("TRUNCATE")
    )
    for table in ("company.companies", "company.company_attributes", "company.people"):
        assert table not in truncates, f"{table} must not be truncated"


def test_v2_creates_new_tables():
    upgrade_src = _v2_upgrade()
    missing = [
        t for t in V2_NEW_TABLES if f"CREATE TABLE company.{t}" not in upgrade_src
    ]
    assert not missing, f"Tables missing from v2 upgrade(): {missing}"


def test_v2_adds_new_columns():
    upgrade_src = _v2_upgrade()
    missing = []
    for table, columns in V2_NEW_COLUMNS.items():
        block_start = upgrade_src.index(f"ALTER TABLE {table}\n")
        block = upgrade_src[block_start : block_start + 1200]
        for col in columns:
            if f"ADD COLUMN {col}" not in block:
                missing.append(f"{table}.{col}")
    assert not missing, f"Columns missing from v2 upgrade(): {missing}"


def test_v2_drops_file_sha256():
    """TDD §1.2 — one hash per document, held on company_documents."""
    assert "DROP COLUMN file_sha256" in _v2_upgrade()
    # and the downgrade must put it back
    assert "ADD COLUMN file_sha256 text" in _v2_downgrade()


def test_v2_pending_content_hash_is_nullable_char64():
    """Task 3.2 — the pending hash of an in-flight version (TDD §1.2, §6, §7.2).

    Nullable by design: it is cleared at promotion and on supersession, so the
    only durable hash stays company_documents.current_content_hash.
    """
    stmt = next(s for s in _v2_upgrade_sql() if "pending_content_hash" in s)
    line = next(ln for ln in stmt.splitlines() if "pending_content_hash" in ln)
    assert " ".join(line.split()).rstrip(",") == "ADD COLUMN pending_content_hash char(64)"
    assert "ALTER TABLE company.document_versions" in stmt
    for s in _v2_upgrade_sql():
        assert not ("pending_content_hash" in s and "NOT NULL" in s.split("pending_content_hash")[1].split("\n")[0])
    assert "DROP COLUMN pending_content_hash" in " ".join(_v2_downgrade_sql())


def test_v2_ingest_jobs_has_register_spec():
    """Task 3.2 — a failed register-CSV upload must be retryable from the job row."""
    create = next(s for s in _v2_upgrade_sql() if "CREATE TABLE company.ingest_jobs" in s)
    assert "register_spec jsonb," in " ".join(create.split())
    # ...and the downgrade removes it with the table.
    assert "DROP TABLE company.ingest_jobs" in _v2_downgrade_sql()


def test_v2_version_no_is_not_null():
    upgrade_src = _v2_upgrade()
    assert "ALTER COLUMN version_no SET NOT NULL" in upgrade_src


def test_v2_status_check_constraint():
    upgrade_src = _v2_upgrade()
    assert "document_versions_status_ck" in upgrade_src
    for state in (
        "draft",
        "in_review",
        "approved",
        "effective",
        "superseded",
        "retired",
    ):
        assert f"'{state}'" in upgrade_src, f"status {state!r} missing from CHECK"
    # The legacy value must NOT be allowed — this is why the TRUNCATE exists.
    ck_start = upgrade_src.index("document_versions_status_ck")
    ck = upgrade_src[ck_start : ck_start + 300]
    assert "'Approved'" not in ck


def test_v2_creates_named_indexes():
    upgrade_src = _v2_upgrade()
    missing = [ix for ix in V2_INDEXES if ix not in upgrade_src]
    assert not missing, f"Indexes missing from v2 upgrade(): {missing}"


def test_v2_partial_unique_indexes_have_predicates():
    """Both partial unique indexes are correctness mechanisms, not optimizations."""
    expected = {
        "company_documents_content_hash_uq": [
            "(company_id, current_content_hash)",
            "WHERE current_content_hash IS NOT NULL",
        ],
        "document_versions_current_uq": ["(company_id, doc_id)", "WHERE is_current"],
        "approval_requests_open_uq": ["(version_id)", "WHERE state = 'open'"],
    }
    by_name = {}
    for stmt in _v2_upgrade_sql():
        for name in expected:
            if name in stmt:
                by_name[name] = stmt
    assert set(by_name) == set(expected), f"missing index DDL: {set(expected) - set(by_name)}"
    for name, fragments in expected.items():
        stmt = " ".join(by_name[name].split())
        assert "CREATE UNIQUE INDEX" in stmt, f"{name} must be UNIQUE"
        for fragment in fragments:
            assert fragment in stmt, f"{name} missing {fragment!r}"


def test_v2_llm_extractions_cache_key():
    upgrade_src = _v2_upgrade()
    ix = upgrade_src[upgrade_src.index("llm_extractions_cache_uq") :][:400]
    for col in ("company_id", "stage", "content_sha256", "prompt_sha256", "model"):
        assert col in ix, f"{col} missing from the llm_extractions cache key"


def test_v2_adds_version_id_to_findings():
    assert "ALTER TABLE engine.findings ADD COLUMN version_id uuid" in _v2_upgrade()
    assert "ALTER TABLE engine.findings DROP COLUMN version_id" in _v2_downgrade()


def test_v2_drops_the_three_dead_tables():
    upgrade_src = _v2_upgrade()
    for table in V2_DROPPED_TABLES:
        assert f"DROP TABLE company.{table}" in upgrade_src, f"{table} not dropped"


def test_v2_keeps_table_columns():
    """TDD §1.6 — company.table_columns belongs to the register path and stays."""
    upgrade_src = _v2_upgrade()
    assert "DROP TABLE company.table_columns" not in upgrade_src


def test_v2_downgrade_recreates_dropped_tables():
    downgrade_src = _v2_downgrade()
    missing = [
        t
        for t in V2_DROPPED_TABLES
        if f"CREATE TABLE company.{t}" not in downgrade_src
    ]
    assert not missing, f"Tables not recreated by downgrade(): {missing}"


def test_v2_downgrade_drops_everything_it_added():
    downgrade_src = _v2_downgrade()
    missing_tables = [
        t for t in V2_NEW_TABLES if f"DROP TABLE company.{t}" not in downgrade_src
    ]
    assert not missing_tables, f"Tables not dropped by downgrade(): {missing_tables}"

    missing_cols = []
    for table, columns in V2_NEW_COLUMNS.items():
        for col in columns:
            if f"DROP COLUMN {col}" not in downgrade_src:
                missing_cols.append(f"{table}.{col}")
    assert not missing_cols, f"Columns not dropped by downgrade(): {missing_cols}"

    missing_ix = [
        ix
        for ix in V2_INDEXES
        if ix not in downgrade_src
    ]
    # Indexes attached to dropped tables disappear with the table.
    table_owned = {"approval_requests_open_uq", "ingest_jobs_state_idx"}
    missing_ix = [ix for ix in missing_ix if ix not in table_owned]
    assert not missing_ix, f"Indexes not dropped by downgrade(): {missing_ix}"

    assert "DROP CONSTRAINT document_versions_status_ck" in downgrade_src


def test_v2_downgrade_does_not_restore_data():
    """A downgrade restores structure only — it must never truncate anything."""
    for stmt in _v2_downgrade_sql():
        assert "TRUNCATE" not in stmt.upper()
    assert "NOT restored" in (_v2_downgrade().splitlines()[1])


# ---------------------------------------------------------------------------
# v2 destructive-upgrade guard
# ---------------------------------------------------------------------------


def _load_v2_module():
    """Import the v2 migration file directly (it is not an importable package)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location("_v2_mig", V2_MIGRATION_PATH)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_v2_upgrade_is_guarded_by_opt_in(monkeypatch):
    """upgrade() must refuse to truncate unless the operator opts in.

    render.yaml runs `alembic upgrade head` before the app starts, so merely
    pushing this migration to the deployed branch would otherwise wipe
    production on the next deploy. Failing loudly turns that accident into a
    failed deploy, which is recoverable; a truncate is not.
    """
    mod = _load_v2_module()
    monkeypatch.setattr(mod, "context_is_offline", lambda: False)

    monkeypatch.delenv(mod._WIPE_ENV_VAR, raising=False)
    with pytest.raises(RuntimeError, match="Refusing to run migration"):
        mod._require_wipe_opt_in()

    monkeypatch.setenv(mod._WIPE_ENV_VAR, "not-the-token")
    with pytest.raises(RuntimeError):
        mod._require_wipe_opt_in()

    monkeypatch.setenv(mod._WIPE_ENV_VAR, mod._WIPE_TOKEN)
    mod._require_wipe_opt_in()  # must not raise


def test_v2_offline_sql_generation_is_exempt(monkeypatch):
    """`alembic upgrade --sql` executes nothing, so it needs no opt-in."""
    mod = _load_v2_module()
    monkeypatch.setattr(mod, "context_is_offline", lambda: True)
    monkeypatch.delenv(mod._WIPE_ENV_VAR, raising=False)
    mod._require_wipe_opt_in()  # must not raise


def test_v2_upgrade_calls_the_guard_first():
    """The guard must be the first statement of upgrade(), before any TRUNCATE."""
    src = _v2_upgrade()
    guard_at = src.find("_require_wipe_opt_in()")
    truncate_at = src.upper().find("TRUNCATE")
    assert guard_at != -1, "upgrade() does not call _require_wipe_opt_in()"
    assert truncate_at != -1, "upgrade() no longer truncates - update this test"
    assert guard_at < truncate_at, "guard must run before the first TRUNCATE"

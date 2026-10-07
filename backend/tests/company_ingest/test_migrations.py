"""
Test 1.2.1: Verify the company schema migration file contains all expected tables.
This is a syntax/content test — no DB connection required.
"""
import ast
import pathlib

MIGRATION_PATH = (
    pathlib.Path(__file__).parent.parent.parent
    / "migrations"
    / "versions"
    / "c3d4e5f6a7b8_company_schema.py"
)

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


def _get_upgrade_source() -> str:
    """Parse the migration file and extract the upgrade() function source."""
    source = MIGRATION_PATH.read_text()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "upgrade":
            # Extract raw lines of the upgrade function
            lines = source.splitlines()
            start = node.lineno - 1
            end = node.end_lineno
            return "\n".join(lines[start:end])
    raise AssertionError("upgrade() function not found in migration file")


def test_migration_file_exists():
    assert MIGRATION_PATH.exists(), f"Migration file not found: {MIGRATION_PATH}"


def test_migration_is_valid_python():
    source = MIGRATION_PATH.read_text()
    # Will raise SyntaxError if invalid
    ast.parse(source)


def test_migration_revision_metadata():
    source = MIGRATION_PATH.read_text()
    assert "revision: str = 'c3d4e5f6a7b8'" in source
    assert "down_revision" in source
    assert "b1c2d3e4f5a6" in source


def test_upgrade_creates_company_schema():
    upgrade_src = _get_upgrade_source()
    assert "CREATE SCHEMA IF NOT EXISTS company" in upgrade_src


def test_upgrade_contains_all_expected_tables():
    upgrade_src = _get_upgrade_source()
    missing = []
    for table in EXPECTED_TABLES:
        qualified = f"company.{table}"
        if qualified not in upgrade_src:
            missing.append(qualified)
    assert not missing, f"Tables missing from upgrade(): {missing}"


def test_downgrade_drops_schema():
    source = MIGRATION_PATH.read_text()
    tree = ast.parse(source)
    downgrade_src = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "downgrade":
            lines = source.splitlines()
            start = node.lineno - 1
            end = node.end_lineno
            downgrade_src = "\n".join(lines[start:end])
            break
    assert downgrade_src is not None, "downgrade() function not found"
    assert "DROP SCHEMA IF EXISTS company CASCADE" in downgrade_src


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

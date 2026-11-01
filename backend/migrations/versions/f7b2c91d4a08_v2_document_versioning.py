"""v2 document versioning, hashing, org and approvals

Implements TDD.md section 1 (1.0 - 1.6) plus section 6.3 (company.ingest_jobs).

WARNING — destructive upgrade. The first statement of upgrade() TRUNCATEs the
company.* document/clause tables and the engine.* run tables. This is required,
not optional: render.yaml runs `alembic upgrade head` *before* the app starts,
against populated tables, and two statements below cannot succeed on existing
rows:

  * `document_versions ADD COLUMN version_no int NOT NULL` has no default, so
    existing rows would have no value.
  * `document_versions_status_ck` rejects 'Approved', which is exactly what the
    existing rows hold.

Cutover is an approved wipe, so the migration truncates first.

`public.code_sections` is NEVER truncated — it holds real, externally-sourced
regulatory data (4,603 rows) that cannot be regenerated. No table in `public`
has a foreign key into `company.*` or `engine.*`, so the CASCADE below cannot
reach it.

downgrade() restores the *structure* only. Truncated rows are not restored.

Revision ID: f7b2c91d4a08
Revises: e5a1c7d9b304
Create Date: 2026-10-30 00:00:00.000000
"""
import os
from typing import Sequence, Union

from alembic import op

revision: str = 'f7b2c91d4a08'
down_revision: Union[str, None] = 'e5a1c7d9b304'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Opt-in token required to run the destructive upgrade. See _require_wipe_opt_in.
_WIPE_ENV_VAR = "STRATA_ALLOW_V2_WIPE"
_WIPE_TOKEN = "yes-destroy-company-and-engine-data"


def _require_wipe_opt_in() -> None:
    """Refuse to run unless the operator has explicitly opted in to the wipe.

    render.yaml runs `alembic upgrade head` before the app starts, so merely
    pushing this file to the deployed branch would otherwise truncate
    production on the next deploy — no command, no confirmation, no warning.

    Failing here makes that accident a *failed deploy* instead of silent data
    loss. A failed deploy is recoverable in minutes; a truncate is not.

    To run the cutover deliberately (see implementation_plan.md task 9.2):

        STRATA_ALLOW_V2_WIPE=yes-destroy-company-and-engine-data alembic upgrade head

    Offline SQL generation (`--sql`) does not execute anything, so it is
    allowed without the token.
    """
    if context_is_offline():
        return
    if os.environ.get(_WIPE_ENV_VAR) == _WIPE_TOKEN:
        return
    raise RuntimeError(
        "Refusing to run migration f7b2c91d4a08: it TRUNCATEs company.* and "
        "engine.* and would destroy data.\n"
        f"Set {_WIPE_ENV_VAR}={_WIPE_TOKEN} to proceed deliberately.\n"
        "Before doing so, confirm the pre-wipe baseline exists: "
        "backend/synthetic/baseline_before_v2.json (implementation_plan.md task 0.1)."
    )


def context_is_offline() -> bool:
    """True when alembic is only emitting SQL (`--sql`), not executing it."""
    from alembic import context

    try:
        return context.is_offline_mode()
    except Exception:  # pragma: no cover - context always available under alembic
        return False


def upgrade() -> None:
    _require_wipe_opt_in()
    # ------------------------------------------------------------------
    # 1.0 Migration preamble — truncate first, or the ALTERs below fail.
    # company.companies, company.company_attributes and company.people are
    # deliberately preserved (re-seeded via the org endpoints, but harmless
    # to keep).  public.code_sections is NEVER touched.
    # ------------------------------------------------------------------
    op.execute("""
        TRUNCATE company.clauses, company.clause_citations, company.clause_parameters,
                 company.clause_links, company.defined_terms, company.term_usages,
                 company.document_scope, company.document_versions,
                 company.company_documents, company.table_columns,
                 company.llm_extractions, company.ingest_runs CASCADE
    """)
    # The engine.* dependent list is taken from e5a1c7d9b304_engine_schema.py.
    # engine.change_records, engine.candidates and engine.radar_items are named
    # explicitly even though they carry ON DELETE CASCADE foreign keys into
    # engine.runs and would be swept implicitly — the statement should say what
    # it does.  engine.llm_calls (a prompt-hash cache) and
    # engine.whatif_scenarios (presets) have no foreign keys and are preserved.
    op.execute("""
        TRUNCATE engine.runs, engine.change_records, engine.candidates,
                 engine.findings, engine.finding_reviews, engine.radar_items,
                 engine.doc_rollups, engine.score_reports CASCADE
    """)
    # engine.whatif_scenarios is preserved (presets are hand-curated), but it
    # has no foreign key to engine.runs, so the truncate above leaves
    # last_run_id pointing at runs that no longer exist. app/engine/whatif.py
    # LEFT JOINs it to engine.runs and api/engine/routes_ui_runs.py filters on
    # it, so a stale pointer surfaces as a scenario with a phantom last run.
    op.execute("UPDATE engine.whatif_scenarios SET last_run_id = NULL")

    # ------------------------------------------------------------------
    # 1.1 company.company_documents
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE company.company_documents
          ADD COLUMN current_content_hash char(64),
          ADD COLUMN doc_number           text,
          ADD COLUMN lifecycle_state      text NOT NULL DEFAULT 'active',
          ADD COLUMN created_at           timestamptz NOT NULL DEFAULT now(),
          ADD COLUMN updated_at           timestamptz NOT NULL DEFAULT now()
    """)
    # Load-bearing: two concurrent identical uploads both pass a SELECT, so the
    # insert must rely on this index and convert UniqueViolation to a 409.
    op.execute("""
        CREATE UNIQUE INDEX company_documents_content_hash_uq
          ON company.company_documents (company_id, current_content_hash)
          WHERE current_content_hash IS NOT NULL
    """)

    # ------------------------------------------------------------------
    # 1.2 company.document_versions
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE company.document_versions
          ADD COLUMN version_no            int,
          ADD COLUMN is_current            boolean NOT NULL DEFAULT false,
          ADD COLUMN superseded_by         uuid,
          ADD COLUMN supersedes_version_id uuid,
          ADD COLUMN created_at            timestamptz NOT NULL DEFAULT now(),
          ADD COLUMN created_by_person_id  text,
          ADD COLUMN change_reason         text,
          ADD COLUMN extraction_r2_key     text,
          ADD COLUMN extraction_method     text,
          ADD COLUMN pending_content_hash  char(64),
          DROP COLUMN file_sha256,
          DROP COLUMN supersedes
    """)
    # `supersedes text` held a version *string* and is replaced by
    # `supersedes_version_id uuid`. Keeping both would leave two columns meaning
    # the same thing — a trap for the writer. Its only writer was
    # collect/register_docs.py (deleted by task 2.3) and it has no readers.
    # Note `version text` is deliberately KEPT: it is the customer-facing
    # version label ("v5.1"), which is genuinely distinct from the
    # system-assigned sequential `version_no int`.
    # Only one *durable* hash per document, and it lives on company_documents —
    # hence the DROP of file_sha256 above.  `pending_content_hash` is the hash of
    # an in-flight version (set at upload, task 6.1/6.2) so promotion (TDD §6
    # step 2) and the "unchanged" check (TDD §7.2) can read it.  It is cleared to
    # NULL when the version is promoted (the hash moves to
    # company_documents.current_content_hash) and when a version is superseded,
    # so it never outlives the version being pending.
    op.execute(
        "ALTER TABLE company.document_versions ALTER COLUMN version_no SET NOT NULL"
    )
    op.execute("""
        ALTER TABLE company.document_versions
          ADD CONSTRAINT document_versions_status_ck
          CHECK (status IN ('draft','in_review','approved','effective','superseded','retired'))
    """)
    op.execute("""
        CREATE UNIQUE INDEX document_versions_no_uq
          ON company.document_versions (company_id, doc_id, version_no)
    """)
    # Load-bearing: at most one current version per document, enforced by the DB.
    op.execute("""
        CREATE UNIQUE INDEX document_versions_current_uq
          ON company.document_versions (company_id, doc_id) WHERE is_current
    """)
    op.execute("""
        CREATE INDEX document_versions_doc_idx
          ON company.document_versions (company_id, doc_id)
    """)

    # ------------------------------------------------------------------
    # 1.4 company.llm_extractions — becomes a real read-through cache
    # ------------------------------------------------------------------
    # The cache payload reuses the EXISTING `response jsonb` column rather than
    # adding `output jsonb` beside it. Two result columns on one row is a trap:
    # a reader cannot tell which holds the cached value.
    op.execute("""
        ALTER TABLE company.llm_extractions
          ADD COLUMN company_id     text,
          ADD COLUMN content_sha256 char(64)
    """)
    # Every column of the cache key must be NOT NULL. Postgres treats NULLs as
    # DISTINCT in a unique index, so a nullable key column would let unlimited
    # duplicate rows through and the read-through cache would silently miss on
    # every lookup — turning the LLM-reuse feature into a no-op while appearing
    # to work. The table is truncated above (and had 0 rows), so this is free.
    op.execute("""
        ALTER TABLE company.llm_extractions
          ALTER COLUMN company_id     SET NOT NULL,
          ALTER COLUMN content_sha256 SET NOT NULL,
          ALTER COLUMN stage          SET NOT NULL,
          ALTER COLUMN prompt_sha256  SET NOT NULL,
          ALTER COLUMN model          SET NOT NULL
    """)
    op.execute("""
        CREATE UNIQUE INDEX llm_extractions_cache_uq
          ON company.llm_extractions (company_id, stage, content_sha256,
                                      prompt_sha256, model)
    """)

    # ------------------------------------------------------------------
    # 1.5 Org and approval tables (all new, additive)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE company.departments (
            company_id text NOT NULL,
            department_id text NOT NULL,
            name text NOT NULL,
            parent_department_id text,
            PRIMARY KEY (company_id, department_id)
        )
    """)

    op.execute("""
        ALTER TABLE company.people
          ADD COLUMN department_id text,
          ADD COLUMN is_active boolean NOT NULL DEFAULT true
    """)

    op.execute("""
        CREATE TABLE company.document_role_assignments (
            company_id text NOT NULL,
            doc_id text NOT NULL,
            person_id text NOT NULL,
            role text NOT NULL CHECK (role IN ('owner','reviewer','approver')),
            assigned_at timestamptz NOT NULL DEFAULT now(),
            PRIMARY KEY (company_id, doc_id, person_id, role)
        )
    """)

    op.execute("""
        CREATE TABLE company.approval_policies (
            company_id text NOT NULL,
            policy_id uuid PRIMARY KEY,
            name text NOT NULL,
            applies_to_vertical text,
            applies_to_doc_class text
        )
    """)

    op.execute("""
        CREATE TABLE company.approval_policy_steps (
            policy_id uuid NOT NULL,
            step_no int NOT NULL,
            required_role text NOT NULL CHECK (required_role IN ('owner','reviewer','approver')),
            min_approvals int NOT NULL DEFAULT 1,
            PRIMARY KEY (policy_id, step_no)
        )
    """)

    op.execute("""
        CREATE TABLE company.approval_requests (
            request_id uuid PRIMARY KEY,
            company_id text NOT NULL,
            version_id uuid NOT NULL,
            policy_id uuid,
            state text NOT NULL CHECK (state IN ('open','approved','rejected','cancelled')),
            created_at timestamptz NOT NULL DEFAULT now(),
            completed_at timestamptz
        )
    """)
    op.execute("""
        CREATE UNIQUE INDEX approval_requests_open_uq
          ON company.approval_requests (version_id) WHERE state = 'open'
    """)

    op.execute("""
        CREATE TABLE company.approval_steps (
            request_id uuid NOT NULL,
            step_no int NOT NULL,
            required_role text NOT NULL,
            assignee_person_id text,
            decision text CHECK (decision IN ('approved','rejected')),
            decided_at timestamptz,
            note text,
            PRIMARY KEY (request_id, step_no)
        )
    """)

    # ------------------------------------------------------------------
    # 6.3 company.ingest_jobs
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE company.ingest_jobs (
            job_id uuid PRIMARY KEY,
            company_id text NOT NULL,
            doc_id text NOT NULL,
            version_id uuid NOT NULL,
            state text NOT NULL CHECK (state IN ('queued','running','succeeded','failed')),
            error text,
            stats jsonb,
            register_spec jsonb,
            created_at timestamptz NOT NULL DEFAULT now(),
            started_at timestamptz,
            finished_at timestamptz
        )
    """)
    # register_spec: the declared RegisterSpec (TDD §3.3) of a register-CSV
    # upload, NULL for documents.  Written by jobs.create_job and read by
    # jobs.prepare_retry — the raw CSV bytes alone cannot be re-ingested.
    op.execute("""
        CREATE INDEX ingest_jobs_state_idx
          ON company.ingest_jobs (state, created_at)
    """)

    # ------------------------------------------------------------------
    # 1.3 Pin a finding to the version it was computed against
    # ------------------------------------------------------------------
    op.execute("ALTER TABLE engine.findings ADD COLUMN version_id uuid")

    # ------------------------------------------------------------------
    # 1.6 Dropped — verified 0 rows each in production.
    # company.table_columns is KEPT (it belongs to the register path).
    # ------------------------------------------------------------------
    op.execute("DROP TABLE company.parameter_checks")
    op.execute("DROP TABLE company.dataset_columns")
    op.execute("DROP TABLE company.datasets")


def downgrade() -> None:
    """Restore the pre-v2 structure.  Rows truncated by upgrade() are NOT restored."""
    # 1.6 reverse — DDL copied verbatim from c3d4e5f6a7b8_company_schema.py
    op.execute("""
        CREATE TABLE company.datasets (
            dataset_pk uuid PRIMARY KEY,
            company_id text,
            doc_id text,
            name text,
            r2_parquet_key text,
            r2_source_key text,
            file_sha256 text,
            row_count bigint,
            primary_key text[],
            description text
        )
    """)
    op.execute("""
        CREATE TABLE company.dataset_columns (
            dataset_pk uuid,
            column_name text,
            dtype text,
            null_rate numeric,
            distinct_count bigint,
            min_value text,
            max_value text,
            top_values jsonb,
            semantic_role text,
            fk_target text,
            description text,
            PRIMARY KEY (dataset_pk, column_name)
        )
    """)
    op.execute("""
        CREATE TABLE company.parameter_checks (
            check_pk uuid PRIMARY KEY,
            company_id text,
            parameter_pk uuid,
            dataset_pk uuid,
            purpose text,
            sql_template text,
            param_bindings jsonb,
            s1_result jsonb,
            validated boolean,
            method text
        )
    """)

    # 1.3 reverse
    op.execute("ALTER TABLE engine.findings DROP COLUMN version_id")

    # 6.3 reverse (register_spec goes with the table)
    op.execute("DROP INDEX company.ingest_jobs_state_idx")
    op.execute("DROP TABLE company.ingest_jobs")

    # 1.5 reverse
    op.execute("DROP TABLE company.approval_steps")
    op.execute("DROP INDEX company.approval_requests_open_uq")
    op.execute("DROP TABLE company.approval_requests")
    op.execute("DROP TABLE company.approval_policy_steps")
    op.execute("DROP TABLE company.approval_policies")
    op.execute("DROP TABLE company.document_role_assignments")
    op.execute("""
        ALTER TABLE company.people
          DROP COLUMN is_active,
          DROP COLUMN department_id
    """)
    op.execute("DROP TABLE company.departments")

    # 1.4 reverse
    op.execute("DROP INDEX company.llm_extractions_cache_uq")
    # Restore the pre-v2 nullability of the columns that already existed.
    op.execute("""
        ALTER TABLE company.llm_extractions
          ALTER COLUMN stage         DROP NOT NULL,
          ALTER COLUMN prompt_sha256 DROP NOT NULL,
          ALTER COLUMN model         DROP NOT NULL
    """)
    op.execute("""
        ALTER TABLE company.llm_extractions
          DROP COLUMN content_sha256,
          DROP COLUMN company_id
    """)

    # 1.2 reverse
    op.execute("DROP INDEX company.document_versions_doc_idx")
    op.execute("DROP INDEX company.document_versions_current_uq")
    op.execute("DROP INDEX company.document_versions_no_uq")
    op.execute("""
        ALTER TABLE company.document_versions
          DROP CONSTRAINT document_versions_status_ck
    """)
    op.execute("""
        ALTER TABLE company.document_versions
          ADD COLUMN supersedes text,
          ADD COLUMN file_sha256 text,
          DROP COLUMN pending_content_hash,
          DROP COLUMN extraction_method,
          DROP COLUMN extraction_r2_key,
          DROP COLUMN change_reason,
          DROP COLUMN created_by_person_id,
          DROP COLUMN created_at,
          DROP COLUMN supersedes_version_id,
          DROP COLUMN superseded_by,
          DROP COLUMN is_current,
          DROP COLUMN version_no
    """)

    # 1.1 reverse
    op.execute("DROP INDEX company.company_documents_content_hash_uq")
    op.execute("""
        ALTER TABLE company.company_documents
          DROP COLUMN updated_at,
          DROP COLUMN created_at,
          DROP COLUMN lifecycle_state,
          DROP COLUMN doc_number,
          DROP COLUMN current_content_hash
    """)

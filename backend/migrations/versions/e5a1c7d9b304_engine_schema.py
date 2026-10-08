"""engine schema

Revision ID: e5a1c7d9b304
Revises: 34ff74b6868a
Create Date: 2026-10-07 16:00:00.000000
"""
from typing import Sequence, Union
from alembic import op

revision: str = 'e5a1c7d9b304'
down_revision: Union[str, None] = '34ff74b6868a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS engine")

    op.execute("""
        CREATE TABLE engine.runs (
            run_id uuid PRIMARY KEY,
            kind text NOT NULL CHECK (kind IN ('kb','baseline','whatif')),
            company_id text NOT NULL,
            scenario_id uuid NULL,
            snapshots jsonb NOT NULL,
            status text NOT NULL CHECK (status IN ('running','done','failed')),
            error text NULL,
            stats jsonb NULL,
            models jsonb NULL,
            started_at timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz NULL
        )
    """)

    op.execute("""
        CREATE TABLE engine.change_records (
            change_id uuid PRIMARY KEY,
            run_id uuid NOT NULL REFERENCES engine.runs ON DELETE CASCADE,
            origin text NOT NULL CHECK (origin IN ('kb','whatif')),
            source_system text NOT NULL,
            citation text NOT NULL,
            rule_key text NOT NULL,
            heading text,
            s1_section_id int NULL,
            s2_section_id int NULL,
            renumbered_from text NULL,
            change_class text NOT NULL,
            s1_text_norm text NULL,
            s2_text_norm text NULL,
            diff_segments jsonb NULL,
            published_date date NULL,
            date_basis text NULL,
            din text NULL,
            amendment_source text NULL,
            in_footprint boolean NOT NULL,
            cited_clause_count int NOT NULL DEFAULT 0,
            obligation_changed boolean NULL,
            direction text NULL,
            summary text NULL,
            value_changes jsonb NULL,
            char_quotes jsonb NULL,
            disposition text NULL,
            disposition_reason text NULL
        )
    """)
    op.execute("""
        CREATE INDEX ix_change_records_run_footprint_class
        ON engine.change_records (run_id, in_footprint, change_class)
    """)

    op.execute("""
        CREATE TABLE engine.candidates (
            candidate_id uuid PRIMARY KEY,
            run_id uuid NOT NULL REFERENCES engine.runs ON DELETE CASCADE,
            change_id uuid NOT NULL REFERENCES engine.change_records ON DELETE CASCADE,
            clause_pk uuid NOT NULL,
            clause_id text NOT NULL,
            doc_id text NOT NULL,
            cited_citation text NULL,
            match_path text NOT NULL,
            path_detail jsonb NOT NULL,
            judged_by text NULL,
            skip_reason text NULL,
            affected boolean NULL,
            rationale text NULL,
            UNIQUE (change_id, clause_pk)
        )
    """)

    op.execute("""
        CREATE TABLE engine.findings (
            finding_id uuid PRIMARY KEY,
            run_id uuid NOT NULL REFERENCES engine.runs ON DELETE CASCADE,
            change_id uuid NOT NULL REFERENCES engine.change_records ON DELETE CASCADE,
            candidate_id uuid NOT NULL REFERENCES engine.candidates ON DELETE CASCADE,
            clause_pk uuid NOT NULL,
            clause_id text NOT NULL,
            doc_id text NOT NULL,
            citation text NOT NULL,
            finding_type text NOT NULL,
            severity text NOT NULL CHECK (severity IN ('high','medium','low')),
            verdict text NOT NULL,
            needs_review boolean NOT NULL DEFAULT false,
            required_change jsonb NULL,
            quotes jsonb NOT NULL,
            quotes_verified boolean NOT NULL,
            rationale text NOT NULL,
            confidence numeric NULL,
            decided_by text NOT NULL CHECK (decided_by IN ('rule','llm')),
            match_path text NOT NULL,
            propagated_from uuid NULL REFERENCES engine.findings,
            route_owner text NULL,
            route_reviewer text NULL,
            route_approver text NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX ix_findings_run_doc ON engine.findings (run_id, doc_id)")

    op.execute("""
        CREATE TABLE engine.doc_rollups (
            run_id uuid REFERENCES engine.runs ON DELETE CASCADE,
            doc_id text,
            status text NOT NULL CHECK (status IN ('flagged','cleared')),
            counts jsonb NOT NULL,
            changes_considered jsonb NOT NULL,
            reason text NULL,
            PRIMARY KEY (run_id, doc_id)
        )
    """)

    op.execute("""
        CREATE TABLE engine.radar_items (
            run_id uuid REFERENCES engine.runs ON DELETE CASCADE,
            change_id uuid REFERENCES engine.change_records ON DELETE CASCADE,
            obligation_changed boolean,
            applicable text CHECK (applicable IN ('yes','no','unclear')),
            attribute_basis text[] NOT NULL DEFAULT '{}',
            affected_activity text,
            reason text,
            quote_s2 text,
            quote_verified boolean,
            rule_covered_by_docs text[] NOT NULL DEFAULT '{}',
            PRIMARY KEY (run_id, change_id)
        )
    """)

    op.execute("""
        CREATE TABLE engine.whatif_scenarios (
            scenario_id uuid PRIMARY KEY,
            title text NOT NULL,
            source_system text NOT NULL,
            citation text NOT NULL,
            s1_section_id int NOT NULL,
            edit_kind text NOT NULL CHECK (edit_kind IN ('text_edit','repeal')),
            edited_text text NULL,
            is_preset boolean NOT NULL DEFAULT false,
            last_run_id uuid NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE engine.finding_reviews (
            review_id uuid PRIMARY KEY,
            finding_id uuid NOT NULL REFERENCES engine.findings ON DELETE CASCADE,
            action text NOT NULL CHECK (action IN ('accept','reject')),
            note text NULL,
            person_id text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE engine.score_reports (
            run_id uuid PRIMARY KEY REFERENCES engine.runs ON DELETE CASCADE,
            snapshot text NOT NULL,
            metrics jsonb NOT NULL,
            raw_stdout text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE engine.llm_calls (
            call_id uuid PRIMARY KEY,
            run_id uuid NULL,
            stage text NOT NULL,
            model text NOT NULL,
            prompt_sha256 text NOT NULL,
            request jsonb NOT NULL,
            response jsonb NULL,
            valid boolean NOT NULL,
            error text NULL,
            latency_ms int NULL,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE INDEX ix_llm_calls_cache
        ON engine.llm_calls (stage, model, prompt_sha256) WHERE valid
    """)


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS engine CASCADE")

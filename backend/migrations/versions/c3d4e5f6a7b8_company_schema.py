"""company schema

Revision ID: c3d4e5f6a7b8
Revises: b1c2d3e4f5a6
Create Date: 2026-10-07 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS company")

    op.execute("""
        CREATE TABLE company.companies (
            company_id text PRIMARY KEY,
            name text
        )
    """)

    op.execute("""
        CREATE TABLE company.company_attributes (
            company_id text,
            key text,
            value_text text,
            value_num numeric,
            value_bool boolean,
            source text,
            PRIMARY KEY (company_id, key)
        )
    """)

    op.execute("""
        CREATE TABLE company.people (
            company_id text,
            person_id text,
            name text,
            title text,
            department text,
            reports_to_id text,
            email text,
            alternate_person_id text,
            oncall_roles text[],
            PRIMARY KEY (company_id, person_id)
        )
    """)

    op.execute("""
        CREATE TABLE company.company_documents (
            company_id text,
            doc_id text,
            title text,
            doc_class text,
            vertical text,
            owner_id text,
            reviewer_id text,
            approver_id text,
            review_cycle text,
            current_version_id uuid,
            PRIMARY KEY (company_id, doc_id)
        )
    """)

    op.execute("""
        CREATE TABLE company.document_versions (
            version_id uuid PRIMARY KEY,
            company_id text,
            doc_id text,
            version text,
            status text,
            effective_date date,
            approved_date date,
            law_as_of date,
            next_review date,
            supersedes text,
            classification text,
            regulatory_basis text[],
            source_r2_key text,
            render_r2_keys text[],
            file_sha256 text,
            ingest_status text,
            ingested_at timestamptz,
            ingest_run_id uuid
        )
    """)

    op.execute("""
        CREATE TABLE company.clauses (
            clause_pk uuid PRIMARY KEY,
            company_id text,
            version_id uuid,
            doc_id text,
            clause_id text,
            local_id text,
            parent_clause_id text,
            ordinal int,
            unit_kind text,
            heading_path text[],
            section_kind text,
            sheet_no text,
            table_id text,
            row_cells jsonb,
            text_raw text,
            text_norm text,
            text_sha256 text,
            char_start int,
            char_end int,
            line_start int,
            clause_role text,
            role_method text,
            assessable boolean,
            normalized_statement text,
            topic_terms text[],
            UNIQUE (version_id, clause_id)
        )
    """)

    op.execute("""
        CREATE TABLE company.clause_citations (
            citation_pk uuid PRIMARY KEY,
            clause_pk uuid,
            citation_raw text,
            span_start int,
            span_end int,
            source_system text,
            title int,
            article text,
            rule text,
            section numeric,
            subsection_path text,
            granularity text,
            in_knowledge_base boolean,
            code_section_id text,
            resolution_status text,
            context text
        )
    """)

    op.execute("""
        CREATE TABLE company.clause_parameters (
            parameter_pk uuid PRIMARY KEY,
            clause_pk uuid,
            kind text,
            name text,
            value_text text,
            span_start int,
            span_end int,
            value_num numeric,
            unit text,
            qualifier text,
            day_type text,
            supported_by_citation_pk uuid,
            value_source text,
            method text,
            verified boolean
        )
    """)

    op.execute("""
        CREATE TABLE company.defined_terms (
            term_pk uuid PRIMARY KEY,
            company_id text,
            doc_id text,
            version_id uuid,
            term text,
            term_norm text,
            definition_clause_pk uuid,
            cites_regulatory_definition boolean,
            citation_pk uuid
        )
    """)

    op.execute("""
        CREATE TABLE company.term_usages (
            term_pk uuid,
            clause_pk uuid,
            occurrences int,
            PRIMARY KEY (term_pk, clause_pk)
        )
    """)

    op.execute("""
        CREATE TABLE company.clause_links (
            link_pk uuid PRIMARY KEY,
            company_id text,
            from_clause_pk uuid,
            to_clause_pk uuid,
            to_doc_id text,
            link_type text,
            method text,
            evidence text,
            confidence numeric
        )
    """)

    op.execute("""
        CREATE TABLE company.document_scope (
            company_id text,
            doc_id text,
            version_id uuid,
            scope_level text,
            scope_key text,
            code_section_id text,
            sources text[],
            clause_count int,
            PRIMARY KEY (version_id, scope_level, scope_key)
        )
    """)

    op.execute("""
        CREATE TABLE company.table_columns (
            company_id text,
            doc_id text,
            table_name text,
            column_name text,
            column_role text,
            role_method text,
            PRIMARY KEY (company_id, doc_id, table_name, column_name)
        )
    """)

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

    op.execute("""
        CREATE TABLE company.llm_extractions (
            extraction_pk uuid PRIMARY KEY,
            run_id uuid,
            stage text,
            unit_id text,
            model text,
            prompt_sha256 text,
            request jsonb,
            response jsonb,
            valid boolean,
            error text,
            created_at timestamptz
        )
    """)

    op.execute("""
        CREATE TABLE company.ingest_runs (
            run_id uuid PRIMARY KEY,
            company_id text,
            started_at timestamptz,
            finished_at timestamptz,
            flags jsonb,
            status text,
            report_r2_key text
        )
    """)

    # Indexes
    op.execute("CREATE INDEX ON company.clauses (doc_id)")
    op.execute("CREATE INDEX ON company.clauses (clause_id)")
    op.execute("CREATE INDEX ON company.clause_citations (code_section_id)")
    op.execute("CREATE INDEX ON company.clause_citations (clause_pk)")
    op.execute("CREATE INDEX ON company.clause_parameters (clause_pk)")
    op.execute("CREATE INDEX ON company.clause_links (from_clause_pk)")
    op.execute("CREATE INDEX ON company.clause_links (to_clause_pk)")
    op.execute("CREATE INDEX ON company.document_scope (scope_key)")


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS company CASCADE")

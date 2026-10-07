-- Company schema DDL reference
-- Generated for Strata company data ingestion pipeline (task 1.2.1)

CREATE SCHEMA IF NOT EXISTS company;

CREATE TABLE company.companies (
    company_id text PRIMARY KEY,
    name text
);

CREATE TABLE company.company_attributes (
    company_id text,
    key text,
    value_text text,
    value_num numeric,
    value_bool boolean,
    source text,
    PRIMARY KEY (company_id, key)
);

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
);

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
);

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
);

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
);

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
);

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
);

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
);

CREATE TABLE company.term_usages (
    term_pk uuid,
    clause_pk uuid,
    occurrences int,
    PRIMARY KEY (term_pk, clause_pk)
);

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
);

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
);

CREATE TABLE company.table_columns (
    company_id text,
    doc_id text,
    table_name text,
    column_name text,
    column_role text,
    role_method text,
    PRIMARY KEY (company_id, doc_id, table_name, column_name)
);

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
);

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
);

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
);

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
);

CREATE TABLE company.ingest_runs (
    run_id uuid PRIMARY KEY,
    company_id text,
    started_at timestamptz,
    finished_at timestamptz,
    flags jsonb,
    status text,
    report_r2_key text
);

-- Indexes
CREATE INDEX ON company.clauses (doc_id);
CREATE INDEX ON company.clauses (clause_id);
CREATE INDEX ON company.clause_citations (code_section_id);
CREATE INDEX ON company.clause_citations (clause_pk);
CREATE INDEX ON company.clause_parameters (clause_pk);
CREATE INDEX ON company.clause_links (from_clause_pk);
CREATE INDEX ON company.clause_links (to_clause_pk);
CREATE INDEX ON company.document_scope (scope_key);

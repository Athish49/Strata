-- Test fixture: minimal company.* DDL loaded into the scratch PostgreSQL cluster by
-- tests/engine/test_version_scoping.py. NOT the production schema (alembic owns that);
-- moved here from app/company_ingest/store/schema.sql by task 2.3, with the dropped
-- datasets / dataset_columns / parameter_checks tables removed.

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

-- ---------------------------------------------------------------------------
-- v2 additions from migration f7b2c91d4a08 (task 5.7). Additive only, and
-- deliberately laxer than production: version_no stays nullable because older
-- tests insert version rows without it, and file_sha256 / supersedes are NOT
-- dropped here. (The document_versions status CHECK *is* present: task 5.6
-- adds it in the next section.)
-- ---------------------------------------------------------------------------
ALTER TABLE company.company_documents
  ADD COLUMN IF NOT EXISTS current_content_hash char(64),
  ADD COLUMN IF NOT EXISTS doc_number           text,
  ADD COLUMN IF NOT EXISTS lifecycle_state      text NOT NULL DEFAULT 'active',
  ADD COLUMN IF NOT EXISTS created_at           timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS updated_at           timestamptz NOT NULL DEFAULT now();

CREATE UNIQUE INDEX IF NOT EXISTS company_documents_content_hash_uq
  ON company.company_documents (company_id, current_content_hash)
  WHERE current_content_hash IS NOT NULL;

ALTER TABLE company.document_versions
  ADD COLUMN IF NOT EXISTS version_no            int,
  ADD COLUMN IF NOT EXISTS is_current            boolean NOT NULL DEFAULT false,
  ADD COLUMN IF NOT EXISTS superseded_by         uuid,
  ADD COLUMN IF NOT EXISTS supersedes_version_id uuid,
  ADD COLUMN IF NOT EXISTS created_at            timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS created_by_person_id  text,
  ADD COLUMN IF NOT EXISTS change_reason         text,
  ADD COLUMN IF NOT EXISTS extraction_r2_key     text,
  ADD COLUMN IF NOT EXISTS extraction_method     text;

CREATE TABLE IF NOT EXISTS company.ingest_jobs (
    job_id uuid PRIMARY KEY,
    company_id text NOT NULL,
    doc_id text NOT NULL,
    version_id uuid NOT NULL,
    state text NOT NULL CHECK (state IN ('queued','running','succeeded','failed')),
    error text,
    stats jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz
);
CREATE INDEX IF NOT EXISTS ingest_jobs_state_idx ON company.ingest_jobs (state, created_at);

-- ---------------------------------------------------------------------------
-- Rest of migration f7b2c91d4a08 (task 5.6): the document_versions indexes and
-- status CHECK, the org/approval tables, and the llm_extractions cache key.
-- Still laxer than production in exactly two ways, both for the older seeds
-- above: version_no stays nullable, and file_sha256 / supersedes are kept.
-- The status CHECK is safe to add because NULL passes a CHECK.
-- document_versions_current_uq is load-bearing for tests/company_ingest/test_promote.py.
-- ---------------------------------------------------------------------------
ALTER TABLE company.document_versions
  ADD CONSTRAINT document_versions_status_ck
  CHECK (status IN ('draft','in_review','approved','effective','superseded','retired'));

CREATE UNIQUE INDEX IF NOT EXISTS document_versions_no_uq
  ON company.document_versions (company_id, doc_id, version_no);
CREATE UNIQUE INDEX IF NOT EXISTS document_versions_current_uq
  ON company.document_versions (company_id, doc_id) WHERE is_current;
CREATE INDEX IF NOT EXISTS document_versions_doc_idx
  ON company.document_versions (company_id, doc_id);

ALTER TABLE company.llm_extractions
  ADD COLUMN IF NOT EXISTS company_id     text NOT NULL,
  ADD COLUMN IF NOT EXISTS content_sha256 char(64) NOT NULL;
ALTER TABLE company.llm_extractions
  ALTER COLUMN stage         SET NOT NULL,
  ALTER COLUMN prompt_sha256 SET NOT NULL,
  ALTER COLUMN model         SET NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS llm_extractions_cache_uq
  ON company.llm_extractions (company_id, stage, content_sha256, prompt_sha256, model);

CREATE TABLE IF NOT EXISTS company.departments (
    company_id text NOT NULL,
    department_id text NOT NULL,
    name text NOT NULL,
    parent_department_id text,
    PRIMARY KEY (company_id, department_id)
);

ALTER TABLE company.people
  ADD COLUMN IF NOT EXISTS department_id text,
  ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;

CREATE TABLE IF NOT EXISTS company.document_role_assignments (
    company_id text NOT NULL,
    doc_id text NOT NULL,
    person_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('owner','reviewer','approver')),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, doc_id, person_id, role)
);

CREATE TABLE IF NOT EXISTS company.approval_policies (
    company_id text NOT NULL,
    policy_id uuid PRIMARY KEY,
    name text NOT NULL,
    applies_to_vertical text,
    applies_to_doc_class text
);

CREATE TABLE IF NOT EXISTS company.approval_policy_steps (
    policy_id uuid NOT NULL,
    step_no int NOT NULL,
    required_role text NOT NULL CHECK (required_role IN ('owner','reviewer','approver')),
    min_approvals int NOT NULL DEFAULT 1,
    PRIMARY KEY (policy_id, step_no)
);

CREATE TABLE IF NOT EXISTS company.approval_requests (
    request_id uuid PRIMARY KEY,
    company_id text NOT NULL,
    version_id uuid NOT NULL,
    policy_id uuid,
    state text NOT NULL CHECK (state IN ('open','approved','rejected','cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS approval_requests_open_uq
  ON company.approval_requests (version_id) WHERE state = 'open';

CREATE TABLE IF NOT EXISTS company.approval_steps (
    request_id uuid NOT NULL,
    step_no int NOT NULL,
    required_role text NOT NULL,
    assignee_person_id text,
    decision text CHECK (decision IN ('approved','rejected')),
    decided_at timestamptz,
    note text,
    PRIMARY KEY (request_id, step_no)
);

-- ---------------------------------------------------------------------------
-- Migration f7b2c91d4a08 addendum (task 3.2). Same definitions as production.
--   pending_content_hash: hash of an in-flight version; promote_version reads it
--     and clears it (NULL) on promotion and on supersession.
--   register_spec: a register-CSV upload's declared RegisterSpec, so
--     jobs.prepare_retry can re-ingest from the raw R2 bytes.
-- ---------------------------------------------------------------------------
ALTER TABLE company.document_versions
  ADD COLUMN IF NOT EXISTS pending_content_hash char(64);

ALTER TABLE company.ingest_jobs
  ADD COLUMN IF NOT EXISTS register_spec jsonb;

-- ---------------------------------------------------------------------------
-- Migration 9c1e4b7a2f05 (verticals re-taxonomy). Same definitions as
-- production: company.verticals lookup table, seeded with the 14 new
-- verticals (name, slug, description verbatim from NEW_VERTICALS in the
-- migration), plus nullable FKs from company_documents.vertical and
-- approval_policies.applies_to_vertical, ON UPDATE CASCADE.
-- ---------------------------------------------------------------------------
CREATE TABLE company.verticals (
    name        text PRIMARY KEY,
    slug        text UNIQUE NOT NULL,
    description text,
    sort_order  integer UNIQUE NOT NULL
);

INSERT INTO company.verticals (name, slug, description, sort_order) VALUES
    ('Corporate Governance & Board', 'corporate-governance-board', 'Board structure, bylaws, charters, fiduciary duties, shareholder rights, entity management, annual filings, regulatory disclosure obligations', 1),
    ('Compliance & Ethics', 'compliance-ethics', 'Code of conduct, anti-corruption (FCPA), anti-bribery, whistleblower protections, compliance training, conflicts of interest, FTC consumer/advertising compliance', 2),
    ('Legal & Contractual', 'legal-contractual', 'Contract governance, litigation holds, IP protection, licensing, entity structure, NDAs, antitrust compliance', 3),
    ('Financial Compliance & Reporting', 'financial-compliance-reporting', 'SOX/ICFR, GAAP/IFRS, financial disclosures, audit requirements, internal controls, revenue recognition, pricing regulations, fee disclosures', 4),
    ('Tax & Trade Compliance', 'tax-trade-compliance', 'Corporate tax, payroll tax, sales tax, international tax (FATCA), transfer pricing, export controls, customs, OFAC sanctions, tariffs', 5),
    ('Workforce & Employment', 'workforce-employment', 'Labor laws, wage & hour, FMLA, ADA, anti-discrimination, benefits (ERISA), immigration/work authorization, DEI policies', 6),
    ('Health & Safety', 'health-safety', 'Workplace safety, emergency preparedness, hazard communication, PPE, incident reporting, product/consumer safety', 7),
    ('Data Privacy & Cybersecurity', 'data-privacy-cybersecurity', 'GDPR, CCPA/CPRA, state privacy laws, data breach notification, cybersecurity frameworks, data retention, information security', 8),
    ('Environmental & Sustainability', 'environmental-sustainability', 'EPA regulations, emissions, waste management, environmental permits, GHG reporting, ESG disclosures, climate risk, energy management', 9),
    ('Operations & Quality', 'operations-quality', 'Quality management, process compliance, GMP, FDA product regulations, CAPA, operational standards, business process documentation', 10),
    ('Information Technology & Records', 'information-technology-records', 'IT policies, system access controls, change management, records retention, digital accessibility (ADA/WCAG), AI governance and responsible use', 11),
    ('Supply Chain & Third-Party Risk', 'supply-chain-third-party-risk', 'Vendor compliance, third-party risk, supplier due diligence, modern slavery/forced labor, supply chain transparency, conflict minerals', 12),
    ('Policy & Training Management', 'policy-training-management', 'Policy lifecycle, document control, version management, compliance training programs, employee acknowledgments', 13),
    ('Risk & Resilience', 'risk-resilience', 'Enterprise risk management, insurance requirements, business continuity, disaster recovery, operational resilience', 14);

ALTER TABLE company.company_documents
  ADD CONSTRAINT company_documents_vertical_fk
  FOREIGN KEY (vertical) REFERENCES company.verticals(name)
  ON UPDATE CASCADE;

ALTER TABLE company.approval_policies
  ADD CONSTRAINT approval_policies_vertical_fk
  FOREIGN KEY (applies_to_vertical) REFERENCES company.verticals(name)
  ON UPDATE CASCADE;

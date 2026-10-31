# Company Document Ingestion — Architecture & Schema

Code: `backend/app/company_ingest/` · Entry: `cli/ingest.py` · Schema: `store/schema.sql`
Flags: `--no-llm` · `--no-datasets` · `--rebuild` · `--dry-run` (no Neon/R2/Qdrant writes)

---

## 1. System Architecture

```mermaid
flowchart LR
    subgraph SRC["Corpus on disk  (backend/app/company/corpus)"]
        direction TB
        S1["docs/&lt;DOC_ID&gt;/*.md<br/>P1 prose"]
        S2["docs/&lt;DOC_ID&gt;/data/*.csv<br/>P2 register / P3 dataset"]
        S3["_global/*  (profile, people, register, fact sheet)<br/>P4 reference"]
        S4["_global/ops/*.csv<br/>P3 dataset"]
        S5["**/render/*  (pdf, docx, xlsx)<br/>RENDER"]
    end

    PIPE["Ingest pipeline<br/>(CLI, 10 stages)"]

    subgraph STORES["Storage"]
        direction TB
        R2[("Cloudflare R2<br/>files &amp; snapshots")]
        NEON[("Neon Postgres<br/>schema: company<br/>structured truth")]
        QD[("Qdrant<br/>company_clauses<br/>hybrid search")]
    end

    LLM["LLM<br/>(clause enrichment,<br/>column roles, SQL checks)"]

    SRC --> PIPE
    PIPE <--> LLM
    PIPE --> R2
    PIPE --> NEON
    PIPE --> QD
    NEON -. "clause_pk / code_section_id" .- QD
    NEON -. "r2 keys, sha256" .- R2

    API["FastAPI<br/>/api/company, /api/engine"]
    NEON --> API
    QD --> API
    R2 --> API
```

---

## 2. Pipeline Workflow

```mermaid
flowchart TD
    A["1 COLLECT<br/>walk corpus · allowlist (deny wins)<br/>SHA-256 · profile · version · upload raw to R2"]
    A --> B1["P4 reference<br/>→ Neon: companies,<br/>company_attributes, people<br/>+ document_register → RegisterEntry list"]
    A --> B2["2 SEGMENT P1<br/>front matter split<br/>→ clause units (headings, paras, tables)"]
    A --> B3["2 SEGMENT P2<br/>1 row = 1 unit<br/>(OBL-/EVT-/RRS- registers)"]
    A --> B4["2 PROFILE P3<br/>DuckDB → parquet, columns,<br/>stats, key detection"]

    B2 --> C
    B3 --> C
    C["3 DETERMINISTIC ENRICH (regex/grammar)<br/>citations · parameters · references · roles · defined terms + usages"]

    C --> D1["4a LLM clause enrichment<br/>role, assessable, normalized_statement, topics"]
    B3 --> D2["4b LLM column roles<br/>(register columns)"]
    B4 --> D3["4c LLM propose SQL checks<br/>→ validate vs parameters"]

    D1 --> E
    E["5 LINK RESOLVE<br/>cites / refs between clauses &amp; docs<br/>citations → code_section_id (reg. KB)"]
    E --> F["6 DOCUMENT SCOPE<br/>rollup: doc → reg. sections touched"]
    F --> G["7 RESTATES LINKS<br/>clause restates regulation"]
    G --> H["8 QDRANT INDEX<br/>dense (MiniLM-L6, 384d) + BM25 sparse<br/>skip if --dry-run"]
    H --> I["9 ACCEPTANCE CHECKS<br/>pass/fail → exit code"]
    I --> J["10 SNAPSHOT + COMMIT<br/>clauses.jsonl → R2<br/>commit_run → Neon (single txn)"]

    D2 --> J
    D3 --> J
    B1 --> J
    B4 --> J
```

### File profiles

| Profile | Match rule | Processing | Raw → R2 key |
|---|---|---|---|
| **P1 prose** | `docs/<ID>/<ID>_vX.md` | segment → clauses | `raw/{doc}/{ver}/file.md` |
| **P2 register** | `docs/<ID>/data/*.csv`, 1st col `*_id` = `OBL-/EVT-/RRS-…` | row → clause unit | `raw/{doc}/{ver}/data/{name}.csv` |
| **P3 dataset** | other CSVs, `_global/ops/*.csv` | DuckDB profile → parquet | `raw/…/data/` or `global/{run}/ops/…` |
| **P4 reference** | `_global/*` non-ops | loaded into Neon | `global/{run}/…` |
| **RENDER** | any `render/` dir | stored only (not parsed) | `raw/{doc}/{ver}/render/…` |

---

## 3. Where Everything Goes

```mermaid
flowchart LR
    subgraph R2["R2  company/{company_id}/…"]
        direction TB
        R2a["raw/{doc}/{ver}/<br/>.md · data/*.csv · render/*<br/><i>original files, immutable source of truth</i>"]
        R2b["global/{run}/<br/><i>global ref + ops files</i>"]
        R2c["derived/{doc}/{ver}/clauses.jsonl<br/><i>clause snapshot (text, citations, params, refs)</i>"]
        R2d["derived/{doc}/{ver}/datasets/*.parquet<br/>derived/global/ops/*.parquet<br/><i>columnar datasets for SQL checks</i>"]
        R2e["ingest_runs/{run}/report.json<br/>ingest_runs/{run}/llm/{stage}/{unit}.json<br/><i>run report, raw LLM outputs</i>"]
    end

    subgraph NEON["Neon  schema company"]
        direction TB
        Na["Master data<br/>companies · company_attributes · people"]
        Nb["Documents<br/>company_documents · document_versions · document_scope"]
        Nc["Clause graph<br/>clauses · clause_citations · clause_parameters<br/>defined_terms · term_usages · clause_links"]
        Nd["Datasets<br/>datasets · dataset_columns · table_columns · parameter_checks"]
        Ne["Audit<br/>ingest_runs · llm_extractions"]
    end

    subgraph QD["Qdrant  company_clauses"]
        Qa["1 point / clause<br/>vectors: dense 384d cosine + bm25 sparse<br/>payload: company_id, doc_id, version_id, clause_id,<br/>clause_role, assessable, is_current, cited_sections,<br/>cited_rules, param_kinds, terms_used, text_preview"]
    end

    Na -.-|"people → owner_id"| Nb
    Nb -.-|"r2 keys + sha256"| R2a
    Nd -.-|"r2_parquet_key"| R2d
    Ne -.-|"report_r2_key"| R2e
    Nc -.-|"same clause_id; point id = uuid5(company, version, clause_id)"| Qa
```

| Store | Holds | Answers |
|---|---|---|
| **R2** | raw files, clause snapshots, parquet, run reports | "Show me the original / re-run a check / audit a run" |
| **Neon** | structured, relational clause graph + metadata | "Who owns it? what does clause X cite/define/link to? which params?" |
| **Qdrant** | clause embeddings + filterable payload | "Which clauses are semantically/lexically relevant to this query/regulation?" |

---

## 4. Data Schema (Neon, `company` schema)

> No FOREIGN KEY constraints are declared in DDL — all relationships below are logical (enforced by the pipeline).
> Only `PK`/`UNIQUE` noted. Indexes: `clauses(doc_id)`, `clauses(clause_id)`, `clause_citations(code_section_id, clause_pk)`, `clause_parameters(clause_pk)`, `clause_links(from_clause_pk, to_clause_pk)`, `document_scope(scope_key)`.

### 4.1 Entity-relationship diagram

```mermaid
erDiagram
    companies ||--o{ company_attributes : has
    companies ||--o{ people : employs
    companies ||--o{ company_documents : owns
    people |o--o{ company_documents : "owner/reviewer/approver"
    people |o--o{ people : "reports_to / alternate"
    company_documents ||--o{ document_versions : "doc_id"
    company_documents ||--o| document_versions : "current_version_id"
    document_versions ||--o{ clauses : "version_id"
    document_versions ||--o{ document_scope : "version_id"
    document_versions ||--o{ defined_terms : "version_id"
    clauses ||--o{ clauses : "parent_clause_id"
    clauses ||--o{ clause_citations : "clause_pk"
    clauses ||--o{ clause_parameters : "clause_pk"
    clauses ||--o{ clause_links : "from_clause_pk"
    clauses |o--o{ clause_links : "to_clause_pk"
    clauses ||--o{ term_usages : "clause_pk"
    clauses |o--o{ defined_terms : "definition_clause_pk"
    defined_terms ||--o{ term_usages : "term_pk"
    clause_citations |o--o{ clause_parameters : "supported_by_citation_pk"
    clause_citations |o--o{ defined_terms : "citation_pk"
    clause_parameters ||--o{ parameter_checks : "parameter_pk"
    datasets ||--o{ dataset_columns : "dataset_pk"
    datasets ||--o{ parameter_checks : "dataset_pk"
    company_documents ||--o{ datasets : "doc_id"
    company_documents ||--o{ table_columns : "doc_id"
    ingest_runs ||--o{ llm_extractions : "run_id"
    ingest_runs ||--o{ document_versions : "ingest_run_id"
```

### 4.2 Master & document tables

```mermaid
erDiagram
    companies {
        text company_id PK
        text name
    }
    company_attributes {
        text company_id PK
        text key PK "applicability attribute"
        text value_text
        numeric value_num
        boolean value_bool
        text source
    }
    people {
        text company_id PK
        text person_id PK
        text name
        text title
        text department
        text reports_to_id
        text email
        text alternate_person_id
        text_arr oncall_roles
    }
    company_documents {
        text company_id PK
        text doc_id PK "e.g. RPL-CS-PRO-004"
        text title
        text doc_class
        text vertical
        text owner_id "people.person_id"
        text reviewer_id
        text approver_id
        text review_cycle
        uuid current_version_id "document_versions"
    }
    document_versions {
        uuid version_id PK "uuid5(company, doc, version)"
        text company_id
        text doc_id
        text version
        text status
        date effective_date
        date approved_date
        date law_as_of "regulation snapshot date"
        date next_review
        text supersedes
        text classification
        text_arr regulatory_basis
        text source_r2_key "raw md in R2"
        text_arr render_r2_keys "pdf/docx/xlsx in R2"
        text file_sha256
        text ingest_status
        timestamptz ingested_at
        uuid ingest_run_id
    }
    document_scope {
        text company_id
        text doc_id
        uuid version_id PK
        text scope_level PK
        text scope_key PK
        text code_section_id "regulatory KB section"
        text_arr sources
        int clause_count
    }
```

### 4.3 Clause graph tables

```mermaid
erDiagram
    clauses {
        uuid clause_pk PK
        text company_id
        uuid version_id "UNIQUE with clause_id"
        text doc_id
        text clause_id "stable human ID"
        text local_id
        text parent_clause_id
        int ordinal
        text unit_kind "heading/para/table/row"
        text_arr heading_path
        text section_kind
        text sheet_no
        text table_id
        jsonb row_cells "P2 register row"
        text text_raw
        text text_norm
        text text_sha256
        int char_start
        int char_end
        int line_start
        text clause_role "LLM/regex role"
        text role_method
        boolean assessable
        text normalized_statement
        text_arr topic_terms
    }
    clause_citations {
        uuid citation_pk PK
        uuid clause_pk
        text citation_raw "e.g. 170 IAC 4-1-23"
        int span_start
        int span_end
        text source_system "IAC / CFR / IC"
        int title
        text article
        text rule
        numeric section
        text subsection_path
        text granularity
        boolean in_knowledge_base
        text code_section_id "→ regulatory code_sections"
        text resolution_status
        text context
    }
    clause_parameters {
        uuid parameter_pk PK
        uuid clause_pk
        text kind "duration, threshold, %…"
        text name
        text value_text
        numeric value_num
        text unit
        text qualifier
        text day_type
        int span_start
        int span_end
        uuid supported_by_citation_pk
        text value_source "regulatory / company / template"
        text method
        boolean verified
    }
    clause_links {
        uuid link_pk PK
        text company_id
        uuid from_clause_pk
        uuid to_clause_pk
        text to_doc_id
        text link_type "refs / restates"
        text method
        text evidence
        numeric confidence
    }
    defined_terms {
        uuid term_pk PK
        text company_id
        text doc_id
        uuid version_id
        text term
        text term_norm
        uuid definition_clause_pk
        boolean cites_regulatory_definition
        uuid citation_pk
    }
    term_usages {
        uuid term_pk PK
        uuid clause_pk PK
        int occurrences
    }
```

### 4.4 Dataset, check & audit tables

```mermaid
erDiagram
    datasets {
        uuid dataset_pk PK
        text company_id
        text doc_id "null for _global/ops"
        text name
        text r2_parquet_key
        text r2_source_key
        text file_sha256
        bigint row_count
        text_arr primary_key
        text description
    }
    dataset_columns {
        uuid dataset_pk PK
        text column_name PK
        text dtype
        numeric null_rate
        bigint distinct_count
        text min_value
        text max_value
        jsonb top_values
        text semantic_role
        text fk_target "detected key link"
        text description
    }
    table_columns {
        text company_id PK
        text doc_id PK
        text table_name PK
        text column_name PK
        text column_role "LLM-inferred"
        text role_method
    }
    parameter_checks {
        uuid check_pk PK
        text company_id
        uuid parameter_pk "clause_parameters"
        uuid dataset_pk
        text purpose
        text sql_template "validated DuckDB SQL"
        jsonb param_bindings
        jsonb s1_result
        boolean validated
        text method
    }
    ingest_runs {
        uuid run_id PK
        text company_id
        timestamptz started_at
        timestamptz finished_at
        jsonb flags
        text status
        text report_r2_key
    }
    llm_extractions {
        uuid extraction_pk PK
        uuid run_id
        text stage
        text unit_id
        text model
        text prompt_sha256
        jsonb request
        jsonb response
        boolean valid
        text error
        timestamptz created_at
    }
```

---

## 5. Key Linking Concepts

```mermaid
flowchart LR
    DOC["doc_id<br/>(company_documents)"] -->|"+ version → uuid5"| VER["version_id<br/>(document_versions)"]
    VER -->|"+ clause_id"| CL["clause_pk<br/>(clauses)"]
    CL --> CIT["citations → code_section_id"]
    CL --> PAR["parameters (value_source)"]
    CL --> LNK["links (refs / restates)"]
    CL -->|"same clause_id"| QP["Qdrant point"]
    CIT -->|"code_section_id"| REG[("Regulatory KB<br/>code_sections")]
    DOC --> DS["datasets (parquet)"]
    PAR -->|"parameter_checks"| DS
    VER -->|"source_r2_key / sha256"| RAW["R2 raw file"]
```

- **Deterministic IDs**: `stable_uuid(company, doc, version)` → re-runs are idempotent (upserts).
- **`value_source`** on parameters: `regulatory` (restates law + has citation) · `company` (internal target/position) · `template` (template field/definition).
- **`parameter_checks`** tie a clause parameter to a dataset via validated SQL — verifies stated policy against actual data.
- **Qdrant ↔ Neon**: shared `clause_id`; Qdrant `is_current` flag marks the live version.

## 6. Known Gaps (from code review)

- CLI passes hardcoded `"v1"` as `version_id` to Qdrant upsert and R2 snapshot; Neon uses the real uuid5 version → payload/path `version_id` ≠ `document_versions.version_id`.
- `mark_previous_versions_stale()` exists but is not called by the CLI → old versions may remain `is_current=true`.
- `report.json` writer (`store/commit.py::write_report`) is not called; `ingest_runs.report_r2_key` is stored as `NULL`.
- No DB-level foreign keys; referential integrity is pipeline-only.

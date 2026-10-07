# Strata — Company Data Ingestion & Storage Spec (v1)

Oct 7, 2026 · @Athish

## 1. Purpose and principles

Every company file is compiled once into addressable **clauses**. Each clause carries its citations, parameters, defined terms and links, so that a Snapshot 1 → 2 change unit can be joined to the exact clauses it affects without re-reading any document. This spec defines what is extracted, how, and where it lives across Neon, Qdrant and R2.

**What the intelligence layer needs from company data.** Each need maps to a stored artifact:

| Engine need | Stored as | Section |
| --- | --- | --- |
| Which clauses cite a changed section or subsection | `clause_citations` resolved to `code_sections` | 6, 7 |
| What value the clause states (to compare with old/new law) | `clause_parameters` with verbatim spans | 6 |
| Which other clauses restate the same value (templates, forms, registers) | `clause_links` type `restates` / `references` | 7 |
| Which clauses use a defined term whose definition changed | `defined_terms` + `term_usages` | 6 |
| Which documents cover a rule where a new section appeared | `document_scope` | 7 |
| Clauses with no citation but on the same topic (recall net) | Qdrant `company_clauses` | 9 |
| Who to route a finding to | `company_documents` + `people` | 4 |
| How many records a changed threshold affects | Parquet datasets in R2 + `parameter_checks` | 8 |

**Design principles**

1. **Generic by structure, never by form.** There are exactly four ingestion profiles: clause-marked prose, register table, operational dataset and reference data (section 2). No code path names a document ID, form number or regulation.
2. **Deterministic first, LLM second.** Parsing, citations, numbers, IDs, references and term usage are regex or parser work. The LLM is used only for semantic fields: clause role when no marker decides it, conditions, parties, content elements and a normalized statement. It always returns a schema-validated JSON object.
3. **Verbatim or nothing.** Every extracted value stores the exact substring and its character offsets in the clause. Code verifies the substring. A value that fails is dropped, never kept as a paraphrase.
4. **Clause is the unit of everything.** Findings, routing, embeddings and evaluation all key on `clause_id`. The corpus's own clause IDs are used as-is, because `scoring.py` scores against them.
5. **Compile once, per document version.** Nothing is re-extracted at change time. Re-ingest happens only when a file's SHA-256 changes.
6. **Information barrier.** The engine ingests only what the corpus spec allows it to see (section 11). Basis files, grounding packs, QA and eval files never enter any database.

**v1 scope:** the 12 documents (T10–T21), their datasets, and the global files under `corpus/_global/`. Renders (docx, pdf, xlsx) are stored for viewing but are not parsed; the canonical Markdown and CSV are the source of truth.

## 2. The 12 documents mapped to four ingestion profiles

All 12 v1 documents run through four generic profiles. The profile is chosen by file structure, not by what the document is about.

| Profile | Detected by | What becomes a clause | Applies to |
| --- | --- | --- | --- |
| **P1 Clause-marked prose** | `.md` with YAML front matter | Each `<!-- clause: ID -->` block; each row of a `<!-- table: ID -->` table; each form field `App-X.Fn` | T13–T21 bodies and appendices; T10, T11, T12 cover memos |
| **P2 Register table** | `.csv` with a `clause_id` column | Each row | T10 `obligations_register.csv` and `controls.csv`, T11 `reporting_calendar_2025.csv`, T12 `retention_schedule.csv` |
| **P3 Operational dataset** | `.csv` without a `clause_id` column | Nothing. Rows stay as data, profiled and bound to clauses | T16, T18, T19, T20, T21 `data/*.csv`; `_global/ops/*.csv` |
| **P4 Reference data** | Files under `corpus/_global/` that are not ops data | Nothing. Loaded into lookup tables | `company_profile.yaml`, `people_directory.csv`, `document_register.csv`, `org_chart.md`, `company_fact_sheet.md` |

**Per-document view** (what each one contributes to matching):

| Task | Doc ID | Profiles | Richest matching surface |
| --- | --- | --- | --- |
| T10 | RPL-CMP-REG-001 | P1 memo, P2 register + controls | One row per obligation with `citation`, `key_parameters`, `implementing_documents` |
| T11 | RPL-REG-CAL-2025 | P1 memo, P2 calendar | `due_rule` quotes, `citation`, `source_procedure` |
| T12 | RPL-LEG-RRS-001 | P1 policy, P2 schedule | `regulatory_minimum`, `citation`, `retention_trigger` |
| T13 | RPL-TAR-GRR-012 | P1 (tariff sub-rules `R13.4(b)`, sheet markers, charge rows `R16.T-n`) | Inline citations on every sub-rule of Rules 9, 11, 12, 13 |
| T14 | RPL-CS-PRO-004 | P1 | Decision table §7, notice elements §8, notice template fields App-A |
| T15 | RPL-CS-PRO-007 | P1 | Fee decision table §8, adjustment scenarios §13 |
| T16 | RPL-DO-PLN-002 | P1, P3 (5 datasets) | Notice timing §11 and App-A; reporting §22 |
| T17 | RPL-CS-PRO-011 | P1 | Deadlines and determination-letter fields App-C |
| T18 | RPL-MTR-PGM-001 | P1, P3 (7 datasets) | Accuracy limits §10, test intervals §9; meter registry for counts |
| T19 | RPL-DCC-PRO-003 | P1, P3 (outage datasets) | Reportability table §7, report timing §8–10; incident log for counts |
| T20 | RPL-ENV-PRO-005 | P1, P3 (`spill_events_2024.csv`) | Decision table §7.2, exclusions §7.3, report content §8 |
| T21 | RPL-SAF-PRO-009 | P1, P3 (`incident_log_2024.csv`) | IURC decision table §8, notice content §9 |

A new company in the future adds no profile unless it brings a new *file structure*. Section 12 covers unmarked documents.

## 3. Ingestion pipeline

One pipeline with seven stages handles all four profiles. Stages 1–3 and 5–7 are code; only stage 4 calls an LLM. Each stage writes to a staging area and commits only after stage 7 passes.

1. **Collect and register (code).** Walk the allowlisted paths (section 11). For each file, compute its SHA-256 and choose its profile (section 2). Upload the original to R2. Upsert `company_documents` and `document_versions` from the YAML front matter, cross-checked against `document_register.csv`. If the version's file hash is unchanged, skip the document.
2. **Parse and segment (code).**
   - P1: parse the Markdown into a heading tree. Split clauses at every `<!-- clause: ... -->` marker. A clause runs from its marker to the next marker of any level. Track the current `<!-- sheet: n -->`. For `<!-- table: ID -->` tables, each row becomes a clause whose ID is `<DOC_ID>:<value of the ID column>`, with the cells kept as JSON. Mermaid blocks are stored on the clause but not parsed.
   - P2: each CSV row becomes a clause with `clause_id` from its column and the cells kept as JSON. Columns are classified once per table (stage 4b).
   - P3: profile each column (type, null rate, distinct count, min/max, top values), convert the file to Parquet and write it to R2. No row-level storage in Neon.
   - P4: load YAML and CSV into reference tables.
3. **Deterministic enrichment (code)**, over each clause's text, or its cells for table rows:
   - citations: regex, then the knowledge layer's own citation parser (the `_scope.py` grammar), then resolve to Snapshot 1 `code_sections`
   - numbers, units, day types and qualifier words (section 6)
   - document, clause, form, record-series, tariff rule/sheet, CIS code and person references
   - role markers: `Internal performance target:`, `Company position:`, `Note:` and `Caution:`, and the `App-X.Fn` form-field grammar
   - defined terms from the Definitions section, and their usages across all clauses
4. **LLM enrichment (one bounded call per unit, structured output).**
   - 4a. **Per assessable clause:** the clause text plus its heading path and parent lead-in goes in; `clause_role`, `normalized_statement`, semantic parameters and parameter-to-citation links come out (section 5 lists the fields). Clauses whose role code already decided as boilerplate are skipped.
   - 4b. **Per P2 table:** column headers plus 5 sample rows go in; a role for each column comes out (section 8).
   - 4c. **Per P3 dataset:** the column profile plus the clauses that describe the data go in; dataset bindings and parameter checks come out (section 8).
5. **Link (code).** Resolve references into `clause_links`. Compute `restates` links by parameter match. Roll citations up into `document_scope`. Validate parameter checks against Snapshot 1.
6. **Index (code).** Embed each clause and upsert it into Qdrant with its payload (section 9).
7. **Validate and commit (code).** Run the acceptance checks (section 12). Write the ingest report to R2. Commit in one Neon transaction and mark the document version `ingested`.

**Model use in v1:** stage 4a runs about 1,500–2,500 calls, stage 4b about 5, and stage 4c about 25. Every call has a fixed JSON schema, temperature 0, and its input and output saved in `llm_extractions` for audit and replay.

## 4. Neon PostgreSQL schema

Company data lives in its own schema, `company`, holding 17 tables. Every table carries `company_id`, so a second company needs no schema change. The regulatory schema is only ever referenced through `code_section_id` foreign keys.

| Table | One row per | Filled by stage |
| --- | --- | --- |
| `companies` | company | 1 |
| `company_attributes` | applicability attribute (key/value) | 1 (P4) |
| `people` | person | 1 (P4) |
| `company_documents` | document (stable across versions) | 1 |
| `document_versions` | document version | 1 |
| `clauses` | clause per document version | 2, 4a |
| `clause_citations` | citation found in a clause | 3, 5 |
| `clause_parameters` | value or semantic parameter in a clause | 3, 4a |
| `defined_terms` | term defined by the company | 3 |
| `term_usages` | (term, clause) occurrence | 3 |
| `clause_links` | edge between clauses or documents | 3, 5 |
| `document_scope` | (document, regulatory rule or section) | 5 |
| `table_columns` | column of a P2 register | 4b |
| `datasets` / `dataset_columns` | dataset and its profiled columns | 2, 4c |
| `parameter_checks` | executable rule binding a parameter to a dataset | 4c, 5 |
| `llm_extractions` / `ingest_runs` | LLM call and ingest run (audit) | 4, 7 |

```sql
CREATE TABLE company.company_documents (
  company_id text, doc_id text, title text,
  doc_class text,          -- procedure|plan|tariff|register|calendar|retention_schedule|reference
  vertical text, owner_id text, reviewer_id text, approver_id text,  -- approver may be null (two-signature docs)
  review_cycle text, current_version_id uuid,
  PRIMARY KEY (company_id, doc_id));

CREATE TABLE company.document_versions (
  version_id uuid PRIMARY KEY, company_id text, doc_id text, version text,
  status text, effective_date date, approved_date date, law_as_of date, next_review date,
  supersedes text, classification text,
  regulatory_basis text[],         -- front-matter list, as written
  source_r2_key text, render_r2_keys text[], file_sha256 text,
  ingest_status text,              -- pending|ingested|failed
  ingested_at timestamptz, ingest_run_id uuid);

CREATE TABLE company.people (
  company_id text, person_id text, name text, title text, department text,
  reports_to_id text, email text, alternate_person_id text, oncall_roles text[],
  PRIMARY KEY (company_id, person_id));

CREATE TABLE company.company_attributes (
  company_id text, key text, value_text text, value_num numeric, value_bool boolean,
  source text,                     -- e.g. company_profile.yaml:applicability_attributes
  PRIMARY KEY (company_id, key));
```

The clause-level tables are defined in sections 5–7, and the dataset tables in section 8. `doc_class` comes from a closed list chosen in stage 4a from the front matter and structure. It is used only for display and default severity, never for branching logic.

## 5. Clause extraction

Every clause row stores its exact text, its place in the document, a role, and an `assessable` flag. Only assessable clauses are matched against regulatory changes.

```sql
CREATE TABLE company.clauses (
  clause_pk uuid PRIMARY KEY,
  company_id text, version_id uuid, doc_id text,
  clause_id text,               -- e.g. RPL-CS-PRO-004:7.2, RPL-TAR-GRR-012:R13.4(b), RPL-CMP-REG-001:OBL-0042
  local_id text, parent_clause_id text, ordinal int,
  unit_kind text,               -- section|appendix|form_field|table_row|tariff_subrule|register_row
  heading_path text[],          -- ['8 Notice requirements', '8.3 Notice content']
  section_kind text,            -- purpose|scope|definitions|regulatory_basis|roles|procedure|records|training|
                                -- related_docs|revision_history|approval|appendix|front_matter|other
  sheet_no text, table_id text, row_cells jsonb,
  text_raw text, text_norm text, text_sha256 text,
  char_start int, char_end int, line_start int,
  clause_role text,             -- see table below
  role_method text,             -- marker|grammar|llm
  assessable boolean,
  normalized_statement text,    -- LLM: who must do what, when, under what condition (one sentence)
  topic_terms text[],           -- LLM: 3-6 plain keywords, free text (no taxonomy in v1)
  UNIQUE (version_id, clause_id));
```

**Deterministic fields:**

- `unit_kind` follows from the clause-ID grammar in corpus spec §3.2: `App-X.Fn` → form\_field, `T<s>-<n>` → table\_row, `R<n>.<n>` → tariff\_subrule, CSV row → register\_row.
- `parent_clause_id` comes from the ID hierarchy (`7.2.3` → `7.2`), falling back to the enclosing heading's clause.
- `section_kind` comes from matching heading text against a small keyword list.
- `text_norm` lowercases the text, collapses whitespace, unifies quotes and dashes, and strips Markdown. `text_sha256` hashes `text_raw` exactly as bounded.

**Clause role.** Code decides first; the LLM decides only the remainder.

| `clause_role` | Decided by | Assessable |
| --- | --- | --- |
| `internal_target` | text starts with `Internal performance target:` | yes (may now exceed a shortened legal limit) |
| `company_position` | text starts with `Company position:` | yes |
| `template_field` | `unit_kind = form_field` | yes |
| `definition` | inside a Definitions section, or a defined-term pattern | yes |
| `boilerplate` | `section_kind` in revision\_history, approval, related\_docs, front\_matter | no |
| `regulatory_restatement` | LLM; must have ≥ 1 resolved citation | yes |
| `out_of_scope_reference` | LLM; cites a statute or CFR outside the knowledge base, states no value | no (kept for display) |
| `internal_procedure` | LLM; company practice, no citation | yes only if it restates a value echoed elsewhere (section 7) |
| `informational` | LLM; purpose, scope prose, notes | no |

The roles match the `clause_type` values in corpus spec §3.4 on purpose. That lets the engine's labels be checked against the hidden basis files during evaluation, without the engine ever reading them.

**Stage 4a LLM contract (per assessable or undecided clause).**

- **Input:** `clause_id`, `heading_path`, parent lead-in text, clause text (or row cells), and the deterministic citations and numbers already found.
- **Output, as JSON:** `clause_role`; `normalized_statement`; `topic_terms`; `parameters[]` (section 6); `citation_links[]` (which parameter each citation supports).
- **Rules:**
  - every parameter `value_text` must be an exact substring of the clause; code checks it and drops any failure
  - no value may be inferred from outside the clause
  - unknown fields come back as null, never guessed
- **Budget:** clause text is capped at 1,500 tokens. Longer clauses (rare; a parent lead-in plus a long list) are split at list items into child units with suffixes `#1`, `#2`.

## 6. Citations, parameters and defined terms

These three tables carry most of the matching power. Citations and numbers are extracted by code. Conditions, parties and content elements come from the stage 4a LLM call. All three are pinned to character spans.

### 6.1 Citations

```sql
CREATE TABLE company.clause_citations (
  citation_pk uuid PRIMARY KEY, clause_pk uuid,
  citation_raw text,               -- exactly as written: '(170 IAC 4-1-16(b))', 'Commission Rule 16 [170 IAC 4-1-16]'
  span_start int, span_end int,
  source_system text,              -- iac|cfr|ic|usc|external_standard|unknown
  title int, article text, rule text, section numeric, subsection_path text,  -- '(b)(2)'
  granularity text,                -- rule|section|subsection
  in_knowledge_base boolean,       -- false for IC, CFR, U.S.C., ANSI and other standards
  code_section_id text,            -- resolved Snapshot 1 CodeSection; null if unresolved
  resolution_status text,          -- resolved|repealed_at_s1|not_found|external
  context text);                   -- inline|regulatory_basis_table|register_column|front_matter
```

- **Parsing:** use the same citation grammar as the knowledge layer. Sections are parsed as Decimal (`16.5`), and there is never any string comparison on citations. Ranges (`4-1-4 through 4-1-14`) expand to individual sections.
- **Resolution:** a citation resolves to the Snapshot 1 section row active on the document's `law_as_of` date. The subsection path is kept so it can later be compared with subsection-level diffs.
- **Register columns** (`citation` in T10/T11/T12) are parsed the same way with `context = register_column`.

### 6.2 Parameters

```sql
CREATE TABLE company.clause_parameters (
  parameter_pk uuid PRIMARY KEY, clause_pk uuid,
  kind text,           -- number|period|deadline|frequency|threshold|amount|qualifier|condition|
                       -- exception|party|channel|content_element|applicability|record_retention
  name text,           -- plain label, e.g. 'notice lead time before disconnection'
  value_text text,     -- verbatim substring
  span_start int, span_end int,
  value_num numeric, unit text,   -- canonical unit: day|hour|minute|month|year|percent|usd|gallon|kva|customer|...
  qualifier text,      -- within|at_least|not_more_than|not_less_than|prior_to|after|exactly|null
  day_type text,       -- calendar|business|working|hours|n_a
  supported_by_citation_pk uuid,  -- which citation in the clause this value restates; null for company values
  value_source text,   -- regulatory|company_practice|unknown (from role + citation presence)
  method text,         -- regex|llm
  verified boolean);   -- substring and offsets re-checked by code
```

- **Regex pass (code):**
  - numbers in digits or words, including "ten (10)" → 10
  - a unit within 4 tokens of the number, mapped to a canonical unit
  - qualifier words in the preceding 6 tokens
  - a day-type word ("business", "calendar", "working")
  - dollar amounts, percentages, times (`08:00`) and dates
- **LLM pass (stage 4a):** the semantic kinds `condition`, `exception`, `party`, `channel`, `content_element` and `applicability`. A notice or report clause produces **one `content_element` row per required element**. That is what makes a "content element added" change matchable.
- **Value source:** a parameter in a clause whose role is `internal_target` or `company_position`, or with no supporting citation, is `company_practice`. This keeps company choices from being flagged as stale law.
- **Register rows:** the columns `key_parameters`, `due_rule`, `regulatory_minimum` and `frequency_or_deadline` go through the same two passes.

### 6.3 Defined terms

```sql
CREATE TABLE company.defined_terms (
  term_pk uuid PRIMARY KEY, company_id text, doc_id text, version_id uuid,
  term text, term_norm text, definition_clause_pk uuid,
  cites_regulatory_definition boolean, citation_pk uuid);

CREATE TABLE company.term_usages (
  term_pk uuid, clause_pk uuid, occurrences int,
  PRIMARY KEY (term_pk, clause_pk));
```

- Terms come from Definitions sections: table rows, list items in the form "**Term** means…", and quoted terms followed by "means".
- Usages are found with a whole-word, case-insensitive match of `term_norm` across every clause in **all** documents, not just the defining one.
- Separately, store regulatory terms: for each defined term in the Snapshot 1 definitions sections the documents cite, record where the company uses it. This feeds the definition-ripple rule in the engine.

## 7. Relationships

One edge table, `clause_links`, holds every company-side relationship. One rollup table, `document_scope`, holds which regulations each document covers. Together they let a single change reach every clause that depends on it, including clauses that never cite the changed section themselves.

```sql
CREATE TABLE company.clause_links (
  link_pk uuid PRIMARY KEY, company_id text,
  from_clause_pk uuid,
  to_clause_pk uuid,          -- null when the target is a whole document
  to_doc_id text,
  link_type text,             -- see table
  method text,                -- regex|register_column|parameter_match|heading_match
  evidence text,              -- the matched text, e.g. 'RPL-CS-PRO-011 §14', 'Sheet Nos. 45–46'
  confidence numeric);        -- 1.0 for explicit references; < 1.0 for parameter_match

CREATE TABLE company.document_scope (
  company_id text, doc_id text, version_id uuid,
  scope_level text,           -- rule|section
  scope_key text,             -- '170 IAC 4-1' or '170 IAC 4-1-16'
  code_section_id text,       -- for section level
  sources text[],             -- front_matter|regulatory_basis_table|clause_citation_rollup
  clause_count int,
  PRIMARY KEY (version_id, scope_level, scope_key));
```

| `link_type` | Found by | Example | Engine use |
| --- | --- | --- | --- |
| `references_doc` | regex on document IDs from the register | "see RPL-CS-PRO-011" | route a change to a related document |
| `references_clause` | regex `<DOC_ID> §n` / `<DOC_ID>:<local>`; register columns `implementing_documents`, `source_procedure` | T10 row → `RPL-CS-PRO-004:8.3` | propagate a finding to dependent rows |
| `references_tariff` | regex `Rule n`, `Sheet No(s). n–m` → tariff clauses carrying that rule or sheet | procedure → `R16.T-2` | procedure ↔ tariff propagation |
| `references_form` | form-ID regex → the appendix clause whose heading names that form | body §8 → App-A (`CS-F-012`) | body ↔ template propagation |
| `references_record_series` | regex `RRS-…` → T12 row | records table → `RPL-LEG-RRS-001:RRS-CS-004` | retention changes reach the procedures |
| `references_obligation` | regex `OBL-nnnn` → T10 row | T11/T12 `register_obligation_ids` | register ↔ calendar / schedule |
| `restates` | parameter match (below) | §8.2 "10 days" ↔ App-A.F4 "10 days" | catch restated values that carry no citation |

**`restates` rule (code, after stage 4a).** Clause A restates clause B when all of these hold:

- both have a parameter with the same `kind`, `value_num`, `unit`, `day_type` and `qualifier`
- either they cite the same section, or one of them has no citation and both are in the same document or linked documents
- their `normalized_statement` embeddings have cosine similarity ≥ 0.6

Confidence is that cosine score. These links reproduce what the hidden answer key calls `acceptable_clause_ids` and `cross_doc_refs`, without reading it.

**`document_scope` rollup.** Take the union of three sources:

- front-matter `regulatory_basis`
- the Regulatory basis section table
- every resolved clause citation, rolled up to section and to rule

The engine uses it for one purpose: when Snapshot 2 adds a section inside a rule, every document whose scope contains that rule becomes a candidate for `new_requirement_gap`.

## 8. Registers and datasets

Registers (P2) are clauses whose cells need typed meaning. Datasets (P3) are never clauses: they are stored as Parquet and connected to clauses through **bindings** and **parameter checks**. Those let the engine count affected records with code, not an LLM.

### 8.1 Register columns (P2)

```sql
CREATE TABLE company.table_columns (
  company_id text, doc_id text, table_name text, column_name text,
  column_role text,   -- id|citation|regulatory_value|rule_quote|summary_text|reference_list|
                      -- owner_person|date|enum|status|free_text|ignore
  role_method text,   -- llm|header_rule
  PRIMARY KEY (company_id, doc_id, table_name, column_name));
```

- **Header rules first:** `clause_id` → id; a header containing `citation` → citation; `*_id` with person IDs → owner\_person; `*_date` → date. The stage 4b LLM call assigns the remaining roles from the headers plus 5 sample rows.
- **Row assembly:** `citation` cells go to `clause_citations`. `regulatory_value` and `rule_quote` cells go through the parameter passes. `reference_list` cells (`implementing_documents`, `source_procedure`, `control_ids`, `register_obligation_ids`) become `clause_links`. The whole row is kept in `clauses.row_cells`.
- `controls.csv` (T10) rows are clauses too (`unit_kind = register_row`, role `internal_procedure`). They are reached through `control_ids` links and are not matched directly.

### 8.2 Datasets (P3)

```sql
CREATE TABLE company.datasets (
  dataset_pk uuid PRIMARY KEY, company_id text, doc_id text,  -- null doc_id for _global/ops
  name text, r2_parquet_key text, r2_source_key text, file_sha256 text,
  row_count bigint, primary_key text[],
  description text);           -- LLM, from column names + describing clauses

CREATE TABLE company.dataset_columns (
  dataset_pk uuid, column_name text, dtype text, null_rate numeric,
  distinct_count bigint, min_value text, max_value text, top_values jsonb,
  semantic_role text,          -- id|foreign_key|timestamp|duration|quantity|flag|category|clause_ref|free_text
  fk_target text,              -- 'circuits_master.circuit_id', or 'clause:RPL-ENV-PRO-005:7.2'
  description text,
  PRIMARY KEY (dataset_pk, column_name));

CREATE TABLE company.parameter_checks (
  check_pk uuid PRIMARY KEY, company_id text,
  parameter_pk uuid,           -- the clause parameter whose value this rule depends on
  dataset_pk uuid,
  purpose text,                -- e.g. 'reportable releases', 'meters due for test', 'late initial reports'
  sql_template text,           -- DuckDB SELECT over the Parquet view; uses {param} placeholders only
  param_bindings jsonb,        -- {"threshold": parameter_pk, ...}
  s1_result jsonb,             -- result with Snapshot 1 values
  validated boolean,           -- passed the Snapshot 1 checks below
  method text);                -- llm_proposed
```

- **Profiling (code):** types, null rates, ranges, top values. A column whose values match clause local IDs (e.g. `decision_row`, `exclusion_applied`) gets `semantic_role = clause_ref` and a `clause:` foreign key. ID columns matching another dataset's key become `foreign_key`.
- **`data/README.md` is not visible to the engine** (corpus spec §0.1), so column meaning has to come from names, profiles and the clauses that describe the data. That is the realistic case for any company.
- **Stage 4c (LLM, one call per dataset):** the column profile goes in, plus the clauses that name the dataset or its form or record series (found via `clause_links`). Out come `description`, a semantic role for each column, and 0–5 `parameter_checks`.
- **Validating a check against Snapshot 1 (code).** A check is kept only if:
  - it runs
  - it returns zero violations with Snapshot 1 values (the corpus is compliant by construction)
  - where the dataset already has a computed flag column (`reportable`, `within_limits`, `iurc_reportable`), the check reproduces it exactly

  Checks that fail are logged and dropped.
- **Change time:** the engine swaps in the Snapshot 2 value for `{param}` and re-runs the check. The difference is the quantified impact.

**Storage:** datasets are not loaded into Neon. The meter registry alone is 409,950 rows. Parquet in R2, queried by DuckDB in the FastAPI service, keeps Neon on the free tier and makes every check a read-only query.

## 9. Qdrant

Qdrant holds one collection, `company_clauses`, with one point per clause in the current document versions. Each point has a dense vector and a sparse BM25 vector for hybrid search. It is the engine's recall net for clauses that the citation and link joins miss; it is never the primary match.

**Vectors**

- `dense`: embedding of `"<doc title> > <heading_path> :: <clause text>"` (for table and register rows, the cells rendered as `column: value` lines). **Use the same embedding model and dimension as the regulatory collection**, so a regulatory change unit's text can query company clauses directly.
- `bm25`: a Qdrant sparse vector over the same text. This catches exact terms such as form names, codes and defined terms that dense vectors blur.

**Point ID:** a UUIDv5 of `company_id + version_id + clause_id`, so re-ingest is idempotent.

**Payload (all filterable):**

| Field | Type | Used to |
| --- | --- | --- |
| `company_id`, `doc_id`, `version_id`, `clause_id` | keyword | scope and join back to Neon |
| `is_current` | bool | search only current versions |
| `clause_role`, `assessable`, `unit_kind`, `section_kind` | keyword / bool | exclude boilerplate; prefer assessable |
| `cited_sections` | keyword\[\] | e.g. `["170 IAC 4-1-16"]` |
| `cited_rules` | keyword\[\] | e.g. `["170 IAC 4-1"]` |
| `param_kinds` | keyword\[\] | e.g. `["period","content_element"]` |
| `param_units` | keyword\[\] | e.g. `["day"]`, to match a changed day-count parameter |
| `terms_used` | keyword\[\] | defined terms in the clause |
| `doc_class`, `owner_id` | keyword | display and routing |

**Not embedded:** dataset rows, front matter, and Mermaid blocks. Boilerplate clauses are embedded but filtered out with `assessable = true` at query time; that keeps one code path.

**v1 size:** about 3,000–4,500 points (12 documents with appendices, plus about 450 register rows), which fits easily in the Qdrant Cloud free tier.

## 10. R2 object layout

R2 holds four kinds of object: originals (immutable, keyed by version), derived artifacts that can be rebuilt (Parquet, clause snapshots), ingest reports, and later the updated versions approved in the portal. Neon stores only R2 keys.

```text
company/{company_id}/
  raw/{doc_id}/{version}/
    {doc_id}_v{version}.md            canonical source
    data/{name}.csv                   canonical datasets (P2 and P3)
    render/...                        docx / pdf / xlsx / charts, for viewing only
  global/{ingest_run_id}/
    company_profile.yaml, people_directory.csv, document_register.csv, org_chart.md,
    company_fact_sheet.md, ops/*.csv
  derived/{doc_id}/{version}/
    clauses.jsonl                     every clause row + citations + parameters, as committed
    datasets/{name}.parquet           P3 datasets, zstd-compressed
  derived/global/ops/{name}.parquet
  ingest_runs/{ingest_run_id}/
    report.json                       acceptance-check results, counts, dropped values
    llm/{stage}/{unit_id}.json        prompt + response for every LLM call
```

**Rules**

- Keys are write-once. A changed file is a new version path, never an overwrite.
- `derived/.../clauses.jsonl` is the portable snapshot of what was committed to Neon. It lets the clause tables be rebuilt without re-running the LLM.
- Object metadata on every raw object: `sha256`, `content_type`, `doc_id`, `version`, `profile`.
- Basis files, `scripts/`, `data/README.md`, `_manifest.json`, grounding packs, `qa/` and `eval/` are **never uploaded**. Section 11 enforces this.

## 11. Order, versioning and the information barrier

Ingest runs in dependency order. It is idempotent per file hash, and it reads only from an explicit allowlist. Anything outside that list is never opened.

**Order (one `ingest_run`):**

1. Global reference data (P4): people, attributes, document register.
2. Ops master datasets (`_global/ops`, P3 profiling only).
3. Prose documents T13–T21 (P1) and their datasets (P3).
4. Registers T10, T11, T12 (P1 memos and P2 tables). They come last because their `implementing_documents`, `source_procedure` and `register_obligation_ids` links resolve against clauses from step 3.
5. Link pass (stage 5) across all documents. Then index, validate, commit.

**Versioning**

- `document_versions` is append-only. A new file hash for the same `doc_id` creates a new version. Its clauses get new `clause_pk`s with the same `clause_id`s, and the previous version's Qdrant points are set to `is_current = false`.
- `clause_id` is the stable cross-version key. Text changes under the same ID are visible through `text_sha256`. This is how the portal's "updated version after approval" step will diff old and new clauses later.
- Findings must reference `(version_id, clause_id)`, so a finding stays pinned to the exact text it was raised on.
- Re-running ingest on unchanged files is a no-op. Re-running after a code change uses `--rebuild`, which re-derives from `clauses.jsonl` and the stored LLM outputs, without new LLM calls unless asked.

**Information barrier (enforced in code, tested in section 12).** The allowlist is the corpus spec's engine view:

```text
ALLOW  corpus/docs/*/*.md
ALLOW  corpus/docs/*/data/*.csv
ALLOW  corpus/docs/*/render/**
ALLOW  corpus/_global/**
DENY   **/*.basis.json  **/scripts/**  **/data/README.md  **/_manifest.json
DENY   corpus/grounding/**  corpus/qa/**  corpus/validation/**  corpus/eval/**
```

DENY wins over ALLOW. The collector logs every path it skipped, and the ingest report lists the denied count. If the engine ever reads a basis file, every evaluation result becomes meaningless. That is why this is a hard rule, not a convention.

## 12. Acceptance checks, build order and out of scope

Ingest is done when all 12 checks below pass on the full corpus. They are code, they run in stage 7, and they write to `report.json`. A failing check blocks the commit.

| # | Check | Pass condition |
| --- | --- | --- |
| 1 | Segmentation completeness | Clause count = number of clause markers + table rows + register rows; no body text outside a clause except headings |
| 2 | ID integrity | Every `clause_id` matches the corpus §3.2 grammar and is unique per version |
| 3 | Text fidelity | Concatenated clause texts reproduce the body (normalized whitespace); `text_sha256` is stable across two runs |
| 4 | Citation parse | 100% of citation-shaped strings parsed; ≥ 99% of IAC citations resolve to Snapshot 1; every unresolved one is listed |
| 5 | Restatement grounding | Every `regulatory_restatement` clause has ≥ 1 resolved citation; otherwise its role is downgraded and logged |
| 6 | Verbatim parameters | 100% of stored parameters have `verified = true` |
| 7 | Link resolution | Every `implementing_documents` / `source_procedure` / `references_*` target resolves, or is listed as unresolved with its evidence |
| 8 | Scope coverage | Every document has ≥ 1 `document_scope` rule; every front-matter `regulatory_basis` entry appears in scope |
| 9 | Dataset integrity | Parquet row count = CSV row count; declared foreign keys resolve (e.g. every `circuit_id` is in `circuits_master`) |
| 10 | Snapshot 1 checks | Every kept `parameter_check` returns zero violations on Snapshot 1 and reproduces any existing flag column |
| 11 | Index parity | Qdrant current points = assessable + non-assessable clauses of current versions; a random sample of 20 IDs round-trips to Neon |
| 12 | Barrier | Zero objects or rows originate from a DENY path; the denied-path count is > 0 (proves the filter ran) |

**Offline quality check (not a gate; run once).** Compare the engine's `clause_role` and `clause_parameters` with the hidden basis files in a separate evaluation script that only the developer runs. Targets: role agreement ≥ 90%; parameter recall ≥ 95% on clauses whose basis role is `regulatory_restatement`. Those files must never be visible to the ingest service.

**Build order for v1**

- [ ] Phase A: stages 1–3 and 5–7 for P1, P2 and P4 (no LLM). Checks 1–4 and 6–8 pass.
- [ ] Phase A+: stage 4a and 4b LLM enrichment. Checks 5 and 11 pass; offline role and parameter targets met.
- [ ] Phase B: P3 profiling and Parquet conversion (check 9), then stage 4c parameter checks (check 10), starting with T20 and T19.
- [ ] Gate to the engine: a Snapshot 1 engine run yields zero non-informational findings (corpus T90 check 15).

**Out of scope for v1** (designed for, not built):

- **Unmarked documents** (other companies): a structural segmenter that mints IDs from heading numbering, or heading path plus ordinal, then feeds the same pipeline. It is the only new component a second company needs.
- Parsing docx, pdf or xlsx as the source of truth, and OCR.
- A fixed topic taxonomy or ontology; free `topic_terms` are enough for 12 documents.
- A graph database. Postgres edge tables cover a few thousand edges.
- Per-document-type extraction schemas; the four profiles cover all 12.
- Embedding dataset rows, or LLM reasoning over datasets.

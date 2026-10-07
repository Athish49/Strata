# Strata v1 — Company Data Ingestion: Implementation Plan

**Companion to:** `company_data_ingestion_spec.md` (the *Company Data Ingestion & Storage Spec (v1)*, exported from Claude Docs). That document defines **what** to build. This one defines **in what order**, **what can run in parallel**, and **exactly what each task delivers**.
**Version:** 1.0 · 2026-10-07

---

## 0. How to use this file

### 0.1 References used in every task

| Short name | File | What it is |
|---|---|---|
| `SPEC §n` | `docs/company_data_ingestion_spec.md` | The ingestion spec. Its sections 1–12 are cited as `SPEC §1` … `SPEC §12`. |
| `CORPUS §n` | `docs/strata_synthetic_corpus_spec.md` | Generation spec of the synthetic company corpus. Used only for file formats, ID grammar and folder layout. |
| `ARCH`, `DATA_MODELS`, `INFRA`, `SEED`, `CHANGE_DET` | `docs/architecture.md`, `docs/data_models.md`, `docs/infrastructure.md`, `docs/seed_data.md`, `docs/change_detection.md` | Existing Strata project docs for the regulatory knowledge layer. |

If a referenced project doc is missing, stop and report which one. Do not guess its contents.

### 0.2 Prompt to give Claude Code for one task

> Read `docs/implementation_plan.md` §0 in full, then read task **X.Y.Z** in full. Read every document section listed under **Read first** for that task. Execute only task X.Y.Z. Do not modify files owned by other tasks unless the task says so. When done, run the task's **Done when** checks, and report: files created or changed, test results, and any deviation from the spec with the reason.

### 0.3 Task format

Every task has these fields:
- **Depends on** — tasks that must be merged first.
- **Parallel with** — tasks that can be built at the same time by another agent (no shared files).
- **Read first** — the exact sections to read before writing code.
- **Build** — numbered instructions.
- **Files** — files this task owns. Two tasks never own the same file.
- **Done when** — tests and checks that must pass. A task is not done until they do.

### 0.4 Global rules (apply to every task)

1. **Language and stack.** Python 3.11+, inside the existing FastAPI backend. Libraries: `pydantic` v2, `psycopg` 3 (or the DB layer already used in the backend — check `ARCH` and reuse it), `markdown-it-py`, `pyyaml`, `pyarrow`, `duckdb`, `qdrant-client`, `boto3` (R2 is S3-compatible), `pytest`. Add new dependencies to the backend's existing dependency file.
2. **Package location.** All company-ingestion code lives in `backend/app/company_ingest/`. If `ARCH` defines a different backend layout, follow `ARCH` and keep the same sub-module names.
3. **Generic code only (SPEC §1, principle 1).** No code path may branch on a specific `doc_id`, form number, task number (T10–T21) or regulation. Branching is allowed only on the four profiles (P1–P4), on file type, and on the clause-ID grammar.
4. **Information barrier (SPEC §11).** Code must never open a DENY path. This includes **code** under `corpus/grounding/` (`_scope.py`, `_normalizer.py`): do not import or copy them. Citation parsing comes from the knowledge layer's own parser (task 1.3.2).
5. **Verbatim values (SPEC §1, principle 3).** Any extracted value must be stored with its exact substring and offsets, verified by code.
6. **Determinism.** Same inputs → same outputs. Sort before writing. IDs that must be stable use UUIDv5 (namespace constant defined in task 1.1.1).
7. **Configuration.** Read paths and credentials only from environment variables defined in task 1.1.1. Never hard-code a corpus path or key.
8. **Tests.** Every task adds `pytest` tests under `backend/tests/company_ingest/`. Tests that need the real corpus are marked `@pytest.mark.corpus` and read `CORPUS_ROOT`. Unit tests use small inline fixtures.
9. **No silent drops.** Anything skipped, dropped or unresolved is logged to the run's issue list (task 1.1.2), and that list ends up in `report.json`.

---

## 1. Build order and parallelism

Each wave starts only when every task in the previous wave is merged. Tasks in the same wave can be built by separate agents at the same time.

| Wave | Tasks (parallel within the wave) | Outcome |
|---|---|---|
| W1 | 1.1.1 | Package skeleton, config, constants |
| W2 | 1.1.2 · 1.2.1 · 1.2.2 · 1.2.3 · 1.3.1 · 1.3.2 · 1.3.3 | Storage clients, migrations, shared libraries |
| W3 | 2.1.1 · 2.1.2 · 2.2.1 | Collector with allowlist; reference data; front-matter registration |
| W4 | 3.1.1 · 3.2.1 · 7.1.1 | Markdown segmenter; register-row segmenter; dataset profiling + Parquet |
| W5 | 4.1.1 · 4.1.2 · 4.1.3 · 4.1.4 · 4.1.5 · 7.1.2 | Deterministic enrichment; dataset key detection |
| W6 | 5.1.1 · 5.2.1 · 7.2.1 | LLM clause enrichment; LLM column roles; DuckDB runner |
| W7 | 5.1.2 · 6.1.1 · 6.1.3 · 7.2.2 | LLM runner + verification; reference links; document scope; LLM parameter checks |
| W8 | 6.1.2 · 6.2.1 · 7.2.3 | `restates` links; Qdrant indexing; Snapshot 1 check validation |
| W9 | 8.1.1 · 8.1.2 | Acceptance checks; commit + snapshot + report |
| W10 | 8.2.1 | `ingest` CLI orchestration (end-to-end run) |
| W11 | 9.1.1 · 9.1.2 | Offline quality evaluation; end-to-end corpus test |

**Milestones** (these match SPEC §12, "Build order for v1"):
- **Phase A** = W1–W5 plus 6.1.1, 6.1.3, 8.1.1, 8.1.2 and 8.2.1, run with LLM stages disabled (`--no-llm`). This proves segmentation, citations and links work without any model.
- **Phase A+** = adds 5.x and 6.1.2 / 6.2.1.
- **Phase B** = 7.x (datasets and parameter checks).

The CLI in 8.2.1 must support `--no-llm` and `--no-datasets`, so each milestone runs end to end on its own.

```text
1.1.1
  ├─ 1.1.2  1.2.1  1.2.2  1.2.3  1.3.1  1.3.2  1.3.3
  │     └─ 2.1.1 ──┬─ 2.1.2
  │               └─ 2.2.1 ──┬─ 3.1.1 ──┬─ 4.1.1 4.1.2 4.1.3 4.1.4 4.1.5 ──┬─ 5.1.1 → 5.1.2 ─┐
  │                          │          │                                 ├─ 6.1.1 ─────────┤
  │                          ├─ 3.2.1 ──┘ └─ 5.2.1                        └─ 6.1.3 ─────────┤
  │                          └─ 7.1.1 → 7.1.2 → 7.2.1 → 7.2.2 → 7.2.3                       │
  │                                                         6.1.2 (needs 5.1.2) ─ 6.2.1 ────┤
  └──────────────────────────────────────────────────────────────── 8.1.1 → 8.1.2 → 8.2.1 → 9.1.1, 9.1.2
```

---

## Phase 1 — Foundations

### 1.1.1 Package skeleton, config and constants

- **Depends on:** —
- **Parallel with:** —
- **Read first:** SPEC §1, §3, §11; `ARCH` (backend layout); `INFRA` (env vars and services)
- **Build:**
  1. Create `backend/app/company_ingest/` with sub-packages: `collect/`, `parse/`, `enrich/`, `llm/`, `link/`, `index/`, `datasets/`, `validate/`, `store/`, `cli/`. Each gets an `__init__.py`.
  2. Create `config.py` with a pydantic `Settings` class reading:
     - `CORPUS_ROOT`, `COMPANY_ID` (default `rpl`)
     - `NEON_DATABASE_URL`
     - `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET`
     - `QDRANT_URL`, `QDRANT_API_KEY`
     - `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY`
     - `EMBED_MODEL`, `EMBED_DIM`

     `EMBED_MODEL` and `EMBED_DIM` must default to the values the regulatory collection already uses (read `INFRA` / existing config). If the backend already has a settings module, extend it instead of creating a second one.
  3. Create `constants.py` with:
     - `UUID_NAMESPACE` (a fixed UUID literal)
     - the profile enum `P1_PROSE`, `P2_REGISTER`, `P3_DATASET`, `P4_REFERENCE`
     - the closed enums from SPEC §4–§8: `doc_class`, `unit_kind`, `section_kind`, `clause_role`, parameter `kind`, `qualifier`, `day_type`, `link_type`, `column_role`, `semantic_role`

     Use `StrEnum` so values serialize exactly as written in the SPEC.
  4. Create `ids.py` with `stable_uuid(*parts: str) -> UUID` (UUIDv5 over `"|".join(parts)`).
- **Files:** `backend/app/company_ingest/**/__init__.py`, `config.py`, `constants.py`, `ids.py`
- **Done when:**
  - Unit tests check every enum against the SPEC lists. Copy the SPEC values into the test as literals.
  - `stable_uuid` is deterministic.
  - Settings load from a `.env.example` that you add with placeholder values.

### 1.1.2 Run context and issue log

- **Depends on:** 1.1.1
- **Parallel with:** 1.2.x, 1.3.x
- **Read first:** SPEC §3 (stage 7), §10 (`ingest_runs/…/report.json`), §12
- **Build:**
  1. `run_context.py` defines `RunContext`, holding `run_id` (UUID4), `company_id`, `started_at`, flags (`no_llm`, `no_datasets`, `rebuild`), a `stats` counter dict, and an `issues` list.
  2. `Issue` model fields: `severity` (`error|warning|info`), `stage`, `code` (short snake_case), `message`, `doc_id`, `clause_id`, `path`, `details` (dict).
  3. Methods: `ctx.issue(...)`, `ctx.count(key, n=1)`, `ctx.to_report() -> dict`. The report dict is the shape written to `report.json` in 8.1.2.
- **Files:** `backend/app/company_ingest/run_context.py`
- **Done when:** unit tests cover issue recording and the report shape.

### 1.2.1 Neon migrations — `company` schema

- **Depends on:** 1.1.1
- **Parallel with:** 1.1.2, 1.2.2, 1.2.3, 1.3.x
- **Read first:** SPEC §4 (table list and DDL), §5 (`clauses`), §6 (`clause_citations`, `clause_parameters`, `defined_terms`, `term_usages`), §7 (`clause_links`, `document_scope`), §8 (`table_columns`, `datasets`, `dataset_columns`, `parameter_checks`); `DATA_MODELS` (how `code_sections` is keyed); the backend's existing migration tool (`ARCH`)
- **Build:**
  1. Use the backend's existing migration tool. If there is none, create plain SQL files under `backend/migrations/company/` and a small `apply.py`.
  2. Create schema `company` and every table in SPEC §4–§8, with exactly the column names and types from the SPEC DDL.
  3. Add the two tables the SPEC lists but does not spell out:
     - `llm_extractions(extraction_pk uuid pk, run_id uuid, stage text, unit_id text, model text, prompt_sha256 text, request jsonb, response jsonb, valid boolean, error text, created_at timestamptz)`
     - `ingest_runs(run_id uuid pk, company_id text, started_at, finished_at, flags jsonb, status text, report_r2_key text)`
  4. Add the `companies(company_id text pk, name text)` table.
  5. Constraints and indexes:
     - primary keys as stated in the SPEC
     - `UNIQUE (version_id, clause_id)` on `clauses`
     - indexes on `clauses(doc_id)`, `clauses(clause_id)`, `clause_citations(code_section_id)`, `clause_citations(clause_pk)`, `clause_parameters(clause_pk)`, `clause_links(from_clause_pk)`, `clause_links(to_clause_pk)`, `document_scope(scope_key)`
  6. `clause_citations.code_section_id` should reference the regulatory table's key **only if** `DATA_MODELS` gives it a stable unique key. Otherwise keep it as plain text with an index and note this in the migration file.
- **Files:** migration files; `backend/app/company_ingest/store/schema.sql` (a copy for reference)
- **Done when:** migrations apply to an empty schema and roll back cleanly, and a test introspects `information_schema.columns` and asserts every SPEC column exists with its type.

### 1.2.2 R2 client and key builder

- **Depends on:** 1.1.1
- **Parallel with:** 1.1.2, 1.2.1, 1.2.3, 1.3.x
- **Read first:** SPEC §10 (layout and rules)
- **Build:**
  1. `store/r2.py`: a boto3 S3 client configured for R2. Functions: `put_bytes(key, data, metadata, content_type)`, `put_file(key, path, metadata)`, `get_bytes(key)`, `exists(key)`, `list_prefix(prefix)`.
  2. **Write-once:** `put_*` raises if the key exists with a *different* `sha256` in its metadata. If the hash is the same, it is a no-op that returns `"unchanged"`.
  3. `store/r2_keys.py`: pure functions that build every key pattern in SPEC §10, for example `raw_doc_key(company_id, doc_id, version, filename)`, `derived_clauses_key(...)`, `parquet_key(...)`, `report_key(run_id)` and `llm_key(run_id, stage, unit_id)`. Versions are sanitized for keys (spaces → `_`).
  4. Every raw object carries the metadata `sha256`, `content_type`, `doc_id`, `version` and `profile`.
- **Files:** `store/r2.py`, `store/r2_keys.py`
- **Done when:**
  - unit tests for every key builder (exact strings)
  - a test of the write-once behaviour with a mocked client (`moto` or a stub)

### 1.2.3 Qdrant collection setup

- **Depends on:** 1.1.1
- **Parallel with:** 1.1.2, 1.2.1, 1.2.2, 1.3.x
- **Read first:** SPEC §9; `INFRA` (Qdrant config, regulatory collection settings)
- **Build:**
  1. `index/qdrant_setup.py` with `ensure_company_collection()`. It creates `company_clauses` if missing, with:
     - named dense vector `dense` (size `EMBED_DIM`, distance matching the regulatory collection, normally cosine)
     - named sparse vector `bm25` (with the IDF modifier enabled if the client version supports it)
  2. Create payload indexes for every field in the SPEC §9 payload table. Use keyword indexes for strings and string arrays, and bool indexes for `is_current` and `assessable`.
  3. If the collection exists with a different vector config, raise with a clear message. Never drop it automatically.
- **Files:** `index/qdrant_setup.py`
- **Done when:** running it twice is idempotent (an integration test marked `@pytest.mark.qdrant`), and a unit test checks the payload index list against SPEC §9.

### 1.3.1 Text utilities: normalization, hashing, offsets

- **Depends on:** 1.1.1
- **Parallel with:** 1.1.2, 1.2.x, 1.3.2, 1.3.3
- **Read first:** SPEC §5 (`text_norm`, `text_sha256`), §6.2 (numeral normalization), CORPUS §3.4 (numeral normalization rule)
- **Build:**
  1. `parse/text.py`:
     - `normalize(text) -> str` lowercases, NFKC-normalizes, unifies curly quotes, en/em dashes, non-breaking spaces and `§`, collapses whitespace and strips Markdown emphasis and link syntax.
     - `sha256_text(text) -> str` hashes the exact bytes with no normalization.
  2. `parse/numbers.py`: `words_to_number("fourteen") -> 14`, and collapsing "ten (10)" to 10. Cover 0–100, tens, "hundred" and "thousand", and fractions written as "one-half".
  3. `find_verbatim(haystack, needle) -> list[(start, end)]`: exact substring positions, used by every verification step.
- **Files:** `parse/text.py`, `parse/numbers.py`
- **Done when:** table-driven unit tests cover at least 40 cases, including "ten (10) business days", "30-day", "fourteen (14)", "$45.00" and "2,500".

### 1.3.2 Citation parser adapter

- **Depends on:** 1.1.1
- **Parallel with:** 1.1.2, 1.2.x, 1.3.1, 1.3.3
- **Read first:** SPEC §6.1; `DATA_MODELS` (CodeSection citation fields); `CHANGE_DET`; the knowledge layer's existing citation-parsing code (search the backend for the IAC citation parser used when ingesting regulations)
- **Build:**
  1. `enrich/citations_grammar.py` exposes a single API: `parse_citation(raw: str) -> list[ParsedCitation]`. `ParsedCitation` has `source_system`, `title`, `article`, `rule`, `section: Decimal | None`, `subsection_path`, `granularity`, `normalized_key` (e.g. `170 IAC 4-1-16`) and `rule_key` (e.g. `170 IAC 4-1`).
  2. **Reuse the knowledge layer's parser.** If it exists, wrap it. If its logic lives inside an ingestion script and is not importable, move it into a shared module (`backend/app/shared/citations.py`) without changing its behaviour, and update the old call site. **Do not** read or copy `corpus/grounding/_scope.py` (§0.4 rule 4).
  3. Supported forms:
     - IAC: `170 IAC 4-1-16`, `170 IAC 4-1-16(b)(2)`, `327 IAC 2-6.1-7`, decimal sections `4-1-16.5`
     - bracketed tariff form: `Commission Rule 16 [170 IAC 4-1-16]`
     - ranges: `170 IAC 4-1-4 through 4-1-14` and `4-1-4..4-1-14`, expanded to individual sections
     - rule-level references: `170 IAC 4-9`
     - external citations: `IC 8-1-2-121`, `40 CFR 112`, `29 CFR 1910.269`, `U.S.C.`, ANSI/IEEE names, all as `source_system ∈ {ic, cfr, usc, external_standard}`

     Sections compare as `Decimal`, never as strings.
  4. Function `find_citation_spans(text) -> list[(start, end, raw)]` locates citation-shaped strings in free text.
- **Files:** `enrich/citations_grammar.py` (+ the shared module if extracted)
- **Done when:**
  - at least 50 table-driven unit tests, including decimal-section ordering (`16.5` sorts after `16` and before `17`) and range expansion
  - the knowledge layer's existing tests still pass

### 1.3.3 LLM client with structured output and audit log

- **Depends on:** 1.1.1
- **Parallel with:** 1.1.2, 1.2.x, 1.3.1, 1.3.2
- **Read first:** SPEC §3 ("Model use in v1"), §5 (stage 4a contract); `ARCH` (any existing LLM wrapper — reuse it)
- **Build:**
  1. `llm/client.py`: `call_structured(stage, unit_id, system, user, schema: type[BaseModel], ctx) -> BaseModel | None`.
     - temperature 0
     - JSON output validated by pydantic
     - one retry on a validation error, passing the error message back to the model
     - on a second failure, return `None` and record an issue
  2. Every call writes an `llm_extractions` row and the R2 object `ingest_runs/{run_id}/llm/{stage}/{unit_id}.json`, holding the request, response, `valid` and `error`.
  3. **Replay cache:** if `rebuild` is set and an earlier valid extraction exists for the same `(stage, unit_id, prompt_sha256)`, return it without calling the model.
  4. Concurrency: an async semaphore (default 8) plus exponential backoff on rate limits.
- **Files:** `llm/client.py`
- **Done when:** unit tests with a fake provider cover a valid response, a retry, a failure, and a replay cache hit.

---

## Phase 2 — Collect and register

### 2.1.1 Collector with allowlist

- **Depends on:** 1.1.2, 1.2.2
- **Parallel with:** 2.1.2 (after this task's interface is merged), 2.2.1
- **Read first:** SPEC §2 (profile detection), §3 stage 1, §11 (the allowlist block, verbatim); CORPUS §0.1 ("Information barriers"), §0.3 (folder layout)
- **Build:**
  1. `collect/allowlist.py`: ALLOW and DENY glob lists copied verbatim from SPEC §11, with `is_allowed(rel_path) -> bool`. **DENY always wins.**
  2. `collect/collector.py`: `collect(ctx) -> list[SourceFile]`. It walks `CORPUS_ROOT`, keeps allowed files, and logs every denied path (counted in `ctx.stats["denied_paths"]`; first 50 recorded as info issues).
  3. `SourceFile` has `rel_path`, `abs_path`, `sha256`, `size`, `doc_id` (from the `corpus/docs/<DOC_ID>/` folder, or None for global files) and `profile`.
  4. Profile detection (SPEC §2) uses structure only:
     - `.md` whose first line is `---` → P1
     - `.csv` with a `clause_id` header → P2
     - other `.csv` → P3
     - files under `_global/` that are not under `_global/ops/` → P4
     - `_global/ops/*.csv` → P3
     - `render/**` → `RENDER` (stored, not parsed)
     - YAML under `_global/` → P4
  5. Upload every allowed file to R2 under its SPEC §10 raw key (`global/{run_id}/…` for global files). The version of a docs file comes from its front matter (P1) or its sibling `.md` front matter (P2, P3, renders), so P1 files are read first.
- **Files:** `collect/allowlist.py`, `collect/collector.py`
- **Done when:**
  - unit tests: every DENY pattern blocks a sample path, including `corpus/docs/X/X.basis.json`, `corpus/docs/X/data/README.md`, `corpus/docs/X/data/_manifest.json` and `corpus/grounding/T10.json`
  - a corpus test: zero denied files reach R2, and `denied_paths > 0`

### 2.1.2 Reference data loaders (P4)

- **Depends on:** 2.1.1, 1.2.1
- **Parallel with:** 2.2.1
- **Read first:** SPEC §2 (P4), §4 (`companies`, `people`, `company_attributes`); CORPUS T01 (`applicability_attributes` block), T02 (people CSV columns), T03 (document register columns)
- **Build:**
  1. `collect/reference.py` loads:
     - `company_profile.yaml` → `companies` (name) and `company_attributes` (one row per key under `applicability_attributes`; typed into `value_text`/`value_num`/`value_bool`; `source` = `company_profile.yaml:applicability_attributes`)
     - `people_directory.csv` → `people`; parse `oncall_roles` (`;`-separated) and `alternate_person_id`
     - `document_register.csv` → kept in memory as `RegisterEntry` objects for 2.2.1, not stored as its own table
  2. Load generically: map columns by header name, and log unknown headers as info, not errors.
  3. `org_chart.md` and `company_fact_sheet.md` are stored in R2 only. They are not parsed.
- **Files:** `collect/reference.py`
- **Done when:** a corpus test loads 27 people and at least 20 attributes, and `customer_count_total` is stored as a number.

### 2.2.1 Front-matter parser and document registration

- **Depends on:** 2.1.1, 1.2.1
- **Parallel with:** 2.1.2
- **Read first:** SPEC §3 stage 1, §4 (`company_documents`, `document_versions`); CORPUS §3.1 (front-matter keys, two-signature documents with `approver: null`), §1.4 (register columns)
- **Build:**
  1. `parse/front_matter.py`: `split_front_matter(md_text) -> (dict, body_text, body_offset)`. `body_offset` is the character offset where the body starts, which keeps clause offsets file-relative.
  2. `collect/register_docs.py`: for each P1 file, upsert `company_documents` and insert a `document_versions` row:
     - `owner_id`, `reviewer_id` and `approver_id` come from the nested `{id: ...}` objects; `approver` can be null
     - `regulatory_basis` is copied as a list, as written
     - `source_r2_key` and `render_r2_keys` are set
     - `ingest_status = 'pending'`
  3. Cross-check against the `document_register.csv` entries from 2.1.2: title, version, effective/approved dates and the three role IDs. Each mismatch is a **warning** naming the field; the front matter wins.
  4. **Skip rule:** if a `document_versions` row exists with the same `file_sha256` and `ingest_status = 'ingested'`, and `rebuild` is off, mark the document *unchanged* in `ctx`. Later stages skip it.
  5. `doc_class` is a provisional value from structure (has a `clause_id` CSV → `register`; has `<!-- sheet:` markers → `tariff`; otherwise `procedure`). It is refined by the LLM in 5.1.1. No doc-ID branching.
- **Files:** `parse/front_matter.py`, `collect/register_docs.py`
- **Done when:** a corpus test registers 12 documents, T15 and T17 have `approver_id IS NULL`, and re-running causes no new versions.

---

## Phase 3 — Segmentation

### 3.1.1 Markdown clause segmenter (P1)

- **Depends on:** 2.2.1, 1.3.1
- **Parallel with:** 3.2.1, 7.1.1
- **Read first:** SPEC §3 stage 2 (P1 bullet), §5 (`clauses` DDL; deterministic fields; `unit_kind` and `section_kind`); CORPUS §3.2 (clause-ID grammar, markers, boundaries) and §3.3 (standard section order)
- **Build:**
  1. `parse/markdown_segmenter.py`: `segment(version, body_text, body_offset) -> list[ClauseUnit]`.
  2. Run a single linear scan over the body that tracks:
     - the heading stack, as `heading_path` (heading text without `#`)
     - the current `<!-- sheet: n -->` value
     - the current `<!-- table: ID -->` value
  3. **Clause boundaries:** a clause starts at the line after `<!-- clause: ID -->` and ends right before the next clause, table or sheet marker, the next heading of the same or higher level, or the end of the body. Store the clause's exact raw text and file-relative `char_start`, `char_end` and `line_start`.
  4. **Tables:** after `<!-- table: TID -->`, parse the following pipe table. Each data row becomes a unit with `clause_id = <DOC_ID>:<ID-cell value>`, `table_id = TID`, `row_cells = {header: cell}`, and the raw row line as its text.
  5. **ID grammar → `unit_kind`** (regexes from CORPUS §3.2):
     - `App-[A-Z]\.F\d+` → `form_field`
     - `App-[A-Z](\.\d+){0,2}` → `appendix`
     - `T\d+-\d+` and table rows → `table_row`
     - `R\d+\.\d+(\([a-z0-9]+\))?` and `R\d+\.T-\d+` → `tariff_subrule`
     - `\d+(\.\d+){0,3}[a-z]?` → `section`

     An ID that matches none of these is an **error** issue and is still stored with `unit_kind = 'section'`.
  6. `parent_clause_id`: drop the last ID segment and use it if that clause exists in the document; otherwise use the nearest enclosing clause before it.
  7. `section_kind`: match the top-level heading against a keyword map (purpose, scope, definitions, regulatory basis, roles, procedure, records, training, related documents, revision history, approval, appendix). Default `procedure` under numbered body sections, `other` elsewhere.
  8. Mermaid code blocks stay inside the clause text and are flagged `has_mermaid` in `row_cells` (a jsonb flag). They are not parsed.
  9. Text between a heading and the first marker (not in any clause) is recorded as an `unclaimed_text` metric, used by acceptance check 1.
- **Files:** `parse/markdown_segmenter.py`
- **Done when:**
  - unit tests with inline Markdown cover nested clauses, a table, a sheet marker, a form field, a tariff sub-rule and unclaimed text
  - a corpus test: for each document, clause count = clause markers + table data rows; zero duplicate IDs; slicing the file at the offsets reproduces every clause's `text_raw`

### 3.2.1 Register-row segmenter (P2)

- **Depends on:** 2.2.1
- **Parallel with:** 3.1.1, 7.1.1
- **Read first:** SPEC §2 (P2), §3 stage 2 (P2), §8.1; CORPUS §3.5 (CSV format), T10 (register and controls columns), T11 (calendar columns), T12 (schedule columns)
- **Build:**
  1. `parse/register_segmenter.py`: `segment_register(version, csv_path) -> list[ClauseUnit]`. Read with the `csv` module (RFC 4180, UTF-8), never pandas type inference.
  2. One unit per row:
     - `clause_id` from the `clause_id` column, as-is
     - `unit_kind = 'register_row'`
     - `table_id = <file stem>`
     - `row_cells` holds every column as a string
     - `text_raw` = the row rendered as `column: value` lines, in header order, skipping empty cells
     - `heading_path = [<document title>, <file stem>]`
  3. A row's `char_start`/`char_end` are offsets inside the rendered `text_raw`, not the CSV, and this is documented in the code. Parameter verification (4.1.2) runs against `text_raw`.
  4. Apply the header rules from SPEC §8.1 to produce provisional `table_columns` rows with `role_method = 'header_rule'`. Unresolved headers get role `null`, to be filled in by 5.2.1.
- **Files:** `parse/register_segmenter.py`
- **Done when:** a corpus test checks that T10 rows fall in 150–260 (CORPUS T10), T11 in 45–90 and T12 in 120–180, with all `clause_id`s unique and every value of the `citation` column given a header-rule role of `citation`.

---

## Phase 4 — Deterministic enrichment (W5, all parallel)

All 4.1.x tasks share the same interface: `enrich_x(units: list[ClauseUnit], ctx) -> None`. Each one appends to its own attribute on `ClauseUnit` (`citations`, `parameters`, `refs`, `role`, `terms`). A task never edits another task's attribute.

### 4.1.1 Citation extraction and resolution

- **Depends on:** 3.1.1, 3.2.1, 1.3.2
- **Parallel with:** 4.1.2–4.1.5, 7.1.2
- **Read first:** SPEC §6.1 (DDL and bullets), §3 stage 3; `DATA_MODELS` (CodeSection: citation, snapshot date, status, effective dates)
- **Build:**
  1. For P1 units, call `find_citation_spans` on `text_raw` and parse each span. For P2 units, parse the cell of every column whose role is `citation`, with `context = 'register_column'` and span offsets inside `text_raw`.
  2. `context`:
     - `regulatory_basis_table` when the unit's `section_kind = regulatory_basis`
     - `front_matter` for the version's `regulatory_basis` list (stored against a synthetic document-level unit `<DOC_ID>:_front_matter`, `unit_kind='section'`, `section_kind='front_matter'`, role `boilerplate`)
     - `inline` otherwise
  3. **Resolution:**
     - IAC citations: find the CodeSection whose citation equals `normalized_key` and which is active on the version's `law_as_of` (that is, the Snapshot 1 row).
     - `resolution_status`:
       - `resolved` when found and active
       - `repealed_at_s1` when found but repealed or expired
       - `not_found` otherwise
       - `external` for non-IAC sources (`in_knowledge_base = false`)
     - Rule-level citations (`granularity = 'rule'`) resolve to null `code_section_id` but keep `rule_key`.
     - Expanded ranges produce one row per section.
  4. Cache CodeSection lookups in memory per run.
- **Files:** `enrich/citations.py`
- **Done when:**
  - unit tests with a stub CodeSection repository
  - a corpus test: ≥ 99% of IAC citations resolve; the unresolved list is written as warnings with `clause_id` and raw text

### 4.1.2 Numeric and unit parameter extraction (regex pass)

- **Depends on:** 3.1.1, 3.2.1, 1.3.1
- **Parallel with:** 4.1.1, 4.1.3–4.1.5, 7.1.2
- **Read first:** SPEC §6.2 (DDL, regex-pass bullet, value-source rule); CORPUS §2.2 (what counts as a parameter: numbers, day types, comparison words), §3.4 (numeral normalization)
- **Build:**
  1. `enrich/parameters_regex.py` finds spans for:
     - numbers (digits, words, "ten (10)")
     - money (`$45.00` → 45.00, unit `usd`)
     - percentages
     - clock times (`08:00`)
     - ISO dates
     - number + unit pairs within 4 tokens
  2. Unit map to canonical units: day(s), business day(s), hour(s)/hrs, minute(s), month(s), year(s), percent, gallon(s)/gal, kVA, kV, customer(s), meter(s), mile(s), $. A bare number with no unit is kept as `kind='number'` only if the clause cites a regulation; otherwise it is dropped. This keeps phone numbers, IDs and counts out.
  3. `day_type` comes from a day-type word directly before the unit (business, calendar, working). It is `hours` for hour units and `n_a` otherwise.
  4. `qualifier` comes from the 6 tokens before the number, using a phrase map: within, at least, not less than, not more than, no later than (→ `not_more_than`), prior to, after, exactly.
  5. `kind`:
     - `amount` for usd
     - `period` for day/hour/minute/month/year paired with a qualifier
     - `deadline` when the text includes "by", "no later than", "due"
     - `frequency` for "every", "per", "annually", "each year"
     - `threshold` for "or more", "exceeds", "greater than"
     - `record_retention` when the same sentence has "retain" or "keep"
     - `number` otherwise
  6. **Never extract from:** CIS codes, form IDs, phone numbers (the `\d{3}-\d{3}-\d{4}` and 1-800 patterns), clause IDs, sheet numbers, citation spans (from 4.1.1's spans, or re-detect them), or IDs such as `OBL-0042`.
  7. Every parameter gets `method='regex'`, `verified=True` only if `find_verbatim` finds `value_text` at its offsets, and `value_source` per the SPEC §6.2 rule. That rule needs the role (4.1.4) and citations (4.1.1), so compute `value_source` at commit time (8.1.2) and leave it null here.
- **Files:** `enrich/parameters_regex.py`
- **Done when:** at least 40 unit cases (true positives and the excluded patterns above), and a corpus test with zero unverified regex parameters.

### 4.1.3 Reference extraction (documents, clauses, tariff, forms, series, obligations)

- **Depends on:** 3.1.1, 3.2.1
- **Parallel with:** 4.1.1, 4.1.2, 4.1.4, 4.1.5, 7.1.2
- **Read first:** SPEC §7 (link-type table, columns "Found by" and "Example"), §8.1 (`reference_list` columns); CORPUS §1.5–§1.6 (form IDs, record series IDs, tariff references, ID formats)
- **Build:**
  1. `enrich/references.py` extracts raw references into `unit.refs` as `(ref_type, raw, span, target_hint)`. Nothing is resolved yet; that happens in 6.1.1.
  2. Patterns (generic shapes only, never a hard-coded list of IDs):
     - document ID: a token matching the shape of IDs in `company_documents` (build the regex from the registered doc IDs at runtime)
     - clause reference: `<DOC_ID>:<local>` and `<DOC_ID> §<n>` / `§<n>` (the latter is same-document)
     - tariff: `Rule \d+`, `Sheet(?: No\.?|s| Nos\.?) \d+(?:[–-]\d+)?`
     - form: `[A-Z]{2,4}-F-\d{3}(?:-[A-Z]{2})?`
     - record series: `RRS-[A-Z]{2,4}-\d{3}`
     - obligation: `OBL-\d{4}`
     - control: `CTL-[A-Z]+-\d{3}`
     - calendar row: `CAL-\d{4}-\d{3}`
  3. For P2 units, every cell of a `reference_list` column is split on `;` or `,` and each item becomes a ref with `ref_type` inferred from its shape.
- **Files:** `enrich/references.py`
- **Done when:** unit tests cover each pattern, and a corpus test finds at least one `references_form` and one `references_tariff` in every procedure document.

### 4.1.4 Deterministic clause-role markers

- **Depends on:** 3.1.1, 3.2.1
- **Parallel with:** 4.1.1–4.1.3, 4.1.5, 7.1.2
- **Read first:** SPEC §5 (clause-role table; the "Decided by" column)
- **Build:**
  1. `enrich/roles.py` sets `role` and `role_method` on a unit when a deterministic rule decides it. Apply rules in the order of the SPEC §5 table:
     - text starts with `Internal performance target:` → `internal_target`
     - text starts with `Company position:` → `company_position`
     - `unit_kind = form_field` → `template_field`
     - inside a Definitions section, or the text matches `^\*\*.+?\*\*\s+(means|is)` → `definition`
     - `section_kind` in {`revision_history`, `approval`, `related_docs`, `front_matter`} → `boilerplate`
  2. Undecided units keep `role=None` for 5.1.1.
  3. Set `assessable`:
     - false for `boilerplate`, `informational` and `out_of_scope_reference`
     - true for the other decided roles
     - provisional `true` for undecided units
- **Files:** `enrich/roles.py`
- **Done when:** unit tests cover each rule and the rule priority (a form field starting with "Company position:" is `company_position`).

### 4.1.5 Defined terms and term usages

- **Depends on:** 3.1.1, 3.2.1, 4.1.1 (interface only: uses its spans to skip citations)
- **Parallel with:** 4.1.1–4.1.4, 7.1.2
- **Read first:** SPEC §6.3 (DDL and bullets)
- **Build:**
  1. Extract terms from Definitions-section units: table rows (first column = term), `**Term** means…` and `"Term" means…`. Store `term`, `term_norm` (normalized, singular) and `definition_clause_pk`, and set `cites_regulatory_definition` when the unit has a resolved citation.
  2. Usages: whole-word, case-insensitive matching of each `term_norm` and its simple plural, across all units of **all** documents in the run. Store `(term_pk, clause_pk, occurrences)`. Skip the defining clause itself.
  3. **Regulatory terms.** For each CodeSection the corpus cites whose heading contains "Definitions" (query via the same repository as 4.1.1), extract defined terms from its Snapshot 1 text with the same patterns, and store them as `defined_terms` rows with `doc_id = '_regulatory'` and `cites_regulatory_definition = true`. Store their company usages the same way. This is the input to the engine's definition-ripple rule.
- **Files:** `enrich/terms.py`
- **Done when:** a corpus test checks that every procedure document has ≥ 14 company terms and that at least one regulatory term has ≥ 3 usages across ≥ 2 documents.

---

## Phase 5 — LLM enrichment

### 5.1.1 Stage 4a schema and prompt (per-clause enrichment)

- **Depends on:** 4.1.1–4.1.5, 1.3.3
- **Parallel with:** 5.2.1, 7.2.1
- **Read first:** SPEC §5 (stage 4a contract, role table, `normalized_statement`, `topic_terms`), §6.2 (semantic parameter kinds; one `content_element` row per required element), §1 principles 2–3
- **Build:**
  1. `llm/schemas.py` defines pydantic models:
     - `ClauseEnrichment { clause_role: ClauseRole | None, normalized_statement: str | None, topic_terms: list[str] (≤ 6), parameters: list[SemanticParam], citation_links: list[{parameter_index: int, citation_raw: str}] }`
     - `SemanticParam { kind: one of condition|exception|party|channel|content_element|applicability, name: str, value_text: str }`
  2. `llm/prompts/clause_enrichment.md` is the system prompt. It must state:
     - the role definitions, copied from the SPEC §5 table
     - `regulatory_restatement` requires a citation in the clause
     - every `value_text` must be copied character for character from the clause text
     - one `content_element` per required element of a notice, report or record
     - return null for anything not stated
     - never infer values from outside the clause
  3. User-message builder: `clause_id`, `heading_path`, the parent clause's lead-in (first 400 characters), the clause text (or rendered row), the deterministic citations and numbers found, and the provisional role if any.
  4. **Selection:** call for units where the role is undecided, **or** the role is one of `definition`/`template_field`/`internal_target`/`company_position` (to get semantic parameters and the statement). Skip `boilerplate`.
  5. **Split rule:** if the clause text exceeds 1,500 tokens, split at top-level list items into child units `#1`, `#2`… sharing the parent `clause_id` plus a suffix (SPEC §5 budget bullet).
  6. Add `doc_class` refinement as one extra call per document: the first 2,000 characters plus the heading outline go in, `doc_class` from the SPEC §4 enum comes out.
- **Files:** `llm/schemas.py`, `llm/prompts/clause_enrichment.md`, `llm/prompts/doc_class.md`, `llm/clause_enrichment.py` (builders only)
- **Done when:** a snapshot test of the rendered prompt for 3 fixture clauses, plus schema round-trip tests.

### 5.1.2 Stage 4a runner and verification

- **Depends on:** 5.1.1
- **Parallel with:** 6.1.1, 6.1.3, 7.2.2
- **Read first:** SPEC §5 (rules bullet), §6.2 (`verified`, `method='llm'`), §12 checks 5–6
- **Build:**
  1. `llm/run_clause_enrichment.py` runs all selected units through `call_structured` with concurrency.
  2. **Post-verification (code):**
     - for each `SemanticParam`, find `value_text` in the clause with `find_verbatim`; on success store the offsets and `verified=True`; on failure drop it and record an info issue `param_not_verbatim`
     - `citation_links` must name a citation already found by 4.1.1; anything else is dropped
     - apply `clause_role` only if the role is undecided
     - if the role is `regulatory_restatement` but the unit has no resolved citation, downgrade it to `internal_procedure` and raise a warning (acceptance check 5)
  3. Recompute `assessable` from the final role (SPEC §5 table). `internal_procedure` is assessable only if it later gets a `restates` link (finalized in 6.1.2).
  4. When `ctx.no_llm` is set: skip the calls, set undecided roles to `internal_procedure` when there is no citation and `regulatory_restatement` when there is, and set `role_method='heuristic'`.
- **Files:** `llm/run_clause_enrichment.py`
- **Done when:** unit tests with a fake LLM cover a dropped non-verbatim value, a downgraded role and the `--no-llm` path; a corpus smoke test on one document.

### 5.2.1 Stage 4b — register column roles

- **Depends on:** 3.2.1, 1.3.3
- **Parallel with:** 5.1.1, 7.2.1
- **Read first:** SPEC §8.1 (column roles, header rules, row assembly)
- **Build:**
  1. One `call_structured` per P2 file whose `table_columns` still have null roles. Input: the headers, provisional roles and 5 sample rows. Output: `{column_name: column_role}` for the null ones only.
  2. Update `table_columns` (`role_method='llm'`).
  3. Then trigger row assembly for the newly classified columns:
     - `citation` → re-run 4.1.1 for those cells
     - `regulatory_value`/`rule_quote` → re-run 4.1.2 and include the cell in 5.1.x semantic extraction
     - `reference_list` → re-run 4.1.3

     Implement this as calls to the existing functions, restricted to those columns.
- **Files:** `llm/run_column_roles.py`, `llm/prompts/column_roles.md`
- **Done when:** a corpus test leaves no null roles, and `key_parameters` (T10), `due_rule` (T11) and `regulatory_minimum` (T12) are `regulatory_value` or `rule_quote`.

---

## Phase 6 — Linking and indexing

### 6.1.1 Resolve references into `clause_links`

- **Depends on:** 4.1.3 (and the clause units of every document in the run)
- **Parallel with:** 5.1.2, 6.1.3, 7.2.2
- **Read first:** SPEC §7 (DDL, link-type table), §11 (ingest order: registers after prose)
- **Build:**
  1. `link/resolve_refs.py` builds lookup indexes:
     - clause IDs per document
     - tariff `sheet_no` → clauses and `R<n>.` prefix → clauses
     - form ID → the appendix clause whose heading (or first line) contains that form ID
     - series ID → the T12 row with that `clause_id` suffix
     - `OBL-` → the T10 row
     - doc IDs → `company_documents`

     Build every index from data, never from constants.
  2. Turn each `unit.refs` entry into a `clause_links` row with the SPEC `link_type`, `method='regex'` or `'register_column'`, `evidence` = the raw string and `confidence=1.0`. `§<n>` without a document means the same document. A sheet range links to every clause on those sheets.
  3. Unresolved targets become warnings (acceptance check 7), and no link row is written.
- **Files:** `link/resolve_refs.py`
- **Done when:** a corpus test resolves every `implementing_documents` and `source_procedure` cell, or lists it in issues.

### 6.1.2 `restates` links

- **Depends on:** 5.1.2, 6.1.1, 6.2.1 (embedding function only — import it, do not index)
- **Parallel with:** 7.2.3
- **Read first:** SPEC §7 (`restates` rule; the three conditions and confidence)
- **Build:**
  1. Group verified parameters by `(kind, value_num, unit, day_type, qualifier)`.
  2. For each pair of clauses in a group (different clauses), check the scope condition from SPEC §7: either the same cited section, or one side has no citation and both are in the same document or in documents connected by any `clause_links` edge.
  3. Embed both `normalized_statement`s (or the clause text if null) with the shared embedding function. Keep the pair if cosine ≥ 0.6, and write two directed `restates` links with `method='parameter_match'` and `confidence` = cosine.
  4. Finalize `assessable` for `internal_procedure` clauses: true if they have a `restates` link to an assessable clause.
  5. Guard: cap groups at 200 members (log if exceeded) to avoid quadratic blow-up on common values like "1".
- **Files:** `link/restates.py`
- **Done when:** unit tests cover the scope conditions, and in a corpus test every procedure document has ≥ 1 body↔template-field `restates` link.

### 6.1.3 `document_scope` rollup

- **Depends on:** 4.1.1
- **Parallel with:** 5.1.2, 6.1.1, 7.2.2
- **Read first:** SPEC §7 (`document_scope` DDL and rollup bullets)
- **Build:**
  1. For each document version, take the union of front-matter `regulatory_basis`, citations in `regulatory_basis` section units, and every resolved citation, at both section and rule level.
  2. Write rows with `sources` (array of the contributing sources) and `clause_count` (clauses citing that key).
- **Files:** `link/document_scope.py`
- **Done when:** a corpus test checks that every document has ≥ 1 rule-level row and every front-matter entry appears (acceptance check 8).

### 6.2.1 Embeddings and Qdrant indexing

- **Depends on:** 1.2.3, 5.1.2 (for payload fields); 6.1.2 imports its embedding function
- **Parallel with:** 6.1.2, 7.2.3
- **Read first:** SPEC §9 (embedded text template, BM25, point ID, payload table, what is not embedded); `INFRA` (embedding provider used for the regulatory collection)
- **Build:**
  1. `index/embed.py`: `embed_texts(list[str]) -> list[list[float]]` using `EMBED_MODEL` (the same model and dimension as the regulatory collection; reuse the regulatory side's embedding helper if one exists), batched with retry.
  2. `index/bm25.py`: a sparse vector per clause. Use Qdrant's built-in BM25 / FastEmbed sparse model if available in the installed client; otherwise a simple hashed term-frequency vector over normalized tokens, documented.
  3. `index/upsert.py`:
     - builds the embedded text exactly as the SPEC §9 template states
     - builds the payload with every field in the table (`cited_sections` and `cited_rules` from resolved citations; `param_kinds` and `param_units` from verified parameters; `terms_used` from `term_usages`)
     - point ID = `stable_uuid(company_id, version_id, clause_id)`
     - upserts in batches of 128
     - for documents with a new version, sets `is_current=false` on the previous version's points via a payload filter update
  4. Skip what SPEC §9 says is not embedded.
- **Files:** `index/embed.py`, `index/bm25.py`, `index/upsert.py`
- **Done when:** a Qdrant integration test round-trips 20 random clause IDs to Neon rows (acceptance check 11), and a filtered search by `cited_sections` returns only matching clauses.

---

## Phase 7 — Datasets (Phase B; tasks 7.1.1–7.1.2 can start early)

### 7.1.1 Dataset profiling and Parquet conversion

- **Depends on:** 2.1.1, 1.2.1, 1.2.2
- **Parallel with:** 3.1.1, 3.2.1
- **Read first:** SPEC §8.2 (`datasets`, `dataset_columns` DDL; profiling bullet; storage note), §10 (`derived/.../datasets/{name}.parquet`); CORPUS §3.5 (CSV conventions: dates, `utc_offset`, empty string = null, `.csv.gz` allowed)
- **Build:**
  1. `datasets/profile.py`: read each P3 CSV (and `.csv.gz`) with pyarrow's CSV reader. Empty strings are null. Infer types, but parse `YYYY-MM-DD` as date and `YYYY-MM-DDThh:mm` as timestamp (local time, kept as written; keep `utc_offset` as its own column).
  2. Write Parquet with zstd compression to the SPEC §10 key (`derived/global/ops/` for `_global/ops`).
  3. Profile every column: `dtype`, `null_rate`, `distinct_count`, `min_value`, `max_value` and `top_values` (top 10 with counts, for columns with ≤ 50 distinct values).
  4. `datasets` row: `doc_id` from the folder (null for global), `name` = file stem, `row_count`, `file_sha256`. `primary_key` is the first column that is unique and non-null and whose name ends in `_id` or `_serial`; otherwise null.
- **Files:** `datasets/profile.py`
- **Done when:** a corpus test checks that Parquet row counts equal CSV row counts for every dataset (acceptance check 9, part 1), and that the meter registry converts in under 2 minutes on the dev machine.

### 7.1.2 Key and clause-reference detection

- **Depends on:** 7.1.1, 3.1.1
- **Parallel with:** 4.1.x
- **Read first:** SPEC §8.2 (profiling bullet: `clause_ref`, `foreign_key`)
- **Build:**
  1. **Foreign keys:** for each column whose name ends in `_id` (or matches another dataset's primary-key name), test containment: ≥ 99% of its non-null values appear in another dataset's primary key. If so, set `semantic_role='foreign_key'` and `fk_target='<dataset>.<column>'`.
  2. **Clause references:** for each string column, test whether ≥ 90% of non-null values match local clause IDs of the dataset's own document (for example `7.2-3` or `7.3.1`). If so, set `semantic_role='clause_ref'` and `fk_target='clause:<DOC_ID>:<prefix>'`. Also write `clause_links`-style metadata: one row per distinct value in a `dataset_clause_refs` jsonb list on `dataset_columns.top_values`, or a small side table if you prefer (document the choice).
  3. Record FK integrity results: values that do not resolve → a warning with a count.
- **Files:** `datasets/keys.py`
- **Done when:** corpus tests detect `circuit_id` → `circuits_master.circuit_id` in T16/T18/T19 datasets, and find a `clause_ref` column in the T20 spill dataset.

### 7.2.1 DuckDB check runner

- **Depends on:** 7.1.1
- **Parallel with:** 5.1.1, 5.2.1
- **Read first:** SPEC §8.2 (`parameter_checks` DDL; storage note: DuckDB in the FastAPI service, read-only)
- **Build:**
  1. `datasets/duckdb_runner.py`: `run_check(sql_template, params: dict, datasets: dict[name, parquet_uri]) -> CheckResult`.
     - Register each Parquet as a view named after the dataset (read via `httpfs` with R2 credentials, or from a local cache directory keyed by sha256).
     - Substitute `{name}` placeholders **only** with typed literals: numbers as numeric literals, durations as `INTERVAL` built from value + unit, strings quoted and escaped.
     - Reject templates containing anything other than a single `SELECT`/`WITH` statement (no `;`, `COPY`, `ATTACH`, `INSTALL`, `PRAGMA`, `CREATE`).
  2. `CheckResult`: `violation_count`, `affected_count`, up to 20 sample rows, and the elapsed time.
  3. 30-second timeout per check.
- **Files:** `datasets/duckdb_runner.py`
- **Done when:** unit tests cover placeholder substitution for each unit type and rejection of unsafe SQL; an integration test runs a count over a fixture Parquet.

### 7.2.2 Stage 4c — LLM-proposed dataset descriptions and parameter checks

- **Depends on:** 7.1.2, 7.2.1, 5.1.2 (needs verified parameters), 6.1.1 (needs links to find describing clauses)
- **Parallel with:** 6.1.3
- **Read first:** SPEC §8.2 (stage 4c bullet; the `parameter_checks` columns; the change-time use)
- **Build:**
  1. **Describing clauses for a dataset:**
     - clauses in the same document whose text names the dataset's file name, a form or record series that the dataset's columns reference, or one of its column names
     - plus clauses linked by `clause_ref` columns

     Cap at 25 clauses, preferring those with verified parameters.
  2. One `call_structured` per dataset. Input: the column profile (no raw rows except `top_values`), the describing clauses with their parameters (each with `parameter_pk`, `kind`, `value_text`, `value_num`, `unit`, `qualifier`), and the runner's placeholder rules. Output schema:
     - `description`
     - per-column `semantic_role` and `description`
     - `checks: list[{purpose, sql_template, param_bindings: {placeholder: parameter_pk}}]`, 0–5 checks; each check returns rows that would **violate** or be **newly in scope** for the bound parameter values
  3. Store the proposals with `validated=false`, `method='llm_proposed'`.
- **Files:** `datasets/propose_checks.py`, `llm/prompts/parameter_checks.md`
- **Done when:** a corpus smoke test on the T20 and T19 datasets stores ≥ 1 proposal each, with every placeholder bound to an existing verified `parameter_pk`.

### 7.2.3 Snapshot 1 validation of parameter checks

- **Depends on:** 7.2.2
- **Parallel with:** 6.1.2, 6.2.1
- **Read first:** SPEC §8.2 ("Validating a check against Snapshot 1"), §12 check 10
- **Build:**
  1. For each proposed check, bind each placeholder to its parameter's **document value** (which equals the Snapshot 1 value by corpus construction) and run it.
  2. Keep the check (`validated=true`, `s1_result` stored) only if all three hold:
     - it runs
     - for violation-type checks, `violation_count = 0`
     - if the dataset has a computed flag column whose name and profile match the check's purpose (`reportable`, `within_limits`, `iurc_reportable`, or any `Y|N` column the stage 4c description links to the purpose), the check's selected set equals the rows with that flag set (exact match by primary key)
  3. Failed checks stay in the table with `validated=false` and an issue describing which test failed. They are never used by the engine.
- **Files:** `datasets/validate_checks.py`
- **Done when:** a corpus test leaves ≥ 1 validated check for each of the T19 and T20 datasets, and every validated check reproduces its flag column exactly.

---

## Phase 8 — Validate, commit, orchestrate

### 8.1.1 Acceptance checks

- **Depends on:** all of Phases 3–6 (7.x optional, behind a flag)
- **Parallel with:** —
- **Read first:** SPEC §12 (all 12 checks with pass conditions)
- **Build:**
  1. `validate/checks.py`: one function per check, `check_n(run_state, ctx) -> CheckOutcome{passed, metric, details}`, numbered as in SPEC §12.
  2. Checks 9 and 10 run only when datasets are enabled. Check 11 runs after indexing. Check 12 reads the collector's stats and the R2 keys written in this run.
  3. `run_all_checks` returns the outcomes. Any failure blocks the commit.
- **Files:** `validate/checks.py`
- **Done when:** each check has a unit test with a passing and a failing fixture.

### 8.1.2 Commit, clause snapshot and report

- **Depends on:** 8.1.1
- **Parallel with:** —
- **Read first:** SPEC §3 stage 7, §10 (`clauses.jsonl`, `report.json`), §11 (versioning bullets), §6.2 (value-source rule)
- **Build:**
  1. Compute `value_source` for every parameter (SPEC §6.2 rule), using the final role and citations.
  2. In one Neon transaction, write all rows for the run's changed document versions (`clauses`, citations, parameters, terms, usages, links, scope, table columns, datasets, columns, checks) and set `document_versions.ingest_status='ingested'` and `ingested_at`. Use bulk `COPY` or batched inserts.
  3. On check failure: no transaction. Set `ingest_status='failed'` and still write `report.json`.
  4. Write `derived/{doc_id}/{version}/clauses.jsonl`, one JSON object per clause with nested citations and parameters, sorted by `clause_id`.
  5. Write `ingest_runs/{run_id}/report.json` from `ctx.to_report()` plus the check outcomes and counts by document. Insert the `ingest_runs` row.
  6. `--rebuild`: rebuild the clause tables for a version from `clauses.jsonl` plus the cached LLM outputs (1.3.3 replay), without new model calls unless `--refresh-llm` is given.
- **Files:** `store/commit.py`, `store/snapshot.py`
- **Done when:** an integration test commits two documents; a forced check failure leaves Neon unchanged; a rebuild produces identical rows (compare hashes).

### 8.2.1 `ingest` CLI and orchestration

- **Depends on:** 8.1.2
- **Parallel with:** —
- **Read first:** SPEC §3 (stage order), §11 (ingest order 1–5), §12 (build order and phases); this file §1 (milestones)
- **Build:**
  1. `cli/ingest.py` provides the command `python -m app.company_ingest.cli.ingest [--no-llm] [--no-datasets] [--rebuild] [--refresh-llm] [--only DOC_ID ...]`.
  2. Steps follow SPEC §11:
     1. collector
     2. reference data
     3. registration
     4. segment P1 then P2 (P2 after all P1 of the run)
     5. 4.1.x enrichment
     6. 5.x (unless `--no-llm`)
     7. 6.1.1, 6.1.3, 6.1.2
     8. datasets 7.x (unless `--no-datasets`)
     9. 6.2.1
     10. checks
     11. commit
  3. Print a one-screen summary: documents processed / skipped / failed, clause count, citations resolved %, parameters verified, links by type, checks passed/failed, and the R2 report key.
  4. `--only` restricts processing to the named documents but still loads every other current document's clause IDs from Neon, so cross-document links resolve.
  5. Exit code is non-zero if any check fails.
- **Files:** `cli/ingest.py`
- **Done when:**
  - `--no-llm --no-datasets` passes all applicable checks on the full corpus (Phase A milestone)
  - a second identical run reports all documents skipped

---

## Phase 9 — Evaluation

### 9.1.1 Offline quality evaluation (developer-only)

- **Depends on:** 8.2.1 (a full run with LLM)
- **Parallel with:** 9.1.2
- **Read first:** SPEC §12 ("Offline quality check"); CORPUS §3.4 (basis schema: `clause_type`, `parameters`)
- **Build:**
  1. Create `tools/offline_eval/compare_basis.py` **outside** `backend/app/` so the ingest service can never import it. It is the only code allowed to read `*.basis.json`, and its README must say so.
  2. Join basis clauses to `company.clauses` by `clause_id`, then report:
     - role agreement (engine `clause_role` vs basis `clause_type`), with a confusion matrix
     - parameter recall on basis `regulatory_restatement` clauses: a basis parameter counts as found if an engine parameter in the same clause has an overlapping span or equal `value_text` after normalization
     - citation agreement: basis `citations` ⊆ engine resolved citations
  3. Write `tools/offline_eval/out/report_<run_id>.md`.
- **Files:** `tools/offline_eval/**`
- **Done when:** the report runs. The targets (role agreement ≥ 90%, parameter recall ≥ 95%) are tracked, not enforced; report them to the user with the top misses.

### 9.1.2 End-to-end corpus test

- **Depends on:** 8.2.1
- **Parallel with:** 9.1.1
- **Read first:** SPEC §12 (all checks); this file §1 (milestones)
- **Build:**
  1. `backend/tests/company_ingest/test_e2e_corpus.py` (marked `corpus`, `qdrant`, `neon`) runs the CLI in three configurations against a fresh schema and collection prefix (`company_test_*`):
     - `--no-llm --no-datasets`
     - full LLM with `--no-datasets`
     - full
  2. It asserts all SPEC §12 checks pass in each configuration and that the counts in the report are within the expected ranges stated in tasks 3.1.1, 3.2.1, 4.1.1 and 4.1.5.
- **Files:** the test file and a fixture for the test schema/collection prefix
- **Done when:** all three configurations pass.

---

## 10. After this plan

The engine (change units → candidate clauses → judgment → ledger, discussed separately) depends on this plan only through the tables and the Qdrant collection above. Its first gate is the SPEC §12 "Gate to the engine": a Snapshot 1 engine run that yields zero non-informational findings. That work gets its own implementation plan once ingest passes 9.1.2.

# Detangle Synthetic Data + Real Document Ingestion with Content-Hash Change Detection

> **Status:** approved. Superseded as the authoritative spec by
> `architecture.md`, `TDD.md` and
> `implementation_plan.md`. Retained as the decision record.

## Amendments after approval

**A1 — approved as recommended.** A new version is created `in_review` and ingested; it is promoted to current only when its approval request completes. The "unchanged" check compares against the current version **and** any pending version.

**A2 — redlining is OUT OF SCOPE.** No in-app clause editing in this round. Consequences:

- `company.clause_edits` is **not** created; `POST /company/documents/{doc_id}/edits` and `/edits/{id}/accept` are **not** built; no clause-edit UI, no textarea-per-clause.
- The two entry points become: (1) **upload a new document**, hash-checked company-wide; (2) **upload a new version of an existing document**, hash-checked against that document's current and pending versions.
- D2 simplifies: every version now originates from an uploaded DOCX, so there is no rendered "canonical byte artifact" case and no asymmetry between upload and edit paths.
- Approval workflow is **retained** — it gates promotion of an uploaded new version, which is the standard document-control flow.
- Added requirement: **all existing features must continue to work undisturbed.** The existing suggestion surface (`engine.findings.required_change` + `rationale`), finding accept/reject reviews, what-if, radar, ledger, scorecard, reader and KB views are preserved unchanged. See the regression gate in the implementation plan.

## Context

Strata's company-document side was built in v1 around a hand-authored synthetic corpus ("Rockridge Power & Light", `RPL-*`) living inside the importable application package at `backend/app/company/corpus`. Three problems follow, and this plan fixes all three.

1. **The application reaches into synthetic data at runtime.** `app/api/company/routes.py:23` resolves a path into `app/company/corpus/_global` and opens `document_register.csv` and `company_profile.yaml` on live requests. Ingestion exists only as a batch CLI that walks `CORPUS_ROOT` and classifies files by the corpus's literal directory shape. The synthetic tree cannot be deleted without degrading the API and breaking ~16 tests.

2. **There is no real document intake, and "map to regulations" does not actually work.** No upload endpoint exists (`python-multipart` isn't installed), and no write endpoint touches the `company.*` schema at all. The pipeline calls `enrich_citations` without a `code_section_repo`, so every citation commits as `code_section_id = NULL, resolution_status = 'not_found'`. The 1,284 resolved links in the live database exist **only** because `scripts/backfill_citations.py` was run by hand. A newly uploaded document today would get zero links and silently never map to any regulation.

3. **Re-uploading is "dumb", and real version history would corrupt data.** Content hashes are computed (`collect/collector.py:38,276`) but never compared — the only compare-and-skip, `collect/register_docs.py:260-291`, has zero callers, and it keys on `version_id = stable_uuid(company_id, doc_id, version)`, so a file is only ever compared against its own prior self under the same name. Worse, the storage layer isn't version-safe: child primary keys aren't version-scoped and insert `ON CONFLICT DO NOTHING`, and **no engine or API clause query filters by version**. A second version today would silently drop the new version's citations and double every document's clause set.

**Outcome:** `backend/synthetic/` can be deleted with zero effect on the running application. Documents enter only by customer upload or in-app edit. A document already on file is rejected with a message and nothing is stored. An edit creates an immutable new version which, once approved, becomes current and replaces the single stored hash. Unchanged clauses reuse stored enrichment instead of re-running the LLM.

---

## Decisions locked

| Decision | Choice |
|---|---|
| Accepted upload types | **DOCX only** for documents, plus **CSV** for registers. PDF deferred (see D1) |
| Extraction | `DocumentExtractor` seam; `python-docx` heading styles → Markdown. External structured-extraction API is a later drop-in |
| Duplicate policy | Reject (409), **store nothing** — no R2 object, no row, no job |
| Hash algorithm | SHA-256 over canonically-extracted text (see D2) |
| Hash cardinality | Exactly one per logical document, on `company_documents.current_content_hash`. Superseded versions keep no hash |
| Version identity | System-assigned sequential `version_no`, immutable, never parsed from filename or content |
| Entry points | (1) Upload — new documents, hash-checked company-wide. (2) Edit/redline — new version of a known document |
| CSV registers (P2) | **KEPT as a real feature** (see D3) — only the synthetic ID grammar is replaced |
| Datasets (P3) / `parameter_checks` | **Dropped** — verified 0 rows in production, zero cost |
| Qdrant | Index **only on promotion**; delete-and-replace per document; no `is_current` flag (see D4) |
| Transport | Multipart POST + `BackgroundTasks`, polled like `GET /engine/runs/{id}`. 25 MB cap (512 MB dyno) |
| Cutover | Wipe company + engine data, re-seed by POSTing through the real APIs, re-run the engine, verify parity |
| Auth | None. Explicit "acting as" `person_id` on every write, recorded on approval records |
| `company_id` | From `ENGINE_COMPANY_ID`; `app/config.py`'s duplicate `COMPANY_ID` is deleted |

---

## Key decisions, with the evidence behind them

### D1. DOCX only; PDF deferred

`parse/markdown_segmenter.py` derives *all* structure from Markdown: `_HEADING_RE` on `#` markers, pipe tables, and `clause_id` from numbered headings. Flat text produces one giant clause. Measured on `RPL-CMP-REG-001`, a 17-page PDF rendered from a 20-heading Markdown source:

| Input | Headings recovered |
|---|---|
| Source `.md` | 20 |
| Same document via `pypdf` | **0** |
| DOCX `w:pStyle` (`RPL-CS-PRO-004`) | `Heading1` ×2, `Heading2` ×31 |

So the extractor's output contract is **Markdown**, which keeps the entire downstream pipeline unchanged. DOCX satisfies it via paragraph styles; `pypdf` cannot. PDF uploads return **415** with a message naming DOCX, rather than silently producing one-clause documents.

**`pypdf` stays in `requirements.txt`** — it is used by the regulatory adapters (`app/regulatory/adapters/iurc_gaos.py:191`, `iurc_rulemakings.py:260`, `iurc_investigations.py:97`) and is unrelated to company uploads.

Where no section numbering exists, synthesize `clause_id` local parts (`s1`, `s1.1`, …) from heading depth and ordinal. The `<!-- RPL-…:1.0 -->` anchors that `front_matter.py:237` relies on do not exist in customer documents.

### D2. The hash is over canonically-extracted text, not raw file bytes

An in-app edit produces no DOCX, so raw-byte hashing cannot compare an edit against an upload at all. Hashing the extracted text makes both paths comparable, and additionally catches a document re-saved from Word with identical wording but different bytes — which is precisely the "same content, different metadata" case in objective 3.

Canonical form: extracted text → Unicode NFC → all whitespace runs collapsed to a single space → lines trimmed → leading/trailing blank lines removed.

Extraction is local and cheap, so it still runs before any write, and a duplicate still stores nothing. This is deliberately distinct from `clauses.text_sha256` (an LLM cache key) and R2 object `sha256` metadata (a storage write-once guard); neither is "the document hash".

**Consequence to accept:** re-uploading an *older* version's bytes passes the check, because superseded versions keep no hash (per the one-hash rule). It is recorded as a new change — effectively a revert.

### D3. CSV registers are kept — reversing an earlier recommendation

An earlier draft of this plan proposed deleting the register path as synthetic scaffolding. Measured against the live database, that was wrong. Three real registers (the 10,928-row outage file is **not** one — `_RE_EVT` requires `EVT-\d{4}-\d{4}` and those ids carry 7 trailing digits, so it is classified as a dataset):

| Register | Doc | Rows |
|---|---|---|
| `compliance_register_2024-12-31.csv` | RPL-CMP-REG-001 | 70 obligations |
| `retention_schedule_2024-12-31.csv` | RPL-LEG-RRS-001 | 86 |
| `calendar_events_2025.csv` | RPL-REG-CAL-2025 | 48 |

Each row becomes one clause (`unit_kind = 'register_row'`). Their contribution:

| | register_row | share |
|---|---|---|
| Clauses | 204 / 2,334 | 8.7% |
| Citations | 419 / 1,550 | 27% |
| Resolved citations | 327 / 1,284 | 25% |
| **Engine findings** | **487 / 1,244** | **39%** |
| **Distinct code_sections touched** | **69** | **more than `section` (60) — largest of any kind** |

8.7% of clauses generate 39% of findings and the widest regulatory surface in the corpus, because the compliance register *is* the obligation→citation map. Deleting it would be a severe demo regression.

**What is kept:** `parse/register_segmenter.py` (generic — one row, one clause), `llm/run_column_roles.py`, and the `table_columns` table (26 rows).
**What is replaced:** the synthetic detection grammar. `_detect_p2`'s sniffing of `_RE_OBL`/`_RE_EVT`/`_RE_RRS` in the first cell is deleted. Register intent becomes **user-declared at upload**: register type and the id column name are supplied by the uploader, not inferred from an ID format.

### D4. Qdrant: index on promotion, delete-and-replace

Only live, approved clauses are indexed. Drafts, in-review versions and superseded versions are never present.

First, a fact that bounds the risk: **nothing currently reads the `company_clauses` collection.** Only `index/upsert.py` writes it; the engine selects candidates from Neon (`candidates.py`, `footprint.py`). It is write-only today, so this is a correctness investment rather than a live bug fix.

This policy is simpler than the alternative. Flipping `is_current = false` on superseded points (`index/upsert.py:109 mark_previous_versions_stale`, which exists but is never called) leaves dead vectors accumulating forever and depends on every future reader remembering the filter — one forgotten filter leaks stale clauses. Delete-and-replace has no flag to forget: if a point is in the collection, it is live.

Implementation — in the promotion transaction (P3), as one step:
1. Delete all points for that `doc_id` (filter on `doc_id` + `company_id`, not `version_id`, so orphans from any prior scheme are swept too).
2. Insert the newly promoted version's points, keyed by the **real** `version_id`.
3. Drop `is_current` from the payload and from `qdrant_setup.py`'s payload indexes; delete `mark_previous_versions_stale`.

This also fixes the existing bug where point ids embed the literal `"v1"` (`ingest.py:227`), so a new version silently overwrote the previous version's vectors.

**Trade-off accepted:** a reviewer cannot semantically search a pending version. Nothing reads the collection today, so nothing is lost now.

---

## Two assumptions still open for your call

### A1. A saved version is not automatically current

Your scenario said "approved **or** saved", while the org requirement asks for a signing hierarchy. These conflict, so the default is explicit:

A saved version is created `in_review` and **is ingested** (reviewers can read its clauses and findings), but is promoted to current only when its approval request completes. The "unchanged" check compares against the current version **and** any pending version, so re-saving identical content twice does not create two pending versions.

Veto option: promote on save, leaving `approval_*` as a record-keeping layer only.

### A2. Redlining is new construction, not preservation

To be explicit, because it was raised as an existing feature: **there is no redlining today.**

- **Exists and is preserved:** findings with suggested changes (`engine.findings.required_change` = `{from_text, to_text}`, plus `rationale`), finding accept/reject reviews, what-if scenarios (editing *regulation* text), radar, ledger, scorecard, document reader, KB browsing, diff views.
- **Disabled placeholders in `frontend/lib/future-features.ts`** (greyed out, no handler): `upload-document`, `export-redline`, `draft-rewrite`, `request-signoff`, `version-history`, `ask-document`, `view-original`, `edit-profile`, `sync-directory`, `connect-source`, `start-monitoring`, `workspace-switcher`.

Note `required_change.to_text` is LLM prose with no character offsets (`engine/prompts/judge.md:30` asks for "what the clause must now say"), so it can *seed* a clause edit but cannot be applied automatically.

---

## P0 — Security remediation (first commit, independent of everything else)

**Done by you:** the Neon credential has been rotated and `backend/.env` updated. The exposed string is now worthless.

**Scan results (completed, read-only).** Across all **731 git-tracked files** (excluding `.venv` and lockfiles):

| Check | Result |
|---|---|
| Connection strings with embedded credentials | **1 file** — `backend/app/company/corpus/grounding/_leaktest.py:27` |
| Hardcoded API keys / tokens / passwords | none |
| Hardcoded Neon / Qdrant / R2 hostnames | none |
| `os.environ` defaults containing secrets | none |
| `.env` tracked by git | no — `**/.env` is gitignored; only `.env.example` is tracked |

So the exposure is a single file and the rest of the repo is already clean and `.env`-driven.

**Steps:**
1. **Delete `backend/app/company/corpus/grounding/_leaktest.py`** — 245 lines of one-time corpus-authoring QA ("T00 leak test for grounding packs"), credential on line 27, imported by no application, script or test code. Its sibling report `_leaktest_report.json` goes with it.
2. Add a **regression test** `backend/tests/test_no_secrets.py` that scans git-tracked files for the four patterns above and fails on a match. This is the same file-scanner shape as `tests/engine/test_barrier.py`, so it reuses a proven approach and stops this recurring.
3. Git history still contains the old string. Rotation already neutralised it; a history rewrite is optional cleanup and is your call.

> Not yet executed: plan mode permits edits only to the plan file. This is step 1 on approval, and waiting is safe because the credential is already dead.

---

## P1 — Detangle synthetic data

**Move** `backend/app/company/` → `backend/synthetic/corpus/`, out of the importable `app` package.

**Remove runtime coupling** in `app/api/company/routes.py`: delete `_GLOBAL` (:23), `load_register` (:102), `load_profile_yaml` (:119), `derive_doc_type` (:63, relies on the `RPL-CS-PRO-004` positional grammar), and the CSV/YAML fallbacks at `:143-145, 288-293`. Those fields now come from the database — see the field map in P2.

**Drop `RPL-` literals** from `parse/front_matter.py:164,206,237`.

**Config:** delete `CORPUS_ROOT` and `COMPANY_ID` from `app/config.py:20-21` and `.env.example`. (`CORPUS_ROOT`'s default is already broken — it resolves to a nonexistent `backend/app/app/company/corpus` — and `--corpus-root` is a no-op because it writes `os.environ` after the settings singleton is built.)

**Enforce the boundary:** widen `tests/engine/test_barrier.py`'s scanner from `[app/engine, app/api/engine, scripts]` to **all of `app/`**, adding **path-shaped** patterns `synthetic/`, `corpus/`, `app/company`. Path-shaped matters: bare `synthetic` false-hits `app/engine/params_text.py:18 _synthetic_unit`, and bare `corpus` false-hits the comment at `app/engine/delta.py:5`. This reuses a working, already-tested mechanism (`scan_barrier`, `scan_file`) and makes deletability CI-enforced.

**Seeder** `backend/synthetic/seed.py` POSTs the corpus through the real upload + org endpoints — the thing that actually proves objective 2. Uploads take DOCX, and 11 of 12 docs already have a DOCX render; the seeder generates one for the twelfth. It POSTs the three registers as CSV with declared intent, and maps each `RPL-*` id into the new `doc_number` field so eval tooling can still correlate.

### Delete outright

- `company_ingest/collect/` — entire package (`allowlist.py`, `collector.py`, `reference.py`, `register_docs.py`). `register_docs.py` was already dead; `allowlist.py` holds the pipeline's only Python-3.13-only call (`full_match`), so removing it makes the 3.11 production runtime safe.
- `company_ingest/datasets/` (whole package), including `propose_checks.py` and `validate_checks.py`
- `company_ingest/constants.py` — the `Profile` enum (P1/P2/P3/P4/RENDER) goes with it; registers are now declared, not sniffed
- `company_ingest/cli/ingest.py` — replaced by the per-document service
- `company_ingest/store/schema.sql` — a stale reference dump, executed by nothing, already missing two columns
- `company_ingest/store/neon.py` — `insert_term_usages()` (:449, superseded) and the dataset/column/check inserters
- `scripts/score_run.py`, `scripts/demo_prep.py` → move to `backend/synthetic/`. `/engine/runs/{id}/scorecard` reads `engine.score_reports` from the DB (`api/engine/routes.py:337`), so it keeps working with no app-side coupling.
- `frontend/scripts/build-fixtures.ts` → repoint at `backend/synthetic/corpus` (already dev-machine-only)
- Corpus-dependent tests: `test_e2e_corpus.py`, `test_collector.py`, `test_reference.py`, `test_dataset_profile.py`, plus four already-dead corpus tests pointing at a nonexistent `backend/corpus` (`test_dataset_keys.py`, `test_parameters_regex.py`, `test_register_segmenter.py`, `test_terms.py`)
- Tables dropped by migration: `datasets`, `dataset_columns`, `parameter_checks` — **verified 0 rows in production**, so this is provably zero-cost. `table_columns` (26 rows) is **kept** with the register path.

**Explicitly kept:** `parse/register_segmenter.py`, `llm/run_column_roles.py`, `company.table_columns`, `pypdf` (regulatory adapters).

---

## P2 — Schema (one Alembic migration on head `e5a1c7d9b304`)

**Deploy safety, first statement.** `render.yaml` runs `alembic upgrade head` *before* the app starts, against populated tables. `ADD version_no int NOT NULL` without a default, and the `status` CHECK (existing rows hold `'Approved'`), would both fail and break the deploy. Since cutover is an approved wipe, the migration **begins by truncating** `company.*` and `engine.runs`/`findings`/dependents — explicitly **never** `public.code_sections`, which holds the real regulatory KB — and then adds the constraints.

### Document identity & the single hash

```sql
ALTER TABLE company.company_documents
  ADD current_content_hash char(64),
  ADD doc_number text,                   -- customer's own reference, display + eval correlation
  ADD lifecycle_state text NOT NULL DEFAULT 'active',
  ADD created_at timestamptz NOT NULL DEFAULT now(),
  ADD updated_at timestamptz NOT NULL DEFAULT now();

CREATE UNIQUE INDEX company_documents_content_hash_uq
  ON company.company_documents (company_id, current_content_hash)
  WHERE current_content_hash IS NOT NULL;
```

`doc_id` becomes system-assigned (`DOC-000123`), never derived from a filename. The partial unique index is what makes the check correct under concurrency: two simultaneous identical uploads both pass a `SELECT`, so the insert must catch the conflict and convert it to the same 409.

### Immutable version history

```sql
ALTER TABLE company.document_versions
  ADD version_no int NOT NULL,
  ADD is_current boolean NOT NULL DEFAULT false,
  ADD superseded_by uuid,
  ADD supersedes_version_id uuid,
  ADD created_at timestamptz NOT NULL DEFAULT now(),
  ADD created_by_person_id text,
  ADD change_reason text,
  ADD extraction_r2_key text,
  ADD extraction_method text,
  DROP COLUMN file_sha256;               -- per "only one hash per document"

ALTER TABLE company.document_versions ADD CONSTRAINT document_versions_status_ck
  CHECK (status IN ('draft','in_review','approved','effective','superseded','retired'));

CREATE UNIQUE INDEX document_versions_no_uq
  ON company.document_versions (company_id, doc_id, version_no);
CREATE UNIQUE INDEX document_versions_current_uq
  ON company.document_versions (company_id, doc_id) WHERE is_current;
CREATE INDEX document_versions_doc_idx ON company.document_versions (company_id, doc_id);
```

`status` is today bare `text` with no default, frozen at ingest as a copy of `"Approved"`, and `supersedes`/`next_review` are hardcoded `None` (`store/neon.py:189-190`). It becomes a real state machine; the second partial index guarantees exactly one current version per document at the database level.

### Version-scoped child keys (data-loss fix)

`citation_pk`, `parameter_pk`, `term_pk`, `link_pk` are derived without `version_id` (`store/neon.py:296,358,415,542`) and inserted `ON CONFLICT DO NOTHING`. Add `version_id` to each `stable_uuid(...)` call so v2's children no longer collide with v1's and get discarded. `clause_pk` is already correct (:217).

Add `version_id` to `engine.findings` so findings pin to the version they were computed against.

**This fix is what keeps the regulation-link mechanism working across versions.** Without it, a new version's `clause_citations` rows are silently dropped, and the citation→`code_section_id` links the engine depends on quietly rot.

### LLM reuse cache

`company.llm_extractions` exists with **zero writers** — the audit record goes only to R2, and `ctx.llm_cache` is in-memory, per-run, read only when `--rebuild` is set.

```sql
ALTER TABLE company.llm_extractions
  ADD content_sha256 char(64), ADD model text, ADD output jsonb;
CREATE UNIQUE INDEX llm_extractions_cache_uq
  ON company.llm_extractions (company_id, stage, content_sha256, prompt_sha256, model);
```

`llm/client.py:call_structured` gains a read-through against this table before calling Anthropic, and writes on success. Keyed on clause content, so an unchanged clause in a new version never re-runs the LLM.

### Org model (additive — existing tables keep working)

`people` and `company_attributes` are **kept as-is** so all existing engine SQL continues to work. New alongside:

```sql
company.departments     (company_id, department_id, name, parent_department_id)
company.document_role_assignments
                        (company_id, doc_id, person_id, role, assigned_at)  -- owner|reviewer|approver
company.approval_policies      (company_id, policy_id, applies_to_vertical, applies_to_doc_class, name)
company.approval_policy_steps  (policy_id, step_no, required_role, min_approvals)
company.approval_requests      (request_id, version_id, policy_id, state, created_at)
company.approval_steps         (request_id, step_no, required_role, assignee_person_id,
                                decision, decided_at, note)
```

`document_role_assignments` supersedes the three flat `owner_id/reviewer_id/approver_id` columns (kept and populated for engine compatibility) and carries the signature hierarchy. `people_directory.csv` already has a `document_roles` column with `DOC:approver` pairs that `collect/reference.py:199-225` silently drops; the seeder now uses it. `people` gains `department_id`, `is_active`.

### Redline / edit

```sql
company.clause_edits (edit_id, company_id, version_id, clause_id, char_start, char_end,
                      proposed_text, author_person_id, state, created_at, decided_at, decided_by)
                      -- state IN ('proposed','accepted','rejected')
```

### Field → column → writer map

Replaces everything the deleted CSV/YAML fallbacks supplied:

| UI field | Column | Written by |
|---|---|---|
| title, doc_class | `company_documents.title/doc_class` | extraction (`DocClassification` in `llm/schemas.py`), user-editable |
| vertical | `company_documents.vertical` | upload entry point (uploads are per-vertical) |
| effective / approved / next_review | `document_versions.*` | extraction, user-editable |
| review_cycle | `company_documents.review_cycle` | org endpoint (currently hardcoded `None` at `neon.py:118-119`) |
| owner / reviewer / approver | `document_role_assignments` | org endpoint |
| doc_number | `company_documents.doc_number` | upload form (optional) |
| regulator, utility_type, legal_name, ownership, jurisdiction, customer_count | `companies.name` + `company_attributes` (existing k/v) | org endpoint |

---

## P3 — Per-document ingest service

New `app/company_ingest/service.py` replacing the corpus-walking CLI:

```python
async def ingest_document(*, company_id, doc_id, version_id, raw_bytes,
                          filename, content_type, register_spec, session, ctx) -> IngestResult
```

**Stage 0 — intake (new).** `app/company_ingest/extract/` with a `DocumentExtractor` protocol returning `ExtractedDocument(markdown, method, confidence)`. `DocxExtractor` maps `Heading1/2/3` → `#`/`##`/`###` and tables → pipe tables. Per D1 the contract is **Markdown out**, so the segmenter is reused unchanged. A CSV upload with a `register_spec` bypasses extraction and goes to `register_segmenter`.

**Empty-extraction guard.** A DOCX containing only images yields empty text; without a guard it would hash `sha256("")` and be rejected as a duplicate of the first such file. Reject with **422 "no extractable text"** *before* hashing.

**Stages 2–8 — reused, given Markdown input:** `parse/markdown_segmenter.py:segment_with_ctx` (or `register_segmenter` for CSV) → `enrich/{citations,parameters_regex,references,roles,terms}` → `llm/run_clause_enrichment` (now cache-backed) → `llm/run_column_roles` for registers → `link/{resolve_refs,restates,document_scope}`.

**Stage 5b — citation resolution, moved in-pipeline (new).** Port `enrich/resolve_citations_db.py:resolve_all_citations` from synchronous psycopg2/whole-table to **async SQLAlchemy scoped to one `version_id`**, and call it as a pipeline stage. This is what makes regulation mapping work for an uploaded document instead of requiring a manual backfill. Preserve its logic: the IAC normalized key `f"{title} IAC {article}-{section}"`, the CFR 14-day `law_as_of` window, and the `_TERMINAL` status set for idempotency.

**Clause-level reuse (new).** Before the LLM stage, match incoming `unit.text_sha256` against the prior version's clauses. Matches inherit `clause_role`, `assessable`, `normalized_statement`, `topic_terms`, citations and parameters, and skip re-embedding. Only changed and new clauses reach the LLM.

**Fixes required inside the reused stages:**
- `store/snapshot.py` — the clause-snapshot key embeds `"v1"`, and the write-once guard raises `ValueError` on changed content without `--rebuild`, failing the whole run. Key by real `version_id`.
- `store/neon.py:191` — `source_r2_key` is always NULL because it reads `getattr(sf, "r2_key", None)` and `SourceFile` has no such field. Pass the key explicitly.
- `store/commit.py:98 write_report` — never called, so `ingest_runs.report_r2_key` is always NULL. Wire it, and insert the `ingest_runs` row at run *start* (today written only at the end, hardcoded `"completed"`, so a crash leaves no trace).

### Promotion & failure semantics

Setting the hash and current pointer before the BackgroundTask runs would leave, on failure or a free-tier restart, either a document that blocks every re-upload with 409 while having no clauses, or a "current" version with no clauses. So:

1. A version is inserted **non-current**, `ingest_status = 'pending'`.
2. A new document reserves its hash in a `pending` state; **released on failure**, so the customer can retry.
3. **Promotion** happens in **one transaction**, only after ingest succeeds and (per A1) approval completes: set `is_current`, `current_version_id`, `current_content_hash`; flip the prior version to `superseded` with `superseded_by`; and **delete-then-insert the document's Qdrant points** (D4).
4. A **startup sweep** marks orphaned `running` jobs as `failed`.
5. `POST /company/ingest-jobs/{job_id}/retry` re-runs from the R2 raw bytes.

---

## P4 — API

Add `python-multipart` and `python-docx` to `requirements.txt`. Keep `pypdf`.

### `POST /company/documents` — new document

Order matters, because a duplicate must store nothing:

1. Read bytes (25 MB cap); reject non-DOCX/CSV (**415**, naming DOCX).
2. Extract → reject empty (**422**) → canonicalize → SHA-256.
3. `SELECT doc_id, title FROM company_documents WHERE company_id = ? AND current_content_hash = ?`
   → **409** `{"status":"duplicate","message":"This document is already in the system as '<title>'.","doc_id":…}`. Nothing written.
4. Assign `doc_id` + `version_no = 1`; insert rows (catching the partial-unique conflict → same 409); upload raw bytes to R2; insert the ingest job row.
5. Schedule the `BackgroundTask`, return **202** `{doc_id, version_id, job_id}`.

`vertical` comes free from the per-vertical entry point, so the form needs only title + vertical (+ optional `doc_number`, + `register_spec` for CSV).

### `POST /company/documents/{doc_id}/versions` — new version / redline save

Same extract → canonicalize → hash, compared against that document's current **and pending** hashes:
→ **200** `{"status":"unchanged","message":"No changes compared to the current version."}`, nothing written.
Otherwise insert `version_no = max + 1` as pending, ingest, then promote per P3.

### `POST /company/documents/{doc_id}/edits`, `/edits/{edit_id}/accept`

Accepting renders the canonical Markdown with edits applied, stores it as the new version's `source_r2_key`, and routes through the same version path. **This is the canonical artifact an in-app edit hashes** — without it, "update the hash" has nothing to hash.

### Also

`GET /company/documents/{doc_id}/versions`, `GET /company/ingest-jobs/{job_id}` (poll shape from `GET /engine/runs/{id}`, but insert the job row **before** scheduling — the existing pattern inserts inside the task and 404s briefly). Org write endpoints for departments, people, role assignments and approval policies; approval request/decision endpoints. Every write carries `acting_person_id`.

### Version-leak fixes (required before any second version can exist)

None of these filter by version; they join `clauses → company_documents` on `doc_id` alone. With real history they double the compliance footprint and duplicate findings:

- `app/engine/footprint.py:33-38` (`_ELIGIBLE_CTE`)
- `app/engine/candidates.py:81-85` (`_ELIGIBLE`)
- `app/engine/radar.py:51-53`
- `app/engine/delta.py:295`
- `app/api/company/routes.py:191-195` (`_CITED_SQL`)
- `app/api/company/routes.py:232-243` — uses `current_version_id` only as an `ORDER BY` key, so it returns **both** versions' clauses
- `app/api/engine/routes_ui_results.py:165` — `DISTINCT ON (clause_id)` currently masks the problem

Each gains `AND c.version_id = d.current_version_id`, plus a regression test.

---

## P5 — Frontend

- Enable `upload-document` (`lib/future-features.ts:40`) → a real per-vertical upload dialog accepting DOCX (and CSV with declared register intent). `lib/api/http/shared.ts:58-70` `request()` is JSON-only; add a `FormData` branch.
- Duplicate / unchanged / failed states need new entries in `lib/labels.ts:70-75`, `board/logic.ts:18` `STATUS_ORDER`, `board/DocStatusPill.tsx:7-12`, and `schemas/company.ts` `documentMetaSchema` (which has no `ingest_status` today).
- Job progress: clone the 2s poller at `lib/api/queries.ts:54-67`.
- Enable `version-history` (`ReaderHeader.tsx:73`) against the versions endpoint.
- Clause edit surface + accept/reject. No editor dependency is installed; a textarea per clause avoids adding tiptap/slate.
- "Acting as" person selector in the shell — there is no current-user concept to attribute an edit or approval to.
- **Gotcha:** `lib/api/http/company.ts:10-14` silently drops documents whose vertical isn't a known slug, and the backend returns literal `"unclassified"` (`routes.py:57-60`), absent from `lib/verticals.ts:13-28`. A newly uploaded unclassified document would vanish with only a `console.warn`.

---

## P6 — Cutover, with parity verification

1. **Before the wipe**, snapshot the baseline: findings per document, findings per `unit_kind`, resolved-citation counts, distinct `code_section_id` coverage, and `engine.score_reports` metrics. (Current values: 2,334 clauses; 1,550 citations / 1,284 resolved; 285 scope rows; 1,244 findings.)
2. The migration truncates `company.*` and engine run data (P2). Separately clear the Qdrant `company_clauses` collection.
3. Run `backend/synthetic/seed.py` — POSTs the corpus through the real upload and org endpoints.
4. Re-run the engine.
5. **Compare against the snapshot** and investigate any material delta. Findings are *regenerated*, not preserved, so exact equality is not expected — but a large drop means something was lost in the detangle, and this is the check that catches it.

Required because version-scoping the child PKs and using real `version_id`s in Qdrant point ids changes every existing primary key, orphaning current findings — which production serves (`ENGINE_COMPANY_ID=rpl`).

**S1/S2 scenarios are unaffected in mechanism.** S1/S2 are the earliest and latest regulatory snapshot dates, discovered per source system (`engine/inputs.py:3` — "S1 = min, S2 = max", never hardcoded), read from `public.code_sections`, which this plan never wipes. They survive because registers are kept (D3) and because `doc_number` preserves eval correlation.

**Memory note:** ingest now runs in the Render free-tier web process. `sentence_transformers` is lazily imported inside functions so it isn't loaded at boot, but embedding pulls torch + MiniLM into a 512 MB dyno. The regulatory `/jobs/ingest` already does this, so there is precedent; the fallback is a separate Render worker service.

---

## P7 — Verification

**Security**
```bash
cd backend && python -m pytest tests/test_no_secrets.py -q    # new regression scanner
git grep -nE "npg_|postgres(ql)?://[^ \"']*:[^ \"']*@" -- . ':!*.md'   # expect no hits
```

**Deletability (objective 1)**
```bash
mv backend/synthetic /tmp/synthetic-check
cd backend && python -m pytest -q            # full suite green
curl localhost:8000/company/documents        # all fields populated from DB
curl localhost:8000/company/profile
mv /tmp/synthetic-check backend/synthetic
python -m pytest tests/engine/test_barrier.py -q
```

**Test placement matters.** `FakeSession` + `ASGITransport` (the pattern at `tests/engine/test_api_routes.py:56-63`) cannot exercise partial unique indexes, CHECK constraints, `ON CONFLICT`, PK collisions or concurrency. Split:

- **Real Postgres** (Neon branch or local PG, existing `neon` marker): tests 2, 3, 5, 7, 8, 13.
- **FakeSession + ASGITransport**: tests 1, 4, 9, 10 (routing, status codes, validation).
- **R2** via `moto[s3]` (already in `requirements.txt`); **Anthropic** mocked with a call counter; **Qdrant** via the existing `qdrant` marker.

1. **New DOCX document** → 202; job completes; clauses written; citations resolved to non-NULL `code_section_id`; Qdrant points keyed by real `version_id`.
2. **Byte-identical re-upload, different filename** → 409; assert **zero** new rows in `company_documents`/`document_versions` and **zero** new R2 objects.
3. **DOCX re-saved from Word**, identical wording, different bytes → 409.
4. **New version, unchanged content** → 200 `"no changes"`, nothing written.
5. **Redline → accept → approve** → v2 `is_current`; v1 `superseded` with `superseded_by` and clauses intact; `current_content_hash` replaced; exactly one row matches the current-version partial index; and **v2's citations and links exist** — the regression the unscoped child PKs would silently have dropped.
6. **LLM reuse** → on v2, `llm_extractions` cache hits > 0 and the mocked Anthropic client records no call for unchanged clauses.
7. **Version leak** → with two versions live, every query listed in P4 returns exactly one version's clauses.
8. **Concurrency** → two simultaneous identical uploads: exactly one 202, one 409, one row.
9. **PDF upload** → 415 naming DOCX, before extraction or write.
10. **DOCX with no extractable text** → 422 before hashing; a second such file also 422, not 409.
11. **Failure recovery** → kill the task mid-ingest; the pending hash is released, re-upload is accepted, and the retry endpoint completes from R2 bytes.
12. **Extraction fidelity** → for each seeded doc, assert the DOCX-extracted clause count is within tolerance of the known `.md` clause count (guards the D1 contract).
13. **Qdrant hygiene** → after promoting v2, the collection contains points for v2 only; zero points reference v1 or any pending version; count equals v2's indexable clause count.
14. **Register path** → upload a CSV with declared intent; assert one clause per row, `unit_kind='register_row'`, citations resolved, and `table_columns` populated.
15. **Cutover parity** → post-reseed findings and coverage within tolerance of the P6 step-1 snapshot.

---

## Open items

- **A1** — saved versions go to `in_review` and are promoted on approval, not on save. Approve or veto.
- **A2** — redlining is new construction; the existing *suggestion* surface (`required_change` + `rationale`) is preserved unchanged.
- **Known boundary:** a customer who edits a document *outside* the app and re-uploads via the upload path gets a new document, not a new version — the upload path is for new documents by design. The hash still catches wording-identical re-uploads. Mitigation if needed later is a title-similarity warning, not a similarity index.
- **PDF** — deferred, not designed out. The extractor seam means adding a structured-extraction vendor later is a new class plus a content-type allowlist entry.
- **Housekeeping:** `implementation_plan.md` in the repo root is a stale duplicate of this file and should be deleted.
- **Deliverables on approval:** `architecture.md`, `TDD.md`, `implementation_plan.md`.

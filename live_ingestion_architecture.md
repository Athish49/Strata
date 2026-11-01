# Company Documents — Live Ingestion Architecture (v2, current)

_Written 2026-10-31 from code read + live Neon/Qdrant/R2 verification. This document describes the pipeline that is actually running today. It replaces nothing — `supplement_docs/CompanyData_Pipeline/company_data_storage.md` and `synthetic_corpus_generation.md` are kept as-is but are now stale on specific counts/claims; see `report.md` (repo root) for the itemized diff. This doc only covers the **company-documents** pipeline; the federal/state regulatory ingestion (`app/regulatory/`) is out of scope._

## 1. One-paragraph summary

v1 had a batch CLI (`app/company_ingest/cli/ingest.py`) that walked a corpus directory on disk and a read API (`app/api/company/routes.py`) that opened local CSV/YAML files on live request paths. **Both are gone.** v2 is a per-document, API-driven pipeline: a document arrives as HTTP upload bytes, is parsed/enriched/linked entirely in memory, and is written to Neon (structured graph), Qdrant (vectors, on promotion only), and R2 (raw bytes + derived snapshot) inside one service call. Nothing in the request path reads a local file except two static, shipped LLM prompt templates (`app/company_ingest/llm/prompts/*.md`, `app/engine/prompts/*.md`) — the same category as a config file, not demo data.

## 2. Pipeline diagram

```mermaid
flowchart TD
    U[Customer / seed.py\nHTTP POST] -->|bytes| UP["app/api/company/upload.py\nextract -> hash -> dedup guard"]
    UP -->|creates company_documents\n+ document_versions row| SVC["app/company_ingest/service.py\ningest_document()"]
    SVC --> S1["1 split_front_matter (prose)"]
    S1 --> S2["2 anchor_clauses -> segment_with_ctx (prose)\nsegment_register_text (registers)"]
    S2 --> S3["3 reuse_from_prior_version\n(LLM-derived fields only)"]
    S3 --> S4["4 enrich_citations -> enrich_parameters\n-> enrich_references -> enrich_roles\n-> extract_terms -> find_term_usages"]
    S4 --> S5["5 run_clause_enrichment (LLM, cache-backed)\n5b run_column_roles (registers only)"]
    S5 --> S7["7 resolve_references -> find_restates_links\n-> build_document_scope"]
    S7 --> S8["8 finalize_parameters"]
    S8 --> S10["10 commit_run — Neon writes,\ncaller's transaction, no commit yet"]
    S10 --> S6["6 resolve_citations_for_version\n(reads back company.clause_citations\nJOIN clauses — must run AFTER commit_run)"]
    S6 --> S9["9 write_clause_snapshot -> R2\nderived/{doc_id}/{version_id}/clauses.jsonl"]
    S9 --> JOBS["jobs.py BackgroundTask\nqueued -> running -> succeeded/failed"]
    JOBS --> PROMOTE["promote.py\n(owner/approver action, separate from ingest)"]
    PROMOTE --> QD[("Qdrant company_clauses\nindexed ONLY on promotion")]
    UP -->|raw bytes, write-once sha256| R2RAW[("R2: raw/{doc_id}/{version}/...")]
    SVC -. report.json .-> R2REPORT[("R2: ingest_runs/{run_id}/report.json")]
```

Stage numbering is the real numbering from `service.py`'s own docstring (stage 6 runs after stage 10 on purpose — the citation resolver reads back rows that `commit_run` just inserted, inside the same DB transaction).

## 3. Entry points (all that exist today)

All paths below are confirmed by `grep -n "@router\."` against the actual decorators, not inferred:

| Entry point | File | What it does |
|---|---|---|
| `POST /company/documents` | `app/api/company/upload.py:521` | New document + version 1; extracts, hashes, dedups, writes raw bytes to R2, queues ingest job |
| `POST /company/documents/{doc_id}/versions` | `app/api/company/upload.py:757` | New version of an existing document; same pipeline |
| `GET /company/documents/{doc_id}/versions` | `app/api/company/versions.py:148` | Version history |
| `GET /company/ingest-jobs/{job_id}` | `app/api/company/versions.py:185` | Poll ingest job status |
| `POST /company/ingest-jobs/{job_id}/retry` | `app/api/company/versions.py:194` | Retry re-runs from the **immutable R2 raw bytes**, not from a re-upload |
| `PATCH /company/documents/{doc_id}` | `app/api/company/doc_admin.py:171` | Metadata edit (title, vertical, owner, review cycle, approval dates) |
| `GET/POST/PATCH/DELETE /company/people`, `/departments`, `/attributes/{key}`, `/approval-policies*`, `/documents/{doc_id}/roles`, `/documents/{doc_id}/versions/{version_id}/approval`, `/approval-requests/{request_id}/*` | `app/api/company/org.py` (33 routes) | Full org/approval write surface — the DB-only replacement for the old `_global/company_profile.yaml` + `_global/people_directory.csv` |
| `GET /company/documents`, `/documents/{doc_id}`, `/documents/{doc_id}/clauses`, `/people`, `/profile` | `app/api/company/routes.py:204,209,217,247,261` | Read-only, all from Neon |

**There is no CLI entry point.** `python -m app.company_ingest.cli.ingest`, still written in `README.md` and in `supplement_docs/application_layer/application_layer.md`, does not exist in the codebase — confirmed by file search (no `cli.py` / `cli/` under `app/company_ingest/`). `backend/synthetic/seed.py` is the only tool that bulk-loads the demo corpus today, and it does so by calling the exact same HTTP endpoints above, nothing else — this is its proof-of-concept, not a separate privileged path.

## 4. R2 writes — real, exercised code, but one of the three is confirmed incomplete

Three call sites, each confirmed live by code read AND by a direct `head_object` check against each document's real `version_id`/`ingest_run_id` from Neon (not a bucket listing, which would be misleading here — see §7 of `tables_and_connections.md` for why):

| Call site | Writes | Verified live |
|---|---|---|
| `app/api/company/upload.py:364` | raw uploaded bytes, on every upload | **15/15** current versions confirmed |
| `app/company_ingest/store/snapshot.py:161` | `derived/{doc_id}/{version_id}/clauses.jsonl` | **3/15** confirmed (the 3 register-CSV documents only) — **12/15 prose documents are missing this object**, a real, confirmed gap. See §5. |
| `app/company_ingest/store/commit.py:154` | `ingest_runs/{run_id}/report.json` | **15/15** confirmed |

`r2.py`'s write-once semantics (sha256 metadata compare, raise on mismatch unless `force=True`) are real, exercised code. The derived-snapshot gap does not appear to be caused by this guard — the affected documents' own `report.json` shows `"status": "completed", "passed": true, "issues": []`.

**⚠️ Real landmine, not a cosmetic local note:** `backend/.env`'s `R2_ENDPOINT` ends in `/strata` (the bucket name). Combined with the boto3 client's own `Bucket="strata"` parameter on every call, **every object the app has ever written physically landed at key `strata/company/...`** — one extra segment versus the clean `company/...` key stored in Neon's `source_r2_key` column. This is invisible to the running app today only because the *same* misconfigured endpoint is used for both writes and reads, so the bug cancels itself out from the app's own point of view. **Do not "fix" `R2_ENDPOINT` without a key-migration plan** — doing so naively (as this audit did, read-only, solely to get a listing working) makes every existing object unreachable at the key the app expects, which would silently break the ingest-job retry path (`versions.py`, which re-fetches from the stored raw key) and any future raw-document download. Check whether the deployed (Render) environment carries the same suffix before treating this as local-only. Full detail in `tables_and_connections.md` §7.

## 5. Known gaps found in the live pipeline (not generation-code issues — real correctness items)

**Top finding, highest severity in this document — see `report.md`'s addendum (repo root) for the full, corrected writeup, this is a summary:** `resolve_references`/`find_restates_links` (`service.py:663-664`) and every one of `resolve_refs.py`'s index-building helpers (`_build_clause_index`, `_build_rule_index`, `_build_form_index`, `_build_series_index`, `_build_obligation_index`) take only the current ingest call's own in-memory `units` — one document's clauses — confirmed by reading every signature, not just the clause index. **All 5 of `LINK_TYPES`' link types plus `restates` are single-document-scoped in the current architecture, not just `references_clause`.** `references_doc` is checked against a real cross-document `company.company_documents` query — structurally capable, but **unverified whether it actually works**: no code anywhere translates a document's human-readable `doc_number` (what prose would actually reference a document by) into its internal `doc_id`, and the one source of likely-fresh v2 data (the 3 register documents) has zero `references_doc` rows to test it against. No reconciliation pass exists anywhere in `app/` to fix the single-document scoping after the fact. This is *consistent with* (not independently proven by) the 3 register documents, which show every sign of being fresh v2 ingests and have **zero** cross-document links of any kind despite 68 recorded `unresolved_ref` warnings pointing at other documents — though even that inference carries some of the same uncertainty as finding 2 below. `app/engine/candidates.py`'s `LINK_TYPES` constant reads `references_clause` (and 4 other reference types, but **not** `restates`) for candidate propagation — so this prevents the engine from flagging a clause as affected solely because it *references* content in *another* document that a regulation change hit, for any new upload. A second, related finding — whether the 12 non-register documents' current data is even fresh v2 output, given it has cross-document links the architecture above says it can't produce — is in `tables_and_connections.md` §8 and `report.md`'s addendum; don't treat this document's other "confirmed live" claims about those 12 documents as settled until that's resolved.

| Gap | Evidence | Who's affected |
|---|---|---|
| **Superseded — see `report.md`'s addendum.** What looked like "stages 5/5b/9 incomplete for 12 prose documents" is now better explained by finding 2 there: those 12 documents' current data likely wasn't produced by a fresh v2 run at all. A 4th independent confirmation found since: genuinely-fresh v2 parameter rows (the 3 register documents', 1,766 of them) are **100% NULL** on `is_citation_fragment` (never set by `insert_clause_parameters`, confirmed), while the 12 prose documents' 2,420 parameter rows are **100% non-NULL** — consistent with that data being old, already-backfilled rows carried over, not fresh output of today's recorded runs. | `ingest_jobs.state = 'succeeded'` for all 15 **[live]** proves the job wrapper finished, not that the recorded run did the enrichment work — don't read it as ruling out anything. | — |
| `company.clause_parameters.is_citation_fragment` is set by the live ingest pipeline **nowhere** (the 3 register documents' 1,766 fresh-v2 rows are 100% NULL). Only a standalone script sets it. **But all 3 read-sites are provably dead:** the flag can only be `True` when `kind='number' AND unit IS NULL`; `candidates.py:98`'s SQL and `rules.py:105`'s `_eligible()` already independently exclude that exact row shape via a separate condition in the same filter, so the flag changes zero outcomes — confirmed by the boolean logic, not assumed. `judge.py:384` only selects it into a dict, no filter. | Live count: 4,186 total parameter rows, 2,420 non-NULL (all on the 12 non-register documents — consistent with that data being old/carried-over, see finding 2), 1,766 NULL (all on the 3 register documents). | **No current engine-output effect**, confirmed by code — this is an unwired-and-inert column, not a silent degradation. Worth a decision (wire it in, or delete it) on cleanup grounds, not urgency. |
| `company.clause_citations` with `resolution_status = 'not_found'`: no live path re-resolves them after the regulatory KB changes. **Open question, not a confirmed defect** — `resolve_all_citations()` is called only by `scripts/backfill_citations.py`, but resolution is bounded by each clause's `law_as_of` (S1) while the daily cron brings in S2 data. A live `dry_run=True` run this session returned `{}` — zero rows currently resolvable. | `grep` for `resolve_all_citations` call sites in `app/`: zero. Dry-run result: `{}` **[live]**. | No active impact today; worth a product decision on whether to wire this in preemptively for the case where S1-snapshot sections arrive late. |
| `app/company_ingest/parse/register_segmenter.py`'s `segment_register()` (the path-based, disk-reading wrapper) has zero production callers — only `segment_register_text()` is used by `service.py`. | `grep` across `app/`: only `tests/company_ingest/test_register_segmenter.py` calls `segment_register`. | Dead code, no functional risk, but it's the one actual `Path.read_text()`-on-disk function left in the ingest path (unreachable). |
| `app/company_ingest/store/r2_keys.py` ships 5 key-builder functions (`raw_dataset_key`, `raw_render_key`, `global_file_key`, `parquet_key`, `global_parquet_key`) and `store/r2.py`'s `put_file` with zero production callers. | Leftover from the removed Parquet/`datasets` feature — confirmed by `validate/checks.py`'s own docstring ("checks 9/10/12 were removed by task 2.3 together with the datasets/ and collect/ packages"). | Dead code, no functional risk. |
| Two docstrings are stale: `store/neon.py` says its functions are "managed by the CLI" (no CLI exists); `r2_keys.py` says key builders "default to rpl" (none actually default `company_id` — it's a required arg everywhere). | Direct read. | Misleading to a future reader, no runtime effect. |

## 6. Design decisions that look like hardcoding but aren't

| Looks like | Actually is |
|---|---|
| `ENGINE_COMPANY_ID: str = "rpl"` default in `app/engine/config.py` | Deliberate single-tenant design, documented in `app/api/company/org.py`'s own module docstring: "`company_id` is always the single-tenant `engine_settings.ENGINE_COMPANY_ID`." The app has no auth; every write instead carries an explicit `acting_person_id`. This is overridable via env, not an immutable literal. |
| `2024-12-31` / `2025-01-02` literals in `app/company_ingest/service.py`, `enrich/resolve_citations.py`, `enrich/resolve_citations_db.py` | Fallback **defaults** used only when a document version's own `law_as_of` column (the real, DB-driven source) is unavailable, and when resolving the known 14-day IAC/CFR snapshot-date offset. The literal is repeated in three files as an inline comment/default rather than a shared constant — a minor DRY cleanup opportunity, not a dynamism defect. |
| 14 hardcoded "vertical" literals in `app/api/company/routes.py`'s `VERTICAL_SLUGS` dict and in `frontend/lib/verticals.ts`'s `VERTICALS` array | **This one is a real "make dynamic" candidate.** A `company.verticals` lookup table (14 rows: `name`, `slug`, `description`) was created by migration `9c1e4b7a2f05_verticals_retaxonomy.py` specifically to be the source of truth — but `routes.py` and the frontend still carry their own hardcoded copies instead of reading the table. See `report.md` action list. |

## 7. The enforced invariant

`backend/tests/engine/test_barrier.py` is a standing, currently-green (9/9, re-run this session) guardrail that scans every file under `app/` and `scripts/` for references to `synthetic/`, `corpus/`, the `app/company` legacy path, or hardcoded `RPL-`/`IAC`/`CFR` identifiers, and fails the build if any appear. Its docstring cites the (now git-history-only) `architecture.md` §10: **"the synthetic boundary: `backend/synthetic/` is deletable."** This is why the exhaustive file-by-file grep in `report.md` found zero production imports of `backend/synthetic/` — it isn't an accident, it's CI-enforced, and has been since before this audit.

# Company Documents — Tables & Connections (live-verified 2026-10-31)

_All counts below were read directly from the live Neon database and live Qdrant collection during this audit (read-only `SELECT`s, no writes). This supersedes the counts in `supplement_docs/CompanyData_Pipeline/company_data_storage.md` — that file is kept as-is (not edited) but is stale; see `report.md` (repo root) for the full diff. R2 object counts were independently confirmed via a live paginated listing (after fixing a local `.env` endpoint issue — see `live_ingestion_architecture.md` §4, repo root)._

## 1. Live row counts — `company.*` schema

| Table | Rows (live) | Rows per last-written doc (stale) |
|---|---|---|
| `companies` | 1 | 1 |
| `company_attributes` | 24 | 22 |
| `people` | 27 | 27 |
| `company_documents` | **15** | 12 |
| `document_versions` | **15** | — (not tracked separately in the stale doc) |
| `clauses` | 2,334 | 2,334 (coincidentally unchanged) |
| `clause_citations` | **1,373** | 1,249 |
| `clause_parameters` | **4,186** | 2,948 |
| `defined_terms` | 67 | 67 |
| `term_usages` | **643** | 693 (went *down*, not up — re-ingestion is not monotonic) |
| `clause_links` | **3,296** | 4,675 |
| `document_scope` | **419** | 285 |
| `table_columns` | 40 | 26 |
| `ingest_runs` | present | — |
| `ingest_jobs` | present | — (new table, not in stale doc at all) |
| `datasets` | **does not exist** | listed as a live group of "0 rows" — wrong framing, the table itself is gone |
| `dataset_columns` | **does not exist** | same |
| `parameter_checks` | **does not exist** | same |
| `llm_extractions` | present | — |

New tables not in the stale doc at all (added for the v2 document-control feature): `approval_policies`, `approval_policy_steps`, `approval_requests`, `approval_steps`, `departments`, `document_role_assignments`, `verticals`.

Two tables present that are **temporary migration scaffolding, not permanent schema**: `_approval_policy_vertical_backfill_20261031`, `_vertical_backfill_20261031` — see §4.

## 2. Live row counts — `engine.*` schema (context, confirms the engine has run against this real data)

| Table | Rows |
|---|---|
| `runs` | 2 |
| `candidates` | 1,175 |
| `findings` | 41 |
| `score_reports` | 2 |
| `whatif_scenarios` | 4 |

`score_reports`/`radar_items`/`whatif_scenarios` are read directly by live API routes (`app/api/engine/routes_ui_runs.py`, `routes_radar.py`) that back the `/trust`, `/radar`, and What-If frontend pages. They were originally populated by offline scripts (`score_run.py`, `run_radar.py`, `make_whatif_presets.py`) but are now just ordinary DB rows — the live routes do a flat `SELECT`, never touch a repo file at request time.

## 3. Clause role / Qdrant point-count reconciliation (previously unexplained, now resolved)

| clause_role | count |
|---|---|
| internal_procedure | 1,147 |
| regulatory_restatement | 726 |
| definition | 221 |
| template_field | 204 |
| boilerplate | **36** |

`2,334 clauses − 36 boilerplate = 2,298`, which is exactly the live Qdrant `company_clauses` point count. **Confirmed both by this count match and by code** — `app/company_ingest/index/upsert.py:61`'s own docstring states clauses that are "boilerplate, front matter, blank table rows... are skipped" during indexing. This was previously an unexplained discrepancy in `application_layer.md` (which separately claimed the collection was "absent (404)," also now confirmed wrong — it is live).

## 4. The two migration backup tables — what they are, why they exist, and the loose end

`migrations/versions/9c1e4b7a2f05_verticals_retaxonomy.py` (current migration head, dated 2026-10-31) creates `company.verticals` (14 rows: `name`, `slug`, `description`), then — before remapping `company_documents.vertical` and `approval_policies.applies_to_vertical` to the new taxonomy — snapshots the pre-migration values into `_vertical_backfill_20261031` and `_approval_policy_vertical_backfill_20261031` via `CREATE TABLE ... AS SELECT`. `downgrade()` reads them back to restore old values and **deliberately does not drop them** — the migration's own comment says: *"retain for 30 days post-cutover per plan.md, then drop in a separate, later migration."*

**The loose end:** `plan.md`, `table_schemas.md`, and `"Strata Verticals — Final Reference.md"` — the three documents this migration cites as the authority for that 30-day retention policy and for a per-document vertical override table — are all currently deleted from the working tree (uncommitted `git status` deletions, confirmed by `git show HEAD:<path>`). The migration itself is correct and shouldn't be touched; but nothing durable now records exactly when/how the planned follow-up "drop the backup tables" migration should run. This is a product decision for the user, not something to fix unilaterally — see `report.md`.

## 5. Vertical taxonomy — three sources of the same 14 values

| Source | Location | Status |
|---|---|---|
| `company.verticals` table | Neon, created by `9c1e4b7a2f05` | The new, intended source of truth (14 rows: name/slug/description) |
| `VERTICAL_SLUGS` dict | `app/api/company/routes.py` (hardcoded Python dict, backend-name → frontend-slug) | Still hardcoded, not reading from the table |
| `VERTICALS` array | `frontend/lib/verticals.ts` (hardcoded TS array, with an explicit "keep in sync with backend" comment) | Still hardcoded, not fetched from an API |

This is a genuine "make dynamic" candidate flagged in `report.md`'s action list — the table exists specifically to replace these two hardcoded copies, but nothing has been repointed to it yet.

## 6. Qdrant — `company_clauses` collection

| Property | Value |
|---|---|
| Status | Live, confirmed via `client.get_collection()` this session |
| Points | 2,298 (= non-boilerplate clauses, see §3) |
| Point ID | `stable_uuid(company_id, version_id, clause_id)` using the **real version UUID**, confirmed by reading `app/company_ingest/index/upsert.py:58,75` — not `doc_id` (an earlier stale doc said `doc_id`; this is why `scripts/backfill_qdrant_clauses.py`, which still uses a hardcoded literal `"v1"` in place of the real version UUID, computes wrong IDs and is unsafe to re-run) |
| Vectors | `dense` (384d, cosine, MiniLM) + `bm25` (sparse, IDF) |
| Indexed when | **Only on promotion** — draft/in-review versions are never indexed (`service.py` docstring: "no Qdrant indexing — drafts and in-review versions must never be indexed; promotion indexes the live version") |
| Shared cluster | Yes, isolated by `project = "strata"` payload filter (shared with an unrelated "FDAComplianceAI" collection, confirmed present in the same Qdrant project) |

## 7. R2 — live bucket layout (confirmed by `head_object` checks against the real per-version `version_id`, not key-sort inference)

### ⚠️ Confirmed real gap, broader than first thought: stages 5/5b/9 are incomplete for all 12 prose documents

A head-check of the exact key `company/{company_id}/derived/{doc_id}/{version_id}/clauses.jsonl` (built from `app/company_ingest/store/r2_keys.py::derived_clauses_key`, using each document's **real, current** `version_id` straight from Neon — not inferred from a bucket listing) against all 15 current versions found:

| | doc_id range | Result |
|---|---|---|
| The 3 register-CSV documents | `DOC-000002`, `DOC-000004`, `DOC-000006` | **EXISTS** |
| The 12 prose/docx documents | `DOC-000001`, `DOC-000003`, `DOC-000005`, `DOC-000007`–`DOC-000015` | **MISSING** — confirmed, not inferred |

This looked at first like an isolated R2-write bug. Two further live checks show it's not — the same 3-vs-12 split shows up in Neon itself:

| Check | Registers (3 docs) | Prose (12 docs) |
|---|---|---|
| `clauses.normalized_statement` populated (a stage-5 LLM-enrichment column) | 70/70, 48/48, 86/86 — all clauses | **0 of 2,249** clauses across all 12 documents |
| Rows in `company.llm_extractions` (persistent LLM cache) under the document's `ingest_run_id` | Present for all 3 run_ids | **Absent for all 12** run_ids — `llm_extractions` has only 3 distinct `run_id`s total |

**Correction to this section's earlier framing — read `report.md`'s addendum (finding 2) for the current, more complete picture:** `company.ingest_jobs.state = 'succeeded'` for all 15 **[live]** proves the job wrapper completed — it does **not** prove the recorded run itself did the work, and a later, deeper check (the per-document `is_citation_fragment` NULL pattern, and the presence of cross-document `clause_links` the architecture can't produce — see §8 and the addendum) makes "every document genuinely went through `service.py` today" the claim now in doubt for the 12 prose documents specifically, not a settled conclusion. The register's `report.json` (`DOC-000002`, run `77168fcd-...`) has a fully populated `stats` block and 70 real `issues` entries; the prose's (`DOC-000001`, run `7f30d5ae-...`) shows `"stats": {}, "issues": [], "checks": []`. That asymmetry is now best read as "the register runs are the genuine fresh v2 ingests; the prose runs' recorded metadata doesn't reflect real pipeline work," not as an unexplained bug in an otherwise-confirmed-fresh run.

**Why this doesn't block anything in Part 3 of `report.md`:** nothing in `app/` reads `derived_clauses_key`/`clauses.jsonl` back at request time (confirmed by grep — zero hits outside the two files that write it), and `normalized_statement`/`topic_terms` are read only by `reuse.py` (a re-ingest optimization) and passed through by `promote.py` — never by Qdrant indexing, the engine, or any read API (confirmed by grep, zero hits). It's entirely internal-enrichment/convenience data that no live feature currently exercises. The three things that *do* matter for the app's correctness — Neon's clause existence/count data (0 orphan clauses, exact per-document counts, verified below), Qdrant's index, and the raw-bytes mirror — are all confirmed complete. This is a **real, standalone pipeline bug worth fixing** (it will cost more on the next re-ingest of these documents, not produce wrong output), not a reason to keep the local `synthetic/corpus/` source files around.

### Neon clause integrity (what actually matters for correctness)

Joined `company_documents` → `document_versions` → `clauses` directly (not inferred): all 15 current versions have a nonzero, document-appropriate clause count, summing exactly to 2,334 with **zero orphan clauses** (clauses whose `version_id` doesn't exist in `document_versions`). `clause_id` values use the new `DOC-00000N:local_id` scheme throughout (e.g. `DOC-000001:1.1`) — this confirms the rows are *keyed* under the new v2 ID scheme, which is necessary for a rekey/carryover to even be possible, but is not by itself proof the rows were *freshly computed* by a v2 run (a migration that re-keys old rows onto new IDs would look identical on this specific check). See the addendum for the fuller evidence on whether this is fresh output or carried-over data for the 12 non-register documents.

### Raw-bytes mirror and run reports (confirmed complete by direct `head_object`, not listing-inference)

**Document IDs, corrected:** `company.company_documents.doc_id` is **sequential and synthetic for every one of the 15 documents** — `DOC-000001` through `DOC-000015`, assigned in upload order (the 12 source documents interleaved with the 3 register CSVs, exactly matching `seed.py`'s documented order). The human-readable strings like `RPL-CS-PRO-004` or `RPL-CMP-REG-001#register` live in a **separate column**, `doc_number` — a display label, not the primary key. Real dynamic ID assignment, not a hardcoded legacy/new split.

| Check (head-checked per-document against the real current `version_id`/`ingest_run_id` from Neon) | Result |
|---|---|
| `raw/{doc_id}/{version_no}/{uuid}.{docx\|csv}` | **15/15 EXISTS** |
| `derived/{doc_id}/{version_id}/clauses.jsonl` | **3/15 EXISTS** (registers only) — see the confirmed gap above |
| `ingest_runs/{run_id}/report.json` | **15/15 EXISTS**, confirmed by direct `head_object`/`get_object` against each document's own `ingest_run_id` (an earlier pass of this audit wrongly cited `company/engine/ingest_runs/.../llm/judge/*.json` as this — those are the **impact engine's** own LLM-judge cache, a separate namespace sharing the `company/` prefix, confirmed unrelated to document ingestion) |

**Conclusion: the raw-bytes mirror and run-report mirror are both genuinely complete for all 15 current versions. The derived-snapshot mirror is genuinely incomplete (3/15) — a real pipeline bug, not a blocker to deleting the local `synthetic/corpus/` source files**, since nothing live reads it back and Neon (the actual source of truth) is independently confirmed complete and correct.

### ⚠️ A real landmine found while verifying this, not a cosmetic note

`backend/.env`'s `R2_ENDPOINT` ends in `/strata` (the bucket name), and the app's own boto3 client always also passes `Bucket=settings.R2_BUCKET_NAME` (`"strata"`) on every call. The practical effect, confirmed live: every object the running app has ever written physically sits in the bucket at key `strata/company/...` — **one extra `strata/` segment prepended** versus the clean key (`company/...`) stored in Neon's own `source_r2_key` column and computed by `r2_keys.py`'s builder functions.

This is self-consistent today only because the **same** misconfigured endpoint is used for every PUT and every GET the app makes — the bug cancels itself out from the app's own point of view. **If anyone "fixes" `R2_ENDPOINT` by stripping the `/strata` suffix (as this audit did, read-only, purely to get a listing to work), every existing object becomes unreachable at its expected key from the app's perspective** — `GET company/rpl/raw/DOC-000001/1/....docx` would 404, because the object actually lives at `strata/company/rpl/raw/...`. This would silently break `versions.py`'s retry-from-raw-bytes path and any future download/display of a raw document.

**Do not change `R2_ENDPOINT` without a key migration plan** (either copy every object one segment up, or update every stored `source_r2_key`/`extraction_r2_key`/snapshot key to add the prefix, done atomically). Confirm whether the *deployed* (Render) environment has the same `/strata` suffix before assuming this is local-only — if it does, the app has been silently operating under this double-prefix the whole time and it's not a bug worth fixing casually, just one worth knowing about.

### Orphaned pre-cutover R2 data (separate finding)

Confirmed live: run ID `01e6f1a3-...` (seen under `strata/company/rpl/ingest_runs/01e6f1a3-.../llm/clause_enrichment/*.json`) matches **zero** rows in `company.ingest_runs` (15 total, all 15 accounted for by the current versions) and **zero** `document_versions.ingest_run_id` values. Alongside it, an earlier bucket listing this session also turned up `derived/{RPL-DOC-ID}/v1/clauses.jsonl` objects using the literal `"v1"` version segment — exactly the pre-v2 key collision `snapshot.py`'s own docstring warns about ("the pre-v2 caller passed the literal `'v1'`, so every version collided on one key"). This is leftover data from before the current 15-document state, safe to delete once verified unreferenced (same query pattern as above), tracked in `report.md`'s inventory as its own item — separate from both the `synthetic/` tree and the `R2_ENDPOINT` landmine.

## 8. Table relationships (unchanged shape from `company_data_storage.md`, counts refreshed)

```
company_documents 1---* document_versions 1---* clauses 1---* clause_citations ---> public.code_sections (cross-schema, regulatory DB)
                                                clauses 1---* clause_parameters
                                                clauses 1---* clause_links (self-join: restates / references_*)
                                       document_versions 1---* document_scope ---> public.code_sections
                                                clauses *---* defined_terms (via term_usages)
```

### ⚠️ `clause_links.restates` / `references_clause` cannot cross a document boundary today — and the 12 non-register documents' existing cross-document links raise a separate provenance question

Confirmed by code (`app/company_ingest/link/resolve_refs.py`, `restates.py`, called from `service.py:663-664`): **every** index-building helper in `resolve_refs.py` (`_build_clause_index`, `_build_rule_index`, `_build_form_index`, `_build_series_index`, `_build_obligation_index`) plus `restates.py`'s grouping is built only from the current ingest call's in-memory `units` list — one document's worth of clauses, never a cross-document query. That's all 5 of `LINK_TYPES`' types plus `restates`, not just `references_clause`. `references_doc` (document-level) is checked against a real `SELECT doc_id FROM company.company_documents` query instead — structurally capable, but **unverified**: no translation exists anywhere from a document's human-readable `doc_number` to its internal `doc_id`, and the register documents (the cleanest evidence available) have zero `references_doc` rows either way. No reconciliation pass exists anywhere in `app/` to backfill cross-document links after the fact. This is a standing property of the current per-document ingest API — *consistent with*, though not independently proven beyond the code read by, the 3 register documents (which show every sign of being fresh v2 ingests), which have **zero** cross-document links of any kind despite 68 recorded `unresolved_ref` warnings pointing at other documents. `app/engine/candidates.py`'s `LINK_TYPES` includes `references_clause` (not `restates`), so the confirmed engine impact is specifically on cross-document `references_clause` propagation, for new uploads.

**Separately:** the 12 non-register documents' live `clause_links` **do** contain real cross-document links (`references_clause`, `references_obligation`, `references_record_series`, `references_tariff`, `restates` — hundreds of rows, live-queried), which the architecture above says today's pipeline cannot produce. Combined with those 12 documents' clause counts matching the pre-cutover v1-era snapshot exactly (down to the register-split sums), this is evidence their current data may be carried over/re-keyed rather than fresh v2 output — not proven, but strong enough that re-ingesting any of them in production before this is resolved would silently destroy the cross-document links they currently have. Full detail and severity assessment in `report.md`'s addendum (repo root) — read it before trusting this document's other "confirmed live" claims about those 12 documents specifically.

`clause_citations.code_section_id` and `document_scope.code_section_id` are the only two columns that cross from the `company.*` schema into the regulatory `public.*` schema — this is the full extent of the integration point between the two pipelines, confirmed by code read of `app/company_ingest/enrich/resolve_citations.py` and `app/company_ingest/link/document_scope.py`. Nothing else in the company pipeline touches regulatory tables.

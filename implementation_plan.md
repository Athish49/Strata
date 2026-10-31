# Verticals Migration — Implementation Plan (Task Sequence)

**Read `plan.md` and `table_schemas.md` fully before starting any task below — they are binding references for every decision, mapping, and schema change referenced here by section number. Do not re-derive the taxonomy, the per-document mapping, or the schema design; they are already decided and signed off.**

Each task below states: **Scope**, **Context** (what to read before touching anything), **Change** (what to actually do), **Test**, **Success criteria**. Tasks marked **[PARALLEL]** within the same phase have no file/data overlap and may be run as concurrent sub-agents. Tasks marked **[SEQUENTIAL]** must run in the stated order — later ones depend on earlier ones completing successfully. A phase does not start until all tasks in the previous phase succeed, unless explicitly noted otherwise.

---

## Phase 0 — Gate (sequential, single agent)

### 0.1 Confirm references and environment
- **Scope:** Verify the binding documents and DB access exist before any work starts.
- **Context:** `plan.md`, `table_schemas.md`, `backend/.env` (contains `DATABASE_URL`).
- **Change:** No file changes. Confirm `plan.md` and `table_schemas.md` exist at repo root and are readable. Confirm `psql "$DATABASE_URL" -c "SELECT 1;"` succeeds (read-only check) against production, using the same `.env`-sourcing approach as the research phase (avoid printing the raw connection string to any log).
- **Test:** N/A.
- **Success criteria:** Both docs present and readable; DB reachable.

---

## Phase 1 — Rehearsal migration (sequential, single agent — DB work must not run concurrently with itself)

### 1.1 Create Neon branch for rehearsal
- **Scope:** Branch the production Neon database so the migration can be tested without touching live data.
- **Context:** `backend/.env` for connection details; Neon branching is done via the Neon console/CLI, not psql.
- **Change:** Create a branch off the current production branch. Record its connection string locally (not committed).
- **Test:** `psql` connect to the new branch, confirm `SELECT count(*) FROM company.company_documents;` returns 15.
- **Success criteria:** Branch created, reachable, data matches prod (15 docs).

### 1.2 Write the Alembic migration
- **Scope:** Implement exactly the schema + backfill described in `table_schemas.md` §1–3, §6, §7.
- **Context:** `table_schemas.md` §1 (new `company.verticals` table + seed rows from §5), §2 (FK additions to `company_documents.vertical` and `approval_policies.applies_to_vertical`, including the `org.py` validation gap noted — that's a code fix, tracked separately in Phase 2, not part of this migration file), §3 (backup tables — create before the UPDATE), §6 (default mapping, all 14 old names) and §7 (explicit per-`doc_number` overrides for the 15 live docs). Existing migration style reference: `backend/migrations/versions/f7b2c91d4a08_v2_document_versioning.py` (for `approval_policies`) and `c3d4e5f6a7b8_company_schema.py` (for `company_documents`).
- **Change:**
  1. `upgrade()`: create `company.verticals`, seed 14 rows (§5). Create both backup tables via `CREATE TABLE ... AS SELECT` per the exact statements in `table_schemas.md` §3. Build the mapping (default §6 keyed on old stored name, overridden per `doc_number` via a join to `company_documents.doc_number` for the 15 explicit rows in §7) and run `UPDATE company.company_documents SET vertical = <mapped> WHERE ...` — **`SET` clause must list only `vertical`, never `updated_at`** (table_schemas.md §2 note on the missing trigger). If any live `vertical` value has no mapping entry, `raise` to abort the transaction — do not silently null or skip. Then add both FK constraints (`ON UPDATE CASCADE`, nullable) in the same transaction.
  2. `downgrade()`: drop both FK constraints, restore `vertical`/`applies_to_vertical` from the two backup tables (join on PK), drop `company.verticals`. Do **not** drop the backup tables in this migration (table_schemas.md §3 — retain for the stated window; dropping them is a separate future migration).
- **Test:** `alembic upgrade head` then `alembic downgrade -1` then `alembic upgrade head` again, against the Neon branch from 1.1 — confirms both directions execute cleanly and idempotently.
- **Success criteria:** Migration applies and reverses cleanly on the branch with no manual intervention.

### 1.3 Apply to branch and verify
- **Scope:** Run the migration against the rehearsal branch and check every invariant before touching production.
- **Context:** `table_schemas.md` §4 (invariant row counts), §7 (expected distribution).
- **Change:** No code change — verification only. Apply migration (if not already applied by 1.2's test) to the branch and leave it applied.
- **Test:**
  1. Row counts for `clauses`, `clause_links`, `clause_citations`, `document_versions`, `document_scope`, `approval_requests`, `approval_steps`, `engine.doc_rollups`, `engine.findings`, `company_documents` — all must match the baseline in `table_schemas.md` §4 exactly.
  2. `SELECT vertical, count(*) FROM company.company_documents GROUP BY 1 ORDER BY 1;` — must match the expected distribution in `table_schemas.md` §7 exactly (Compliance & Ethics=6, Operations & Quality=3, Financial Compliance & Reporting=2, Information Technology & Records=2, Environmental & Sustainability=1, Health & Safety=1).
  3. `SELECT count(*) FROM company.company_documents WHERE vertical IS NOT NULL AND vertical NOT IN (SELECT name FROM company.verticals);` — must return 0.
  4. Run `backend/synthetic/rehearsal_inner.py` against the branch — must pass (it asserts no seeded doc is "unclassified").
- **Success criteria:** All four checks pass. If any fails, fix the migration (back to 1.2) — do not proceed to Phase 2 verification or Phase 5 with a failing rehearsal.

---

## Phase 2 — Code changes (3 tasks, **[PARALLEL]** — independent files/directories, no shared-file conflicts, can start as soon as Phase 1 sign-off data is final; does not require the branch DB to be up)

### 2.1 [PARALLEL] Backend code
- **Scope:** Update every backend code location that defines or validates the vertical allowlist.
- **Context:** `table_schemas.md` §5 (new names/slugs/descriptions), §8 (full list of code locations). Files: `backend/app/api/company/routes.py` (`VERTICAL_SLUGS`), `backend/app/api/company/upload.py` (`_canonical_vertical`), `backend/app/api/company/org.py` (`create_policy` line ~632, `update_policy` line ~660 — **add missing `_canonical_vertical()` validation**, per `table_schemas.md` §2's noted gap), `backend/synthetic/corpus_meta.py` (`CANONICAL_VERTICALS`).
- **Change:** Replace the 14 old name/slug entries with the 14 new ones everywhere listed above. Add `_canonical_vertical(body.applies_to_vertical)` validation calls in `org.py`'s policy create/update routes (currently absent), returning 422 on an invalid value instead of letting a bad value reach the DB. Extend `backend/tests/synthetic/test_corpus_meta.py`'s existing pinning pattern (it currently AST-parses `VERTICAL_SLUGS` and compares to `CANONICAL_VERTICALS`) to also assert the migration's seed list (§5) and `frontend/lib/verticals.ts`/`frontend/scripts/build-fixtures.ts` (read as text/AST, same technique) all agree — this is the one shared cross-reference test, write it once here.
- **Test:** `test_corpus_meta.py` passes. Manually submit an invalid vertical to `POST /company/approval-policies` and confirm 422, not 500.
- **Success criteria:** All 14 new names/slugs present and consistent across the 3 backend files; policy routes reject invalid verticals with 422.

### 2.2 [PARALLEL] Frontend code
- **Scope:** Update every frontend code location that defines, displays, or validates the vertical allowlist.
- **Context:** `table_schemas.md` §5, §8. Files: `frontend/lib/verticals.ts`, `frontend/scripts/build-fixtures.ts` (constants at ~lines 69-93 **and** every individual hardcoded sample-document row from ~line 524 onward), `frontend/fixtures/company/documents.json` (regenerated, don't hand-edit).
- **Change:** Replace the 14 entries in `lib/verticals.ts` with the new name/slug/description from `table_schemas.md` §5 (descriptions sourced verbatim from the "What It Covers" column — do not paraphrase). In `build-fixtures.ts`, update the slug/order constants, then remap **every** sample-document row's hardcoded old-slug literal through the default mapping in `table_schemas.md` §6 (not just the constants — the research found dozens of individual rows with their own literal slug). Regenerate `frontend/fixtures/company/documents.json` by running the script. Confirm `frontend/lib/future-features.ts:95`'s `PAGE_CUES["vertical"]` key is untouched (confirmed in `table_schemas.md` §8 to be a page-type key, not a vertical name — do not change it).
- **Test:** `npm run build` (or equivalent type-check) in `frontend/` succeeds. Spot-check the regenerated `documents.json` has no leftover old slug strings: `grep -E "policy-governance|compliance-legal|financial-reporting|revenue-pricing|operations-processes|technology-systems|workforce-hr|environmental-esg|supply-chain-procurement|risk-insurance|strategic-competitive|reputational-stakeholder|contractual-third-party|capital-infrastructure" frontend/fixtures/company/documents.json` returns nothing.
- **Success criteria:** No old slug/name string remains in any frontend source or fixture file; type-check passes.

### 2.3 [PARALLEL] Seed / synthetic data
- **Scope:** Update the synthetic corpus so a future re-seed doesn't resurrect the old vertical names.
- **Context:** `table_schemas.md` §6 (default mapping) and §7 (explicit per-`doc_number` overrides — this is the authoritative source, not a blanket find-and-replace, because the old "Policy & Governance"/"Compliance & Legal" buckets split non-1:1). Files: `backend/synthetic/corpus/_global/document_register.csv` (`vertical` column), per-doc front matter under `backend/synthetic/corpus/docs/*/` (the `vertical:` key).
- **Change:** For each of the 15 `doc_number` rows (join key, not `doc_id`), set `vertical` to the explicit override in `table_schemas.md` §7. Do not apply the §6 default table to these 15 — they all have explicit overrides. (The §6 default table exists for any *other* environment's seed data that might contain additional old-vertical documents outside this list — apply it there if such rows exist.)
- **Test:** `grep -c` each old vertical name in `document_register.csv` and all front-matter files — must return 0 matches for all 14 old names.
- **Success criteria:** No old vertical name remains in any seed/corpus file; every `doc_number` in the CSV matches its `table_schemas.md` §7 target.

---

## Phase 3 — Test updates (2 tasks, **[PARALLEL]**, depends on Phase 2 completing — tests reference the new names Phase 2 introduced)

### 3.1 [PARALLEL] Backend tests
- **Scope:** Update every backend test that hardcodes an old vertical name/slug, and check for tests that will now violate the new FK.
- **Context:** `backend/tests/api_company/*` (`test_company_routes.py`, `test_doc_admin.py`, `test_org_endpoints.py`, `test_upload.py`), `backend/tests/synthetic/test_seed.py`, `backend/tests/company_ingest/test_front_matter.py` — this is the exact test list in `plan.md`'s "Code updates required" section. `test_corpus_meta.py` was already extended in 2.1 per `plan.md` — just confirm it passes here, no further edits.
- **Change:** Replace hardcoded old vertical strings with the new ones per `table_schemas.md` §6/§7 as applicable to each test's fixture data. **Grep for any direct SQL `INSERT` with a literal vertical string** — these will now hit the new FK constraint if the literal isn't one of the 14 new names; fix each one.
- **Test:** `pytest` full suite.
- **Success criteria:** Full backend suite passes, zero FK violations, zero hardcoded old names remaining (`grep` confirms).

### 3.2 [PARALLEL] Frontend tests
- **Scope:** Update every frontend test that hardcodes an old vertical slug/name.
- **Context:** This is the exact test list from `plan.md`'s "Code updates required" section: `frontend/tests/unit/verticals.test.ts` (update `realVerticals()` assertion from 5 to 6 entries per `table_schemas.md` §7's expected distribution), `documents-board-logic.test.tsx`, `company-fixtures.test.ts`, `http-company.test.ts`, `http-company-writes.test.ts`, `upload-dialog.test.tsx`, `kb-logic.test.tsx`, `engine-structure.test.tsx`, plus `frontend/tests/e2e/company-and-kb.spec.ts` and `frontend/tests/support/mock-api/company.ts` (mock upload endpoint's allowlist replica), both called out separately in `plan.md`.
- **Change:** Replace hardcoded old slugs with new ones per `table_schemas.md` §6/§7.
- **Test:** Frontend unit test suite + e2e spec.
- **Success criteria:** All frontend tests pass, zero hardcoded old slugs remaining.

---

## Phase 4 — Local verification (sequential, single agent, depends on Phases 1–3 all complete)

### 4.1 Full-suite verification against the rehearsal branch
- **Scope:** Confirm Phase 2/3 code changes work correctly against the already-migrated Neon branch from Phase 1.
- **Context:** Point local backend config at the Phase-1 branch connection string.
- **Change:** None — verification only.
- **Test:** Run full `pytest` suite and frontend test suite against the branch-backed backend. Manually walk the UI: documents board shows the new vertical names, each new vertical's page loads and shows the correct documents per `table_schemas.md` §7, the upload dialog's dropdown lists the 14 new verticals, the admin PATCH endpoint accepts a new vertical name and rejects an old one (422), and approval-policy create/update reject an invalid vertical with 422 (confirming 2.1's fix).
- **Success criteria:** Everything above passes against the rehearsed branch, with zero manual data fixes required — this is the dry run for Phase 5.

---

## Phase 5 — Production cutover (sequential, single agent, requires a maintenance window — human-supervised, not run unattended)

### 5.1 Stop the backend
- **Scope:** Take uploads offline for the window (no feature-flag mechanism exists for this per `plan.md` — a process stop is the chosen mechanism).
- **Change:** Stop the backend service.
- **Success criteria:** Backend confirmed stopped; no in-flight uploads.

### 5.2 Apply the Alembic migration to production
- **Scope:** Run the exact migration validated in Phase 1, against production this time.
- **Context:** `table_schemas.md` §1–3, §6–7 (same migration file from 1.2 — no changes between rehearsal and production).
- **Change:** `alembic upgrade head` against the production `DATABASE_URL`.
- **Test:** Immediately re-run the Phase 1.3 verification queries against production.
- **Success criteria:** Same as 1.3, now against production: row-count invariants hold, distribution matches `table_schemas.md` §7, 0 unmapped values.

### 5.3 Deploy backend and frontend
- **Scope:** Ship the Phase 2 code changes.
- **Change:** Deploy backend (2.1 changes) and frontend (2.2 changes) together — per `plan.md`'s cutover decision (step 4), both must land in the same window because the backend's allowlist (`VERTICAL_SLUGS`/`_canonical_vertical`) and the frontend's allowlist (`lib/verticals.ts`) must agree on the same 14 names at all times; shipping one without the other reintroduces the "4 hand-synced copies out of sync" risk `plan.md` identifies as the core fragility this migration closes.
- **Success criteria:** Both deployed, health checks green.

### 5.4 Restart the backend
- **Scope:** Reopen the system for uploads.
- **Change:** Restart the backend service.
- **Success criteria:** Service healthy, uploads functional.

---

## Phase 6 — Post-migration verification (sequential, single agent)

### 6.1 Production invariant check
- **Scope:** Final confirmation nothing is orphaned or corrupted.
- **Test:** Re-run every check from `table_schemas.md` §4 (row-count invariants) and §7 (distribution) against production. Run a manual UI walkthrough identical to Phase 4.1's, now against production.
- **Success criteria:** All invariants hold; UI walkthrough clean; no error-rate spike in the minutes following reopen.

### 6.2 Monitor
- **Scope:** Watch for any delayed failure.
- **Change:** None.
- **Success criteria:** No vertical-related errors in logs over the following day (422s on upload with an unrecognized vertical are expected/healthy; 500s are not).

---

## Phase 7 — Deferred cleanup (future task, explicitly NOT part of this run)

### 7.1 Drop backup tables
- **Scope:** After the stated retention window (recommend 30 days post-cutover) and confirmed stability, drop `company._vertical_backfill_20261031` and `company._approval_policy_vertical_backfill_20261031` in a new, separate Alembic migration.
- **Do not schedule or execute this as part of the current migration run.** It is listed here only so it isn't forgotten.

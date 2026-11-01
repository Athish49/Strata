# Implementation Plan — Company Documents Pipeline Decoupling

**Source:** `report.md`, `live_ingestion_architecture.md`, `tables_and_connections.md` (all at repo root). This plan breaks that audit's action list into discrete, independently-executable tasks for sub-agents, with explicit ownership, dependencies, and parallelism.

**Note on task numbering:** several code comments in this repo (`test_export.py`, `test_service.py`, `test_w1_foundations.py`) cite task IDs like "task 9.4" or "task 1.1.1" from an **earlier, unrelated** `implementation_plan.md` that existed before this one (recoverable via `git log --all -- implementation_plan.md`, confirmed by the prior audit session). The task IDs below (1.1, 1.2, …) are fresh and bear no relation to those — task 1.1 in this file is not the same as "task 1.1.1" in old comments. Task 1.1 below explicitly includes removing the one stale cross-reference this causes.

**Recovery anchor:** `git rev-parse HEAD` = `147cf2dd9ab6a7cbf7f789eee2daf0d0e42a4245`. Everything under `backend/synthetic/` is tracked at this commit. Deleting it later is recoverable via `git show 147cf2d:backend/synthetic/<path>` unless history is rewritten — treat local-file deletions in this plan as low-risk, not irreversible.

**Baselines captured this session (compare against these, don't re-derive counts from memory) — two different numbers, use the right one:**
- Backend, node IDs: `pytest -m "not neon and not qdrant and not corpus" --collect-only -q` → 1,473 node IDs saved to `.audit_baseline_backend_nodeids.txt` (repo root, currently untracked — `git add` it if it should survive a commit). This collection count doesn't depend on DB connectivity and is the same either way.
- Backend, pass/skip count **in a real, connected `.env`**: 1,473 passed, 0 skipped.
- Backend, pass/skip count **in an isolated worktree with a dummy `.env`** (what every sub-agent will actually see — use this one as the real baseline for acceptance checks): 1,470 passed, 3 skipped — `tests/engine/test_llm.py::test_live_smoke` (skips once `LLM_API_KEY` is blanked, see guardrail 7) and `tests/engine/test_reviews_ui.py`'s two live-Neon tests (see guardrail 1). 0 failed in both environments once `LLM_API_KEY` is blanked.
- Frontend: `pnpm test` → 43 files / 435 tests, all passing. `pnpm typecheck` → clean, zero errors.

---

## Guardrails — read before executing any task

1. **`backend/.env` points at live production Neon, Qdrant, and R2.** No task in this plan runs a database migration, a script under `backend/scripts/` or `backend/synthetic/`, or a `pytest -m neon`/`-m qdrant`-marked test against it without the explicit gate noted on that task. **The default command (`pytest -m "not neon and not qdrant and not corpus"`) is not fully isolated — confirmed this session, don't assume it is:** `tests/engine/test_reviews_ui.py::test_accept_then_visible_and_reject_rules` and `::test_unknown_finding_or_person_404` connect to live Neon and exercise a real review-accept/reject write path, unmarked by `neon`, wrapped in a transaction that's always rolled back (no permanent write — confirmed by reading the test's `live` fixture). Run tasks against a *disconnected* backend (rule 7's worktree setup) specifically so these two skip cleanly instead of touching production.
2. **Migrations are serialized, never parallel.** Alembic has one linear chain. If two tasks each create a new revision off the same head, `alembic upgrade head` gets two heads and Render's deploy-time `alembic upgrade head` (see `backend/render.yaml`) fails the next deploy. In this round, two possible future migrations exist: 5.3 (dropping the backup tables, explicitly deferred past this round, date-gated) and 3.4's Option B deploy 2 (dropping `is_citation_fragment`, only if that option is chosen, and only as a second deploy after its code-only first deploy is stable). **Neither is scheduled to run in this round** — but whichever one is created first must land before the other is written, and each must check `alembic heads` shows exactly one head immediately before writing its revision. No two migration-writing tasks run concurrently, ever.
3. **File ownership.** Task 3.4 (is_citation_fragment wiring) does **not** touch `app/company_ingest/service.py` — its changes live in `enrich/parameter_entry.py`, `enrich/parameters_regex.py`, and `store/neon.py`, so it has no file overlap with anything else scheduled in this round and can run in Group A. `service.py` itself is currently only touched by task 5.4 (collapsing date-literal constants), which is why 5.4 is listed solo rather than in Group A — not because of a conflict with 3.4. **If and when a fix comes out of task 1.0's or 1.2's investigation and that fix touches `service.py`, it must run sequentially with 5.4** (or any other `service.py`-touching task active at that time), not in parallel — re-check this guardrail when that follow-up task is created, since this round has no such conflict yet. Task 3.2 bundles the `r2_keys.py` dead-code removal with its stale docstring fix into one task for the analogous reason — don't split it across agents. The `store/neon.py` docstring fix moved into task 3.4 (it already touches that file's INSERT statement) — 3.2 no longer touches `neon.py` at all.
4. **Git hygiene.** Each parallel task works in its own `git worktree`, not just "stages only the files it owns" — two agents editing the same working directory, even disjoint files, will stomp each other's uncommitted state and git index. Never `git add -A`. Never touch or recreate `"Strata Verticals — Final Reference.md"`, `plan.md`, or `table_schemas.md` — the user deleted those from the working tree themselves, as their own in-progress change, unrelated to this plan. **`implementation_plan.md` — this file — is different: it exists at `HEAD` as an older, unrelated vertical-taxonomy plan and this session overwrote it in the working tree with the plan you're reading.** `git status` shows it as modified, not new. **Never run `git checkout -- implementation_plan.md` or any other command that would discard the working-tree version** — that would restore the old committed content and destroy this plan; if the old content is ever needed for reference, read it read-only via `git show HEAD:implementation_plan.md`, never by checking it out over this file. No commits unless the user explicitly asks for one at that point. **Merging any of this to the branch Render deploys from is itself a production deploy** — its start command runs `alembic upgrade head` automatically (`backend/render.yaml`). Treat a merge, not just a migration file, as the trigger for guardrail 2.
5. **Never upload, create a new version of, or re-ingest any company document against production while tasks 1.0/1.2 are open.** This applies beyond task 1.2's own guardrail — it also covers task 1.4's `seed.py` check (run it with `--plan` only, never for real against production) and any other task that might be tempted to "just try an upload" to verify something.
6. **Every task's acceptance check includes a baseline diff**, not just "tests pass" — compare node-ID lists (backend) or file/test counts (frontend) against the saved baselines above, not just a pass/fail count, so a silently-skipped test doesn't read as success.
7. **Worktree setup for every backend task, including Phase 4's doc-only ones if they run alongside code tasks:**
   - `git worktree add <path> <branch>` from the main checkout — do not clone fresh (loses the local `.venv`/`node_modules` install time).
   - Copy (don't symlink) `backend/.env.example` to the worktree's `backend/.env`, **not** the real `backend/.env`. Its placeholder values (`host`, `your-cluster.qdrant.io`, etc.) fail DNS fast rather than hanging, and physically enforce guardrail 1 — a task literally cannot reach production even if its code tries to.
   - Point `PYTHONPATH`/the venv invocation at the **existing** `backend/.venv` by absolute path (`/Users/athish/Documents/Strata/backend/.venv/bin/python`) from inside the worktree — don't recreate it per worktree.
   - Reference `.audit_baseline_backend_nodeids.txt` by its absolute repo-root path, since a worktree's relative root differs.
   - **Already run this session, with one finding — don't re-discover it, account for it.** With a copy of `.env.example` as-is: `1,470 passed, 1 failed, 2 skipped, 114 deselected`. The one failure, `tests/engine/test_llm.py::test_live_smoke`, is **not** a Neon/Qdrant/R2 leak (none occurred) — it's a real, unmarked attempt to call the live Anthropic API, because `.env.example`'s `LLM_API_KEY=your-anthropic-api-key` placeholder is a non-empty string, so the test's own `if not settings.LLM_API_KEY: skip` guard doesn't trigger, and the call fails against an invalid key instead of skipping. **Before using `.env.example` as the dummy env in any worktree, blank `LLM_API_KEY=` to an empty string** so this test skips cleanly — otherwise expect this one pre-existing failure every time, unrelated to whatever task is running. Separately, `test_live_smoke` is not `neon`/`qdrant`/`corpus`-marked, so it currently also runs (and makes a real paid API call) during any normal default-suite run against the real `.env` — this is a pre-existing test-hygiene gap outside this plan's scope, worth a one-line note back to the user, not a task to fix here.
   - **Re-run this check after any task that adds a new test or fixture**, to catch the same class of problem early — a sub-agent should not assume the dummy-env baseline stays valid forever.
   - Frontend tasks: same pattern with `pnpm install` already run once in the main checkout; a worktree can reuse `frontend/node_modules` by absolute path rather than reinstalling.
   - Tasks 1.1 and 1.5 temporarily rename `backend/synthetic` during their own acceptance checks — this is exactly why worktree isolation (not shared-directory "stage only your files") matters: a shared directory would break any other task reading `backend/synthetic` mid-run.

---

## Decision gates — get explicit user sign-off before executing the gated tasks

| Gate | Question | Default if no answer given | Blocks |
|---|---|---|---|
| **DG-1** | Relocate `backend/synthetic/seed.py` (the only bulk-upload tool) somewhere outside the app repo, or let it be deleted with no replacement? | Relocate to a new `tools/demo-seed/` or similar, outside `backend/app` | Task 1.4, then 2.1 |
| **DG-2** | Copy `corpus/_global/ops/*` (43,400 raw CSV rows, the audit trail behind numbers already baked into the 12 documents) and `corpus/grounding/_scope.py`/`_normalizer.py` (the only surviving doc-generation machinery) out of the repo before deletion, or accept the loss? | Copy out (cheap insurance, ~low effort) | Task 1.3, then 2.1 |
| **DG-3** | Make the frontend's vertical list dynamic (fetch from a new `GET /company/verticals`), or keep it static? | **Keep static** — the blast radius is real (~10 files, an async route-guard rewrite, a `sort_order` DB column needed, a full rewrite of `frontend/tests/unit/verticals.test.ts`'s hardcoded assertions) and nothing requires it today | Task 3.7 (skipped by default) |
| **DG-4** | `is_citation_fragment` is unwired at write time **and confirmed dead at all 3 read sites** (`candidates.py`, `rules.py`, `judge.py` — see task 3.4's card for the boolean proof). Wire it in (Option A) or delete the column/script/read-sites entirely (Option B)? Either is low-risk since nothing currently depends on its value. | No default — genuinely a toss-up; Option B fits this audit's "remove unused code" goal better, Option A preserves a feature that might matter later if the engine logic changes | Task 3.4 (which option), then 3.5 only if A |
| **DG-5** | When should the two migration backup tables actually be dropped? | **Not before 2026-11-30** (30-day retention from the migration's creation date) | Task 5.3 (not scheduled this round regardless) |
| **DG-6** | Fix the `R2_ENDPOINT` double-prefix misconfiguration? | **No — not in this round.** Needs a full key-migration plan first (see `tables_and_connections.md` §7); fixing the env var alone orphans every existing object | Task 5.1 stays investigation-only |
| **DG-7** | Delete the confirmed-orphaned R2 objects (old `v1`-keyed derived snapshots, the stale `01e6f1a3…` LLM-cache audit JSONs)? | Approve after task 5.2 re-confirms they're still unreferenced immediately before deleting | Task 5.2 |
| **DG-8** | Delete `tools/offline_eval/` together with `backend/synthetic/`, or keep it as a standalone manual tool? | Delete — it only reads `*.basis.json` files that live inside `backend/synthetic/corpus/` | Task 2.1's scope |
| **DG-9** | Add a small sample of real `.docx` files to `tests/fixtures/` (today's single fixture covers only 1 of 12 documents), in addition to the 3 register CSVs? | Copy the 3 CSVs (required to avoid losing coverage outright); the extra docx samples are optional, lower priority | Task 1.5 |

---

## Task index (orchestration summary)

| Task | Phase | Depends on | Parallel group | Approval needed | Can a fresh sub-agent run this cold? |
|---|---|---|---|---|---|
| **1.0 Investigate the cross-document `restates`/`references_clause` gap** | 1 | none | C (read-only) | no | Partially — see task card |
| 1.1 Split `test_export.py` | 1 | none | A | no | Yes |
| 1.2 Investigate stages 5/5b/9 gap | 1 | none (must finish before 2.1) | C (read-only) | no | Partially — see task card |
| 1.3 Copy out ops data + grounding code | 1 | DG-2 | A | **DG-2** | Yes |
| 1.4 Relocate/retire `seed.py` | 1 | DG-1 | A | **DG-1** | Yes |
| 1.5 Add register-CSV + docx test fixtures | 1 | none | A | DG-9 (partial) | Yes |
| 1.6 Re-confirm baselines before deletion | 1 | 1.1–1.5 done | — (gate, not parallel) | no | Yes |
| 2.1 Delete `synthetic/`, `tests/synthetic/`, `tools/offline_eval/` | 2 | 1.1–1.6 all done | — (single task) | DG-8 | Yes |
| 3.1 `register_segmenter` cleanup | 3 | none | A | no | Yes |
| 3.2 `r2_keys.py`/`r2.py` dead-code + docstring | 3 | none | A | no | Yes |
| 3.3 Delete 2 superseded scripts | 3 | none | A | no | Yes |
| 3.4 Decide + implement: wire `is_citation_fragment` in, or delete it (expand/contract if B) | 3 | **DG-4 picks the option first.** Option A doesn't wait on 1.2 (validated against `test_service.py`'s fixture harness, not production). Option B's code-only deploy should wait for 1.2 to confirm it's done with the NULL/set split as evidence. | A for Option A (does not touch `service.py` — see guardrail 3); solo for Option B's migration deploy | **DG-4** | Yes |
| 3.5 Backfill existing NULLs | 3 | 3.4 (Option A) merged + verified, **and 1.2 finished** — the 1,766-NULL/2,420-set split is part of 1.2's evidence | — (solo, production write) | **DG-4** | Yes, but needs explicit go-ahead first |
| 3.6 Vertical taxonomy backend repoint | 3 | none | A | no | Yes |
| 3.7 Vertical taxonomy frontend dynamism | 3 | 3.6, new `sort_order` migration | — (deferred) | **DG-3** | Skip by default |
| 4.1 Fix `README.md` | 4 | none | A | no | Yes |
| 4.2 Fix `application_layer.md` | 4 | none | A | no | Yes |
| 4.3 Pointer notes on stale docs | 4 | none | A | no | Yes |
| 4.4 Fix `build-fixtures.ts`/frontend README stale path | 4 | none (functional repoint depends on 1.3/1.4 outcome) | A | no | Yes |
| 5.1 Confirm deployed `R2_ENDPOINT` | 5 | none | — (human, not an agent) | **DG-6** | **No — human only, dashboard access** |
| 5.2 Delete orphaned R2 objects | 5 | **1.2 must finish first** — these orphaned objects are task 1.2's primary evidence | — (solo, production delete) | **DG-7** | Yes, but needs explicit go-ahead first |
| 5.3 Drop migration backup tables | 5 | DG-5 date reached | — (not scheduled this round) | **DG-5**, date-gated | Not before 2026-11-30 |
| 5.4 Collapse date-literal constants | 5 | none this round; **future** `service.py` fixes from 1.0/1.2 must serialize with this | B (solo — currently the only `service.py` toucher) | no | Yes |

**Parallel group A** = 13 tasks with no file overlap (1.1, 1.3, 1.4, 1.5, 3.1, 3.2, 3.3, **3.4**, 3.6, 4.1, 4.2, 4.3, 4.4) — can all run as separate concurrent sub-agents right now, each in its own worktree per the setup guardrail. **Parallel group B** = `service.py` touchers — currently just 5.4, solo; re-evaluate when a follow-up fix from 1.0/1.2 is scheduled, since that will also touch `service.py`. **Parallel group C** = the two read-only investigations (1.0, 1.2) — safe to run alongside group A since they write no files, but see each task card for the human-only sub-steps and the scratch-DB-only reproduction rule. Everything else is a solo task (either a single step, or explicitly gated/deferred).

---

## Phase 1 — Preconditions (must complete before Phase 2's deletion)

### 1.0 — Investigate the cross-document `restates`/`references_clause` gap (read-only; highest priority in this plan)

**Goal:** this is the top finding of the whole audit (see `report.md`'s addendum). Confirmed by code, not yet confirmed in terms of exact product impact or a fix design. Owns no files — produces a findings/design note.

**Confirmed already, don't re-derive:** `app/company_ingest/service.py:663-664` calls `resolve_references(units, known_doc_ids, ctx)` and `find_restates_links(units, links, ctx)` with `units` scoped to the single document being ingested. Every index-building helper in `resolve_refs.py` (`_build_clause_index`, `_build_rule_index`, `_build_form_index`, `_build_series_index`, `_build_obligation_index`) takes only that in-memory `units` list, confirmed by reading every signature — so **all 5 of `LINK_TYPES`' link types, plus `restates`, are single-document-scoped, not just `references_clause`**. `references_doc` is structurally different — checked against a real `company.company_documents` query — but **whether it actually works for real documents is unconfirmed, not proven**: no code anywhere in `enrich/references.py` or `resolve_refs.py` translates a document's human-readable `doc_number` (e.g. "RPL-TAR-GRR-012," the form prose would actually name a document by) into its internal `doc_id` (e.g. "DOC-000007") — confirmed by grep, zero hits — and the one source of likely-fresh v2 data (the register documents) has zero `references_doc` rows to test it against either way. No reconciliation pass exists anywhere in `app/` (confirmed by grep for "relink"/"reconcile"/"cross_document").

**Consistent with, not independently proven by, the cleanest live data available:** the 3 register documents (`DOC-000002`/`000004`/`000006`) show every sign of being fresh v2 ingests (full `report.json` stats, real `llm_extractions` rows, real R2 derived snapshots) and have **zero** cross-document links of any kind, despite 68 recorded `unresolved_ref` warnings pointing at other documents — matching the code-level finding. Treat this as corroboration, not a second independent proof; their reference hints are also in the untranslated `doc_number` format, so this data can't distinguish "cross-doc resolution is architecturally impossible" from "it's possible but the hint format defeats it" on its own — the code read already settles that question regardless.

**Narrower than an earlier pass of this plan claimed on engine impact — confirm before writing anything up:** `app/engine/candidates.py`'s `LINK_TYPES` constant is `("references_clause", "references_obligation", "references_record_series", "references_tariff", "references_form")` — it does **not** include `restates`. So the confirmed engine-impact is on cross-document `references_clause` (and the other 4 reference types) specifically; `restates` links are confirmed cross-document-incapable too, but this task found no evidence they feed candidate propagation at all — don't claim an engine-impact for `restates` without finding a real consumer first.

**Do this task using the 3 register documents as your evidence base, not the 12 others** — see task 1.2 for why the other 12's data is a separate, open question whose own resolution shouldn't be assumed here.

**Steps:**
1. Confirm product impact precisely using the register documents' own recorded `unresolved_ref` warnings (their `report.json` already lists which cross-document references failed to resolve, with target hints) — pick one, manually trace whether the engine's current 41 findings would have included an additional cross-document finding had the link existed. This turns "the mechanism is broken" into "and here's a specific finding we're missing today," which is the number the user will want. **Do not use the 12 non-register documents for this trace** — their link data's provenance is in question (task 1.2); using it here would taint the conclusion.
2. Decide (propose options, don't just pick one) how a fix should work architecturally — this is a design question, not a quick patch:
   - (a) On every ingest, re-run `resolve_references`/`find_restates_links` with units pulled from **all** of the company's current clauses (query Neon, not just the one document's in-memory units) — simplest, but changes per-document ingest into an operation whose cost scales with corpus size.
   - (b) A background reconciliation job (triggered post-promotion, or on a schedule) that re-scans the whole corpus for cross-document links — matches v1's batch-processing model more closely, but reintroduces a job that per-document ingest was specifically designed to avoid.
   - (c) Something narrower — e.g. only re-resolve `references_clause` entries that failed to resolve at ingest time (the `unresolved_ref` warnings already recorded in each run's `report.json` are a ready-made backlog), triggered whenever a new document is promoted.
3. **Already confirmed this session, carry it into the write-up, don't re-derive it:** none of options (a)/(b)/(c) are as simple as they look, because no translation step exists anywhere between a reference's `target_hint` (which uses `doc_number`-style values like `RPL-TAR-GRR-012`, per the register documents' own warnings) and the internal `doc_id` (`DOC-00000N`) that `company_documents`/`clauses` actually key on — confirmed by grep of `enrich/references.py` and `resolve_refs.py`, zero hits. Any fix option needs this translation added as part of it, not as an assumed-solved prerequisite.
4. Write up: the confirmed mechanism (above), the concrete missed-finding example from step 1, the hint-format note from step 3, and the options from step 2 with tradeoffs — as a decision document for the user, not a silent code change. **Do not implement a fix in this task** — get the user's choice of approach first, then this becomes its own follow-up task with its own task card.

**Acceptance:** a written decision document exists covering steps 1–4; no code was changed.

**Rollback:** n/a (read-only).

---

### 1.1 — Split `tests/engine/test_export.py`

**Goal:** stop 5 unrelated tests from being skipped as a side effect of `backend/synthetic/` being deleted.

**Owned files:** `backend/tests/engine/test_export.py` (modify), new file `backend/tests/engine/test_score_run_metrics.py` (create).
**Reference only:** `backend/synthetic/score_run.py`.

**Steps:**
1. Read `test_export.py` in full (it's short, ~130 lines).
2. Move `test_parse_metrics_s2` and `test_parse_metrics_baseline_and_garbage` — the only two tests that actually use the dynamically-imported `score_run` module — into a new file `test_score_run_metrics.py`, keeping the module-level guard (`if not _SCORE_RUN.exists(): pytest.skip(..., allow_module_level=True)`) and the dynamic `importlib` load in that new file only.
3. Leave `test_section_level`, `test_assemble_export_all_docs_and_status`, `test_assemble_export_rekeys_doc_id_and_clause_id_to_doc_number`, `test_build_export_with_fake_session`, and `test_build_export_rejects_whatif` in `test_export.py`, with the dynamic `score_run` import and its guard **removed entirely** — they only need `app.engine.export`.
4. Update the one-line comment that currently cites "`implementation_plan.md` task 9.4" — replace it with a plain description of why the split exists (no task-ID cross-reference to a file that no longer carries that numbering).

**Acceptance:**
- `pytest backend/tests/engine/test_export.py backend/tests/engine/test_score_run_metrics.py -v` → 7 tests total, all pass, zero skips (with `synthetic/` still present).
- Temporarily rename `backend/synthetic` to confirm `test_export.py`'s 5 tests still pass with no skip, and `test_score_run_metrics.py` skips cleanly (not errors) — then rename back.
- Full default suite, run in a dummy-`.env` worktree (guardrail 7): still 1,470 passed, 3 skipped (the same 3 as the baseline — `test_live_smoke` and the 2 `test_reviews_ui.py` tests — no new skips from this change).

**Rollback:** `git checkout -- backend/tests/engine/test_export.py` and delete the new file.

---

### 1.2 — Determine the provenance of the 12 non-register documents' current data (read-only, high priority — leading hypothesis has changed since this task was first drafted)

**Goal:** this started as "why are stages 5/5b/9 incomplete for 12 documents" and has become a bigger question: **whether the 12 non-register documents' current clause/citation/parameter/link data was produced by a fresh v2 ingest at all**, versus carried over from before the v1→v2 cutover and re-keyed. See `report.md`'s addendum (finding 2) for the full writeup — this task's job is to settle it, not re-derive it.

**Leading hypothesis, confirmed by multiple independent live checks, don't start from scratch — start from here:**
1. All 12 documents' current clause counts match `supplement_docs/CompanyData_Pipeline/company_data_storage.md`'s pre-cutover table **exactly**, including the register-split sums (155=85+70, 84=36+48, 173=87+86, and all 9 standalone counts digit-for-digit).
2. Their `clause_links` contain real cross-document links (`references_clause`, `references_obligation`, `references_record_series`, `references_tariff`, `restates` — hundreds of rows), which task 1.0 proves the current `service.py` architecture **cannot produce** from a single-document ingest call.
3. Their `report.json` shows empty `stats`/`issues`/`checks` and a ~2.5 second runtime; no `llm_extractions` rows exist for their run IDs; no `normalized_statement`/`topic_terms` were set.
4. `ingest_jobs.state = 'succeeded'` for all 12 — this proves the job wrapper completed, **not** that the work it's supposed to wrap actually ran (an earlier pass of this investigation treated this as proof of a real pipeline run; it isn't).
5. No script or migration anywhere in the current tree or git history writes directly to `company.clauses` other than `app/company_ingest/store/neon.py` (checked via a case-sensitive, INSERT-only `git log --all -S "INSERT INTO company.clauses"` and a repo-wide grep) — so if this is a carryover, it most likely went through a real call into `service.py`/`neon.py` (possibly assisted by `reuse.py`'s "inherit from prior version" mechanism), not a separate ad-hoc script bypassing it entirely. This is the main open question — and the search so far has a gap: it was case-sensitive and INSERT-only. Before concluding anything, also run: `git log --all -i -S "update company.clauses"` (case-insensitive, catches UPDATE too), `git log --all --diff-filter=D --name-only -- backend/scripts` (any deleted script that might have done this and no longer exists), and a case-insensitive text grep of migration `f7b2c91d4a08` (the v2 document-versioning migration) for any DML beyond its DDL.
6. A 4th independent data point, found this session: genuinely-fresh v2 parameter rows (the 3 register documents', 1,766 of them) are **100% NULL** on `is_citation_fragment` (confirmed never set by the live `insert_clause_parameters`); the 12 non-register documents' 2,420 rows are **100% non-NULL**. This is consistent with the carryover hypothesis (old, already-backfilled data) and inconsistent with "these were frozen or filtered differently for some other reason."
7. **Already checked, read precisely — this confirms "same source text," not "copy vs. fresh re-parse" on its own.** An orphaned pre-cutover R2 snapshot survives at `derived/RPL-CS-PRO-004/v1/clauses.jsonl` (237 clauses, matching `DOC-000008`'s current count). Its `text_sha256` for `local_id` `1.2`/`1.3` matches `DOC-000008`'s current Neon rows byte-for-byte; `1.1`/`2.1` do **not** match (see item 8). A hash match proves the same source text — which a deterministic re-parse of an unchanged `.md` would also produce — so it doesn't by itself distinguish "copied" from "freshly re-parsed." **The carryover conclusion rests on items 2 and 6 (the cross-document links and the `is_citation_fragment` split), not on this hash check** — carry that distinction into the write-up; don't present the hash match as the clincher.
8. **New finding from the same check, not yet explained — fold this in as its own data point:** 274 clauses across 6 of the 12 prose documents (`DOC-000008`: 29, `DOC-000010`: 83, `DOC-000012`: 29, `DOC-000013`: 60, `DOC-000014`: 37, `DOC-000015`: 36 — confirmed live; zero in the other 6 prose docs, zero in any register) have an **empty** `text_raw` where the surviving v1 snapshot shows real content for the same `local_id`. Confirmed this isn't a hashing artifact — `count(*) FILTER (WHERE text_sha256 = <empty-hash> AND text_raw <> '')` is 0 for every document, meaning every empty-hash row genuinely has empty text, not a hash bug. Determine: is this intentional (e.g., some clause-type-specific stripping rule) or a real content-loss bug, and whether `app/engine/judge.py`/`candidates.py` (or anything quoting clause text to a user) reads `text_raw` for these specific clauses in a way that would show up as missing/degraded content.

**⚠️ Guardrail — do not re-ingest or re-upload any of these 12 documents in production before this task resolves.** Doing so would run them through the real, cross-document-incapable pipeline and silently replace their currently-present cross-document links with none — turning an open question into irreversible (without a backup) data loss.

**Must run before Phase 2.** The two tools most likely to help here (`backend/synthetic/rehearsal.py`, which replays ingestion against a throwaway Postgres, and `backend/synthetic/seed.py`, the only end-to-end bulk-upload path) are deleted in task 2.1. If this task is somehow deferred past Phase 2, restore them read-only from the anchor commit (`git show 147cf2d:backend/synthetic/rehearsal.py`) rather than reverting the deletion.

**Owned files:** none — this is a read-only investigation (except step 4, which is a *scratch* database, never production). Deliverable is a findings note (append to `report.md` or a new short doc), not a code change.

**Reference files:** `app/company_ingest/service.py` (the orchestrator), `app/company_ingest/reuse.py` (the "inherit from prior version" mechanism — the most promising lead for a non-bypass explanation), `app/company_ingest/llm/client.py` (cache lookup/store), `app/company_ingest/store/snapshot.py` (stage 9 write), `app/company_ingest/store/commit.py` (report-building).

**Steps:**
1. Re-run the live comparison queries from `tables_and_connections.md` §7/§8 and `report.md`'s addendum to reconfirm the pattern still holds (state may drift if anyone re-ingests in the meantime) — read-only `SELECT`s, safe for a sub-agent against the real DB.
2. Read `reuse.py` in full and determine precisely what it inherits from a prior version and under what condition — does its inheritance mechanism extend to `clause_links` (not just `normalized_statement`/`topic_terms`/LLM parameters, per its docstring)? If these 12 documents' *current* version is actually a **new** `document_versions` row created on top of an **existing** document that already had this data from before the v1→v2 cutover, `reuse.py` might legitimately explain inherited links/citations/parameters without any bypass — but it would still need to explain why `normalized_statement` itself wasn't inherited (the docstring says it should be) and why stage 9's snapshot write (unconditional, no skip path) didn't happen.
3. **Human-only sub-step, not executable by a sub-agent:** check application logs (Render's log viewer, or wherever `uvicorn`/`BackgroundTasks` output lands — not just the `report.json` summaries already reviewed) for the specific `ingest_run_id`s of 2–3 of these documents, around their `started_at`/`finished_at` timestamps, for any swallowed exception or an early return. A sub-agent has no access to this; flag it back to the user as a pending human step rather than skipping it silently.
4. Grep `service.py` and `jobs.py` for every `return` statement and every path that can mark a job `succeeded` without completing the full `ingest_document` call.
5. **If reproduction is attempted, it must be against a scratch Postgres only** (via `rehearsal.py`/`rehearsal_inner.py`, which already builds a throwaway DB for exactly this purpose), using **one small document from this set** (`DOC-000003`/`RPL-REG-CAL-2025`, 36 clauses — the smallest, cheapest to iterate on) with an explicit LLM-call cap where the harness supports it. **Never re-ingest any of the 12 documents against production** to test a hypothesis — see the guardrail above.
6. Write up findings: either a specific mechanism (file:line) that explains the pattern (ideally resolving whether it's a legitimate `reuse.py`-mediated carryover or something else), or a documented "still unexplained, here's what was ruled out" note, explicitly marking which parts came from the human-only log review (step 3) if that hasn't happened yet — and including the item 8 empty-`text_raw` finding (explained or still open) as part of the same write-up, since it's the same investigation.

**Acceptance:** a findings note exists, naming either a mechanism or a concrete list of ruled-out hypotheses, and explicitly stating whether step 3 (human log review) has or hasn't happened yet. No live data was written to, and none of the 12 documents were re-ingested.

**Rollback:** n/a (read-only).

---

### 1.3 — Copy out ops data and grounding machinery *(gated: DG-2)*

**Goal:** preserve the two one-way-door pieces of `backend/synthetic/` before deletion, if the user wants that insurance.

**Owned files:** new location (e.g. `archive/synthetic-corpus-generation/` outside `backend/`, or wherever the user directs) for copies of: `backend/synthetic/corpus/_global/ops/*` (43,400 CSV rows) and `backend/synthetic/corpus/grounding/_scope.py` + `_normalizer.py`.

**Steps:**
1. Confirm DG-2's answer.
2. `cp -r` the named paths to the agreed destination (outside the app repo's deployed tree, e.g. a sibling `archive/` folder that isn't part of `backend/`'s build).
3. Note in the copy's own README (one line) what it is and that it's the output of the now-deleted `backend/synthetic/` generation tooling, dated.

**Acceptance:** files exist at the new location; `git status` shows them as untracked/new there, not modified in place.

**Rollback:** delete the copies; nothing in the main tree was touched.

---

### 1.4 — Relocate or formally retire `seed.py` *(gated: DG-1)*

**Owned files:** `backend/synthetic/seed.py` → copy to agreed new location (per DG-1), or explicitly note its retirement with no replacement.

**Steps:**
1. Confirm DG-1's answer.
2. If relocating: copy `seed.py` (it already works purely over HTTP, no `app/` imports — confirmed by its own docstring) to the new location; update its own docstring's example invocation path; verify it still runs against a local backend (`--plan` flag, no network needed, per its own usage note) without modification beyond the path move.
3. If retiring: no file action needed here — task 2.1 deletes it along with the rest of `synthetic/`. Just make sure task 4's README fix (4.1) doesn't claim a bulk-load path exists if there isn't one anymore.

**Acceptance:** either the relocated copy runs `--plan` successfully from its new home, or the retirement decision is recorded in the README fix (task 4.1).

**Rollback:** delete the relocated copy; original is untouched until task 2.1.

---

### 1.5 — Add register-CSV and docx test fixtures

**Goal:** stop `test_register_spec.py`'s 2 `@pytest.mark.corpus` tests (the only coverage of real register-CSV parsing) from losing their only data source when `synthetic/` is deleted.

**Owned files:** new files under `backend/tests/fixtures/` (e.g. `backend/tests/fixtures/registers/`), `backend/tests/company_ingest/test_register_spec.py` (update paths only, not logic).

**Steps:**
1. Copy the 3 real register CSVs from `backend/synthetic/corpus/docs/{RPL-CMP-REG-001,RPL-REG-CAL-2025,RPL-LEG-RRS-001}/data/*.csv` into a new `backend/tests/fixtures/registers/` directory — same pattern as the existing `tests/fixtures/docx/` fixture.
2. Update `test_register_spec.py`'s `corpus_csv()` helper (or wherever it resolves the path) to check the new fixture location first, same pattern as how the docx fixture is resolved elsewhere, and drop the `@pytest.mark.corpus` marker from these 2 tests once they no longer depend on `synthetic/` being present.
3. **If DG-9 approves it:** also copy a small sample (2–3) of real `.docx` source files into `tests/fixtures/` for the 6 `@pytest.mark.corpus` tests in `test_extract_docx.py` that currently exercise prose/docx extraction beyond the single existing `RPL-CS-PRO-004_v5.1.docx` fixture. Same pattern, same marker removal.

**Acceptance:** `pytest backend/tests/company_ingest/test_register_spec.py -v` passes with `backend/synthetic/` temporarily renamed away. If DG-9 was approved, same check for the `test_extract_docx.py` corpus-marked tests.

**Rollback:** delete the new fixture files; revert the test file's path changes.

---

### 1.6 — Re-confirm baselines immediately before Phase 2

**Goal:** catch drift between this planning session and execution time.

**Steps:**
1. Re-run `pytest -m "not neon and not qdrant and not corpus" --collect-only -q` and diff the node-ID list against `.audit_baseline_backend_nodeids.txt` — the only expected differences are the additions from 1.1 (`test_score_run_metrics.py`) and any marker removals from 1.5.
2. Re-run `pnpm test && pnpm typecheck` in `frontend/` and confirm still 43/435 passing, clean typecheck (nothing in Phase 1 should have touched the frontend yet).
3. Confirm tasks 1.1–1.5 are all done (or explicitly skipped per their decision gate) before proceeding to 2.1.

**Acceptance:** diffs match expectations exactly; nothing unexplained changed.

---

## Phase 2 — Deletion

### 2.1 — Delete `backend/synthetic/`, `backend/tests/synthetic/`, `tools/offline_eval/`

**Depends on:** all of Phase 1 complete (1.1–1.6).

**Owned files:** `backend/synthetic/` (delete, minus anything relocated in 1.3/1.4), `backend/tests/synthetic/` (delete), `tools/offline_eval/` (delete per DG-8).

**Steps:**
1. `git rm -r backend/synthetic backend/tests/synthetic tools/offline_eval` (or delete + `git add` only those paths — never a blanket `git add -A`).
2. Re-run the full baseline diff from 1.6 — expect the backend node-ID diff to be **exactly**: minus every node ID under `tests/synthetic/`, plus/minus whatever 1.1 and 1.5 already changed, and **zero other additions or removals**, especially zero new skips.
3. Re-run `pytest backend/tests/engine/test_barrier.py -v` — expect 9/9 pass (these tests scan `app/`/`scripts/` for forbidden references; they don't assert `synthetic/` exists, confirmed by reading `test_scan_dirs_cover_app_and_exclude_synthetic` and `test_scanner_no_score_run_exemption` this session, so this isn't a new risk, just a re-confirmation).
4. Run `pnpm test && pnpm typecheck` in `frontend/` — expect unchanged (43/435, clean), since nothing under `backend/synthetic/` is imported by any frontend **test** (only the manual `fixtures:build` script, unaffected by the test run).

**Acceptance:** backend diff matches exactly as predicted above; `test_barrier.py` still 9/9; frontend unchanged.

**Rollback:** `git show 147cf2d:backend/synthetic/<path>` to recover any specific file; or `git checkout 147cf2d -- backend/synthetic backend/tests/synthetic tools/offline_eval` to restore the whole trees (only if this hasn't been committed and pushed yet — check with the user first per the standing git-safety rules).

---

## Phase 3 — Dead-code cleanup in the production tree (independent of Phase 1/2 — can run anytime, including in parallel with Phase 1)

### 3.1 — `register_segmenter.py` cleanup

**Owned files:** `backend/app/company_ingest/parse/register_segmenter.py`, `backend/tests/company_ingest/test_register_segmenter.py`.

**Confirmed this session, no need to re-derive:** the live upload path (`app/api/company/upload.py:221,235` and `app/company_ingest/register_spec.py:81`) also decodes with `utf-8-sig` — the same encoding `segment_register`'s wrapper used. Porting the tests to call `segment_register_text` directly with the same decode step preserves real, live behavior; it isn't porting coverage of dead encoding logic.

**Steps:**
1. Confirm (still true, re-check before acting) that `segment_register()` has zero production callers — only `segment_register_text()` is called by `service.py`.
2. In `test_register_segmenter.py`, change each of the 36 calls to `segment_register(version_id, doc_id, csv_path, document_title, ctx)` to instead read the file (`csv_path.read_text(encoding="utf-8-sig")`) and call `segment_register_text(version_id, doc_id, text, document_title, ctx, table_id=csv_path.stem, source_label=str(csv_path))` directly — this is the exact delegation `segment_register` itself does, so behavior is unchanged.
3. Delete `segment_register()` from `register_segmenter.py`.

**Acceptance:** `pytest backend/tests/company_ingest/test_register_segmenter.py -v` — confirm the exact current test count first (36 calls were counted this session, but re-verify before relying on it), all pass, same assertions as before, no behavior change.

**Rollback:** `git checkout -- <both files>`.

---

### 3.2 — `r2_keys.py` / `r2.py` dead-code and docstring cleanup (one task — don't split)

**Owned files:** `backend/app/company_ingest/store/r2_keys.py`, `backend/app/company_ingest/store/r2.py`, `backend/tests/company_ingest/test_r2.py`. (Note: `store/neon.py`'s stale docstring fix moved to task 3.4, which already owns that file for the `is_citation_fragment` INSERT change — don't touch `neon.py` from this task, to avoid two tasks editing the same file.)

**Steps:**
1. Confirm (re-check) zero production callers of `raw_dataset_key`, `raw_render_key`, `global_file_key`, `parquet_key`, `global_parquet_key` (in `r2_keys.py`) and `put_file` (in `r2.py`) — all confirmed this session.
2. Delete those 5 functions from `r2_keys.py` and `put_file` from `r2.py`.
3. Remove the corresponding tests from `test_r2.py`: `test_raw_dataset_key`, `test_raw_render_key`, `test_global_file_key`, `test_parquet_key`, `test_global_parquet_key`, `test_put_file`.
4. Fix `r2_keys.py`'s stale docstring ("defaults to rpl" — none of the remaining functions default `company_id`, it's always a required arg).

**Acceptance:** `pytest backend/tests/company_ingest/test_r2.py -v` passes with the 6 removed tests gone and nothing else broken; grep confirms no remaining reference to the 6 deleted functions anywhere in `app/`, `scripts/`, or `tests/`.

**Rollback:** `git checkout -- <all 3 files>`.

---

### 3.3 — Delete the two superseded scripts

**Owned files:** `backend/scripts/backfill_qdrant_clauses.py` (delete), `backend/scripts/extract_register_citations.py` (delete).

**Steps:**
1. Confirm (re-check) neither is referenced by `render.yaml`, any README, or any other script/test (confirmed clean this session).
2. Delete both files.

**Acceptance:** `grep -rln "backfill_qdrant_clauses\|extract_register_citations" .` (excluding `.git`) returns nothing.

**Rollback:** `git checkout -- <both files>`, or recover from history if already committed.

---

### 3.4 — Decide and implement: wire `is_citation_fragment` in (Option A), or delete it entirely (Option B) *(gated: DG-4 picks the option)*

**Confirmed this session — this column is not just unwired, it's currently inert everywhere it's read:**
- `ParameterEntry` (`enrich/parameter_entry.py`) has **no `is_citation_fragment` field at all**.
- `insert_clause_parameters` in `store/neon.py` does **not include `is_citation_fragment`** in its INSERT column list, VALUES, or `ON CONFLICT DO UPDATE SET` clause.
- **All 3 read-sites are provably dead, by boolean logic, not by assumption:** the flag can only be `True` when `kind='number' AND unit IS NULL` (per the script's own rule). `app/engine/candidates.py:98`'s SQL filter (`COALESCE(is_citation_fragment, false) = false AND (kind <> 'number' OR unit IS NOT NULL)`) and `app/engine/rules.py:105`'s `_eligible()` (`if is_citation_fragment: return False` followed by `return kind != 'number' or unit is not None`) both already exclude every row where `kind='number' AND unit IS NULL` via their *other* condition — so whether `is_citation_fragment` is `True`, `False`, or `NULL` never changes which rows pass either filter. `app/engine/judge.py:384` only selects the column into a result dict; nothing downstream filters on it.
- **Consequence: wiring this in has zero effect on current engine output, and deleting it also has zero effect.** Pick based on which fits better, not on urgency.

**Option A — wire it in:**

**Owned files:** `backend/app/company_ingest/enrich/parameter_entry.py`, `backend/app/company_ingest/store/commit.py` (the `finalize_parameters` function), `backend/app/company_ingest/store/neon.py` (the `insert_clause_parameters` function **and** its stale "managed by the CLI" docstring — moved here from task 3.2 since this task already owns this file), `backend/scripts/recompute_citation_fragments.py` (repoint, don't duplicate), `backend/tests/engine/test_citation_fragments.py` (update import), `backend/tests/company_ingest/test_parameters_regex.py` (add coverage). **Owns `service.py` not at all.**

**Resolved convention (read the script's `main()` closely — it settles this exactly):** `recompute_citation_fragments.py::main()` computes `is_citation_fragment()` over **every** `clause_parameters` row with no `WHERE kind=...` filter, and the function itself returns a plain `False` (not `None`) whenever `kind != "number" or unit is not None`. Its `UPDATE ... SET is_citation_fragment = %s` always writes a real boolean. **The column must be a boolean on every row, never `NULL`, to match this exactly.**

**Compute it in `finalize_parameters` (stage 8, `store/commit.py:60`), not inside `enrich_parameters` alone — this matters.** `ParameterEntry` objects are constructed in **3 places**: `enrich/parameters_regex.py:346` (regex extraction), `llm/run_clause_enrichment.py:89` (LLM-derived), and `reuse.py:192` (inherited from a prior version). Computing the flag only inside `enrich_parameters()` would leave the other two construction paths with whatever default the dataclass has, uncomputed — wrong for LLM-derived or reused parameters that happen to be citation fragments. `finalize_parameters` already runs "just before commit," already iterates `for unit in units: for entry in unit.parameters:` to set `value_source` the same way — it sees every parameter regardless of which path created it, so it's the correct single place to add this.

**Steps:**
1. Add `is_citation_fragment: bool = False` (not `Optional`) to the `ParameterEntry` dataclass in `enrich/parameter_entry.py`.
2. Relocate the two pure functions `is_whole_token()` and `is_citation_fragment()` from `scripts/recompute_citation_fragments.py` into a shared module (e.g. `enrich/parameters_regex.py`, since that's where the original regex logic already lives) — keep them pure, no DB access, matching their current form exactly.
3. In `finalize_parameters()` (`store/commit.py`), inside the existing per-entry loop, also call `is_citation_fragment(entry.kind, entry.unit, entry.value_text, [c.parsed.citation_raw for c in unit.citations])` and set `entry.is_citation_fragment` to the result, for every entry regardless of which of the 3 construction sites produced it.
4. Add `is_citation_fragment` to `insert_clause_parameters`'s column list, VALUES, and `ON CONFLICT DO UPDATE SET` clause (so a re-ingest updates it, matching how `value_source`/`verified` are already handled there).
5. Fix `store/neon.py`'s stale docstring ("managed by the CLI" — no CLI exists) while this task already has the file open.
6. Update `scripts/recompute_citation_fragments.py` to `import` the relocated functions from their new home instead of defining them locally — becomes a thin batch-runner for task 3.5's backfill. Do not delete yet.
7. Update `tests/engine/test_citation_fragments.py`'s import line.
8. Add a test confirming a bare-digit parameter that's a whole-token match inside a clause's citation gets `is_citation_fragment=True`, and every other kind/unit combination gets `False` (never `None`), regardless of which construction path produced the parameter (add a case exercising `reuse.py`'s path if the test harness supports it).

**Acceptance (Option A):**
- `pytest backend/tests/engine/test_citation_fragments.py backend/tests/company_ingest/test_parameters_regex.py -v` all pass.
- `tests/company_ingest/test_service.py` already calls the real `ingest_document()` against the `RPL-CS-PRO-004_v5.1.docx` test fixture through a controlled test harness — add an assertion there confirming `is_citation_fragment` comes back populated on every parameter from that run, regardless of construction path.
- Full default suite, run in a dummy-`.env` worktree: 1,470 (+ whatever 1.1/1.5/3.1-3.3 added) still passes, the same 3 pre-existing skips, no new failures or skips.
- Confirm (don't just assume) engine output is unaffected: re-run `candidates.py`'s query logic conceptually against a wired-in test ingest and confirm candidate selection is identical to before — this is expected to be a no-op given the dead-code proof above, but verify it rather than taking it on faith.

**Option B — delete it, as two separate deploys (expand/contract), not one:** dropping the column in the same deploy as removing the code that reads it is unsafe — `judge.py:384`'s `SELECT` names the column explicitly, and during a rolling deploy the old process keeps serving requests while the new schema migrates; if the column is already gone, the old instance's query errors until it's fully replaced.
- **Deploy 1 (code only, no migration):** remove the 3 now-pointless references in `candidates.py:98`, `rules.py:105`, `judge.py:384` (simplifying those filters to just their other condition, which this session proved is equivalent — don't reference the column at all anymore, including in `SELECT` lists); remove the `is_citation_fragment` field from `ParameterEntry` if task 3.4 had added it; delete `scripts/recompute_citation_fragments.py` and `tests/engine/test_citation_fragments.py`. **Depends on task 1.2 finishing first** — same reasoning as 3.5: the current 1,766/2,420 NULL split is part of 1.2's evidence, don't remove the code that makes that split meaningful to discuss until 1.2 is done (the column itself isn't touched in this deploy, just the dead reads, so this is a soft dependency — safe to relax once 1.2 explicitly says it's done with this data point).
- **Deploy 2 (separate migration, later, user-approved), only after deploy 1 is confirmed live and stable:** `ALTER TABLE company.clause_parameters DROP COLUMN is_citation_fragment`. Sequence this with guardrail 2 (one migration head at a time) and get explicit approval before running it — it's irreversible without a backup.

**Acceptance (Deploy 1):** the 3 engine files' filters produce byte-identical query/logic results before and after simplification (they're provably equivalent, confirm with a quick before/after diff of the SQL and the `_eligible()` logic); full default suite unaffected.

**Rollback:** `git checkout -- <all touched files>` for either option — Option A is purely additive/code change (no data touched until 3.5); Option B needs the migration rolled back too if it was applied.

---

### 3.5 — Backfill existing `is_citation_fragment` NULLs *(only if Option A was chosen in 3.4; gated: depends on 3.4 merged and verified, and on task 1.2 finishing first)*

**This is a production write against live Neon. Do not run without explicit confirmation that Option A (not B) was chosen, and not before task 1.2 finishes** — the 1,766-NULL (register) vs. 2,420-set (non-register) split this backfill would erase is part of 1.2's supporting evidence for the data-provenance question; flattening it first removes a data point 1.2 might still need.

**Steps:**
1. Confirm 3.4 chose Option A and is merged, tests pass, and task 1.2 has finished.
2. Run `scripts/recompute_citation_fragments.py` **without** `--apply` first (dry run) — it should report exactly how many of the (re-confirm the current count first, it may have shifted) 1,766 register-document rows would change, and 0 changes among the 2,420 already-set rows (if it reports any changes there too, something about 3.4's rule doesn't match the original script's — stop and reconcile before applying).
3. Tell the user before running `--apply`: per the dead-code proof in 3.4, this backfill is **not** expected to change engine output at all — note this plainly, don't repeat an earlier, now-corrected warning that findings/trust scores would shift.
4. Run `scripts/recompute_citation_fragments.py --apply` (importing the shared, already-tested function from 3.4) against production.
5. Verify: `SELECT count(*), count(is_citation_fragment) FROM company.clause_parameters` — the two counts should now be equal. Also re-run the dry run once more — it should report "rows to change: 0," confirming idempotence, not just a count match (a count match alone can't catch a value that's wrong-but-non-null).
6. Only after this is verified: delete `scripts/recompute_citation_fragments.py` (now fully redundant).

**Acceptance:** the verification query in step 5 matches expectations; no unrelated columns changed (the script only ever writes `is_citation_fragment`, confirmed by its own docstring).

**Rollback:** this is a production write with no automatic rollback — the script is documented as idempotent (`"Idempotent: only rows whose flag differs from the computed value are updated"`), so re-running it is safe, but reverting the *values* would require restoring from a DB backup/snapshot taken before this step. Take one if the user wants a safety net.

---

### 3.6 — Vertical taxonomy: backend repoint to `company.verticals`

**Owned files:** `backend/app/api/company/routes.py` (`VERTICAL_SLUGS` + `vertical_slug()`), `backend/app/api/company/upload.py` (its direct `VERTICAL_SLUGS` import/usage), `backend/tests/api_company/test_upload.py` and any other test file with a fake DB session that currently has no branch for a verticals query (see step 4), new backend test file (static contract test — no live DB).

**Confirmed this session:** `company_documents.vertical` already has a live FK constraint to `company.verticals(name)`; the 6 vertical values actually in use are an exact subset of the 14 rows in `company.verticals`. The data is already consistent — this is a read-path change, not a data-migration.

**Two things that would otherwise hit production or break tests — avoid both:**
- **Do not read `company.verticals` at import time or at app startup.** `VERTICAL_SLUGS` is currently a module-level dict, built once when `routes.py` is imported — if the replacement does a DB query at the same point, it runs during test collection, against whatever `.env` the process has (including the real one, in a non-worktree run), every single time any test imports this module. Resolve it through the existing request-scoped `get_db` dependency instead (same pattern the rest of this module already uses), so it only runs inside an actual request and respects test dependency overrides.
- **`tests/api_company/test_upload.py`'s `FakeSession.execute()` (and any similar fake session elsewhere in `tests/api_company/`) matches on SQL substrings and returns an empty result for anything it doesn't recognize.** A new, unmatched `SELECT name, slug FROM company.verticals`-shaped query would silently return `[]`, making every vertical look unmapped, and turning every upload test into a 422. Add a matching branch to every fake session this touches, returning the expected static rows, as part of this task — not as a surprise test failure to debug afterward.

**Confirmed this session — one more wrinkle:** `routes.py:55`'s `vertical_slug(name)` is a plain **sync** function with exactly one caller (`routes.py:128`, inside a read endpoint) — it currently just does a dict lookup. Making the backing data request-scoped means `vertical_slug()` itself can't fetch asynchronously; its single call site needs to fetch the verticals dict first (via the request's session) and pass it in, or `vertical_slug()` needs to become async and its one caller needs an `await`. Either is a small change given there's only one caller — just don't miss it.

**Also confirmed:** the migration does **not** build a literal SQL `INSERT` string — it inserts from a plain Python module-level constant, `NEW_VERTICALS` (a list of `(name, slug, description)` tuples), via `bind.execute(sa.text(...), [{"name": n, "slug": s, "description": d} for n, s, d in NEW_VERTICALS])`. The static contract test should import or statically parse `NEW_VERTICALS` directly (even simpler than `test_migrations.py`'s AST approach, since it's a plain Python literal, not SQL text) rather than looking for INSERT-row text that doesn't exist in this form.

**Steps:**
1. Replace the hardcoded `VERTICAL_SLUGS` dict in `routes.py` with a function that queries `company.verticals` (name, slug) through the request-scoped session — the table has no `order` column; don't need one for this task since the frontend stays static per DG-3's default. Update `vertical_slug()`'s one call site to supply the fetched dict (see the wrinkle above).
2. Update `upload.py`'s usage (`names = {k: k.title() for k in VERTICAL_SLUGS}`, `by_slug = {...}`) to call the same function (via its own request-scoped session), preserving its exact validation behavior (unmapped vertical → 422).
3. Update `tests/api_company/test_upload.py`'s `FakeSession` (and any sibling fake sessions in that test directory) to recognize the new query and return the 14 expected rows — do this as part of this task, confirmed necessary per the warning above.
4. Add a **static** contract test — no live DB connection — that imports (or statically parses, if importing the migration module is awkward) `migrations/versions/9c1e4b7a2f05_verticals_retaxonomy.py`'s `NEW_VERTICALS` constant and asserts its 14 `(name, slug)` pairs — **both fields, not just name**, since a slug mismatch alone would misroute `isVerticalSlug` and silently send a document to "unclassified" — exactly match `frontend/lib/verticals.ts`'s static `VERTICALS[].name`/`.slug` pairs. This is what catches future drift between the two without making the frontend dynamic, and without needing a database at all.

**Acceptance:** existing `tests/api_company/test_upload.py`, `test_org_endpoints.py` etc. still pass unchanged (behavior preserved) — specifically confirm no new 422s appear on previously-passing upload tests; new static contract test passes with no DB connection required.

**Rollback:** `git checkout -- <touched files>`.

---

### 3.7 — Vertical taxonomy: frontend dynamism *(deferred by default — DG-3)*

**Only execute if the user explicitly opts in.** If so, this needs its own follow-up plan — it is not a "quick repoint," it touches:
- A new `sort_order` column + migration on `company.verticals` (sequenced, see guardrail 2 — no other migration-writing task may run concurrently).
- A new `GET /company/verticals` endpoint.
- Making `app/app/documents/verticals/[vertical]/page.tsx`'s `isVerticalSlug` check async (it currently gates a synchronous `notFound()` call).
- Rewriting `frontend/lib/verticals.ts` to fetch instead of hardcode, and every one of its ~10 consumers (`VerticalView.tsx`, `upload/logic.ts`, `lib/api/http/company.ts`, `tests/support/mock-api/company.ts`, etc.).
- A full rewrite of `frontend/tests/unit/verticals.test.ts`, which currently hard-asserts the exact static array shape, order, and length.

Do not start this without a dedicated task breakdown of its own — it's out of scope for "default" execution of this plan.

---

## Phase 4 — Documentation fixes (independent, can run anytime, in parallel with everything)

### 4.1 — Fix `README.md`

**Owned files:** `README.md`.
**Steps:** remove or replace the dead `python -m app.company_ingest.cli.ingest` load-data line with the real flow (API upload, or the relocated `seed.py` per task 1.4's outcome — if retired with no replacement, say so plainly rather than describing a path that doesn't exist); fix or remove the broken "Design docs" links (`architecture.md`, `TDD.md`, `implementation_plan.md`, `plan_mode.md` — the first three are gone from git history per the prior audit, the fourth now refers to *this* file).
**Acceptance:** every command/link in the README's "Load data" and "Design docs" sections actually resolves to something real in the current repo.

### 4.2 — Fix `supplement_docs/application_layer/application_layer.md`

**Owned files:** that file.
**Steps:** correct the doc/people/attribute counts (12/27/22 → 15/27/24), correct "Qdrant `company_clauses` absent (404)" (it's live, 2,298 points), correct "ingest is manual via CLI" (it's automatic, per-upload, API-driven).
**Acceptance:** counts match `tables_and_connections.md`.

### 4.3 — Pointer notes on stale docs (light touch, optional)

**Owned files:** `supplement_docs/CompanyData_Pipeline/company_data_storage.md`, `synthetic_corpus_generation.md`.
**Steps:** add a single-line header note to each pointing readers at `tables_and_connections.md` / `live_ingestion_architecture.md` / `report.md` (repo root) for current state — **do not edit their existing content**, per the audit's original decision to leave them as a historical snapshot.
**Acceptance:** one line added to each file's top, nothing else changed.

### 4.4 — Fix `frontend/scripts/build-fixtures.ts` and `frontend/README.md`'s stale path

**Owned files:** `frontend/scripts/build-fixtures.ts` (header comment only, unless task 1.3/1.4 relocated the corpus, in which case also repoint the functional `CORPUS` constant on line 20), `frontend/README.md` line 35.
**Steps:** both currently say `../backend/app/company/corpus` (the old v1 path) in prose while the code actually resolves `../backend/synthetic/corpus` (confirmed this session) — fix the comment to match reality regardless of other decisions. If 1.3 relocated the ops data elsewhere and that's the new intended source, repoint the constant; if `synthetic/` is just being deleted outright with fixtures frozen as test-owned, note in the comment that the script is no longer runnable rather than silently leaving a dangling path.
**Acceptance:** comment and code agree; running the script (if still runnable) or its documented failure mode (if not) both match what's written.

---

## Phase 5 — Deferred, manual, or time-gated (not for immediate execution)

### 5.1 — Confirm the deployed `R2_ENDPOINT` value *(human only, not a sub-agent task)*

No code in this repo can answer this — `render.yaml` marks it `sync: false`, meaning the value lives only in the Render dashboard. A human with deploy access should check whether the deployed value carries the same `/strata` suffix found in the local `.env`. No action follows automatically either way — see DG-6.

### 5.2 — Delete orphaned R2 objects *(gated: DG-7; depends on 1.2 — do not run first)*

**These orphaned objects are task 1.2's primary evidence — the `derived/RPL-*/v1/clauses.jsonl` snapshots are literally what this audit diffed against current Neon rows to confirm finding 2 (byte-identical `text_sha256` match).** Deleting them before 1.2 finishes removes the ability to verify or extend that finding, or to check it for other documents beyond the one (`DOC-000008`) already checked. Run 1.2 to completion first.

**Steps:** immediately before deleting, re-run the unreferenced-check queries from `tables_and_connections.md` §7 (`ingest_runs`, `document_versions.ingest_run_id`, `llm_extractions.run_id` — all should still return zero matches for the orphaned run ID(s)) since time has passed since the audit. Then delete the confirmed-orphaned objects only (the stale `v1`-keyed derived snapshots and the specific orphaned `ingest_run_id`'s LLM-cache audit JSONs) — never bulk-delete by pattern.
**Acceptance:** re-verification queries return the same zero-reference result immediately before deletion; nothing under a *current* `document_versions.source_r2_key`/`ingest_run_id` is touched.

### 5.3 — Drop the two migration backup tables *(date-gated: not before 2026-11-30, DG-5)*

Not scheduled in this round. When the date arrives, this is a new, single, sequential migration (see guardrail 2) that drops `company._vertical_backfill_20261031` and `company._approval_policy_vertical_backfill_20261031`. Note: once run, `9c1e4b7a2f05`'s own `downgrade()` can no longer function (it reads from these tables).

### 5.4 — Collapse repeated date-literal constants

**Owned files:** `app/company_ingest/service.py`, `app/company_ingest/enrich/resolve_citations.py`, `app/company_ingest/enrich/resolve_citations_db.py` — **same file as 3.4 touches (`service.py`), sequence these, don't run in parallel.**
**Steps:** the `2024-12-31`/`2025-01-02` fallback-default literals repeated across these 3 files could become one shared constant. Low priority, purely cosmetic, zero behavior change if done correctly (it's literally the same value today in every location).
**Acceptance:** grep confirms one definition, 3 usages; existing tests unchanged.

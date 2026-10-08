# Strata v1 — Action Plan to a Happy Demo

Status: ready to hand to Claude Code · Written 2026-10-07 · Motto: **signal over noise**.
Goal of this plan: fix only what blocks a strong, believable demo. Everything else is listed under "Deferred" and must not be started.

How to use: give this file to Claude Code and spawn **one agent per task** (`T1`…`T10`). Each task states its files, steps and acceptance. Respect the wave order (§4) and the owner decisions (§2).

---

## 1. The story the demo must tell (the bar)

1. Company RPL (electric distribution, 12 documents, 5 verticals) is **compliant with government snapshot S1** (`law_as_of = 2024-12-31`). A baseline run (S1 vs S1) flags **0** things. ✅ already true.
2. Snapshot S2 arrives. We use **only the S1→S2 diffs** (never rescan S2 against company data).
3. Strata separates noise from real changes, finds the company clauses that depend on a real change, judges each clause, proves it with verified quotes, and routes it to owner/reviewer/approver.
4. The audience sees **documents and clauses marked "Action required / Review / Cleared"** with proof, in the real wave and in what-if scenarios.
5. The engine is **generic** (no logic keyed to RPL, doc ids, or citations).

## 1.1 Where we are (facts, with source)

Tags: **[M]** = measured by us on 2026-10-07 against the live backend/DB. **[R]** = reported by the "Strata Demo Readiness" artifact (third-party, unverified; each [R] claim used below is re-verified by the task that depends on it).

| Area | State |
|---|---|
| Backend `/engine/ui/*`, `/company/*` endpoints | Done, zod-validated against real data [M] |
| Frontend (all analysis + KB + company pages, search, what-if presets) | Done; live on `:3000` reading `:8000`; typecheck/lint/298 tests/prod build green [M] |
| Latest real run `05b50712-79df-4c4e-bdb3-c84f31e189ec` | 1,114 changes → 1,015 noise → 96 in footprint (87 are noise, **9 real**) → 7 findings (4 action_required, 3 review) → **2 docs flagged / 10 cleared**; 718 clauses cleared with reasons [M] |
| Document-level correctness | **All 12 documents' flagged/cleared status matches the expected status** (stored per-doc scoring) [M] |
| Clause-level scoring | precision 0, recall 0, `matched 0` (4 non-info findings vs 6 expected); FP-rate-on-negatives PASS; routing PASS; baseline PASS [M] |
| Judge input | `app/engine/prompts/judge.md` says "citing a section is NOT enough"; `clause_role` is **not passed** to the judge although 640 clauses are `regulatory_restatement` [M] — consistent with [R] root cause B1 |
| Presets (what-if) | 4 presets, all done. Union of flagged docs = 6 of 12. **Never flagged in any run: PRO-007, DO-PLN-002, MTR-PGM-001, DCC-PRO-003, ENV-PRO-005, SAF-PRO-009** → verticals Operations, Environmental, Workforce never light up [M] |
| LLM | Live LLM smoke test fails; [R] says API unavailable until **2026-11-01**. All engine results currently come from cached/offline-filled judgments (`engine.llm_calls`: 1,606 rows, 707 valid) [M]. **Assume no live LLM.** |
| DB connection | Intermittent `500: connection is closed` on the first request after idle (Neon pooled conn dropped; `app/db.py` has no `pool_pre_ping`) [M] |
| Review write path | Never executed against the live DB; only unit-tested with stubs [M] |
| Custom what-if | Paused by decision (needs LLM, writes to DB). Presets run free [M] |
| Working tree | Everything (backend + frontend + docs) is **uncommitted** [M] |

---

## 2. Decisions needed from the owner (defaults let agents proceed)

| # | Decision | Recommended default (agents use this unless told otherwise) |
|---|---|---|
| D1 | How to re-judge candidates while the API is down (until 2026-11-01)? (a) wait; (b) offline regeneration by Claude Code in batches (the way the existing cache rows were filled); (c) demo on the current frozen results | **(b)**, but only after T2 proves the 0/6 is accuracy and not an export bug |
| D2 | Scorecard presentation if clause-level metrics stay low | **Show honestly, never hide**, and show the true positive alongside it: "12/12 documents correctly flagged/cleared" (T3) |
| D3 | May an agent perform **one** real Accept on a what-if finding in the shared DB (a permanent row)? | **Yes, exactly one**, on a what-if preset finding (clearly simulated data). Everything else uses a rolled-back transaction (T5) |
| D4 | Delete the ~18 intermediate runs? | **No.** The run selector already collapses to 6 runs. Deleting is irreversible and unnecessary |
| D5 | May the working tree be committed (T10)? | **Yes**, as 4 commits grouped by area, on `main`. No worktrees, no force-push |
| D6 | Demo local or deployed? | **Local** (`:3000` + `:8000`). Deployment is Deferred unless you say otherwise |
| D7 | `stale_at_approval` appears on 3 of 4 action items for the Reporting Calendar (rule DIN published 2025-02-19, document approved 2025-03-14). It means "already out of date when approved" and sits a little oddly with "compliant at S1" | **Keep** (it is a designed engine feature); T7 makes the UI copy neutral and factual |
| D8 | Enable custom what-if? | **No** (stay paused). Needs LLM + writes |

---

## 3. Rules for EVERY agent (copy into each prompt)

- **File ownership is strict.** Edit only the files listed in your task. Read anything. If you need a change elsewhere, stop and report it.
- **No git commits/stash/checkout/worktrees** (except T10). Never use `isolation: worktree`.
- **Information barrier (architecture.md §5):** never open `backend/app/company/corpus/eval/**`, `grounding/**`, `qa/**`, `validation/**`, `*.basis.json`, `expected_findings.*`. Use aggregate metrics only. No hardcoded doc ids, citations, titles or RPL literals in `app/engine/`.
- **No live LLM.** Do not call the Anthropic API. Anything that needs the model must be built and tested with fakes, then handed to T1b.
- **Shared remote DB (Neon).** SELECT only unless the task explicitly says otherwise. No POSTs to `/engine/*` that create runs or scenarios.
- **Ports:** the backend on `:8000` and the dev server on `:3000` belong to the lead. Use your own: backend `:80NN`, Next dev `NEXT_DIST_DIR=.next-<task> pnpm exec next dev -p 31NN` (never `next build` while `:3000` is running; never without `NEXT_DIST_DIR`). Use a private scratchpad subfolder for scripts. Clean up `.next-*` and revert any `tsconfig.json` churn when finished.
- **Never remove or enable a disabled "coming soon" control** (`frontend/lib/future-features.ts`, spec §18). They are intentional.
- **Acceptance gates:** backend `cd backend && PYTHONPATH=. .venv/bin/python -m pytest tests/engine tests/api_company -q` (the pre-existing `test_live_smoke` failure is expected); frontend `cd frontend && pnpm exec next typegen && pnpm typecheck && pnpm lint && pnpm test`.
- **Report** in ≤12 lines: `task | DONE/BLOCKED | key numbers | files`.

---

## 4. Waves and dependencies

```
Wave 1 (parallel, no LLM):  T2  T4  T5  T7  T8  T9   + T1a (code only)
Wave 2 (needs D1):          T1b  ->  T3  ->  T6 (new presets)
Wave 3 (gate, last):        T10 (end-to-end demo check + commit)
```
T2 must finish before T1b (a format bug would waste a regeneration). T3 and T6 consume the new run produced by T1b. T9 (docs) runs last within Wave 1/2 so it records final numbers.

---

## 5. Tasks

### P0 — blockers for a believable demo

#### T1a — Judge sees the clause's role (code only, no LLM)
**Problem.** The judge decides "affected?" without knowing what kind of clause it is. 640 clauses are `regulatory_restatement` (they restate a rule inside a register row, tariff sub-rule or procedure) and 165+ are `definition`. The prompt tells the judge that merely citing a section is "NOT enough", so restating clauses that should be compared against the new rule text are dismissed. Result: 4 findings, 0 of 6 expected matched, even though all 12 documents' status is correct [M]. [R] names this as the root cause; T1a/T1b must confirm it with aggregate metrics only.
**Files you own:** `backend/app/engine/judge.py`, `backend/app/engine/prompts/judge.md`, `backend/app/engine/schemas.py` (only if a field must be added), `backend/tests/engine/test_judge*.py`.
**Do:**
1. Read `app/engine/judge.py`, `candidates.py`, `prompts/judge.md`, `engine_spec.md` §4.
2. Add `clause_role` (`regulatory_restatement | internal_procedure | definition | template_field`) and `unit_kind` to the judge input, loaded with the clause (query already filters `clause_role <> 'boilerplate'`).
3. Update `judge.md` generically: for a `regulatory_restatement` or `definition` clause, the clause is *meant to reproduce or summarize the cited rule*, so compare its wording and values to the S2 text; a restatement that no longer matches S2 **is** affected. For `internal_procedure` keep the current strictness. Keep "never speculate", quote verification and `stale_at_approval` rules unchanged. No doc-specific or citation-specific wording.
4. Because the prompt hash changes, the LLM cache will miss; do **not** run anything live. Provide `scripts/` helper only if needed to export the pending judge prompts (see T1b), otherwise nothing.
5. Unit tests with a fake LLM: restatement clause + mismatched S2 value → `affected`; internal procedure with the same wording → unchanged behaviour; prompt contains the role line; barrier test (`tests/engine/test_barrier.py`) still passes.
**Done when:** tests pass; diff shows only generic wording; `git grep -nE "RPL-|IAC |CFR " backend/app/engine` finds nothing new.
**Does not do:** re-judge anything (that is T1b).

#### T2 — Explain `matched = 0` (is it accuracy or an export/format bug?)
**Problem.** Per-document status agrees for all 12 documents, yet clause-level `matched` is 0 even for `RPL-REG-CAL-2025` (3 system findings vs 3 expected) [M]. If part of this is a format mismatch (clause id form, citation granularity, `finding_type`, or route fields in the exported JSON), regenerating judgments (T1b) will not fix it and would burn the offline effort.
**Files you own:** `backend/app/engine/export.py`, `backend/scripts/score_run.py`, `backend/tests/engine/test_export*.py`, plus a short note `development_docs/scoring_diagnosis.md` (new).
**Do:**
1. Re-export the latest kb run (`05b50712-…`) with `scripts/score_run.py` (no LLM; non-verbose; it writes `engine.score_reports`). Read only the **aggregate** lines.
2. Read the scorer's *input contract* (module docstring / argument handling / the keys it reads from our export in `scoring.py`) — **not** `expected_findings.*`. If matching semantics cannot be understood without opening forbidden files, **stop and report BLOCKED** (the owner decides).
3. Compare our export's field forms against that contract (clause_id format, citation level — section vs rule — `finding_type`, `severity`, `route_to`). The Demo Readiness report notes citation exports changed for rule-level findings: check `RPL-REG-CAL-2025:EVT-2025-0044` (`170 IAC 1-6`, rule-level) specifically.
4. Produce one of two outcomes in `scoring_diagnosis.md`: **(A) format bug** — fix `export.py`, re-score, report new aggregate metrics and confirm baseline S1 still passes; or **(B) not a format bug** — state that the gap is accuracy (T1b) with the evidence (aggregate numbers only).
**Done when:** the note exists, and either the metric moved because of a real format fix or the note rules the format out. Never tune to the answer key; never use clause-level key output.

#### T1b — Re-judge and re-run the real wave (needs D1)
**Depends on:** T1a, T2 (outcome B or A fixed), owner decision D1.
**Problem.** After T1a the judge prompts change, so the cache misses for the affected candidates (the report estimates the ~411 LLM-judged candidates, ~9 batches).
**Do (default D1 = offline regeneration):**
1. Find how the existing offline-filled cache rows were produced (`engine.llm_calls` has 1,606 rows / 707 valid; [R] says 283 are provenance-tagged). Reuse that mechanism; do not invent a new cache format. If it is not discoverable in the repo, report BLOCKED with what you found.
2. Export only the **missing** judge prompts (cache misses for the new prompt hash) into batches of ≤50. Answer them as the judge (strict JSON per `JudgeResult`), write them back to the cache with the same provenance tag, then run `scripts/run_engine.py --kind kb --radar` (cache-only; must make 0 live calls).
3. Score with `scripts/score_run.py --run <new_id>` and report aggregate metrics (precision, recall, FP-rate, routing) and baseline. **At most 3 iterations** of generic prompt/logic improvement (`implementation_plan.md` 4.1.5). Never read the key.
4. The new run becomes the default demo run automatically (the UI picks the newest `done` kb run). Old runs stay untouched.
**Files you own:** the offline-fill helper script (new, in `backend/scripts/`), cache rows in `engine.llm_calls` (writes allowed **only** for this task), the new run.
**Done when:** a new kb run is `done`, baseline still 0 findings, the funnel numbers are reported, and the metrics are recorded. Target (prd.md §7): precision ≥ 0.80, recall ≥ 0.83, FP = 0, routing ≥ 0.80. If the target is missed after 3 iterations, report the numbers and stop; do not game.

#### T3 — Scorecard that tells the truth and shows what is right
**Depends on:** T1b result (can start after T2 with current data).
**Problem.** Overview tile and Trust page show `0%/0%/0%/0%` and FAIL for the real run [M]. That is factually correct but hides the strongest true signal: all 12 documents' flagged/cleared status is correct.
**Files you own:** `backend/app/api/engine/routes_ui_runs.py` (score endpoint only), `frontend/lib/api/schemas/engine.ts` (`scoreReportSchema` additive field), `frontend/components/overview/TrustPage.tsx`, `frontend/components/overview/OverviewPage.tsx`, related unit tests.
**Do:**
1. Backend: add `doc_agreement: {agree: int, total: int}` to the `/engine/ui/runs/{rid}/score` payload, computed from `score_reports.metrics.per_doc` (`system == expected`). Additive; null if unavailable.
2. Frontend: on Trust and the Overview tile show, in this order: the four metrics vs targets (unchanged, honest) and a distinct line "**12 of 12 documents correctly flagged or cleared**" with a one-sentence explanation of the difference between document-level and clause-level agreement. No hiding, no recoloring a FAIL as a pass.
3. Keep what-if/baseline behaviour ("Not scored").
**Done when:** live Trust page shows the new line; schema tests updated; numbers equal the API.

#### T4 — No random 500s mid-demo
**Problem.** First request after idle returns 500 (`InterfaceError: connection is closed`, Neon drops pooled connections) [M]. In a live demo this shows up as an error screen.
**Files you own:** `backend/app/db.py`, `backend/app/main.py` (only to add `GZipMiddleware(minimum_size=1000)` — payloads are text-heavy), `frontend/lib/api/http/shared.ts` and its tests.
**Do:**
1. `create_async_engine(..., pool_pre_ping=True, pool_recycle=300)`; keep `ssl=require` and the URL handling.
2. Frontend `getJson`: retry **once** (after ~300 ms) on network failure or 5xx for GET requests only; never retry POST. Surface a clear `ErrorState` after the retry fails.
3. Test: start a server, hit an endpoint, wait ≥ 6 minutes idle (or simulate by closing pooled connections via a test hook), hit again → 200.
**Done when:** idle-then-request returns 200; unit tests cover retry on 500/network and no retry on POST/4xx.

#### T7 — Numbers an expert will not question
**Problem.** (a) Overview funnel says "In your footprint 96" but 87 of those are cosmetic noise; only **9** are real changes [M]. (b) "Substantive" is **99** in the funnel (substantive + repealed + new + renumbered) but the Changes "Substantive only" filter shows **63** [M]. (c) The `stale_at_approval` wording (D7).
**Files you own:** `backend/app/api/engine/routes_ui_common.py` (`map_stats` additive field `in_footprint_real`, plus test), `frontend/components/overview/**`, `frontend/components/changes/**` (labels/filter naming only), `frontend/lib/labels.ts`, `frontend/lib/sentences.ts`, related tests.
**Do:**
1. One definition everywhere: a **real change** = class in `{substantive, repealed, renumbered, new_section}`; **noise** = the four noise classes. Rename the Changes chip "Substantive only" → "Real changes only" and make its count equal the Overview number (99 / 9 in footprint). Keep the class sub-chips.
2. Funnel stage 3 becomes "**Real changes in your documents' rules**" (= `in_footprint_real`, 9) with "+ N noise changes also touched your documents — cleared" shown as a secondary gray line (87). Update all Overview links so each destination page shows exactly the number on the bar (verify by clicking).
3. `stale_at_approval` copy: factual and neutral — "This document was approved on {date}, after the rule change was published on {date}." Do not imply the company was non-compliant at S1.
**Done when:** every funnel number equals the number shown on its destination; no two screens use "substantive" with different meanings.

#### T5 — Reviews actually work on live data (and show up)
**Problem.** Accept/Reject has never run against the live DB [M]; the Documents board has no reviewed count (known gap in `runbook.md`).
**Files you own:** `backend/tests/engine/test_reviews_ui.py` (new), `backend/app/api/engine/routes_ui_results.py` (add `reviewed` count to rollups only), `frontend/components/engine/EvidenceCardBody.tsx` (review state wording), `frontend/components/documents/board/**` (reviewed count), related tests.
**Do:**
1. Integration test with FastAPI `TestClient`, a dependency-overridden DB session inside a **transaction that is rolled back**: POST accept → GET finding shows the review; POST reject without note → 422; reject with note → stored; unknown finding/person → 404. No permanent write.
2. Add `reviewed: int` to `/engine/ui/runs/{rid}/rollups` (count of findings with ≥1 review); show "N of M reviewed" on document cards and the reader header; after a review the finding row shows "Accepted"/"Rejected" and who/when (reviewer name from the route).
3. **If D3 = yes:** perform exactly one real Accept on a what-if preset finding via the UI/API, confirm it appears after reload, report the `review_id`, and do not repeat.
**Done when:** tests pass; the UI reflects a saved review without a page reload.

### P1 — strengthens the story, bounded

#### T6 — Presets that light up the other verticals (needs T1b / D1)
**Problem.** Across the real wave and 4 presets only 6 of 12 documents are ever flagged; the Operations, Environmental and Workforce verticals never light up [M]. The story "a rule change marks the right documents across the company" is weaker than it should be.
**Files you own:** `backend/scripts/make_whatif_presets.py` (+ its test), new preset scenario rows and their runs.
**Do:**
1. Make preset selection **generic and coverage-aware** (no hardcoding): greedily pick candidate sections so that the chosen presets together flag documents in as many distinct verticals as possible (use `company_documents.vertical`/the register mapping, never doc ids). Keep 3 value presets + 1 repeal as the minimum; allow up to 6 total.
2. Add `--dry-run` that prints, per candidate section, the clause/document/vertical coverage it would produce, **without any LLM call** (this part ships in Wave 1).
3. Running the new presets needs characterize/judge answers → do it only after T1b (same offline mechanism, D1) and with the run cap (`ENGINE_MAX_LLM_CALLS_WHATIF=300`).
**Done when:** each of the 5 live verticals has at least one flagged document in at least one preset (or the report states which verticals have no eligible cited section and why); preset titles are readable; run time is "instant" in the UI (pre-run).

#### T8 — Activity feed shows dates sanely
**Problem.** Regulations → Activity lists rulemakings and investigations with no `date_published`; the existing `/actions` list orders `date_published DESC` with NULLs **first**, so undated rows sit on top of page 1 and the real recent items are buried [M, R]. IURC GAO titles are literally "PDF" and IDEM titles end in "[PDF]" [M].
**Files you own:** `backend/app/api/regulatory/actions.py` (ordering only: `NULLS LAST`; this is a deliberate one-line exception to the PRD "don't touch existing routes" guardrail, approved by this plan), `frontend/lib/api/http/kb.ts` (title fallback), `frontend/components/kb/ActionList.tsx`, tests.
**Do:** `ORDER BY date_published DESC NULLS LAST, id DESC`; for GAOs titled "PDF" display `GAO <source_id>`; strip a trailing "[PDF]"; undated rows show "Date not published". No scraping or data repair in this task.
**Done when:** page 1 of Activity (IURC) shows dated items first; no row renders a bare "PDF".

#### T9 — Docs match reality (so the next agent is not misled)
**Files you own:** `development_docs/runbook.md`, `api_ui.md`, `prd.md`, `data_model.md`, `engine_spec.md`, `implementation_plan.md`, `frontend/README.md`, `frontend/.env.example`. No code.
**Do:**
1. `runbook.md`: replace `NEXT_PUBLIC_API_BASE` with the real variables (`NEXT_PUBLIC_STRATA_DATA=mock|http`, `NEXT_PUBLIC_STRATA_API_URL`, `NEXT_PUBLIC_STRATA_ALLOW_CUSTOM_WHATIF`); add "local demo" start commands (backend `uvicorn` + `pnpm dev`, `pnpm exec next typegen` first on a clean checkout); add the Neon idle note (T4).
2. `api_ui.md`: add a banner "UI contract superseded by `ui_wiring_contract.md`; the `/engine/ui/*` and `/company/*` endpoints are the live UI API"; note quote spans are plain-text offsets (not diff coordinates) in the UI endpoints.
3. `prd.md` §3 / `data_model.md` / `engine_spec.md`: update numbers that are now stale (use the run's real numbers: 4 cited sections → recompute, CFR resolution claim), the rule-level citation export form (from T2), and add an "Offline-filled judgments" note describing the cache provenance (from T1b).
4. `implementation_plan.md`: mark waves done/not done truthfully; add the final status of W4 scoring.
**Done when:** every number in these docs either matches the live data or is removed; run T9 **after** T1b/T2 so it records the final numbers.

#### T10 — Final gate: end-to-end demo check, then commit
**Depends on:** everything above.
**Files you own:** `frontend/tests/e2e/demo.spec.ts` (new), `frontend/playwright.config.ts`, `backend/scripts/demo_prep.py` (only if its checks are stale), then git.
**Do:**
1. Fix `playwright.config.ts` so it uses the locally cached Chromium (`CHROMIUM_PATH` or the newest `~/Library/Caches/ms-playwright/chromium-*`), not `/opt/pw-browsers`.
2. Write a **read-only** live-mode Playwright test that walks the demo script (spec §12) and asserts values **read from the API at test time** (not hardcoded): Overview funnel numbers; open a flagged document → reader → a finding's evidence card shows three verified quotes; Changes → a cleared noise change shows its reason and "Cleared (N)"; Matrix cells; Radar tabs; Trust figures; a what-if preset opens with the SIMULATED banner and **issues no POST**; every disabled "coming soon" cue exists and is disabled; zero console errors.
3. Run `scripts/demo_prep.py --api-base http://localhost:8000 --skip-llm` and fix only stale checks.
4. **If D5 = yes:** commit in this order, each commit passing the acceptance gates: (1) backend UI endpoints + engine changes + tests, (2) frontend app, (3) docs, (4) plan/diagnosis notes. Do not push. Use the attribution line required by the session.
**Done when:** the e2e test passes twice in a row; commits exist; `git status` clean.

---

## 6. Deferred (explicitly NOT in this plan — do not start)

Why: none of these changes what the audience sees in the happy path, or they cost LLM budget we do not have.
- **Government-data adapter polish** from the Compliance/Data audits: FR embeddings (217/990 vectorized — semantic search is not used by the UI), DIN extraction and cross-linking, FR/CFR/IC citation extraction from PDFs, LSA numbers in `docket_ids`, investigation filtering/backfills, GAO topic categories, weekly tree refetch, CloudFront hostname alerting, adapter version bump, `cfr_references` field misuse, heading-only change detection. *Many were patched since the audits (`scripts/patch_*`, `verify_compliance_patches.py`): re-verify before ever reopening.*
- Ohio cleanup comment nits (`puco` in two comments), R2/Qdrant Ohio data cleanup.
- Marketing landing page (`/` redirects to `/app`), reader clause popover (spec §9.4 P2), "view original file", compare-scenarios, any item in `lib/future-features.ts`.
- Enabling custom what-if (needs LLM; D8), deleting intermediate runs (D4), deployment to Render/Vercel (D6; `runbook.md` already documents it).
- Radar: screened-out items rarely carry an attribute basis (1 of 54). Needs LLM regeneration; the UI already falls back to the reason line.
- Any new feature, new page, or new endpoint not listed above.

---

## 7. Definition of "happy demo ready"

- Baseline: 0 findings; all 12 documents cleared. ✅
- Real wave: the flagged documents/clauses are the right ones (T1b/T2), 718+ cleared clauses carry reasons, quotes are verified.
- What-if presets open instantly, cover all 5 live verticals (T6), and are clearly labeled SIMULATED, with no POST.
- Every number on Overview equals the number on the page it links to (T7).
- Trust shows the honest clause-level numbers **and** "12 of 12 documents correct" (T3).
- Reviews save and show up (T5). No random 500 after idle (T4).
- `e2e` gate green twice, work committed (T10), docs match reality (T9).

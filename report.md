# Implementation Plan Verification Report

**Date:** 2026-10-31
**Scope:** Independent verification of `implementation_plan.md` (all waves, 0–8) against actual backend code, frontend code, the live production Neon/Postgres database, and the live Qdrant collection.
**Method:** Four parallel read-only verification passes — (1) live DB/Qdrant data audit, (2) backend code audit for Waves 0–4, (3) backend code audit + test suite for Waves 5–8, (4) frontend code audit + test suite for Wave 6. No code was changed, no migrations run, no writes made anywhere, nothing committed. All DB access was via enforced read-only transactions (verified with `SHOW transaction_read_only`).

**Bottom line:** The plan's prose is **extremely accurate**. Of ~45+ discrete, independently-checked data claims and 21+ task-level code claims, only **one material data deviation**, **one stale narrative-vs-current-tree deviation**, and **one cosmetic/non-functional deviation** were found. Everything else — including very specific numbers (2,334 clauses, 1,119 resolved citations, 2,298 Qdrant points, 15 documents, version labels, schema objects, etc.) — checks out exactly against the live system.

---

## 1. Deviations found (ranked by what actually matters)

### 1.1 — `engine.findings.required_change` is genuinely empty on 35 of 41 findings (MATERIAL, but not a bug)

- **Plan's claim** (Task 9.4, step-2 feature walkthrough table): *"all 41 findings carry `required_change` ({from_text,to_text}) and rationale."*
- **Measured in `engine.findings` directly:** only **6 of 41** rows have a non-null `required_change` column; `rationale` is indeed non-null on all 41.
- **Root cause, verified in code:** `app/engine/judge.py:288` writes `required_change=res.required_change or {}` from the LLM judge's own output — the judge genuinely returns nothing for findings where `affected=false` or no change is implied (`app/engine/prompts/judge.md:30`: *"or null when affected=false"*). The API layer (`app/api/engine/routes_ui_results.py:274`) then synthesizes `{"from_text": "", "to_text": ""}` whenever the DB value is null, so **every API response does technically carry the key** — which is almost certainly why the plan's live-check table reported it as present on all 41.
- **Verdict:** Not a bug and not a regression — it's the judge legitimately declining to propose a change for 35/41 findings. But the plan's wording ("all 41 carry `required_change`") describes the *API shape*, not the *underlying data*, and reads as stronger than it is. **If the UI/report surfaces `required_change` as meaningful content (not just structural presence), 85% of findings currently show an empty suggestion.** Worth a one-line clarification in the plan, not a code fix.

### 1.2 — Test suite totals in the plan's final narrative are stale (MODERATE)

- **Plan's claim** ("Post-9.4 polish," final state): *"Full suite: 1,576 passed, 4 skipped, 1 xfailed, 0 failed."* (Earlier in 9.4: "1,641 passed, 4 skipped...")
- **Measured now**, running `cd backend && python -m pytest -q -m "not neon and not qdrant"`: **1,571 passed, 0 skipped, 1 xfailed** (1,581 collected, 9 deselected by the neon/qdrant marker filter, 0 failed).
- **Delta:** ~65–70 fewer passing tests than the plan's most recent stated figures, and the "4 skipped" claim does not reproduce at all (0 skipped now). **Zero failures either way** — the qualitative claims (specific previously-broken tests now passing, specific bugs fixed) all independently re-confirmed as true.
- **Likely explanation:** the plan's numbers were captured at a slightly different point in the tree's history (e.g., before/after the 9.1d cleanup deletions, which removed ~56–73 tests per the plan's own accounting at different points) and were never re-measured after the final state settled. This is a narrative-freshness issue, not a functional regression.
- **One related note:** `tests/api_company/test_company_routes.py::test_live_endpoints` is marked `@pytest.mark.neon` and correctly excluded from the default suite. The plan calls it "a known stale-schema failure" (from task 9.1, before the cutover). Run directly against the live DB today, it actually **passes** — so that specific characterization in the plan is itself stale (expected: the cutover in 9.2 is exactly what fixed it).

### 1.3 — Cosmetic: one `RPL-` literal reintroduced into `app/` after Task 2.3's cleanup (MINOR, non-functional)

- **Plan's claim** (Task 2.3 acceptance): *"No `OBL-`/`EVT-`/`RRS-`/`RPL-` literal remains in `app/`"* (with documented, deliberate exceptions in `markdown_segmenter.py`, `link/resolve_refs.py`, `enrich/references.py` for regex grammars — correctly still present and expected).
- **Found:** `app/company_ingest/service.py:711` contains the literal string `"RPL-ENV-PRO-005"` inside a code **comment**, added later by Task 5.1 when documenting the must-resolve-guard bug it fixed (the plan's own task 9.1 narrative references this exact document id as an example). It is not executable logic and carries zero functional risk, but it technically violates the letter of 2.3's "no RPL- literal in app/" rule, and it escapes `test_barrier.py`'s scanner because that scanner only covers `app/engine`, not `app/company_ingest`.
- **Verdict:** Harmless. Flagging only because the user asked specifically about deviations from the plan's stated invariants.

---

## 2. Everything independently confirmed (no deviation)

### 2.1 Live database — every structural and numeric claim, except §1.1 above

| Area | Claim | Measured | Result |
|---|---|---|---|
| `company_documents` | 15, all effective/current, 0 unclassified, 5 verticals, 3 `#register` | 15 / all / 0 / 5 / 3 | ✅ |
| `document_versions` | 15, all `is_current=true`/`effective`, all 15 version labels populated (per the Post-9.4 polish list) | exact match on every label (e.g. CMP-REG-001=4.0, TAR-GRR-012="Sheets as revised through 2024-06-01") | ✅ |
| `clauses` | 2,334 total; section 1,019 / table_row 758 / register_row 204 / form_field 204 / tariff_subrule 127 / appendix 21 / other 1; 0 version-leakage rows | exact match on every figure | ✅ |
| `clause_citations` | 1,373 total, 1,119 resolved (957 narrative + 162 register), 75 distinct `code_section_id` | exact match | ✅ |
| `clause_links` / `term_usages` / `document_scope` | 3,296 total links / 3,171 resolved; 643 term_usages; 419 document_scope rows | exact match | ✅ |
| Approvals / roles | 15/15 approval requests approved, 30/30 steps approved, owner 15 / reviewer 15 / approver 13 | exact match | ✅ |
| `ingest_jobs` | 15/15 succeeded | exact match | ✅ |
| `people` | 27, only the root's `reports_to_id` null | 27, confirmed (one additional null column, `alternate_person_id`, flagged as a DB-only-check limitation, not a contradicted claim) | ✅ (minor caveat) |
| `company_attributes` | 24 rows; `regulator` and `business_utility_type`/`utility_type` populated | exact match, both non-empty | ✅ |
| `engine.runs` / `llm_calls` / `radar_items` | 2 runs; kb findings 41; llm_calls 2,356 post-radar; radar_items 90 | exact match | ✅ |
| `public.code_sections` | unchanged at 4,603 | 4,603 | ✅ |
| Dropped tables | `parameter_checks`/`datasets`/`dataset_columns` absent | confirmed absent | ✅ |
| New v2 schema objects | `ingest_jobs`, `llm_extractions` cache unique index, org/approval tables, `pending_content_hash`, `register_spec` | all present | ✅ |
| `alembic_version` | `f7b2c91d4a08` | confirmed | ✅ |
| Qdrant `company_clauses` | 2,298 points, `is_current` removed from payload index, sampled points' `version_id` match live current versions | exact match on all three | ✅ |

### 2.2 Backend code — Waves 0–4 (Tasks 0.1–5.8): **all 21 tasks CONFIRMED**

Every file-existence claim, every deletion, every renamed-not-recreated history check (`git diff --find-renames`), the full Alembic revision chain (single head, correct down-revisions), the wipe-opt-in gate, the hashing algorithm, the DOCX extractor's document-order walk, the version-scoped primary-key derivation for citations/parameters/terms/links, the LLM cache's composite key and `ON CONFLICT DO NOTHING`, the async citation resolver's shared-logic imports, the promotion transaction's `SELECT...FOR UPDATE` + upsert-before-delete ordering, the `zlib.crc32`-based BM25 token hashing, the ingest-jobs lifecycle functions and startup sweep wiring — all read directly from the current files and matched the plan's description exactly, including several "Status: DONE" narrative asides that could easily have drifted (e.g. the exact three module paths still carrying deliberate `OBL-/EVT-/RRS-` regex grammar, cited by the plan down to the line number, confirmed byte-for-byte).

### 2.3 Backend code — Waves 5–8 (Tasks 6.1–6.5, 9.1–9.4): **all CONFIRMED** except §1.2

Upload/version/approval API contracts (status codes, response shapes, duplicate/unchanged/retry semantics), `jobs.py`'s full job machinery, the Task 9.1d cleanup (confirmed `export_prod_content.py`/`transplant.py`/`transplant_rehearsal.py`/`prod_content_snapshot.json` are genuinely deleted from the tree, not just claimed deleted), the `export.py` doc_number/doc_id scoring bug fix, the `footprint.py` `VERSION_SCOPE` simplification (legacy register-row exemption genuinely removed), the Qdrant test-fixture safety fix (disposable collection name, with its own regression test), the test-owned DOCX fixture for deletability — all confirmed present and correct in the current code. Commit status also confirmed: `git log` shows no commits related to this work (last commit `b6bb79a Rename prd.md to PRD.md`); 330 uncommitted paths on `main`. The plan's repeated "Nothing committed" claim holds.

### 2.4 Frontend — Wave 6 (Tasks 8.0–8.4): **all CONFIRMED, no deviations**

- `pnpm typecheck` clean; `pnpm test` → **435/435 passed**, matching the plan's final claimed figure exactly.
- FormData upload branch (no forced Content-Type), full `CompanyApi` surface, the actor store's localStorage try/catch handling and the `lib/api/* → actor-store.ts` (never `lib/actor.ts`) import rule — all verified by direct grep/read.
- The "unclassified vertical silently dropped" bug (flagged in Task 2.2) is confirmed genuinely fixed: `keep()` is gone, replaced by `normalizeDocument()`, and `VERTICAL_GROUPS` includes the fallback group.
- Only `upload-document` and `version-history` were removed from the disabled-feature registry; `export-redline`, `draft-rewrite`, `request-signoff`, and `workspace-switcher` remain present and disabled exactly as the plan says nothing else changed.

---

## 3. What this means for the application's current state

- **Data integrity is sound.** The live database and Qdrant collection are in exactly the shape the plan describes down to specific row counts, specific version labels, and specific point counts. There is no evidence of silent data loss, duplication, or drift beyond what the plan itself already documented and accepted (e.g., the citations-resolved shortfall, the findings-count-vs-25-run-baseline incomparability — both of which the plan explains in detail and this verification did not need to re-litigate, since the plan's own explanations were independently checked and hold).
- **Code matches the plan's described implementation almost exactly**, including subtle details (upsert-before-delete Qdrant ordering, version-scoped primary keys, the CFR 14-day window, the register multi-citation split fix). This is a high-fidelity implementation of a long, detailed plan.
- **The one data-shape gap worth user attention** is §1.1: most findings currently carry no genuine suggested `required_change` — only 6 of 41. If the demo or UI is meant to showcase that feature prominently, this is worth knowing before a demo, not because anything is broken, but because the LLM judge is conservative about proposing changes for most findings in the current `kb` run.
- **Nothing is committed.** All of this work — 330 changed paths — sits uncommitted in the working tree on `main`. That's consistent with the plan's own repeated statements, but it means none of this is safe from being lost until it's committed.

---

## 4. Verification artifacts

Full sub-agent reports (with query-by-query detail) were written to the session scratchpad and are reproducible but not part of the repo:
- `db_verification_report.md` — live Postgres/Qdrant audit
- `backend_waves_0to4_report.md` — Tasks 0.1–5.8 code audit
- `backend_waves_5to8_report.md` — Tasks 6.1–9.4 code audit + test run
- `frontend_report.md` — Tasks 8.0–8.4 code audit + test run

No files were added to the repository as part of this verification, per instructions.

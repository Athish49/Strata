# Strata v1 — Implementation Plan

## Rules for every task
- Specs: `prd.md`, `architecture.md`, `data_model.md`, `engine_spec.md`, `api_ui.md`. Build exactly what they say. No extra features, tables or routes.
- Guardrails in `architecture.md` §5 always apply (information barrier, no hardcoded doc/citation literals in `app/engine/`, read-only company data, cost caps).
- Task numbers here are unrelated to the retired ingestion plan. "T2/T4/T5/T6" in older migrations and scripts are pre-engine fixes (commit `12e6e7c`) with no doc.
- All paths are relative to `backend/` unless stated. Corpus = `app/company/corpus/`.
- Each task is done only when its **Done-when** holds and `pytest tests/engine` passes.
- If a spec is unclear or the data contradicts it: stop, report in ≤5 lines, and do not guess.
- **Reporting:** after each wave, ≤15 lines. Format: `task | DONE/BLOCKED | key numbers | files`. No narrative, no code dumps.
- `∥` = may run in parallel with the listed tasks. `→` = depends on.

---

## W0 — Data fixes (all ∥, start immediately)
**0.1.1 Normalizer patterns.** Locate `normalize_for_diff`. Sample: the cosmetic pairs cited by company clauses, 20 random content-hash-changed pairs with equal `diff_hash`, and 10 substantive pairs. Add generic patterns for (a) appended readoption entries and (b) DIN spacing variants (`IR- 170…` → `IR-170…`). Unit tests: ≥10 readoption-only pairs normalize equal; ≥5 one-word substantive pairs differ (include a "shall not"→"may not" pair: it must still differ, because judging style is the LLM's job).
*Done-when:* tests pass; no previously-substantive pair with a real wording change becomes equal.

**0.1.2 Re-backfill `diff_hash`** (→0.1.1) with the existing backfill script.
*Done-when:* report substantive counts per source/title (before → after), and the list of substantive sections cited by company clauses: `citation | #clauses | docs`.

**0.2.1 Citation-fragment flag.** Recompute `clause_parameters.is_citation_fragment` per `data_model.md` §2 (token rule).
*Done-when:* about 278 TRUE; report counts by `kind`.

**0.3.1 Verify 327/326 IAC resolution.** For RPL-ENV-PRO-005 and every doc citing titles 326/327: counts by `resolution_status`. If a citation names a section that exists in the KB but did not resolve, fix the resolver generically and re-run it.
*Done-when:* report before/after per title.

**0.4.1 Verify routing data** (report only): `approved_date` is present for all current versions; `approver_id` is NULL only for the two-signature documents.

**0.5.1 Route inventory** (report only): existing prefixes are `/regulations /actions /diff /timeline /impact /search /jobs /health`; `/engine` is free. Confirm nothing else is mounted.

**0.7.1 Version-id mismatch (DONE).** `scripts/fix_current_version_ids.py --apply` re-pointed `current_version_id` for RPL-CMP-REG-001, RPL-LEG-RRS-001, RPL-TAR-GRR-012 to their prose clause sets. Engine eligibility uses `clauses.doc_id` (engine_spec §3.1).

**0.6.1 Merge Alembic heads.** The repo and DB have two heads (`77a04f843fe2`, `d1e2f3a4b5c6`). Add an empty merge migration in `migrations/versions/`, then run `alembic heads` and `alembic upgrade head`.
*Done-when:* `alembic heads` shows one head and the DB is stamped with it.

---

## W1 — Foundation
**1.1.1 Engine schema migration** (→0.6.1). Alembic migration (revises the merge head) creating all `engine.*` tables from `data_model.md` §3. Run upgrade/downgrade.
*Done-when:* tables exist; downgrade is clean.

**1.1.2 `config.py`, `schemas.py`** (∥1.1.1): settings from `architecture.md` §6 (as `Settings` fields or an extras-ignoring class). Pydantic models: `ChangeInput`, `ValueChange`, `Characterization`, `JudgeResult`, `RadarResult`, plus API DTOs.

**1.1.3 `llm.py`** (→1.1.1): first add an optional `model` argument to `company_ingest/llm/client.call_structured` (default `settings.LLM_MODEL`; existing tests must still pass). Then async `call_cached(stage, model, system, user, schema, run_id)` over it. Cache hit = a valid row with the same (stage, model, prompt_sha256). Logs every call. Semaphore concurrency; enforces the run's call cap; 1 retry on schema failure.
*Done-when:* a unit test with a mocked client proves cache hits skip the client.

**1.1.4 `quotes.py`** (∥): `verify_quote(quote, text) -> bool` (whitespace- and case-normalized substring, min 8 chars), `locate_quote(quote, text) -> (start, end) | None` mapped back to original offsets. Tests.

**1.1.5 `params_text.py`** (∥): `extract_parameters_from_text(text) -> list[{kind, unit, value_num, value_text, day_type, span}]` wrapping `enrich_parameters` with a synthetic ClauseUnit. Drop citation fragments using `find_citation_spans`. Tests on strings like "within ten (10) business days", "$25.00", "at least 48 hours".

**1.1.6 `diffing.py`** (∥): tokenizer, `diff_segments(a, b)`, `changed_tokens(a, b)`, `only_punct(changed)`. Tests.

**1.1.7 `tests/engine/test_barrier.py`** (∥): greps `app/engine/`, `app/api/engine/` and `scripts/` for the forbidden paths (`architecture.md` §5.1), allowing only the `scoring.py` subprocess call in `score_run.py` (do not scan `app/company/` or `company_ingest/collect/allowlist.py`, which legitimately contain those strings); greps `app/engine/**/*.py` for `RPL-`, ` IAC `, ` CFR ` literals.
*Done-when:* passes on the current repo.

---

## W2 — Stage 1: Delta (→W0, W1)
**2.1.1 `textnorm.py`:** wrap `normalize_for_diff`; implement `strip_metadata` (`engine_spec.md` §1.1). Derive patterns by sampling 30 changed pairs. Tests.
**2.1.2 `footprint.py`** (∥2.1.1): `rule_key`, `cited_section_ids`, `cited_rule_keys`, `cited_clause_count` (§1.5). Tests with DB fixtures.
**2.1.3 `dates.py`** (∥): DIN extraction plus FR lookup (§1.4). Tests.
**2.1.4 `inputs.py`** (∥): `build_kb_inputs`, `build_baseline_inputs` (§0).
*Done-when:* kb input count = S2 rows (IAC 1,068 + CFR 46).

**2.1.5 `delta.py`** (→2.1.1–2.1.4, 1.1.6): classification table §1.2, diff, dates, footprint, Stage 1 dispositions, and noise candidates (§1.6). Persists `change_records` and `candidates`.

**2.1.6 `run.py` skeleton + `scripts/run_engine.py`** (→2.1.5): create the run, execute Stage 1, write partial stats, set status.
*Done-when:* a kb run completes. Report: class counts per source; in-footprint changes as `citation | class | #cited clauses`.
**⏸ CHECKPOINT: send this report to the human before W3.**

---

## W3 — Stages 2–3 (→W2)
**3.1.1 `characterize.py` + `prompts/characterize.md`:** code param hints, LLM call, verification, dispositions (§2).
*Done-when:* runs on all in-footprint substantive changes; report `citation | obligation_changed | direction | #value_changes`.

**3.2.1 `candidates.py`** (∥3.1.1): eligibility (§3.1) and the four paths (§3.2), dedupe, `path_detail`. Unit-test `value_echo` with a fixture `ValueChange`.
*Done-when:* report candidate counts by path for the kb run.

**3.3.1 `rules.py`** (→3.2.1): R1–R4 (§4.1). Tests for each rule.

---

## W4 — Stages 4–5, scoring (sequential)
**4.1.1 `judge.py` + `prompts/judge.md`** (→3.1.1, 3.3.1): LLM judge on non-rule candidates and post-rules P1–P6 (§4.2–4.3).
**4.1.2 `ledger.py`** (→4.1.1): propagation, routing, dispositions, completeness check, doc rollups, stats (§5).
**4.1.3 `export.py` + `scripts/score_run.py`** (→4.1.2): §6. Never `--verbose`; never open `expected_findings.*`.

**4.1.4 End-to-end baseline** (→4.1.3): `run_engine --kind baseline`, then `score_run --snapshot S1`.
*Done-when:* 0 non-informational findings; all 12 docs `cleared`.

**4.1.5 End-to-end kb run** (→4.1.4): `run_engine --kind kb`, then `score_run`.
- If a metric misses its target (`prd.md` §7), improve only generic logic (normalizer, metadata stripping, prompts, thresholds), at most 3 iterations.
- Report metrics per iteration, the funnel, and per-doc status.
- Never use clause-level output from the key.

**⏸ CHECKPOINT: send metrics + funnel to the human.**

---

## W5 — API & UI (→4.1.4; UI work may start ∥ against the `api_ui.md` contract)
**5.1.1 `app/api/engine/routes.py`:** all `/engine/*` routes except the what-if, radar and review routes (built in W6–W8). Register in `app/main.py`; add CORSMiddleware. Background runs via `BackgroundTasks`.
*Done-when:* httpx tests for each route against the kb run.

**5.2.1 Frontend scaffold** (∥5.1.1): in repo-root `frontend/` (empty now), Next.js App Router, TypeScript, Tailwind; `lib/api.ts` typed client; layout with nav and run selector; `?run=` handling.
**5.2.2 Overview page** (→5.2.1): funnel, tiles, scorecard tile.
**5.2.3 Documents + Document pages** (∥5.2.2).
**5.2.4 Finding evidence card** (∥5.2.2): diff rendering with collapsed equal runs, quote highlights.
**5.2.5 Ledger page** (∥5.2.2).
*Done-when (5.2.x):* every page renders the real kb run with no console errors; links between finding ↔ change ↔ document work.

---

## W6 — What-if (Must; →W5)
**6.1.1 Engine + API:** `build_whatif_inputs`, `whatif.py`, routes `/engine/whatif/*` (`api_ui.md` §1).
*Done-when:* a manual text_edit scenario run completes; findings are visible in the UI via `?run=`.

**6.1.2 `scripts/make_whatif_presets.py`** (→6.1.1): 3 value presets + 1 repeal preset (§8); run them all.
*Done-when:* each value preset yields ≥1 `parameter_change` finding; report `title | findings by verdict | docs flagged | duration`.

**6.1.3 `/whatif` page + SIMULATED banner** (∥6.1.2).

---

## W7 — Radar (Should; ∥W6 after W5)
**7.1.1 `radar.py` + `prompts/radar.md` + `--radar` flag on kb runs + `GET /engine/runs/{id}/radar`** (§7).
*Done-when:* report counts yes/no/unclear; spot-check 10 "yes" items for attribute basis and quotes.
**7.1.2 `/radar` page** (→7.1.1).

## W8 — Review actions (Should; ∥W7)
**8.1.1** Routes `POST /engine/findings/{id}/reviews` and `GET /engine/people`. **8.1.2** Review buttons and reviewed count on the evidence card and document page.

---

## W9 — Deploy & demo prep (→W6; include W7/W8 if done)
**9.1.1** Deploy backend to Render (add `LLM_API_KEY` and `ENGINE_*` to `render.yaml`; run `alembic upgrade head` before uvicorn in the start command).
**9.1.2** Deploy frontend to Vercel (`NEXT_PUBLIC_API_BASE`). **9.1.1 ∥ 9.1.2**.
**9.1.3** Demo prep script: run baseline, kb (+radar), all presets, score. Warm caches. Verify every page in production.
**9.1.4** Final report (≤20 lines): URLs, metrics, funnel numbers, preset results, known gaps.

## Parallelism summary
| Can run together | Must be sequential |
|---|---|
| All of W0 · 1.1.2/1.1.4–1.1.7 · 2.1.1–2.1.4 · 3.1.1 ∥ 3.2.1 · 5.1.1 ∥ 5.2.1 · 5.2.2–5.2.5 · 6.1.2 ∥ 6.1.3 · W7 ∥ W8 · 9.1.1 ∥ 9.1.2 | 1.1.1→1.1.3 · 2.1.5→2.1.6 · 3.3.1 → 4.1.1→4.1.2→4.1.3→4.1.4→4.1.5 · 6.1.1→6.1.2 |

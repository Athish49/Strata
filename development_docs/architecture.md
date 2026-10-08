# Strata v1 — Architecture

## 1. Shape
A deterministic pipeline with bounded LLM calls. No agents, no tool-using loops.
Code decides: change classes, footprint, candidates, value conflicts, dates, routing, rollups.
The LLM is used only for: characterizing a change, judging a (change, clause) pair, and radar applicability. Every LLM call has a Pydantic schema, temperature 0, verified quotes, and is cached.

```
ChangeInput builders (kb | baseline | whatif)
        │
        ▼
[1] DELTA (code) ── classify: repealed · renumbered · new_section · cosmetic · metadata_only
        │                     · punctuation_only · cross_ref_only · substantive
        │           + word diff, publication date, footprint flag
        ├── not in footprint & substantive ───────────────► [R] RADAR (LLM, should-have)
        ▼
[2] CHARACTERIZE (LLM, in-footprint substantive only) ── obligation_changed? direction, value_changes
        ▼
[3] CANDIDATES (code) ── direct_section · direct_rule · register_hop · value_echo
        ▼
[4] JUDGE ── rules first (noise, repeal, renumber, value override) → LLM for the rest
        │     → quote verification → confidence gate → stale_at_approval → relaxed label
        ▼
[5] LEDGER (code) ── dispositions · completeness check · doc rollups · routing · funnel stats · export
        ▼
engine.* tables ──► FastAPI /engine/* ──► Next.js UI
                └─► scripts/score_run.py ──► app/company/corpus/eval/scoring.py (subprocess, aggregate metrics only)
```

## 2. Stores
- **Neon Postgres** (the only store the engine writes to). New schema `engine.*`. Reads `public.*` (regulations) and `company.*` (company data). W0 makes small additive changes to `public`/`company` (see `data_model.md` §3).
- Qdrant and R2: **not used** by the engine in v1.

## 3. Module layout (all paths relative to `backend/`; extend the existing FastAPI app)
Paths below such as `corpus/...` mean `app/company/corpus/...` (same as `settings.CORPUS_ROOT`).
```
app/engine/
  config.py          # models, thresholds, caps (env-overridable)
  schemas.py         # Pydantic: ChangeInput, Characterization, JudgeResult, RadarResult, API DTOs
  inputs.py          # build_kb_inputs(), build_baseline_inputs(), build_whatif_inputs(scenario)
  textnorm.py        # wraps the existing normalize_for_diff + new strip_metadata()
  diffing.py         # word-level diff → segments, hunks, changed-token classification
  dates.py           # DIN extraction, FR date lookup
  footprint.py       # cited section ids, rule keys, rule_key(citation)
  delta.py           # Stage 1
  params_text.py     # adapter: extract_parameters_from_text(text) over enrich/parameters_regex.py
  characterize.py    # Stage 2
  candidates.py      # Stage 3
  rules.py           # deterministic decisions R1–R4
  judge.py           # Stage 4 (LLM + post-rules)
  quotes.py          # verify_quote(), locate_quote()
  ledger.py          # Stage 5
  export.py          # scoring JSON
  radar.py           # Should-have
  whatif.py          # scenario → run; preset builder helpers
  llm.py             # cached wrapper over llm/client.py call_structured()
  run.py             # orchestrator: run_engine(kind, scenario_id=None) → run_id
  prompts/characterize.md, judge.md, radar.md
app/api/engine/routes.py   # /engine/* (see api_ui.md); register with one include_router line in app/main.py, and add CORSMiddleware there (none exists today)
scripts/run_engine.py      # CLI: --kind kb|baseline|whatif --scenario <id>
scripts/score_run.py       # export + run scoring.py + store metrics
scripts/make_whatif_presets.py
migrations/versions/<new>_engine_schema.py   # Alembic script_location = migrations
tests/engine/...
```
The Next.js app (App Router, TypeScript, Tailwind) lives in the repo-root `frontend/` directory (currently empty), not under `backend/`.
```
```

## 4. Reuse — do not rebuild
| Need | Existing | Note |
|---|---|---|
| Normalization | `app/regulatory/ingestion/normalize.py` → `normalize_for_diff(text, source_system)` + `code_sections.diff_hash` | Extend in W0 |
| Citation parsing | `app/company_ingest/enrich/citations_grammar.py` → `parse_citation`, `find_citation_spans` | Directly callable. Its `rule_key` is title-level for CFR (`18 CFR`), so `footprint.rule_key` computes CFR keys itself (see `engine_spec.md` §1.5) |
| Parameter extraction | `app/company_ingest/enrich/parameters_regex.py` → `enrich_parameters(units: list[ClauseUnit], ctx: RunContext)` | Wrap via `params_text.py` (needs a synthetic `ClauseUnit` and `RunContext`) |
| LLM | `app/company_ingest/llm/client.py` → `call_structured(stage, unit_id, system, user, schema, ctx: RunContext)` (async, Anthropic; model is hardcoded to `settings.LLM_MODEL`; cache is in-memory on `ctx`) | W1 extends it with an optional `model: str | None = None` argument (backward compatible). `engine/llm.py` adds the Postgres cache (`engine.llm_calls`), the call cap and concurrency on top |
| Citation resolution | `company.clause_citations.code_section_id` / `resolution_status` | Already populated (points to S1 rows) |
| Version chain | `code_sections.prior_version_id` (S2 → S1) | The pairing key |
| Line diff API | `app/api/regulatory/diff.py` | Leave unchanged; the engine has its own word diff |
| Router registration | `app/main.py` (explicit `include_router` per module) | Add the engine router; `/engine` does not collide with `/regulations /actions /diff /timeline /impact /search /jobs` |

## 5. Guardrails (non-negotiable)
1. **Information barrier.** No code in `app/` or `scripts/` may read `corpus/eval/**`, `corpus/grounding/**`, `corpus/qa/**`, `corpus/validation/**`, `*.basis.json`, `corpus/docs/*/scripts/**`, or `_manifest.json`. (The corpus itself lives at `app/company/corpus/`; the barrier concerns code that *reads* those paths. `company_ingest/collect/allowlist.py` names them only in its DENY list and is exempt.)
   - The single exception: `scripts/score_run.py` may *execute* `app/company/corpus/eval/scoring.py` as a subprocess. It must never pass `--verbose` and never open `expected_findings.*`.
   - `tests/engine/test_barrier.py` enforces this by grepping `app/engine/`, `app/api/engine/` and `scripts/` (not `app/company/`, which is data, and not `company_ingest/collect/allowlist.py`).
2. **No tuning to the answer key.** Use only aggregate metrics. Never hardcode clause IDs, citations, doc IDs, or titles in `app/engine/` (`test_barrier.py` greps for `RPL-`, `IAC `, `CFR ` literals outside `prompts/` examples, which must stay generic).
3. **Evidence.** Every non-informational finding needs verified quotes (S1, S2 and clause substrings). If verification fails, the finding becomes `informational` with `needs_review=true`.
4. **Precision first.** Noise classes never reach the LLM. Judge confidence < `MIN_CONFIDENCE` (0.6) → informational/review. There is no finding without a candidate path.
5. **Completeness.** The ledger check fails the run if any change record lacks a disposition, or any candidate is neither judged nor given a `skip_reason`.
6. **Read-only on company data.** The engine writes only to `engine.*`.
7. **Cost caps.** `MAX_LLM_CALLS_KB=900` (including radar) and `MAX_LLM_CALLS_WHATIF=300`. If a run would exceed its cap, it fails loudly. LLM concurrency = 8 (radar 16).
8. **Determinism.** Temperature 0. Cache key = (stage, model, sha256(system+user+schema)). Reruns reuse the cache.

## 6. Config (env, defaults)
`app/config.py` `Settings` forbids unknown env keys, so add these as fields on `Settings` (or a separate `EngineSettings` that ignores extras); otherwise `.env` entries crash startup.
| Key | Default |
|---|---|
| ENGINE_CHARACTERIZE_MODEL | `claude-sonnet-5-5` |
| ENGINE_JUDGE_MODEL | `claude-sonnet-5-5` |
| ENGINE_RADAR_MODEL | `claude-haiku-4-5-20251001` |
| ENGINE_MIN_CONFIDENCE | 0.6 |
| ENGINE_RENUMBER_JACCARD | 0.80 |
| ENGINE_JUDGE_MAX_SECTION_CHARS | 8000 (beyond this, send ±1500-char windows around hunks) |
| ENGINE_COMPANY_ID | `rpl` |

## 7. Deployment
- Backend: FastAPI on Render (`backend/render.yaml`; add `LLM_API_KEY`, `ENGINE_*` env vars and a migration step to the start command). Runs execute as background tasks; CLI scripts are available too.
- Frontend: Next.js on Vercel, configured with `NEXT_PUBLIC_API_BASE`. Configure CORS in FastAPI.
- No auth. A single company comes from config.

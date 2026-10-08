# Demo runbook

## Environment variables

Backend (Render, `backend/render.yaml`; secrets are `sync: false` and must be set in the dashboard):
- Secrets: `DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `LLM_API_KEY`.
- Preset in render.yaml: `LLM_PROVIDER=anthropic`, `LLM_MODEL`, all `ENGINE_*` (models, thresholds, call caps, concurrency; defaults match architecture.md section 6).
- `ENGINE_CORS_ORIGINS`: comma-separated allowed origins, set to the Vercel URL (e.g. `https://strata.vercel.app`). Unset or `*` allows all.
- `DATABASE_URL` must use the `postgresql+asyncpg://` form.
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` (Procfile identical). The live DB is already at head `e5a1c7d9b304`, so this is a no-op there.

Frontend (Vercel, root directory `frontend`, framework Next.js, no vercel.json needed; `npm run build` verified):
- `NEXT_PUBLIC_API_BASE` = Render service URL with no trailing slash and no `/engine` suffix (e.g. `https://strata-backend.onrender.com`). Baked in at build time, so redeploy after changing it.

## Deploy order
1. Render: create the service from `backend/render.yaml` (Blueprint), fill in secrets, deploy. Check `<render-url>/health` and `<render-url>/engine/runs`.
2. Vercel: import the repo, root `frontend`, set `NEXT_PUBLIC_API_BASE`, deploy.
3. Back in Render set `ENGINE_CORS_ORIGINS` to the Vercel URL and redeploy.
4. Free Render instances sleep: open `/health` a minute before the demo.

## Demo prep (from backend/, local or against production DB)
```
export PYTHONPATH=.
.venv/bin/python scripts/demo_prep.py --api-base http://localhost:8000          # full (uses the LLM)
.venv/bin/python scripts/demo_prep.py --api-base <render-url> --skip-llm        # verify only, no LLM
```
`demo_prep.py` reuses finished runs (pass `--force` to start new ones), so it is safe to re-run. It exits non-zero if any route check fails.

Manual equivalents, in order:
```
scripts/run_engine.py --kind baseline            # no LLM; then scripts/score_run.py --run <id> --snapshot S1
scripts/run_engine.py --kind kb --radar          # LLM
scripts/score_run.py --run <kb_id>               # defaults to S2
scripts/run_radar.py <kb_id>                     # only if radar is missing/partial (LLM)
scripts/make_whatif_presets.py --run             # create presets and run each (LLM); --dry-run to preview
```

## Rerun after the Anthropic API limit is lifted
1. Raise/replace the key (`LLM_API_KEY` in `backend/.env` and in Render).
2. `scripts/run_engine.py --kind kb --radar`, then `scripts/score_run.py --run <id>`.
3. For an existing kb run with missing radar items: `scripts/run_radar.py <run_id>`.
4. `scripts/make_whatif_presets.py --run`, then `scripts/demo_prep.py --api-base <url>` to verify and print the table.

## Pinning a good demo run
- With no `?run=`, the UI uses the latest done `kb` run. A newer (worse) kb run therefore replaces the demo view.
- Pin explicitly by sharing URLs with `?run=<run_id>` (the Header run picker sets it), and avoid starting new kb runs once a good one exists.
- Judge a run by `/engine/runs/<id>/scorecard` and `score_reports` (recall, precision, FP rate, routing).

## Known gaps
- The documents list lacks a reviewed count.
- Ingest `v1` version fallback bug in `app/company_ingest/cli/ingest.py`.
- 2 pre-existing failing tests in `tests/company_ingest/test_roles.py`.
- Radar items for 3 changes are still pending (rerun `run_radar.py` once the API limit is lifted).
- The S2 scoring parser (`scripts/score_run.py`) was verified on synthetic text only; check the stored metrics against the raw scoring output.
- Current latest kb run (`61237079...`) scores recall 0.0 / precision 0.0 on S2 (3 non-informational findings vs 6 expected); the S1 baseline check passes.

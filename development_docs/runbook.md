# Demo runbook

## Local demo start
```
cd backend && PYTHONPATH=. .venv/bin/uvicorn app.main:app --port 8000
cd frontend && pnpm exec next typegen   # first time / clean checkout only
cd frontend && NEXT_PUBLIC_STRATA_DATA=http pnpm dev      # http://localhost:3000 (set the vars in frontend/.env.local)
```

## Demo day checklist (one page)
1. Start the backend (command above); `curl http://localhost:8000/health` returns `{"status":"ok"}`. Hit it again just before going on stage (Neon warm-up).
2. Start the frontend; confirm `frontend/.env.local` has `NEXT_PUBLIC_STRATA_DATA=http` and `NEXT_PUBLIC_STRATA_API_URL=http://localhost:8000`.
3. Open `http://localhost:3000/app?run=0dcc125e-6da6-419f-beb1-8c347e4fb2d4` and keep `?run=` in every shared URL (pins the run).
4. Expected: 4 action required, 0 review, 2 documents flagged / 10 cleared, 721 clauses cleared, 1,114 changes -> 1,015 noise -> 96 in footprint -> 9 real, radar 20/53/17.
5. Scorecard: say it honestly. Clause-level precision/recall are 0 (4 vs 6 expected, export-format question open); 12/12 documents correctly flagged/cleared; FP-rate, routing, baseline PASS.
6. What-if: use the 4 presets only (simulated data).
7. Do NOT click: custom what-if (paused; needs LLM, writes to DB); Accept/Reject review buttons on real findings (reviews write to the shared Neon DB); do not start new kb runs (a newer run replaces the default view).
8. Fallback: set `NEXT_PUBLIC_STRATA_DATA=mock` and restart `pnpm dev`.

## Environment variables

Backend (Render, `backend/render.yaml`; secrets are `sync: false` and must be set in the dashboard):
- Secrets: `DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `LLM_API_KEY`.
- Preset in render.yaml: `LLM_PROVIDER=anthropic`, `LLM_MODEL`, all `ENGINE_*` (models, thresholds, call caps, concurrency; defaults match architecture.md section 6).
- `ENGINE_CORS_ORIGINS`: comma-separated allowed origins, set to the Vercel URL (e.g. `https://strata.vercel.app`). Unset or `*` allows all.
- `DATABASE_URL` must use the `postgresql+asyncpg://` form.
- Start command: `alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT` (Procfile identical). The live DB is already at head `e5a1c7d9b304`, so this is a no-op there.

Frontend (Vercel, root directory `frontend`, framework Next.js, no vercel.json needed; `npm run build` verified):
- `NEXT_PUBLIC_STRATA_DATA=mock|http` (default `mock`; use `http` for live data).
- `NEXT_PUBLIC_STRATA_API_URL` = backend URL with no trailing slash and no `/engine` suffix (e.g. `https://strata-backend.onrender.com`; local `http://localhost:8000`).
- `NEXT_PUBLIC_STRATA_ALLOW_CUSTOM_WHATIF=1` enables custom what-if in http mode. Leave unset (paused: needs LLM and writes to the DB).
- All are baked in at build time, so rebuild/redeploy (or restart `pnpm dev`) after changing them. Deployment is currently deferred; the demo is local.

## Deploy order
1. Render: create the service from `backend/render.yaml` (Blueprint), fill in secrets, deploy. Check `<render-url>/health` and `<render-url>/engine/runs`.
2. Vercel: import the repo, root `frontend`, set `NEXT_PUBLIC_STRATA_DATA=http` and `NEXT_PUBLIC_STRATA_API_URL`, deploy.
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

## Neon idle connections
Neon drops idle pooled connections, which used to give a `500: connection is closed` on the first request after idle. Fixed with `pool_pre_ping`/`pool_recycle` in `backend/app/db.py` plus a one-time GET retry in the frontend. Still warm `/health` before the demo.

## Offline-filled judgments and LLM use
The LLM key works again, but demo runs are cache-only: judgments live in `engine.llm_calls`, many filled offline (see `engine_spec.md`, "Offline-filled judgments"; tools `backend/scripts/offline_judge_export.py` / `offline_judge_import.py`, guide `backend/scripts/offline_judge_GUIDE.md`). If you must start a kb run, set `ENGINE_MAX_LLM_CALLS_KB` low as a fuse.

## Known gaps
- The documents list lacks a reviewed count.
- Ingest `v1` version fallback bug in `app/company_ingest/cli/ingest.py`.
- 2 pre-existing failing tests in `tests/company_ingest/test_roles.py`.
- The S2 scoring parser (`scripts/score_run.py`) was verified on synthetic text only; check the stored metrics against the raw scoring output.
- Default demo run `0dcc125e-6da6-419f-beb1-8c347e4fb2d4` scores recall 0 / precision 0 / matched 0 (4 non-info findings vs 6 expected); FP-rate PASS, routing PASS, baseline PASS, 12/12 documents correct. Open export-format question: `scoring_diagnosis.md`.

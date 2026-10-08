# Strata

Strata shows a company which clauses in which of its documents are affected when government regulations change, why (with verified quotes), what must change and who must act. It flags only; it never edits documents. The demo applies real federal and Indiana rules to a synthetic utility's 12 policy documents.

Design docs: start with [`development_docs/README.md`](development_docs/README.md) ([PRD](development_docs/PRD.md), [TDD](development_docs/TDD.md)).

## Prerequisites

- Python 3.11, Node 22+, [pnpm](https://pnpm.io)
- Accounts and keys for:

| Service | Used for | Variables |
|---|---|---|
| [Neon](https://neon.tech) Postgres | All relational data | `DATABASE_URL` |
| [Qdrant Cloud](https://qdrant.tech) | Vector search | `QDRANT_URL`, `QDRANT_API_KEY` |
| [Cloudflare R2](https://developers.cloudflare.com/r2/) | Raw source files | `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME` |
| [Anthropic](https://console.anthropic.com) | Impact engine and company enrichment | `LLM_API_KEY` |

## Backend

```bash
cd backend
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in the keys above; FRONTEND_URL=http://localhost:3000
alembic upgrade head            # create database schemas
python scripts/setup_qdrant.py  # create vector collections
uvicorn app.main:app --reload   # http://localhost:8000  (docs at /docs)
```

## Load data (once, from `backend/` with the venv active)

```bash
# law snapshots: S1 (2024-12-31) then S2 (2025-12-31)
python scripts/seed_agencies.py
python scripts/seed_phase1.py && python scripts/seed_indiana_phase1.py
python scripts/seed_phase2.py && python scripts/seed_indiana_phase2.py
python scripts/embed_all.py                       # vector index
# company documents, then the impact engine
python -m app.company_ingest.cli.ingest
python scripts/run_engine.py --kind kb
```

Afterwards, `POST /jobs/ingest` pulls new law updates incrementally. Runs and their results are stored in the database, so this only needs doing once.

## Frontend

```bash
cd frontend
pnpm install
cp .env.example .env.local      # BACKEND_URL=http://localhost:8000
pnpm dev                        # http://localhost:3000
```

## Tests

```bash
cd backend && pytest -m "not neon and not qdrant and not corpus"
cd frontend && pnpm test
```

## Deploy

Set `BACKEND_URL` (frontend host) to the backend's public URL and `FRONTEND_URL` (backend host) to the frontend's public URL. Both are origins without a trailing slash.

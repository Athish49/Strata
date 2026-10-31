# Synthetic demo data — deletable

Everything under `backend/synthetic/` exists only to produce a demo company
("Rockridge Power & Light", `RPL-*`). **The application does not depend on it.**
You can delete this whole directory and the app, its API and its test suite
keep working.

## The rule

Nothing under `backend/app/` may reference this directory. That is enforced by
`tests/engine/test_barrier.py` (task 2.4), so a violation fails CI.

## What is here

| Path | Purpose |
|---|---|
| `corpus/` | The generated demo corpus: 12 policy documents, 3 CSV registers, global reference files, plus the generator scripts and the evaluation key. Moved from `app/company/` in task 2.1 |
| `seed.py` | Loads the corpus **through the real HTTP API** (org endpoints, `POST /company/documents`, roles, metadata `PATCH`, approval decisions), exactly as a customer's upload would arrive; idempotent (a re-run makes zero writes). `--plan` prints the 15-document plan without HTTP (task 9.1) |
| `corpus_meta.py` | Loaders for `corpus/_global/` (people directory incl. `document_roles`, company profile, document register) and the per-document files; the register + people directory are the source of truth, not `.md` front matter (task 9.1) |
| `make_docx.py` | Deterministic `.md` -> DOCX generator the seeder uploads (the `render/*.docx` files are lossy and one is corrupt); every heading and table survives `DocxExtractor` (task 9.1) |
| `rehearsal.py` | End-to-end rehearsal on THROWAWAY infrastructure: local scratch Postgres (127.0.0.1, SSL, random port) -> the real `alembic upgrade head` -> schema diff vs `tests/engine/fixtures/company_schema.sql` -> read-only KB copy -> `--inner`. Exit 0 = every 9.1 acceptance check held (task 9.1) |
| `rehearsal_inner.py` | The `--inner` stage: the real app + `seed.seed()` in-process over `httpx.ASGITransport`, with R2 = moto, Qdrant = `QdrantClient(":memory:")`, a deterministic hash embedding, a deterministic LLM stub and every non-loopback socket refused. Seeds twice, asserts 9.1, prints the 9.3 parity prediction |
| `copy_kb.py` | Copies `public.code_sections` + its FK parents from production into a 127.0.0.1 scratch DB with a `readonly=True` session (SELECT only); the production URL never enters `os.environ` |
| `score_run.py`, `demo_prep.py` | Demo tooling. `score_run.py` shells out to `corpus/eval/scoring.py` |
| `baseline_snapshot.py`, `baseline_before_v2.json` | Production metrics captured **before** the v2 cutover wiped `company.*`/`engine.*` (task 0.1). The rehearsal's parity table and `verify_parity.py` (9.3) compare against it |

## Rehearsing the seed (no production writes, no external calls)

```bash
backend/.venv/bin/python backend/synthetic/rehearsal.py            # ~45 s
backend/.venv/bin/python backend/synthetic/rehearsal.py --keep     # keep the scratch dir
backend/.venv/bin/python backend/synthetic/rehearsal.py --stop-after migrate|copy
```

Needs local PostgreSQL 17 binaries (`STRATA_PG_BIN`, default
`/opt/homebrew/opt/postgresql@17/bin`) and `openssl`. The only thing that touches
production is `copy_kb.py`'s read-only SELECT of the KB (it reads `backend/.env`
itself). The migrate and `--inner` children get `child_env()`: the scratch
`DATABASE_URL`, dummy keys, an empty working directory (no `.env`) and a scratch
`HOME`; `--inner` additionally records and fails on any non-loopback connection
attempt.

## Why seeding goes through the API

If the seeder works, the real customer path works — there is no privileged
ingestion route. Do not add direct database writes here.

## Rules for this directory

- Read `DATABASE_URL` and other secrets from `backend/.env`; never hardcode them.
  Exception: the rehearsal's child processes must never see `.env` or real keys
  (do not add `**os.environ` or `.env` reading to `rehearsal.py`'s child path or
  `rehearsal_inner.py`).
- `corpus/eval/` and `corpus/grounding/` are the information barrier's protected
  ground truth. The engine must never read them (`tests/engine/test_barrier.py`).

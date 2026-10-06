# Strata — Infrastructure & Deployment

## Design Principle

All services run on free-tier cloud platforms from day one. No local Docker instances, no migration later. Data flows to production services from the first ingestion.

---

## Service Stack

| Component | Service | Plan | Limits | Purpose |
|---|---|---|---|---|
| Backend API + Workers | **Render** | Free | 750 hrs/mo, auto-sleep after 15 min inactivity, 512 MB RAM | FastAPI app serving the REST API and running ingestion adapters |
| Cron Scheduler | **Render Cron Jobs** | Free | 1 cron job, min interval: daily | Triggers ingestion adapters on schedule |
| Frontend | **Vercel** (deferred) | Free (Hobby) | — | Not in V1 backend scope — will be built later |
| Primary Database | **Neon PostgreSQL** | Free | 0.5 GB storage, 1 project, autoscaling compute | CodeSections, RegulatoryActions, relationships, sync state, agency registry |
| Vector Database | **Qdrant Cloud** | Free | 1 GB, 1 cluster, 1M vectors | Embedded regulation text chunks for semantic search |
| Object Storage | **Cloudflare R2** | Free | 10 GB storage, 1M Class A ops/mo, 10M Class B ops/mo, zero egress fees | Raw API responses, scraped HTML, PDFs |

---

## Backend (Render)

**Service type:** Web Service (Python)
**Runtime:** Python 3.11+
**Framework:** FastAPI
**Build command:** `pip install -r requirements.txt`
**Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Handling Auto-Sleep

Render free tier sleeps the service after 15 minutes of no inbound requests. This affects:
- **API endpoints:** First request after sleep takes ~30s to spin up. Acceptable for V1.
- **Ingestion jobs:** Must be triggered by Render Cron Job, which wakes the service. The cron hits a `/jobs/ingest` endpoint that runs the adapter pipeline.

### Project Structure (Backend)

```
strata-backend/
├── app/
│   ├── main.py                    # FastAPI app entry point
│   ├── config.py                  # Environment variables, DB URLs
│   ├── api/
│   │   ├── regulations.py         # /regulations endpoints
│   │   ├── actions.py             # /actions endpoints
│   │   ├── diff.py                # /diff endpoints
│   │   ├── timeline.py            # /timeline endpoints
│   │   ├── impact.py              # /impact endpoints
│   │   ├── search.py              # /search (vector) endpoints
│   │   └── jobs.py                # /jobs/ingest trigger endpoint
│   ├── adapters/
│   │   ├── base.py                # SourceAdapter interface
│   │   ├── ecfr.py                # eCFR adapter → CodeSection
│   │   ├── federal_register.py    # FR API adapter → RegulatoryAction
│   │   ├── oac.py                 # OAC scraper → CodeSection
│   │   └── puco_dis.py            # PUCO DIS scraper → RegulatoryAction
│   ├── ingestion/
│   │   ├── pipeline.py            # Validation, dedup, status mapping
│   │   ├── change_detector.py     # Hash-diff for codebook sources
│   │   ├── version_chain.py       # Links new snapshots to prior versions
│   │   └── stitcher.py            # Cross-reference linking engine
│   ├── models/
│   │   ├── code_section.py        # SQLAlchemy model
│   │   ├── regulatory_action.py   # SQLAlchemy model
│   │   ├── agency.py              # Agency registry model
│   │   ├── sync_state.py          # Adapter sync cursor model
│   │   └── relationship.py        # Action relationship model
│   ├── services/
│   │   ├── vector.py              # Qdrant client wrapper
│   │   └── storage.py             # Cloudflare R2 client wrapper
│   └── db.py                      # Database connection (Neon)
├── migrations/                    # Alembic migrations
├── requirements.txt
├── render.yaml                    # Render service config
└── .env.example
```

### Environment Variables

```
DATABASE_URL=postgresql://...@...neon.tech/neondb     # Neon connection string
QDRANT_URL=https://...qdrant.io                       # Qdrant Cloud endpoint
QDRANT_API_KEY=...                                    # Qdrant Cloud API key
QDRANT_PROJECT_TAG=strata                             # Project isolation tag — must prefix ALL Qdrant queries
R2_ENDPOINT=https://...r2.cloudflarestorage.com       # R2 S3-compatible endpoint
R2_ACCESS_KEY_ID=...                                  # R2 credentials
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=strata                                 # Bucket name (not strata-raw)
```

---

## Frontend (Deferred)

Frontend will be built later on Vercel with Next.js. Not in V1 backend scope.

---

## Primary Database (Neon PostgreSQL)

### Why Neon over alternatives

- Free tier has 0.5 GB storage (sufficient for V1 text data)
- Serverless Postgres — auto-scales compute, sleeps when idle (matches Render's sleep pattern)
- Standard PostgreSQL — no vendor lock-in, standard SQLAlchemy/psycopg2 drivers
- Branch-able databases for testing

### Tables Overview

```sql
-- Core data tables
code_sections          -- Versioned regulation text snapshots
regulatory_actions     -- Immutable agency action records
action_relationships   -- Typed edges between actions

-- Reference tables
agencies               -- Canonical agency registry

-- Operational tables
sync_state             -- Per-adapter sync cursors
```

Note: Action type mappings (source type → canonical `action_type`) are handled as configuration within each adapter, not as a DB table. An `ingestion_log` table can be added later for audit purposes but is not required for V1 core functionality.

### Storage Estimate (V1)

| Data | Estimated Records | Avg Size | Total |
|---|---|---|---|
| CodeSection snapshots (2 ingestions × ~160 sections) | ~360 | 5 KB | ~1.8 MB |
| RegulatoryAction records (2 quarters × ~70 docs/cases) | ~140 | 2 KB | ~0.3 MB |
| Relationships | ~150 | 0.1 KB | ~0.015 MB |
| Agencies, mappings, sync state | ~20 | 0.5 KB | ~0.01 MB |
| **Total** | | | **~2.1 MB** |

Well within the 0.5 GB free tier limit. Room for 50x+ growth before needing to upgrade.

---

## Vector Database (Qdrant Cloud)

### Purpose

Store embedded chunks of regulation text for semantic search. Enables queries like "find regulations about emissions monitoring for coal plants" without exact keyword matching.

### Shared Cluster — Project Isolation

The Qdrant cluster (`Athish_Personal_Projects`) is shared with another project (FDAComplianceAI) on the same free-tier instance. To keep data isolated:

- **Every vector upserted must include `project: "strata"` in its payload.**
- **Every search or filter query must include a `must` condition on `project = "strata"` before any other filters are applied.**
- This applies to all operations: upsert, search, scroll, delete, and count.
- The `QDRANT_PROJECT_TAG` env var holds this value (`strata`) — always read it from config, never hardcode the string.

### Setup

- **Collection:** `regulation_chunks`
- **Vector size:** 384 (`all-MiniLM-L6-v2` via `sentence-transformers` — free, no API key needed, runs locally on Render)
- **Payload:** `{ project, citation, source_system, heading, chunk_index, snapshot_date, agency, status }` — `project` is always first and always `"strata"`.

### Chunking Strategy

- Each `CodeSection.body_text` is split into chunks of ~500 tokens with 50-token overlap.
- Each `RegulatoryAction.abstract` is stored as a single chunk (abstracts are typically short enough).
- Chunks carry metadata allowing filtered search (by agency, status, jurisdiction).
- All chunks carry `project: "strata"` in payload — this is the outermost filter in every query.

### Storage Estimate

~200 unique CodeSections × avg 3 chunks = ~600 vectors + ~140 action abstracts = ~740 vectors. At 384 dims × 4 bytes × 740 = ~1.1 MB. Well within 1 GB free tier. (Only current versions are embedded, not historical snapshots.)

---

## Object Storage (Cloudflare R2)

### Purpose

Store raw source data for audit, replay, and debugging. Not queried in normal operation — only accessed when investigating a data issue.

### Bucket Structure

```
strata-raw/
├── ecfr/
│   ├── 2025-01-02/
│   │   ├── title-18.xml
│   │   └── title-40-part-60.xml
│   └── 2025-07-01/
│       ├── title-18.xml
│       └── title-40-part-60.xml
├── federal-register/
│   ├── 2025-Q1/
│   │   ├── 2026-00001.json
│   │   └── ...
│   └── 2025-Q2/
│       └── ...
├── oac/
│   ├── 2025-01/
│   │   └── 4901-1-10-10.html
│   └── 2025-07/
│       └── ...
└── puco-dis/
    ├── cases/
    │   ├── 24-0100-EL-SSO.html
    │   └── ...
    └── filings/
        └── ...
```

### Access Pattern

- **Write:** Adapters upload raw responses after each pull using S3-compatible SDK (`boto3` with R2 endpoint).
- **Read:** Rarely — only for debugging or replaying ingestion. No read path in normal API flow.

---

## Deployment Sequence

### First-Time Setup

1. **Neon:** Create project `strata`, database `strata`. Run Alembic migrations to create tables. Seed agency registry.
2. **Qdrant Cloud:** Create cluster, create `regulation_chunks` collection with correct vector config.
3. **Cloudflare R2:** Create bucket `strata-raw`.
4. **Render:** Create web service from GitHub repo. Set environment variables. Deploy.
5. **Render Cron:** Create cron job pointing to `https://<service>.onrender.com/jobs/ingest` on daily schedule.

### Ingestion Runs

Ingestion is triggered by hitting the `/jobs/ingest` endpoint, either:
- Manually (during development/seed data loading)
- Via Render Cron Job (production daily sync)

The endpoint runs all adapters in sequence, processes the pipeline, and returns a summary of what was ingested.

---

## Cost Summary

| Service | Monthly Cost |
|---|---|
| Render (backend) | $0 |
| Neon (PostgreSQL) | $0 |
| Qdrant Cloud (vectors) | $0 |
| Cloudflare R2 (storage) | $0 |
| **Total** | **$0** |

Embedding uses `all-MiniLM-L6-v2` via `sentence-transformers` — runs locally on Render, zero API cost. V1 seed data is ~740 vectors, trivial compute.

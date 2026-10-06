# Strata — System Architecture

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL DATA SOURCES                                   │
│                                                                                      │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐  ┌────────────┐                    │
│  │  eCFR API  │  │ Federal    │  │  Ohio OAC   │  │  PUCO DIS  │                    │
│  │ (Title 18, │  │ Register   │  │ (codes.     │  │ (dis.puc.  │                    │
│  │  Title 40) │  │ API        │  │  ohio.gov)  │  │ state.oh.  │                    │
│  │  Bucket 1  │  │ Bucket 2   │  │  Bucket 3   │  │  us)       │                    │
│  │  Codebook  │  │ Journal    │  │  Codebook   │  │  Bucket 4  │                    │
│  │  JSON/XML  │  │ JSON       │  │  HTML/scrape│  │  Journal   │                    │
│  └─────┬──────┘  └─────┬──────┘  └──────┬──────┘  │  HTML/scrape│                   │
│        │               │                │          └──────┬──────┘                    │
└────────┼───────────────┼────────────────┼────────────────┼───────────────────────────┘
         │               │                │                │
         ▼               ▼                ▼                ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          SOURCE ADAPTERS  (one per source)                            │
│                                                                                      │
│  Each adapter:                                                                       │
│  ├── Polls source on schedule (daily/weekly)                                         │
│  ├── Manages its own sync cursor (last-pulled date/state)                            │
│  ├── Handles pagination, rate limiting, retries                                      │
│  ├── Normalizes raw data → CodeSection or RegulatoryAction                           │
│  └── Preserves raw source response for audit                                         │
│                                                                                      │
│  ┌────────────┐  ┌────────────┐  ┌─────────────┐  ┌─────────────┐                   │
│  │eCFR Adapter│  │FedReg      │  │OAC Adapter  │  │PUCO Adapter │                   │
│  │→CodeSection│  │Adapter     │  │→CodeSection  │  │→Regulatory  │                   │
│  │            │  │→Regulatory │  │             │  │  Action     │                   │
│  │            │  │  Action    │  │             │  │             │                   │
│  └─────┬──────┘  └─────┬──────┘  └──────┬──────┘  └──────┬──────┘                   │
└────────┼───────────────┼────────────────┼────────────────┼───────────────────────────┘
         │               │                │                │
         ▼               ▼                ▼                ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                           INGESTION PIPELINE                                         │
│                                                                                      │
│  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐                     │
│  │  Schema          │  │  Change           │  │  Status          │                    │
│  │  Validator       │  │  Detector         │  │  Mapper          │                    │
│  │                  │  │                   │  │                  │                    │
│  │  Validates       │  │  CodeSection:     │  │  Maps source     │                    │
│  │  required fields,│  │  hash-diff vs     │  │  type + dates    │                    │
│  │  enum values,    │  │  stored version   │  │  → three-level   │                    │
│  │  type checks     │  │                   │  │  status model    │                    │
│  │                  │  │  RegulatoryAction: │  │  (in_progress,   │                    │
│  │                  │  │  dedup check on   │  │   approved,      │                    │
│  │                  │  │  (sys, id) key    │  │   blocked)       │                    │
│  └────────┬─────────┘  └────────┬──────────┘  └────────┬─────────┘                   │
│           └──────────────┬──────┴────────────────┬──────┘                             │
│                          ▼                       ▼                                    │
│           ┌──────────────────────────┐ ┌──────────────────────┐                      │
│           │  Version Chain Builder   │ │  Stitching Engine    │                      │
│           │                          │ │                      │                      │
│           │  CodeSection: links new  │ │  Links journal →     │                      │
│           │  snapshot to prior via   │ │  codebook via        │                      │
│           │  prior_version_id        │ │  cfr_references      │                      │
│           │                          │ │                      │                      │
│           │  RegulatoryAction: links │ │  Links action chains │                      │
│           │  related actions via     │ │  via RIN, docket_ids │                      │
│           │  RIN / docket matching   │ │                      │                      │
│           └───────────┬──────────────┘ │  Links cross-juris.  │                      │
│                       │                │  via CFR citations   │                      │
│                       │                │  in state filings    │                      │
│                       │                └──────────┬───────────┘                      │
└───────────────────────┼──────────────────────────┼───────────────────────────────────┘
                        │                          │
                        ▼                          ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                              DATA LAYER                                              │
│                                                                                      │
│  ┌────────────────────────────────────────────────────┐                               │
│  │            PostgreSQL (Neon — free tier)            │                               │
│  │                                                    │                               │
│  │  Tables:                                           │                               │
│  │  ├── code_sections (versioned snapshots)           │                               │
│  │  ├── regulatory_actions (immutable records)        │                               │
│  │  ├── action_relationships (typed edges)            │                               │
│  │  ├── agencies (canonical registry)                 │                               │
│  │  ├── sync_state (cursors per adapter)              │                               │
│  │  └── action_type_mappings (source→canonical maps)  │                               │
│  └───────────────────┬────────────────────────────────┘                               │
│                      │                                                                │
│  ┌───────────────────▼────────────────────────────────┐                               │
│  │          Vector Store (Qdrant Cloud — free tier)    │                               │
│  │                                                    │                               │
│  │  Collections:                                      │                               │
│  │  └── regulation_chunks (embedded reg text + action │                               │
│  │       abstracts, filtered by metadata)             │                               │
│  └───────────────────┬────────────────────────────────┘                               │
│                      │                                                                │
│  ┌───────────────────▼────────────────────────────────┐                               │
│  │       Object Storage (Cloudflare R2 — free tier)   │                               │
│  │                                                    │                               │
│  │  Buckets:                                          │                               │
│  │  ├── raw-sources/ (original API responses, HTML)   │                               │
│  │  └── documents/ (downloaded PDFs from PUCO DIS)    │                               │
│  └────────────────────────────────────────────────────┘                               │
└──────────────────────┬───────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                            API LAYER  (Render — free tier)                            │
│                                                                                      │
│  ┌──────────────────────────────────────────────┐                                    │
│  │          FastAPI Backend                      │                                    │
│  │                                               │                                   │
│  │  Endpoints:                                   │                                   │
│  │  ├── /regulations — list/search CodeSections  │                                   │
│  │  ├── /actions — list/search RegulatoryActions │                                   │
│  │  ├── /diff/{citation} — version diff          │                                   │
│  │  ├── /timeline/{citation} — version history   │                                   │
│  │  ├── /impact/{entity} — cross-agency impact   │                                   │
│  │  ├── /deadlines — upcoming dates              │                                   │
│  │  └── /search — semantic search via vectors    │                                   │
│  └──────────────────────┬────────────────────────┘                                   │
└─────────────────────────┼────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                          FRONTEND  (deferred — not in V1 backend scope)               │
└──────────────────────────────────────────────────────────────────────────────────────┘
```

## Four Data Buckets

Every jurisdiction follows the same **codebook + journal** pattern:

| Bucket | Role | V1 Source | Data Type Emitted |
|---|---|---|---|
| 1. Federal Codified Regs | Compiled federal rulebook in force | eCFR API (free, keyless) | `CodeSection` |
| 2. Federal Agency Actions | Stream of published rules, orders, actions | Federal Register API (free, keyless) | `RegulatoryAction` |
| 3. State Codified Regs | Compiled state rulebook in force | Ohio OAC (codes.ohio.gov, scraping) | `CodeSection` |
| 4. State Agency Proceedings | Cases, orders, rate decisions | PUCO DIS (dis.puc.state.oh.us, scraping) | `RegulatoryAction` |

- **Buckets 1 & 3** are codebooks — compiled text that changes in place. Produce `CodeSection` records.
- **Buckets 2 & 4** are journals — immutable records that accumulate. Produce `RegulatoryAction` records.
- Adding a new jurisdiction = one new codebook source + one new journal source.

## Source Adapter Contract

Each source is isolated as a pluggable adapter:

```
Interface: SourceAdapter
├── configure(source_config)        # API URLs, credentials, filters
├── get_sync_cursor() -> cursor     # Last-pulled state
├── poll(cursor) -> RawRecord[]     # Fetch new/changed records since cursor
├── normalize(RawRecord) -> CodeSection | RegulatoryAction
├── update_sync_cursor(new_cursor)  # Persist after successful batch
└── health_check() -> status        # Is the source accessible
```

Adding a new agency/domain requires writing one adapter + one type mapping config. No changes to ingestion pipeline, data store, or downstream application.

## Infrastructure Stack (All Free Tier)

| Component | Service | Tier | Purpose |
|---|---|---|---|
| Backend API + Ingestion Workers | Render | Free (750 hrs/mo) | FastAPI app, adapter scheduling, stitching engine |
| Frontend | Vercel (deferred) | Free | Not in V1 backend scope — will be built later |
| Primary Database | Neon PostgreSQL | Free (0.5 GB) | CodeSections, RegulatoryActions, relationships, sync state, agency registry |
| Vector Database | Qdrant Cloud | Free (1 GB, 1 cluster) | Embedded regulation text chunks for semantic search |
| Object Storage | Cloudflare R2 | Free (10 GB, no egress) | Raw API responses, scraped HTML, downloaded PDFs |

### Infrastructure Notes

- **Render free tier** auto-sleeps after 15 min of inactivity. Scheduled ingestion jobs should be triggered via Render Cron Jobs (available on free tier) to wake the service.
- **Neon free tier** has a 0.5 GB storage limit. For V1 scope (3 FERC parts + 4 EPA parts + PUCO electric rules and cases), estimated ~2-4 MB total. Well within limits with room for 100x+ growth.
- **Qdrant Cloud free tier** provides 1 GB and 1 cluster. Sufficient for V1 embedding volume.
- **Cloudflare R2** has no egress fees — ideal for storing raw source data that the backend reads back.
- All services communicate over public HTTPS. No VPC or private networking needed for V1.

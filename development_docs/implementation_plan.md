# Strata — Implementation Plan

## How to Use This Document

Each task is numbered (e.g. `1.1.1`). Tasks specify:
- **What to build** — a specific, self-contained unit of work
- **Read before starting** — which doc(s) and section(s) to read
- **Depends on** — which tasks must be completed first (`NONE` = can start immediately)
- **Parallel** — whether multiple agents can work on sibling tasks simultaneously
- **Output** — what files/artifacts this task produces
- **Verify** — how to confirm the task is done correctly

Tasks marked `⛓ SEQUENTIAL` must be completed before any task that depends on them. Tasks marked `⚡ PARALLEL` can be worked on simultaneously by different agents.

---

## Phase 1: Project Foundation

> These tasks set up the project structure, database, and core models. Must be completed before any other phase.

### 1.1 Backend Project Setup `⛓ SEQUENTIAL`

**1.1.1 — Initialize backend project**
- **What:** Create the `backend/` directory structure as specified in `infrastructure.md` → "Project Structure (Backend)". Initialize a Python project with `requirements.txt`. Set up FastAPI app entry point at `app/main.py` with a health check endpoint `GET /health` that returns `{"status": "ok"}`.
- **Read:** `infrastructure.md` → "Project Structure (Backend)" section
- **Depends on:** NONE
- **Output:** `backend/` directory with `app/main.py`, `app/config.py`, `app/__init__.py`, `requirements.txt`
- **Dependencies to install:** `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `psycopg2-binary`, `httpx`, `boto3`, `qdrant-client`, `sentence-transformers`, `beautifulsoup4`, `lxml`
- **Verify:** `uvicorn app.main:app --port 8000` starts and `GET /health` returns 200

**1.1.2 — Configure environment and external services**
- **What:** Create `app/config.py` that reads environment variables for all external services. Create `.env.example` with all required vars. Create `app/db.py` with SQLAlchemy async engine and session factory pointing to Neon PostgreSQL. Create `app/services/storage.py` with a Cloudflare R2 client (boto3 S3-compatible). Create `app/services/vector.py` with a Qdrant client wrapper.
- **Read:** `infrastructure.md` → "Environment Variables" section, "Object Storage" section, "Vector Database" section
- **Depends on:** 1.1.1
- **Output:** `app/config.py`, `app/db.py`, `app/services/storage.py`, `app/services/vector.py`, `.env.example`
- **Env vars needed:** `DATABASE_URL`, `QDRANT_URL`, `QDRANT_API_KEY`, `R2_ENDPOINT`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`
- **Verify:** App starts without errors when env vars are set. DB connection can be tested with a simple query. R2 client can list bucket contents (empty is fine). Qdrant client can check cluster info.

---

### 1.2 Database Schema `⛓ SEQUENTIAL`

**1.2.1 — Create SQLAlchemy models for core data types**
- **What:** Create all database models matching the schemas in `data_models.md`. Each model in its own file under `app/regulatory/models/`. Create:
  - `app/regulatory/models/code_section.py` — `CodeSection` table with all fields from the CodeSection schema. Primary key: auto-increment `id`. Unique constraint on `(source_system, citation, snapshot_date)`. Index on `(source_system, citation)` for current-version lookups.
  - `app/regulatory/models/regulatory_action.py` — `RegulatoryAction` table with all fields. Primary key: auto-increment `id`. Unique constraint on `(source_system, source_id)`. `dates` stored as individual columns (`date_published`, `date_effective`, `date_comment_close`, `date_filed`). `docket_ids`, `cfr_references`, `legal_refs`, `affected_entities` stored as PostgreSQL `ARRAY(String)`.
  - `app/regulatory/models/relationship.py` — `ActionRelationship` table: `id`, `from_action_id` (FK), `to_action_id` (FK), `relationship_type` (enum from relationship types in data_models.md).
  - `app/regulatory/models/agency.py` — `Agency` table: `agency_id` (PK, string), `name`, `aliases` (ARRAY), `jurisdiction_level`, `jurisdiction_geo`, `codebook_title`, `domain` (ARRAY).
  - `app/regulatory/models/sync_state.py` — `SyncState` table: `id`, `source_system` (unique), `cursor_data` (JSON — flexible per adapter), `last_sync_at` (timestamp).
  - `app/regulatory/models/__init__.py` — imports all models, exposes `Base` for Alembic.
- **Read:** `data_models.md` → entire document (CodeSection schema, RegulatoryAction schema, Relationship Types, Agency Registry)
- **Depends on:** 1.1.2
- **Output:** All files listed above
- **Verify:** Models can be imported without errors. `Base.metadata.tables` lists all 5 tables.

**1.2.2 — Set up Alembic and run initial migration**
- **What:** Initialize Alembic in the project (`alembic init migrations`). Configure `alembic.ini` and `migrations/env.py` to use `DATABASE_URL` from environment and import all models from `app.regulatory.models`. Generate initial migration with `alembic revision --autogenerate -m "initial schema"`. Run migration against Neon PostgreSQL with `alembic upgrade head`.
- **Read:** No additional doc needed — standard Alembic setup
- **Depends on:** 1.2.1
- **Output:** `migrations/` directory, `alembic.ini`, initial migration file
- **Verify:** `alembic upgrade head` succeeds. Tables exist in Neon. `alembic current` shows head revision.

**1.2.3 — Seed agency registry**
- **What:** Create a seed script `scripts/seed_agencies.py` that inserts the V1 agencies into the `Agency` table. Agencies to seed:
  - `ferc`: Federal Energy Regulatory Commission, aliases: `["FERC", "federal-energy-regulatory-commission"]`, jurisdiction: federal, codebook_title: "18", domain: `["energy", "electricity"]`
  - `epa`: Environmental Protection Agency, aliases: `["EPA", "environmental-protection-agency"]`, jurisdiction: federal, codebook_title: "40", domain: `["environment", "energy"]`
  - `puco`: Public Utilities Commission of Ohio, aliases: `["PUCO"]`, jurisdiction: state, geo: "OH", codebook_title: "4901", domain: `["energy", "electricity"]`
- **Read:** `data_models.md` → "Agency Registry" section
- **Depends on:** 1.2.2
- **Output:** `scripts/seed_agencies.py`, seed data in Neon
- **Verify:** Query `SELECT * FROM agencies` returns 3 rows.

---

### 1.3 Vector Store Setup `⚡ PARALLEL with 1.2`

**1.3.1 — Create Qdrant collection**
- **What:** Create a setup script `scripts/setup_qdrant.py` that creates the `regulation_chunks` collection in Qdrant Cloud. Configuration: vector size 384 (for `all-MiniLM-L6-v2` — free, no API key needed), distance metric: Cosine. Payload indexes on: `project`, `source_system`, `citation`, `agency`, `status`, `jurisdiction_level`.
- **Shared cluster note:** The cluster (`Athish_Personal_Projects`) is shared with another project. Every vector upsert must include `project: settings.QDRANT_PROJECT_TAG` in its payload. Every search/filter must include a `must` condition on `project = settings.QDRANT_PROJECT_TAG` as the first filter. See `infrastructure.md` → "Shared Cluster — Project Isolation" section.
- **Read:** `infrastructure.md` → "Vector Database" section (entire — including "Shared Cluster" subsection)
- **Depends on:** 1.1.2 (needs Qdrant client)
- **Output:** `scripts/setup_qdrant.py`
- **Verify:** Script runs without error. Qdrant Cloud dashboard shows the collection with correct config. `project` payload index exists.

---

## Phase 2: Source Adapters

> Each adapter is independent. All four can be built in parallel by different agents. Each adapter must conform to the same interface.

### 2.0 Adapter Base Class `⛓ SEQUENTIAL — before 2.1-2.4`

**2.0.1 — Create adapter base interface**
- **What:** Create `app/regulatory/adapters/base.py` with an abstract base class `SourceAdapter` defining the interface all adapters must implement:
  ```python
  class SourceAdapter(ABC):
      source_system: str  # e.g. "cfr", "federal_register"
      
      @abstractmethod
      async def get_sync_cursor(self, db: Session) -> dict: ...
      
      @abstractmethod
      async def poll(self, cursor: dict) -> list[dict]: ...  # Returns raw records
      
      @abstractmethod
      def normalize(self, raw: dict) -> CodeSection | RegulatoryAction: ...
      
      @abstractmethod
      async def update_sync_cursor(self, db: Session, new_cursor: dict): ...
      
      async def health_check(self) -> bool: ...
  ```
  Also create shared utility functions: `compute_content_hash(text: str) -> str` (SHA-256), `upload_raw_to_r2(source_system: str, key: str, data: bytes)`.
- **Read:** `architecture.md` → "Source Adapter Contract" section, `data_models.md` → both schemas (to know the target types)
- **Depends on:** 1.1.2
- **Output:** `app/regulatory/adapters/base.py`
- **Verify:** Class can be imported. Abstract methods enforce implementation.

---

### 2.1 eCFR Adapter `⚡ PARALLEL`

**2.1.1 — Build eCFR adapter core**
- **What:** Create `app/regulatory/adapters/ecfr.py` implementing `SourceAdapter`. The adapter:
  1. Checks `/api/versioner/v1/titles` for `latest_amended_on` on Title 18 and Title 40.
  2. If date advanced since cursor, fetches version history via `/api/versioner/v1/versions/title-{n}` to identify changed sections.
  3. Fetches full part XML via `/api/versioner/v1/full/{date}/title-{n}.xml?part={p}` for the V1 parts only.
  4. Parses XML to extract individual sections: citation, heading, body text.
  5. Filters to target subparts for Title 40 (Da, KKKK, TTTTa, UUUUb for Part 60; UUUUU, YYYY for Part 63; all of Parts 72, 73).
  6. Normalizes each section into a `CodeSection` dict with all required fields.
  7. Computes `content_hash` (SHA-256 of body text).
  8. Uploads raw XML to R2 under `ecfr/{date}/title-{n}-part-{p}.xml`.
  9. Updates sync cursor with new `latest_amended_on` dates.
- **Read:** `data_sources.md` → "Source 1: eCFR" (entire section including endpoints, field mapping, scope filter, limitations), `change_detection.md` → "eCFR (Federal)" section
- **Depends on:** 2.0.1
- **Scope constants to hardcode:**
  - Title 18 parts: `[35, 37, 38]`
  - Title 40 parts: `[60, 63, 72, 73]`
  - Title 40 Part 60 target subparts: `["Da", "KKKK", "TTTTa", "UUUUb"]`
  - Title 40 Part 63 target subparts: `["UUUUU", "YYYY"]`
- **Output:** `app/regulatory/adapters/ecfr.py`
- **Verify:** Running adapter against eCFR API returns a list of CodeSection dicts. Each has `citation`, `heading`, `body_text`, `content_hash`, `source_system="cfr"`, `source_url`. Count is ~80 sections for Title 18, ~80 for Title 40 target subparts.

---

### 2.2 Federal Register Adapter `⚡ PARALLEL`

**2.2.1 — Build Federal Register adapter core**
- **What:** Create `app/regulatory/adapters/federal_register.py` implementing `SourceAdapter`. The adapter:
  1. Queries `GET /documents.json` with agency filters (`federal-energy-regulatory-commission`, `environmental-protection-agency`), type filters (`RULE`, `PRORULE`), and `publication_date[gte]` from cursor.
  2. Paginates through all results following `next_page_url`.
  3. Normalizes each document into a `RegulatoryAction` dict: maps `type` + `action` text → `action_type` using the mapping table in `data_sources.md`.
  4. Maps status: `PRORULE` → `in_progress`; `RULE` with effective date → `approved`.
  5. Extracts `cfr_references` from the API's `cfr_references` field (array of title/part objects) into citation strings like `"18 CFR 35"`.
  6. Uploads raw JSON responses to R2 under `federal-register/{quarter}/{document_number}.json`.
  7. Updates sync cursor with the latest `publication_date` seen.
- **Read:** `data_sources.md` → "Source 2: Federal Register API" (entire section including endpoints, field mapping, type mapping, limitations), `change_detection.md` → "Federal Register API" section
- **Depends on:** 2.0.1
- **Output:** `app/regulatory/adapters/federal_register.py`
- **Verify:** Running adapter with date range 2025-01-01 to 2025-03-31 returns a list of RegulatoryAction dicts. Each has `source_id` (document number), `title`, `action_type`, `status`, `agency`, `cfr_references`. Expected ~50-100 results.

---

### 2.3 OAC Adapter `⚡ PARALLEL`

**2.3.1 — Build OAC scraper adapter**
- **What:** Create `app/regulatory/adapters/oac.py` implementing `SourceAdapter`. The adapter:
  1. Scrapes `https://codes.ohio.gov/ohio-administrative-code/rule-{rule_number}` for each target rule.
  2. Target rules are under chapters: `4901:1-10`, `4901:1-21`, `4901:1-22`, `4901:1-25`. First discover rule numbers by scraping the chapter index pages.
  3. For each rule: extracts heading, body text, effective date from the HTML page.
  4. Normalizes into `CodeSection` dict with `source_system="oac"`, `jurisdiction_level="state"`, `jurisdiction_geo="OH"`, `owning_agency="puco"`.
  5. Computes `content_hash`.
  6. Uploads raw HTML to R2 under `oac/{date}/{rule_number}.html`.
  7. Updates sync cursor with scrape date.
- **Read:** `data_sources.md` → "Source 3: Ohio Administrative Code" (entire section), `change_detection.md` → "OAC (State — Ohio)" section
- **Depends on:** 2.0.1
- **Important:** Use polite scraping — 1 second delay between requests. Set a standard User-Agent header. Handle potential HTML structure changes gracefully with try/except.
- **Output:** `app/regulatory/adapters/oac.py`
- **Verify:** Running adapter returns ~40-60 CodeSection dicts. Each has `citation` (e.g. `4901:1-10-10`), `heading`, `body_text`, `content_hash`.

---

### 2.4 PUCO DIS Adapter `⚡ PARALLEL`

**2.4.1 — Build PUCO DIS scraper adapter**
- **What:** Create `app/regulatory/adapters/puco_dis.py` implementing `SourceAdapter`. The adapter:
  1. Discovers cases by scraping DIS search results filtered to Industry Code `EL` and Purpose Codes `SSO`, `AIR`, `ATA`.
  2. For each case, scrapes `https://dis.puc.state.oh.us/CaseRecord.aspx?CaseNo={case_number}` to extract: case title, status, industry code, purpose code, date opened, date closed, related cases, parties of record.
  3. Scrapes the filing list for each case. Identifies key filings (orders, decisions, stipulations) by looking for keywords in the filing summary: "Order", "Opinion and Order", "Entry", "Stipulation", "Application".
  4. Normalizes case-level data into a `RegulatoryAction` dict. Maps purpose codes to `action_type` using the mapping in `data_sources.md`.
  5. Maps status: case status OPEN → `in_progress`; presence of a Commission Order → `approved`; CLOSED/ARCHIVED → `approved`.
  6. Stores key filing metadata as a JSON array in a `filings` field (or separate table).
  7. Uploads raw HTML to R2 under `puco-dis/cases/{case_number}.html`.
  8. Updates sync cursor with latest scan date.
- **Read:** `data_sources.md` → "Source 4: PUCO DIS" (entire section including scraping strategy, field mapping, purpose code mapping, limitations), `change_detection.md` → "PUCO DIS" section
- **Depends on:** 2.0.1
- **Important:** DIS has bot detection (WAF). Use 2-second delays between requests. Set realistic browser User-Agent. Handle `Request Rejected` responses with retry + backoff. If blocked, log and skip rather than crash.
- **Output:** `app/regulatory/adapters/puco_dis.py`
- **Verify:** Running adapter returns ~10-20 RegulatoryAction dicts. Each has `source_id` (case number like `24-0100-EL-SSO`), `title`, `action_type`, `status`, `agency="puco"`.

---

## Phase 3: Ingestion Pipeline

> Must be built after Phase 1 (models) and Phase 2 (adapters). Tasks within Phase 3 are sequential.

### 3.1 Pipeline Core `⛓ SEQUENTIAL`

**3.1.1 — Build schema validator**
- **What:** Create `app/regulatory/ingestion/pipeline.py` with a `validate_record(record: dict, record_type: str) -> bool` function that checks:
  - All `(req)` fields from `data_models.md` are present and non-null
  - `source_system` is a known enum value
  - `jurisdiction_level` is a valid enum value
  - `status` is one of `in_progress`, `approved`, `blocked_suspended`
  - `content_hash` is a 64-char hex string (SHA-256)
  - Dates are valid ISO format
  Returns True if valid, raises `ValidationError` with details if not.
- **Read:** `data_models.md` → CodeSection and RegulatoryAction field tables (check which fields are `(req)`)
- **Depends on:** 1.2.1 (models)
- **Output:** `app/regulatory/ingestion/pipeline.py` (initial — will be extended in later tasks)
- **Verify:** Passes with a well-formed record. Raises on missing required fields, invalid enum values, bad hashes.

**3.1.2 — Build change detector**
- **What:** Add to `app/regulatory/ingestion/change_detector.py` a function `detect_changes(record: CodeSection_dict, db: Session) -> str` that:
  - Queries the DB for the most recent `CodeSection` with the same `(source_system, citation)`
  - If none exists → returns `"new"`
  - If exists and `content_hash` matches → returns `"unchanged"`
  - If exists and `content_hash` differs → returns `"changed"`
  - Also add `detect_action_duplicate(record: RegulatoryAction_dict, db: Session) -> bool` that checks if `(source_system, source_id)` already exists.
- **Read:** `change_detection.md` → "Codebook Sources — Poll-and-Diff" section, `stitching.md` → "Deduplication Rules" section
- **Depends on:** 1.2.1
- **Output:** `app/regulatory/ingestion/change_detector.py`
- **Verify:** Returns `"new"` for a section not in DB. Returns `"unchanged"` when hash matches. Returns `"changed"` when hash differs. Dedup returns True for existing action.

**3.1.3 — Build version chain builder**
- **What:** Add to `app/regulatory/ingestion/version_chain.py` a function `create_version_chain(new_record: CodeSection_dict, db: Session) -> CodeSection` that:
  - Finds the previous current version of this `(source_system, citation)`
  - Creates the new `CodeSection` DB row with `prior_version_id` pointing to the previous version's `id`
  - Returns the created record
  - Also add `store_regulatory_action(record: RegulatoryAction_dict, db: Session) -> RegulatoryAction` that simply inserts and returns (no version chain — actions are immutable).
- **Read:** `change_detection.md` → "Version Chain Model" section (both CodeSection and RegulatoryAction subsections)
- **Depends on:** 3.1.2
- **Output:** `app/regulatory/ingestion/version_chain.py`
- **Verify:** Creating two versions of the same citation links them via `prior_version_id`. The second record's `prior_version_id` equals the first record's `id`.

**3.1.4 — Build main ingestion orchestrator**
- **What:** Add to `app/regulatory/ingestion/pipeline.py` a function `run_ingestion(adapter: SourceAdapter, db: Session)` that:
  1. Gets sync cursor from DB
  2. Calls `adapter.poll(cursor)` to get raw records
  3. For each raw record: calls `adapter.normalize()` to get a typed dict
  4. Validates with `validate_record()`
  5. For CodeSection: calls `detect_changes()` → if "new" or "changed", calls `create_version_chain()`. If "unchanged", skips.
  6. For RegulatoryAction: calls `detect_action_duplicate()` → if not duplicate, calls `store_regulatory_action()`. If duplicate, skips.
  7. Updates sync cursor
  8. Returns a summary: `{"new": N, "changed": N, "unchanged": N, "skipped": N, "errors": N}`
- **Read:** `change_detection.md` → entire document (for the full flow), `architecture.md` → "Ingestion Pipeline" diagram
- **Depends on:** 3.1.1, 3.1.2, 3.1.3, and at least one adapter from Phase 2
- **Output:** Updated `app/regulatory/ingestion/pipeline.py`
- **Verify:** Running `run_ingestion(ecfr_adapter, db)` processes records and returns a summary with non-zero counts. Records appear in the DB. Running it again returns all "unchanged" (idempotent).

---

### 3.2 Stitching Engine `⛓ SEQUENTIAL after 3.1`

**3.2.1 — Build journal-to-codebook stitcher**
- **What:** Create `app/regulatory/ingestion/stitcher.py` with a function `stitch_action_to_codebook(action: RegulatoryAction, db: Session)` that:
  - For each entry in `action.cfr_references`:
    - Finds the current `CodeSection` with a matching `citation`
    - If the CodeSection's `amendment_source` is null and dates align (CodeSection's `effective_date` is within 30 days of action's `date_effective`), sets `amendment_source` to `action.source_id`
  - This links "why this regulation changed" (the FR document) to "what changed" (the CFR section).
- **Read:** `stitching.md` → "Journal → Codebook (Primary Link)" section and "After Ingesting a RegulatoryAction" pseudocode
- **Depends on:** 3.1.4
- **Output:** `app/regulatory/ingestion/stitcher.py`
- **Verify:** After ingesting both FR actions and eCFR sections, some CodeSection records have non-null `amendment_source` values that match real FR document numbers.

**3.2.2 — Build action chain stitcher**
- **What:** Add to `app/regulatory/ingestion/stitcher.py` a function `stitch_action_chains(action: RegulatoryAction, db: Session)` that:
  - If the action has a `rin`: finds all other RegulatoryActions with the same `rin`. Creates `ActionRelationship` records with inferred types (proposed_rule → final_rule = `supersedes`; final_rule → correction = `corrects`). See relationship inference table in `stitching.md`.
  - If the action has `docket_ids`: finds all other actions sharing any docket ID. Creates `related_to` relationships for any not already linked.
  - Also directly stores any `related_actions` data that came from the source adapter (e.g. PUCO DIS "Related Cases").
- **Read:** `stitching.md` → "Journal → Journal (Action Chains)" section and "Relationship Inference" table
- **Depends on:** 3.2.1
- **Output:** Updated `app/regulatory/ingestion/stitcher.py`
- **Verify:** After ingesting two quarters of FR data, some RegulatoryActions are linked via `ActionRelationship` records with correct types.

**3.2.3 — Integrate stitching into pipeline**
- **What:** Update `run_ingestion()` in `app/regulatory/ingestion/pipeline.py` to call stitching after storing records:
  - After storing a `RegulatoryAction`: call `stitch_action_to_codebook()` and `stitch_action_chains()`
  - After storing a changed `CodeSection`: call a reverse stitch `stitch_codebook_to_action()` that finds the FR action whose `cfr_references` includes this citation and whose dates align
  - Add a post-ingestion step that runs stitching on all unlinked records (handles the eCFR-lags-FR timing issue).
- **Read:** `stitching.md` → "After Ingesting a CodeSection Change" pseudocode, `change_detection.md` → "eCFR lags FR" timing section
- **Depends on:** 3.2.1, 3.2.2
- **Output:** Updated `app/regulatory/ingestion/pipeline.py`
- **Verify:** After running full ingestion for both eCFR and FR, check that amendment_source links exist and action relationships are populated.

---

## Phase 4: Seed Data Ingestion

> Must be done after Phase 3. Sequential — Phase 1 ingestion before Phase 2 ingestion.

### 4.1 Phase 1 Ingestion (Baseline) `⛓ SEQUENTIAL`

**4.1.1 — Run baseline eCFR ingestion**
- **What:** Create a script `scripts/seed_phase1.py` that:
  1. Instantiates the eCFR adapter with date `2025-01-02`
  2. Runs `run_ingestion(ecfr_adapter, db)`
  3. Logs the summary
- **Read:** `seed_data.md` → "Bucket 1: eCFR" section, "Phase 1: Before Baseline" in ingestion sequence
- **Depends on:** 3.1.4, 2.1.1
- **Output:** `scripts/seed_phase1.py`, ~160 CodeSection records in DB
- **Verify:** `SELECT COUNT(*) FROM code_sections WHERE source_system='cfr'` returns ~160. Spot-check a few: `18 CFR 35.28` should have heading, body_text, content_hash.

**4.1.2 — Run baseline Federal Register ingestion**
- **What:** Extend `scripts/seed_phase1.py` to:
  1. Instantiate FR adapter with date range 2025-01-01 to 2025-03-31
  2. Run `run_ingestion(fr_adapter, db)`
  3. Run stitching pass
  4. Log summary
- **Read:** `seed_data.md` → "Bucket 2: Federal Register" section
- **Depends on:** 4.1.1, 2.2.1, 3.2.3
- **Output:** ~50-100 RegulatoryAction records in DB. Some linked to CodeSections via `amendment_source`.
- **Verify:** `SELECT COUNT(*) FROM regulatory_actions WHERE source_system='federal_register'` returns >0. Some records have non-empty `cfr_references`. Check `ActionRelationship` table for any RIN-based links.

**4.1.3 — Run baseline OAC ingestion**
- **What:** Extend `scripts/seed_phase1.py` to run OAC adapter.
- **Read:** `seed_data.md` → "Bucket 3: Ohio Administrative Code" section
- **Depends on:** 2.3.1, 3.1.4
- **Output:** ~40-60 CodeSection records with `source_system='oac'`
- **Verify:** `SELECT COUNT(*) FROM code_sections WHERE source_system='oac'` returns ~40-60.

**4.1.4 — Run baseline PUCO DIS ingestion**
- **What:** Extend `scripts/seed_phase1.py` to run PUCO DIS adapter, then run stitching.
- **Read:** `seed_data.md` → "Bucket 4: PUCO DIS" section
- **Depends on:** 2.4.1, 3.2.3
- **Output:** ~10-20 RegulatoryAction records with `source_system='puco_dis'`
- **Verify:** `SELECT COUNT(*) FROM regulatory_actions WHERE source_system='puco_dis'` returns >0. Cases have correct `action_type` mapped from purpose codes.

---

### 4.2 Phase 2 Ingestion (Update) `⛓ SEQUENTIAL after 4.1`

**4.2.1 — Run update eCFR ingestion**
- **What:** Create `scripts/seed_phase2.py` that runs eCFR adapter with date `2025-07-01`.
  - This should detect changed sections (different `content_hash`) and create new version snapshots linked to Phase 1 versions via `prior_version_id`.
  - Unchanged sections should be skipped.
- **Read:** `seed_data.md` → "Phase 2: After Update" section, `change_detection.md` → "Version Chain Model"
- **Depends on:** 4.1.1
- **Output:** New CodeSection snapshots for changed sections. Version chains visible via `prior_version_id`.
- **Verify:** `SELECT citation, COUNT(*) FROM code_sections WHERE source_system='cfr' GROUP BY citation HAVING COUNT(*) > 1` returns rows — these are sections that changed between the two dates. Check `prior_version_id` is populated.

**4.2.2 — Run update Federal Register ingestion**
- **What:** Extend `scripts/seed_phase2.py` to run FR adapter with date range 2025-04-01 to 2025-06-30. Run stitching to create action chains (Q1 proposed → Q2 final).
- **Depends on:** 4.1.2
- **Output:** New RegulatoryAction records. Action chains linking Q1 and Q2 documents.
- **Verify:** `ActionRelationship` table has entries linking proposed rules to final rules.

**4.2.3 — Run update OAC and PUCO DIS ingestion**
- **What:** Extend `scripts/seed_phase2.py` to re-run OAC and PUCO adapters. For OAC: detects any rule text changes. For PUCO: finds new filings and status changes.
- **Depends on:** 4.1.3, 4.1.4
- **Output:** Any OAC changes create version chains. PUCO cases may show status changes.
- **Verify:** Check for PUCO cases that were OPEN in Phase 1 and now CLOSED.

---

## Phase 5: API Layer

> Can begin once Phase 1 models exist (1.2). API development can proceed in parallel with Phase 4 (seed data). Endpoints are independent of each other.

### 5.1 API Endpoints `⚡ PARALLEL`

**5.1.1 — Build regulation listing and search endpoint**
- **What:** Create `app/api/regulatory/regulations.py` with:
  - `GET /regulations` — lists current CodeSections (latest snapshot per citation). Query params: `source_system`, `agency`, `jurisdiction_level`, `status`, `search` (text search on heading/citation), `page`, `limit`.
  - `GET /regulations/{source_system}/{citation}` — returns one CodeSection's current version with full body text.
  - Returns JSON matching CodeSection schema.
- **Read:** `data_models.md` → CodeSection schema
- **Depends on:** 1.2.1 (models)
- **Output:** `app/api/regulatory/regulations.py`, registered in `app/main.py`
- **Verify:** `GET /regulations?source_system=cfr&agency=ferc` returns CodeSection records (after seed data exists).

**5.1.2 — Build regulatory action listing and search endpoint**
- **What:** Create `app/api/regulatory/actions.py` with:
  - `GET /actions` — lists RegulatoryActions. Query params: `source_system`, `agency`, `status`, `action_type`, `date_from`, `date_to`, `search`, `page`, `limit`.
  - `GET /actions/{source_system}/{source_id}` — returns one RegulatoryAction with all metadata + related actions.
  - Returns JSON matching RegulatoryAction schema.
- **Read:** `data_models.md` → RegulatoryAction schema
- **Depends on:** 1.2.1
- **Output:** `app/api/regulatory/actions.py`, registered in `app/main.py`
- **Verify:** `GET /actions?source_system=federal_register&agency=ferc&status=approved` returns results.

**5.1.3 — Build version diff endpoint**
- **What:** Create `app/api/regulatory/diff.py` with:
  - `GET /diff/{source_system}/{citation}` — returns the version history of a CodeSection: all snapshots ordered by `snapshot_date`, with a text diff between consecutive versions. Use Python `difflib.unified_diff` for the diff. Response: `{ citation, versions: [{ snapshot_date, effective_date, content_hash, amendment_source, diff_from_previous: string | null }] }`.
  - `GET /diff/{source_system}/{citation}/compare?date_a=YYYY-MM-DD&date_b=YYYY-MM-DD` — returns diff between two specific snapshots.
- **Read:** `change_detection.md` → "Version Chain Model" → "For CodeSection"
- **Depends on:** 1.2.1
- **Output:** `app/api/regulatory/diff.py`, registered in `app/main.py`
- **Verify:** `GET /diff/cfr/18%20CFR%2035.28` returns version history with diffs (after Phase 4.2 seed data).

**5.1.4 — Build timeline endpoint**
- **What:** Create `app/api/regulatory/timeline.py` with:
  - `GET /timeline/{source_system}/{citation}` — returns chronological list of all events affecting a citation: CodeSection version changes + linked RegulatoryActions that reference this citation. Merged into one timeline sorted by date.
  - `GET /timeline/deadlines` — returns upcoming dates (effective dates, comment close dates) across all actions, sorted by date. Query params: `days_ahead` (default 90), `agency`, `status`.
- **Read:** `data_models.md` → both schemas (to join data), `prd.md` → "In Scope" (deadlines are in scope)
- **Depends on:** 1.2.1
- **Output:** `app/api/regulatory/timeline.py`, registered in `app/main.py`
- **Verify:** Timeline for a regulation shows both version changes and the FR actions that caused them.

**5.1.5 — Build impact and cross-agency endpoint**
- **What:** Create `app/api/regulatory/impact.py` with:
  - `GET /impact/{entity}` — returns all RegulatoryActions and CodeSection changes affecting a named entity (company name), across all agencies and jurisdictions. Query params: `date_from`, `date_to`.
  - `GET /impact/agency/{agency_id}` — returns all recent actions from one agency.
  - `GET /impact/cross-agency` — returns pairs of actions from different agencies that share CFR references, affected entities, or temporal proximity. This is the multi-agency correlation feature.
- **Read:** `prd.md` → "Core Goal", `stitching.md` → "Cross-Jurisdiction Linking"
- **Depends on:** 1.2.1
- **Output:** `app/api/regulatory/impact.py`, registered in `app/main.py`
- **Verify:** `GET /impact/cross-agency?date_from=2025-01-01&date_to=2025-06-30` returns results linking federal and state actions.

**5.1.6 — Build semantic search endpoint**
- **What:** Create `app/api/regulatory/search.py` with:
  - `GET /search?q=emissions+monitoring+power+plants` — embeds the query using `all-MiniLM-L6-v2`, searches Qdrant `regulation_chunks` collection, returns top-K results with citation, heading, snippet, relevance score.
  - Also create `app/regulatory/ingestion/embedder.py` with a function `embed_and_store(record: CodeSection | RegulatoryAction, db, qdrant_client)` that chunks text, embeds chunks, and upserts to Qdrant. This should be called during ingestion (add to pipeline).
- **Shared cluster note:** All upserts must include `project: settings.QDRANT_PROJECT_TAG` in payload. All searches must apply `project = settings.QDRANT_PROJECT_TAG` as the first `must` filter before any user-supplied filters. See `infrastructure.md` → "Shared Cluster — Project Isolation".
- **Read:** `infrastructure.md` → "Vector Database" section (chunking strategy, payload fields, shared cluster isolation)
- **Depends on:** 1.3.1 (Qdrant setup), 1.2.1
- **Output:** `app/api/regulatory/search.py`, `app/regulatory/ingestion/embedder.py`, registered in `app/main.py`
- **Verify:** After embedding seed data, `GET /search?q=electric+rate+tariff` returns relevant CFR sections. Verify no FDAComplianceAI vectors appear in results.

**5.1.7 — Build ingestion trigger endpoint**
- **What:** Create `app/api/regulatory/jobs.py` with:
  - `POST /jobs/ingest` — triggers a full ingestion run across all adapters. Runs sequentially: eCFR → FR → OAC → PUCO DIS → stitching. Returns summary of what was ingested. This is the endpoint Render Cron Job will hit for scheduled syncs.
  - `POST /jobs/ingest/{source_system}` — triggers ingestion for one specific source only.
- **Read:** `architecture.md` → "Ingestion Pipeline" diagram, `infrastructure.md` → "Handling Auto-Sleep" section
- **Depends on:** 3.1.4, all adapters
- **Output:** `app/api/regulatory/jobs.py`, registered in `app/main.py`
- **Verify:** `POST /jobs/ingest` runs and returns `{"ecfr": {...}, "federal_register": {...}, ...}` summary.

---

## Phase 6: Deployment & Integration Testing

> Final phase. All prior phases must be substantially complete.

### 6.1 Deploy `⛓ SEQUENTIAL`

**6.1.1 — Deploy backend to Render**
- **What:** Create `render.yaml` in `backend/`. Push to GitHub. Create Render web service linked to the repo. Set all environment variables. Verify deployment and health check.
- **Read:** `infrastructure.md` → "Backend (Render)" section, "Deployment Sequence" section
- **Depends on:** All Phase 5 tasks, Phase 4 seed data
- **Output:** Live backend at `https://strata-backend.onrender.com`
- **Verify:** `GET /health` returns 200. `GET /regulations` returns data.

**6.1.2 — Set up scheduled ingestion**
- **What:** Create a Render Cron Job that hits `POST /jobs/ingest` on the backend daily. This is the production sync that keeps data current.
- **Read:** `infrastructure.md` → "Handling Auto-Sleep", "Cron Scheduler" rows
- **Depends on:** 6.1.1
- **Output:** Render Cron Job configured
- **Verify:** Cron triggers, backend wakes, ingestion runs, new data appears if sources have updates.

---

### 6.2 Integration Tests `⚡ PARALLEL`

**6.2.1 — End-to-end ingestion test**
- **What:** Verify the full ingestion pipeline: trigger ingestion → adapters pull data → pipeline validates and stores → stitching links records → vectors are embedded. Check all tables have expected record counts matching `seed_data.md` volume estimates.
- **Depends on:** 6.1.1, Phase 4 seed data
- **Verify:** DB record counts match estimates. Version chains exist. Relationships exist. Qdrant has vectors.

**6.2.2 — End-to-end API test**
- **What:** Verify all API endpoints return correct data: regulation listing, action listing, diff, timeline, impact, search, deadlines. Check that cross-references work (a regulation's detail page links to the FR action that amended it).
- **Depends on:** 6.1.1
- **Verify:** Each endpoint returns 200 with expected data shape. Cross-references resolve correctly.

---

## Dependency Graph Summary

```
Phase 1: Foundation
  1.1.1 → 1.1.2 → 1.2.1 → 1.2.2 → 1.2.3
                           └→ 1.3.1 (parallel with 1.2.2)

Phase 2: Adapters (all parallel, need 2.0.1 first)
  2.0.1 → 2.1.1 ⚡ 2.2.1 ⚡ 2.3.1 ⚡ 2.4.1

Phase 3: Pipeline (sequential, needs Phase 1 + 2)
  3.1.1 → 3.1.2 → 3.1.3 → 3.1.4 → 3.2.1 → 3.2.2 → 3.2.3

Phase 4: Seed Data (sequential, needs Phase 3)
  4.1.1 → 4.1.2 → 4.1.3 → 4.1.4 → 4.2.1 → 4.2.2 → 4.2.3

Phase 5: API (parallel endpoints, needs Phase 1 models)
  5.1.1 ⚡ 5.1.2 ⚡ 5.1.3 ⚡ 5.1.4 ⚡ 5.1.5 ⚡ 5.1.6 ⚡ 5.1.7

Phase 6: Deploy + Test (needs Phase 5 + Phase 4)
  6.1.1 → 6.1.2
  6.2.1 ⚡ 6.2.2
```

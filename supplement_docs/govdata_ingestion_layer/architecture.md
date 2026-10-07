# Strata Regulatory Intelligence — Architecture

## Pipeline Overview

```mermaid
flowchart TD
    FR["federalregister.gov\nAPI v1"]
    ECFR["ecfr.gov\nXML API"]
    IAC["iar.iga.in.gov\nCloudFront API"]
    IURC_R["in.gov/iurc/rulemakings"]
    IURC_G["in.gov/iurc/general-administrative-orders"]
    IURC_I["in.gov/iurc/docketed-cases\n(weekly PDFs)"]
    IDEM["in.gov/idem/legal/rulemaking"]

    subgraph Adapters["Adapters (poll → normalize)"]
        A1[FederalRegisterAdapter]
        A2[ECFRAdapter]
        A3[IACAdapter]
        A4[IURCRulemakerAdapter]
        A5[IURCGAOAdapter]
        A6[IURCInvestigationsAdapter]
        A7[IDEMRulemakerAdapter]
    end

    FR --> A1
    ECFR --> A2
    IAC --> A3
    IURC_R --> A4
    IURC_G --> A5
    IURC_I --> A6
    IDEM --> A7

    subgraph Pipeline["pipeline.py — run_ingestion()"]
        V[validate_record]
        CD[detect_changes\ndetect_action_duplicate]
        VC[version_chain.py\ncreate_version_chain /\nstore_regulatory_action]
        ST[stitcher.py\nstitch_action_to_codebook\nstitch_codebook_to_action\nstitch_action_chains]
        EM[embedder.py\nchunk → embed → upsert]
        UC[update_sync_cursor]
    end

    Adapters -->|normalized dict| V
    V --> CD
    CD -->|new / changed| VC
    VC --> ST
    ST --> EM
    EM --> UC

    VC -->|upsert| PG[(PostgreSQL)]
    EM -->|384-dim vectors| QD[(Qdrant)]
    Adapters -->|raw HTML / PDF| R2[(Cloudflare R2)]
```

> **Trigger:** HTTP POST to `/jobs/ingest` (all sources) or `/jobs/ingest/{source_system}` (one source). Each adapter is health-checked before running; failures are skipped and logged.

---

## Data Sources

| Source Key | Agency | Type | URL | Adapter |
|---|---|---|---|---|
| `federal_register` | FERC, EPA | Rulemakings & Proposed Rules (JSON API) | `federalregister.gov/api/v1` | `FederalRegisterAdapter` |
| `ecfr` | FERC (Title 18), EPA (Title 40) | Codified CFR text (XML) | `ecfr.gov` | `ECFRAdapter` |
| `iac` | IURC (170), IDEM (326/327), Labor (610/675) | Indiana Admin Code (HTML/API) | `iar.iga.in.gov` | `IACAdapter` |
| `iurc_rulemakings` | IURC | Pending & effective rulemakings (HTML/PDF) | `in.gov/iurc/rulemakings/` | `IURCRulemakerAdapter` |
| `iurc_gaos` | IURC | General Administrative Orders (HTML/PDF) | `in.gov/iurc/general-administrative-orders/` | `IURCGAOAdapter` |
| `iurc_investigations` | IURC | Docket investigations (weekly PDF filings) | `in.gov/iurc/docketed-cases/` | `IURCInvestigationsAdapter` |
| `idem_rulemakings` | IDEM | Environmental Rules Board packets (HTML/PDF) | `in.gov/idem/legal/rulemaking/` | `IDEMRulemakerAdapter` |

---

## Storage Layers

```mermaid
flowchart LR
    subgraph PostgreSQL
        CS[code_sections\ncitation · body_text · content_hash\nprior_version_id · amendment_source\nsnapshot_date · status]
        RA[regulatory_actions\nsource_id · title · abstract\nagency · action_type · status\ncfr_references · rin · docket_ids]
        AR[action_relationships\nfrom_action_id ↔ to_action_id\nrelationship_type]
        SS[sync_state\nsource_system → cursor JSON]
    end

    subgraph Qdrant
        RC["regulation_chunks\n384-dim · all-MiniLM-L6-v2\npayload: record_type · db_id\ncitation · chunk_text · agency\nstatus · jurisdiction_level"]
    end

    subgraph R2["Cloudflare R2"]
        RAW["raw-sources/{source}/{key}\nraw HTML / XML / PDF\nfor every scraped page"]
    end
```

| Store | What it holds | Why |
|---|---|---|
| **PostgreSQL `code_sections`** | Versioned snapshots of CFR / IAC text sections | Structured queries, version history, stitching lookups |
| **PostgreSQL `regulatory_actions`** | Federal Register rules, IURC/IDEM orders/investigations | Immutable action records, relationship graph |
| **PostgreSQL `action_relationships`** | Links between related actions (same RIN, docket chain) | Navigate rulemaking chains |
| **PostgreSQL `sync_state`** | Per-source cursor (last publication date, amendment date, etc.) | Incremental polling — only fetch what changed |
| **Qdrant `regulation_chunks`** | 384-dim vectors of chunked section/action text | Semantic search across all regulatory content |
| **Cloudflare R2** | Raw bytes of every fetched HTML/XML/PDF | Audit trail, re-parsing without re-scraping |

---

## Adapter Contract

Every adapter extends `SourceAdapter` and must implement:

```python
class SourceAdapter(ABC):
    source_system: str

    async def get_sync_cursor(self, db) -> dict:
        """Load last-pulled state from sync_state table."""

    async def poll(self, cursor: dict) -> list[dict]:
        """Fetch raw records from source since cursor. Returns raw dicts."""

    def normalize(self, raw: dict) -> dict | None:
        """Map raw record → CodeSection or RegulatoryAction dict. None = skip."""

    async def update_sync_cursor(self, db, new_cursor: dict) -> None:
        """Persist new cursor to sync_state after successful batch."""

    async def health_check(self) -> bool:
        """Return False to skip this source this run (default: True)."""
```

---

## Ingestion Trigger

```mermaid
sequenceDiagram
    participant C as Caller
    participant J as jobs.py
    participant A as Adapter
    participant P as pipeline.py

    C->>J: POST /jobs/ingest[/{source}]
    J->>A: health_check()
    alt healthy
        J->>P: run_ingestion(adapter, db)
        P->>A: get_sync_cursor()
        P->>A: poll(cursor)
        loop each raw record
            P->>A: normalize(raw)
            P->>P: validate_record()
            P->>P: detect_changes / detect_action_duplicate
            P->>P: create_version_chain / store_regulatory_action
            P->>P: stitch (codebook ↔ action ↔ chains)
            P->>P: embed_and_store (Qdrant)
        end
        P->>P: _retroactive_stitch() — fix timing gaps
        P->>A: update_sync_cursor()
        J-->>C: {status, new, changed, unchanged, skipped, errors}
    else unhealthy
        J-->>C: {status: skipped}
    end
```

---

## Versioning & Change Detection

Code sections (`cfr`, `iac`) are **versioned by snapshot**, not mutated in place.

```mermaid
flowchart TD
    A[Poll source] --> B[normalize section]
    B --> C[SHA-256 of heading + body_text]
    C --> D{Lookup most recent DB row\nfor source_system + citation}
    D -- No row found --> E[NEW\nInsert, prior_version_id = NULL]
    D -- Hash matches --> F[UNCHANGED\nSkip — no insert]
    D -- Hash differs --> G[CHANGED\nInsert new row\nprior_version_id → old row id]
```

Implementation: `app/regulatory/ingestion/change_detector.py → detect_changes()`

**Version chain** — singly-linked list, newest at head:

```
Phase 1 (2024-12-31)                     Phase 2 (2025-12-31)
┌─────────────────────────────┐          ┌─────────────────────────────┐
│ id=100  "170 IAC 4-1-6"     │ ◄─────── │ id=200  "170 IAC 4-1-6"     │
│ prior_version_id = NULL      │          │ prior_version_id = 100       │
│ content_hash = abc123        │          │ content_hash = def456        │
└─────────────────────────────┘          └─────────────────────────────┘
        (historical)                              (current)
```

| Change Type | Result |
|---|---|
| Body text changed | New row, `prior_version_id` linked |
| Heading changed | New row (heading included in hash) |
| Status → repealed | New row, `status='repealed'` |
| No change | Skipped — UNCHANGED |

**Current snapshots:** Phase 1 = 2024-12-31, Phase 2 = 2025-12-31 (~4,600 sections each)

---

## Diff API

Diffs are computed on-demand from the version chain. Base prefix: `/diff`  
Implementation: `app/api/regulatory/diff.py`

| Endpoint | Description |
|---|---|
| `GET /diff/{source}/{citation}/compare?date_a=…&date_b=…` | Unified diff between two snapshot dates |
| `GET /diff/{source}/{citation}` | Full version history with `diff_from_previous` per version |

Diff format: `+` = added in newer snapshot, `-` = removed. Empty string = no text change.

---

## eCFR vs IAC Change Detection

| Source | Signal | Behaviour |
|---|---|---|
| **eCFR** (federal) | `GET /api/versioner/v1/titles` → `latest_amended_on` | Skip title entirely if date hasn't advanced — no section-level requests |
| **IAC** (Indiana) | None | Every sync scrapes all sections, hashes, and compares — no shortcut |

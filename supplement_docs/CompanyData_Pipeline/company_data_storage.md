# Company Data Storage — Neon · Qdrant · R2

**Entity:** Rockridge Power & Light (RPL) · `company_id = rpl`  
**Source:** 12 processed corpus documents → 2,334 clauses across 3 stores  
**Companion doc:** `../comdata_generation/` covers how the 12 documents were authored; this doc covers what was extracted and how it's stored.

---

## What Gets Stored (and Why Not Raw Docs)

The application never queries raw `.md` files. The pipeline decomposes each document into typed, indexed, cross-linked **clause units** — the atomic unit of meaning — so that an AI agent or query layer can:

- Retrieve the exact clause(s) relevant to a question (Qdrant semantic/hybrid search)
- Traverse relationships: "what does this clause cite / restate / reference?" (Neon graph)
- Filter by role, assessability, doc type, parameter kind (Neon + Qdrant payload filters)
- Pull the full structured extract for a document in one read (R2 JSONL snapshot)

---

## Live Metrics (as of ingest run)

| Store | Key Entity | Count |
|-------|-----------|-------|
| Neon | Companies | 1 |
| Neon | People | 27 |
| Neon | Documents | 12 |
| Neon | Clauses | **2,334** |
| Neon | Citations | 1,249 |
| Neon | Parameters | 2,948 |
| Neon | Defined terms | 67 |
| Neon | Term usages | 693 |
| Neon | Clause links | **4,675** |
| Neon | Document scope rows | 285 |
| Qdrant | Vectors (dense + BM25) | 2,334 points |
| R2 | Raw files + derived snapshots | 12 docs |

---

## Store 1 — Neon PostgreSQL (`company.*` schema)

18 tables in one schema. Split into three logical groups.

### Group A — Entity Registry (who + what exists)

| Table | Key Columns | Purpose |
|-------|-------------|---------|
| `companies` | `company_id`, `legal_name`, `jurisdiction` | Top-level entity; all rows carry `company_id = rpl` |
| `company_attributes` | `company_id`, `key`, `value` | 22 KV facts (territory, financials, IURC ID, etc.) |
| `people` | `person_id`, `name`, `title`, `dept`, `email` | 27 employees P01–P27 used as doc owners/reviewers |
| `company_documents` | `doc_id`, `title`, `doc_class`, `owner_id`, `status` | 12 registered documents with class and owner |
| `document_versions` | `version_id UUID`, `doc_id`, `version`, `effective_date` | One version per doc currently; `version_id` is a UUIDv5 of `(company_id, doc_id, version)` |

### Group B — Clause Graph (the core)

**`company.clauses`** — every extractable unit of meaning

| Column | Type | Notes |
|--------|------|-------|
| `clause_pk` | UUID | UUIDv5 of `(company_id, doc_id, clause_id)` |
| `clause_id` | text | `DOC_ID:local_id` e.g. `RPL-CS-PRO-004:3.2.1` |
| `clause_role` | text | `internal_procedure`, `regulatory_restatement`, `definition`, `template_field`, `boilerplate` |
| `unit_kind` | text | `section`, `table_row`, `register_row`, `form_field`, `tariff_subrule`, `appendix`, `other` |
| `text_raw` / `text_norm` | text | Original text and normalised version |
| `assessable` | bool | Whether this clause can be evaluated for compliance |
| `char_start/end`, `line_start` | int | Position in the source document |
| `heading_path`, `section_kind`, `table_id` | text | Structural provenance |
| `normalized_statement`, `topic_terms` | text / text[] | LLM-enriched fields |

**Role distribution:**

| Role | Count |
|------|-------|
| `internal_procedure` | 1,233 |
| `regulatory_restatement` | 640 |
| `definition` | 221 |
| `template_field` | 204 |
| `boilerplate` | 36 |

**Unit kind distribution:**

| Kind | Count |
|------|-------|
| `section` | 1,019 |
| `table_row` | 758 |
| `register_row` | 204 |
| `form_field` | 204 |
| `tariff_subrule` | 127 |
| `appendix` | 21 |

**Clauses per document:**

| Doc ID | Clauses |
|--------|---------|
| RPL-DO-PLN-002 (Distribution Plan) | 331 |
| RPL-DCC-PRO-003 (Disconnection) | 277 |
| RPL-SAF-PRO-009 (Safety) | 248 |
| RPL-CS-PRO-004 (Customer Service) | 237 |
| RPL-ENV-PRO-005 (Environmental) | 228 |
| RPL-CS-PRO-011 (Complaint) | 174 |
| RPL-LEG-RRS-001 (Compliance Register) | 173 |
| RPL-CS-PRO-007 (Meter Testing) | 144 |
| RPL-MTR-PGM-001 (Meter Program) | 147 |
| RPL-TAR-GRR-012 (Tariff) | 136 |
| RPL-CMP-REG-001 (Regulatory Calendar) | 155 |
| RPL-REG-CAL-2025 (Cal 2025) | 84 |

---

**`company.clause_citations`** — regulatory citations extracted from clause text

| Column | Notes |
|--------|-------|
| `clause_pk` → `clauses.clause_pk` | FK to owning clause |
| `citation_raw` | Verbatim citation string from text |
| `source_system`, `title`, `article`, `rule`, `section` | Parsed fields |
| `granularity` | `article / rule / section / subsection` |
| `resolution_status` | `external` (91) or `not_found` (1,158) |
| `in_knowledge_base` | bool — whether the cited regulation is in Neon's `code_sections` |
| `code_section_id` | FK to gov regulatory DB when resolved |

---

**`company.clause_parameters`** — quantitative values extracted from clauses (2,948 total)

| Column | Notes |
|--------|-------|
| `clause_pk` | FK to clause |
| `kind` | `number` (1,608) · `period` (564) · `deadline` (286) · `frequency` (196) · `amount` (196) · `threshold` (85) · `record_retention` (13) |
| `name`, `value_text`, `value_num`, `unit` | The extracted value |
| `qualifier`, `day_type` | e.g. "at least", "business days" |
| `supported_by_citation_pk` | Links a parameter back to its governing citation |
| `value_source`, `method`, `verified` | Audit fields |

---

**`company.defined_terms`** + **`company.term_usages`** — glossary graph

- 67 defined terms extracted from `definitions` sections
- 693 usage links — which clauses use each term

---

**`company.clause_links`** — cross-clause relationship graph (4,675 edges)

| Link type | Count | Meaning |
|-----------|-------|---------|
| `restates` | 3,048 | This clause restates content from another clause |
| `references_clause` | 445 | Explicit "see clause X" reference |
| `references_record_series` | 320 | Points to a record series doc |
| `references_doc` | 295 | Points to another document |
| `references_tariff` | 217 | Points to a tariff schedule |
| `references_form` | 207 | Points to a form |
| `references_obligation` | 143 | Points to a regulatory obligation |

Columns: `from_clause_pk`, `to_clause_pk`, `to_doc_id`, `link_type`, `method`, `confidence`

---

**`company.document_scope`** — per-document regulatory coverage rollup (285 rows)

Maps each document to the regulation sections it covers. Scope levels: `section` (248) · `rule` (37). Links `doc_id` → `code_section_id` in the gov regulatory DB.

---

### Group C — Run Tracking

| Table | Purpose |
|-------|---------|
| `table_columns` | Column-role metadata for P2 register CSVs (26 rows) |
| `datasets` / `dataset_columns` | Profiled P3 operational datasets |
| `parameter_checks` | Proposed compliance checks against dataset parameters |
| `llm_extractions` | Raw LLM call inputs/outputs for auditability |
| `ingest_runs` | Run log: `run_id`, `started_at`, `finished_at`, `flags`, `status`, `report_r2_key` (2 runs) |

---

### Primary Key Pattern

All PKs are **UUIDv5** (deterministic, reproducible):
- `version_id = UUIDv5(company_id, doc_id, version)`
- `clause_pk = UUIDv5(company_id, doc_id, clause_id)`

Re-ingesting the same doc produces the same PKs → safe `ON CONFLICT DO UPDATE` upserts.

---

## Store 2 — Qdrant (`company_clauses` collection)

Hybrid vector search over all 2,334 clauses.

**Vectors per point:**
- `dense` — 384-dim, Cosine similarity (`all-MiniLM-L6-v2` embeddings of `text_norm`)
- `bm25` — sparse, IDF-weighted for keyword recall

**Payload (filterable fields):**

| Field | Type | Use |
|-------|------|-----|
| `company_id` | keyword | Always filter: `company_id = rpl` |
| `doc_id` | keyword | Restrict to a document |
| `clause_id` | keyword | Retrieve a specific clause |
| `clause_role` | keyword | Filter by role (e.g. only `regulatory_restatement`) |
| `unit_kind` | keyword | Filter by structure type |
| `section_kind` | keyword | Filter by section type |
| `cited_sections` | keyword[] | IAC sections cited by this clause |
| `cited_rules` | keyword[] | IAC rules cited |
| `param_kinds` | keyword[] | Parameter kinds present |
| `param_units` | keyword[] | Unit types (days, kV, MW…) |
| `terms_used` | keyword[] | Defined terms used |
| `doc_class` | keyword | Document class |
| `owner_id` | keyword | Document owner (person ID) |
| `project` | keyword | Always filter: `project = strata` (cluster isolation) |
| `assessable` | bool | Only fetch assessable clauses |
| `is_current` | bool | Version currency flag |

**Point ID** = `clause_pk` (UUID) — same as Neon, enabling direct join by ID.

**Typical query pattern:**
```python
client.search(
    collection_name="company_clauses",
    query_vector=("dense", embed(query)),
    query_filter=Filter(must=[
        FieldCondition(key="project", match=MatchValue(value="strata")),
        FieldCondition(key="company_id", match=MatchValue(value="rpl")),
        FieldCondition(key="assessable", match=MatchValue(value=True)),
    ]),
    limit=10
)
```

---

## Store 3 — Cloudflare R2 (object storage)

Key layout under `company/rpl/`:

| Path pattern | Contents |
|-------------|---------|
| `raw/{doc_id}/{version}/{filename}.md` | Original source document |
| `raw/{doc_id}/{version}/data/{name}.csv` | Source CSV datasets |
| `derived/{doc_id}/{version}/clauses.jsonl` | Full clause extract (one JSON per line) |
| `derived/{doc_id}/{version}/datasets/{name}.parquet` | Profiled datasets as Parquet |
| `derived/global/ops/{name}.parquet` | Global operational CSVs as Parquet |
| `ingest_runs/{run_id}/report.json` | Full run report with check outcomes |
| `ingest_runs/{run_id}/llm/{stage}/{unit_id}.json` | LLM call audit trail |

`clauses.jsonl` is the **bulk read path** — fetch one file to get all clauses for a document without N Neon queries. Each line is a serialised `ClauseUnit` with all enrichment fields included.

R2 uses **write-once semantics** with content-addressed SHA-256 verification. Use `--rebuild` flag on re-ingest to force overwrite.

---

## How the Three Stores Connect

```
Corpus document (.md / .csv)
        │
        ▼ ingest pipeline
┌──────────────────┐       ┌──────────────────────┐
│  Neon clauses    │──pk──▶│  Qdrant point        │
│  (structured     │       │  (same clause_pk UUID)│
│   graph + params)│       │  vectors + payload   │
└──────────────────┘       └──────────────────────┘
        │
        ▼ per-doc snapshot
┌──────────────────┐
│  R2 clauses.jsonl│
│  (bulk read,     │
│   full payload)  │
└──────────────────┘
```

- **Qdrant `point_id` = Neon `clause_pk`** — retrieve by vector search, then JOIN to Neon for citations/parameters/links
- **R2 snapshot** mirrors Neon clause data at ingest time — use for bulk document processing without DB queries

---

## Building Applications on This Data

| Use case | Primary store | Pattern |
|----------|--------------|---------|
| "Find clauses about disconnection notice periods" | Qdrant | Semantic search → filter `assessable=true` |
| "What parameters does clause X define?" | Neon `clause_parameters` | `WHERE clause_pk = ?` |
| "What regulations does this document reference?" | Neon `document_scope` + `clause_citations` | Join on `doc_id` |
| "Traverse: what does clause A restate?" | Neon `clause_links` | `WHERE from_clause_pk = ? AND link_type = 'restates'` |
| "Give me all clauses of a document in one read" | R2 `derived/{doc_id}/v1/clauses.jsonl` | Stream JSONL |
| "Which people own documents touching IAC 170 IAC 4?" | Neon `document_scope` → `company_documents` → `people` | 3-table join |
| "Find all numeric thresholds across the corpus" | Neon `clause_parameters` | `WHERE kind = 'threshold'` |

---

## Acceptance Quality Gates (passed on ingest)

| Check | Threshold | Result |
|-------|-----------|--------|
| Unclaimed text | ≤ 5% | **3.0%** ✅ |
| Duplicate clause IDs | 0 | **0** ✅ |
| Text coverage per doc | ≥ 95% | ✅ all 12 |
| Regulatory restatements with citations | 100% | ✅ (86 fixed) |
| Total checks | 12 | **12/12 passed** ✅ |

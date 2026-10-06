# Strata — Data Sources & Adapters

## Overview

Each data source is isolated behind a pluggable adapter. This document specifies the V1 sources, their APIs, access patterns, field mappings, and known limitations.

---

## Source 1: eCFR (Bucket 1 — Federal Codified Regulations)

**Purpose:** Ingest the current text of all relevant CFR sections. Produces `CodeSection` records.

**API Base:** `https://www.ecfr.gov/api/`
**Auth:** None required. Fully public, keyless.
**Rate Limits:** Not published; be respectful (~1 req/sec).
**Data Format:** XML (content endpoints), JSON (metadata endpoints)

### Key Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/versioner/v1/titles` | List all 50 CFR titles with `latest_amended_on`, `latest_issue_date`, `up_to_date_as_of` |
| `GET /api/versioner/v1/versions/title-{n}` | Amendment history per section within a title. Shows dates, substantive vs editorial flag. |
| `GET /api/versioner/v1/full/{date}/title-{n}.xml` | Full title text as of a specific date. Returns XML. |
| `GET /api/versioner/v1/structure/title-{n}` | Hierarchical table of contents — parts, subparts, sections with headings. |
| `GET /api/search/v1/results` | Full-text search with `date=current` to get current versions only. |

### Polling Strategy

1. **Daily:** Check `/api/versioner/v1/titles` — compare `latest_amended_on` for our tracked titles (18 for FERC, 40 for EPA) against stored value.
2. **If changed:** Call `/api/versioner/v1/versions/title-{n}` to find which sections were amended since our last sync.
3. **For each changed section:** Pull current text, compute SHA-256 hash, compare against stored `content_hash`.
4. **If hash differs:** Create new `CodeSection` snapshot linked to prior version via `prior_version_id`.

### V1 Scope Filter (Minimized)

- **Title 18:** Part 35 (rate schedules/tariffs, ~50 sections), Part 37 (OASIS, ~15 sections), Part 38 (business standards, ~15 sections). Total: ~80 sections.
- **Title 40:** Part 60 subparts Da, KKKK, TTTTa, UUUUb only (emission standards for power plants, ~30 sections). Part 63 subparts UUUUU, YYYY only (MATS + combustion turbine HAPs, ~20 sections). Part 72 (acid rain permits, ~15 sections). Part 73 (SO2 allowances, ~15 sections). Total: ~80 sections.
- **Skipping:** All other Title 18 parts (accounting, forms, procedures, non-FERC agencies). All Title 40 parts outside air programs for power plants (mobile sources, water, waste, general ambient standards).

### Known Limitations

- eCFR lags the Federal Register by 1-2 business days. A final rule published in FR on Monday may not appear in eCFR until Wednesday.
- Using today's date on versioner endpoints causes 404 errors. Auto-resolve to latest available date.
- The full-title XML endpoint returns the entire title even with subset parameters. For large titles (Title 40), expect large responses.
- Without `date=current`, search returns ALL historical versions including superseded.

### Field Mapping → CodeSection

| eCFR Field | → CodeSection Field |
|---|---|
| Title + Part + Section number | `citation` (e.g. `18 CFR 35.28`) |
| — | `source_system` = `cfr` |
| — | `jurisdiction_level` = `federal` |
| Section heading | `heading` |
| Section XML body (stripped to text) | `body_text` |
| SHA-256 of body_text | `content_hash` |
| Agency from title/chapter mapping | `owning_agency` |
| Amendment date from versions endpoint | `effective_date` |
| Pull timestamp | `snapshot_date` |
| `https://www.ecfr.gov/current/title-{t}/part-{p}/section-{p}.{s}` | `source_url` |
| FR citation from versions endpoint | `amendment_source` |

---

## Source 2: Federal Register API (Bucket 2 — Federal Agency Actions)

**Purpose:** Ingest published rules, proposed rules, notices, and presidential documents. Produces `RegulatoryAction` records.

**API Base:** `https://www.federalregister.gov/api/v1/`
**Auth:** None required. Fully public, keyless.
**Rate Limits:** Not published; pagination capped at 2000 results per query (page × per_page).
**Data Format:** JSON
**Cadence:** New documents daily on business days, available at 8:45 AM ET.

### Key Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /documents.json` | Search/list documents with filters |
| `GET /documents/{document_number}.json` | Single document with full metadata |
| `GET /agencies.json` | List all agencies with slugs |

### Query Parameters for Incremental Sync

```
conditions[publication_date][gte]=YYYY-MM-DD   # Since our last sync date
conditions[agencies][]=federal-energy-regulatory-commission
conditions[agencies][]=environmental-protection-agency
conditions[type][]=RULE
conditions[type][]=PRORULE
per_page=100
order=newest
```

### Polling Strategy

1. **Daily at ~9 AM ET:** Query with `conditions[publication_date][gte]` set to our last sync date, filtered to our tracked agency slugs.
2. **Paginate** through all results (100 per page, follow `next_page_url`).
3. **For each document:** Normalize to `RegulatoryAction`, check dedup key `(federal_register, document_number)`.
4. **Store** new records. Documents are immutable — no need to re-pull previous records.

### V1 Scope Filter (Minimized)

- **Agencies:** `federal-energy-regulatory-commission`, `environmental-protection-agency`
- **Types:** `RULE`, `PRORULE` only. Skipping `NOTICE` (meeting announcements, information requests — ~60-70% of volume, no regulation changes) and `PRESDOCU`.
- **Date window:** 6 months per ingestion pass (Q1 2025 baseline, Q2 2025 update).
- **Expected yield:** ~50-100 documents per quarter.

### Field Mapping → RegulatoryAction

| FR API Field | → RegulatoryAction Field |
|---|---|
| `document_number` | `source_id` |
| — | `source_system` = `federal_register` |
| — | `jurisdiction_level` = `federal` |
| `type` | `source_type` (e.g. `Rule`, `Proposed Rule`) |
| `type` mapped to vocabulary | `action_type` (e.g. `final_rule`, `proposed_rule`) |
| `action` | `action_text` |
| `title` | `title` |
| `abstract` | `abstract` |
| `agencies[].slug` | `agency` (mapped to canonical ID) |
| Derived from type + dates | `status` |
| `publication_date` | `dates.published` |
| `effective_on` | `dates.effective` |
| `comments_close_on` | `dates.comment_close` |
| `docket_ids` | `docket_ids` |
| `regulation_id_numbers` | `rin` |
| `cfr_references` (title + part) | `cfr_references` |
| `html_url` | `source_url` |
| `full_text_xml_url` or `body_html_url` | `full_text_url` |

### Type Mapping → action_type

| FR `type` | FR `action` contains | → `action_type` |
|---|---|---|
| `Rule` | "Final rule" | `final_rule` |
| `Rule` | "Interim final rule" | `interim_final_rule` |
| `Rule` | "Direct final rule" | `direct_final_rule` |
| `Rule` | "Correction" | `correction` |
| `Rule` | "Withdrawal" | `withdrawal` |
| `Proposed Rule` | any | `proposed_rule` |
| `Proposed Rule` | "Advance notice" | `advance_notice` |
| `Notice` | any | `notice` *(not ingested in V1)* |
| `Presidential Document` | any | `presidential_document` *(not ingested in V1)* |

### Known Limitations

- Pagination is page-based, capped at 2000 total results per query. Use date-range narrowing for bulk historical pulls.
- The `action` field is free text with no controlled vocabulary — parsing requires substring matching.
- `cfr_references` may be empty on some documents (especially notices).
- Full text requires a separate fetch of `body_html_url` or `full_text_xml_url`.

---

## Source 3: Ohio Administrative Code (Bucket 3 — State Codified Regulations)

**Purpose:** Ingest current text of PUCO rules. Produces `CodeSection` records.

**Access:** Web scraping from `https://codes.ohio.gov/ohio-administrative-code/`
**Auth:** None required. Public.
**API:** No structured API exists. HTML scraping required.
**Data Format:** HTML pages

### Scraping Strategy

1. Navigate to agency 4901 (PUCO) rule listings.
2. For each rule under chapters of interest: pull the rule page, extract heading and body text.
3. Hash body text, compare against stored `content_hash`.
4. If changed, create new `CodeSection` snapshot.

### V1 Scope Filter (Minimized)

- **Agency:** `4901` (PUCO)
- **Chapters:** `4901:1-10` (electric general provisions), `4901:1-21` (SSO), `4901:1-22` (market rate offers), `4901:1-25` (renewable energy). Total: ~40-60 rules.
- **Skipping:** Gas, telephone, water/sewer rules, general PUCO administrative rules.

### Field Mapping → CodeSection

| OAC Page Element | → CodeSection Field |
|---|---|
| Rule number from URL/heading | `citation` (e.g. `4901:1-10-10`) |
| — | `source_system` = `oac` |
| — | `jurisdiction_level` = `state` |
| — | `jurisdiction_geo` = `OH` |
| Agency number `4901` | `title_number` |
| Chapter from rule number | `part` |
| Rule heading | `heading` |
| Rule body text | `body_text` |
| SHA-256 of body_text | `content_hash` |
| — | `owning_agency` = `puco` |
| "Effective" date on rule page | `effective_date` |
| Pull timestamp | `snapshot_date` |
| Rule page URL | `source_url` |

### Known Limitations

- No API — scraping is fragile and may break on site redesigns.
- Older rules may be PDFs filed with the Legislative Service Commission, requiring PDF text extraction.
- The OAC site shows prior effective dates but not the historical text at each date.

---

## Source 4: PUCO DIS (Bucket 4 — State Agency Proceedings)

**Purpose:** Ingest case records and key filings (orders, decisions). Produces `RegulatoryAction` records.

**Access:** Web scraping from `https://dis.puc.state.oh.us/`
**Auth:** None required. Public.
**API:** No structured API. HTML scraping with some search functionality.
**Data Format:** HTML pages, PDFs for individual filings.

### Scraping Strategy

1. **For active cases:** Periodically scrape `CaseRecord.aspx?CaseNo={case_number}` for each tracked case.
2. **For discovering new cases:** Search DIS by industry code `EL` and date range to find new electric cases.
3. **For each case:** Extract metadata (title, status, industry/purpose codes, dates, parties, related cases).
4. **For key filings:** Extract filing date, summary, filer name, document type. Track only orders, decisions, stipulations, and applications — skip routine motions and correspondence.
5. **Detect changes:** Compare filing list against stored records to find new filings. Check case status for changes (OPEN → CLOSED).

### V1 Scope Filter (Minimized)

- **Industry Code:** `EL` (Electric)
- **Purpose Codes:** `SSO` (Standard Service Offer), `AIR` (rate increases), `ATA` (tariff approval) only. Total: ~10-20 active cases in 2025.
- **Skipping:** `COI` (commission inquiries), `CSS` (complaints), `RDR` (riders), `ORD` (administrative orders), `TRF` (final tariffs — captured through ATA proceedings).

### Field Mapping → RegulatoryAction

| DIS Field | → RegulatoryAction Field |
|---|---|
| Case number | `source_id` (e.g. `14-1297-EL-SSO`) |
| — | `source_system` = `puco_dis` |
| — | `jurisdiction_level` = `state` |
| — | `jurisdiction_geo` = `OH` |
| Purpose code mapped to vocabulary | `action_type` (e.g. `SSO` → `rate_case`) |
| Purpose code raw | `source_type` (e.g. `EL-SSO`) |
| Case title | `title` |
| — | `agency` = `puco` |
| Case status mapped | `status` |
| Date Opened | `dates.filed` |
| Most recent order date | `dates.effective` (when an order is issued) |
| Related Cases field | `related_actions` |
| Case page URL | `source_url` |

### Purpose Code → action_type Mapping

| PUCO Purpose Code | → `action_type` |
|---|---|
| `SSO` (Standard Service Offer) | `rate_case` |
| `AIR` (Application to Increase Rates) | `rate_case` |
| `ATA` (Application for Tariff Approval) | `tariff_approval` |
| `COI` (Commission Inquiry) | `commission_inquiry` |
| `RDR` (Tariff Riders) | `tariff_approval` |
| `TRF` (Commission Approved Final Tariffs) | `tariff_approval` |
| `ORD` (Administrative Order) | `order` |
| `CSS` (Complaint on Service/Safety) | `complaint` |
| `ACE` (Application for Certificate) | `certificate` |

### Known Limitations

- No API — all data via HTML scraping.
- DIS has bot-detection (WAF) — requests from automated tools may be blocked. Implement polite scraping with delays and standard headers.
- Filing summaries are free text written by filers — no structured document type field.
- Confidential filings show only a placeholder — flag these, don't attempt content extraction.
- Individual filings within a case don't have stable unique IDs in DIS — we generate our own (`{case_number}_{filing_date}_{sequence}`).

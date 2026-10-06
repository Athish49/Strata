# Strata — Seed Data Strategy

## Purpose

To demo versioning, diffing, and change tracking, we need two time snapshots of data across all three agencies. This document defines the tightly scoped data to pull, which dates, and the ingestion sequence.

## V1 Data Scope — Minimized for Quality

We are optimizing for execution quality, not breadth. Every source is narrowed to only the parts directly relevant to an Ohio electricity provider company.

### Scope Summary

| Source | Full Size | V1 Scope | Estimated Sections/Records |
|---|---|---|---|
| eCFR Title 18 (FERC) | ~140 parts, 1 volume | 3 parts (35, 37, 38) | ~80 sections |
| eCFR Title 40 (EPA) | ~100+ parts, 37 volumes | 4 parts (60 select subparts, 63 select subparts, 72, 73) | ~50-80 sections |
| Federal Register | Thousands of docs/quarter | FERC + EPA, RULE + PRORULE only, 6-month window | ~50-100 documents |
| OAC (PUCO) | Entire state admin code | Agency 4901, chapters 1-10, 1-21, 1-22, 1-25 | ~40-60 rules |
| PUCO DIS | All utility cases | EL industry, SSO/AIR/ATA purpose codes, 2025 only | ~10-20 cases |

**Total estimated: ~230-340 records per ingestion pass.** Small enough to process in minutes, large enough to demonstrate all features.

---

## Bucket 1: eCFR — Tightened Parts

### Title 18 (FERC) — 3 parts, ~80 sections

| Part | Name | Why Relevant | Sections |
|---|---|---|---|
| **35** | Filing of Rate Schedules and Tariffs | Core electric rate regulation — how utilities file rates, market-based rates, transmission investment, cybersecurity | ~50 |
| **37** | Open Access Same-Time Information System (OASIS) | Transmission access transparency requirements | ~15 |
| **38** | Business Operations and Communications Standards | How utilities conduct wholesale business | ~15 |

**Skipping:** Part 39 (NERC reliability — out of V1 scope), Part 40 (reporting forms — just form numbers), Parts 131-382 (accounting, forms, procedures — not regulation substance), Parts 400+ (other agencies, not FERC).

### Title 40 (EPA) — 4 parts, specific subparts only, ~50-80 sections

| Part | Subparts | Name | Why Relevant | Sections |
|---|---|---|---|---|
| **60** | Da, KKKK, TTTTa, UUUUb only | New Source Performance Standards | Emission limits for utility boilers (Da), combustion turbines (KKKK), GHG for EGUs (TTTTa), GHG emission guidelines for existing EGUs (UUUUb) | ~30 |
| **63** | UUUUU, YYYY only | Hazardous Air Pollutant Standards (NESHAP) | Mercury/air toxics for coal/oil EGUs (UUUUU = MATS rule), HAPs for stationary combustion turbines (YYYY) | ~20 |
| **72** | All | Acid Rain Permits | Permit requirements for affected power plants | ~15 |
| **73** | All | Sulfur Dioxide Allowance System | SO2 trading program for power plants | ~15 |

**Skipping:** All mobile source parts (85-94), ambient air quality standards (50-58) — these set ambient standards, not direct plant obligations, general NESHAP subparts for non-power industries, Parts 74-78 (acid rain monitoring/reporting — lower priority for V1), Part 97 CSAPR (large and complex, defer to V2).

### eCFR API Calls

```
# Ingestion 1: Jan 2, 2025 baseline
GET /api/versioner/v1/full/2025-01-02/title-18.xml?part=35
GET /api/versioner/v1/full/2025-01-02/title-18.xml?part=37
GET /api/versioner/v1/full/2025-01-02/title-18.xml?part=38
GET /api/versioner/v1/full/2025-01-02/title-40.xml?part=60  # then filter to target subparts
GET /api/versioner/v1/full/2025-01-02/title-40.xml?part=63  # then filter to target subparts
GET /api/versioner/v1/full/2025-01-02/title-40.xml?part=72
GET /api/versioner/v1/full/2025-01-02/title-40.xml?part=73

# Ingestion 2: Jul 1, 2025 update (same calls, different date)
# Same endpoints with date=2025-07-01
```

**Note:** The eCFR full endpoint returns the entire part even with subpart filters. We filter to target subparts in our adapter code after download.

---

## Bucket 2: Federal Register — Tightened Filters

### Scope: FERC + EPA, rules and proposed rules only, H1 2025

| Parameter | Ingestion 1 | Ingestion 2 |
|---|---|---|
| **Date range** | `2025-01-01` to `2025-03-31` | `2025-04-01` to `2025-06-30` |
| **Agencies** | `federal-energy-regulatory-commission`, `environmental-protection-agency` | Same |
| **Types** | `RULE`, `PRORULE` only | Same |
| **CFR filter** | Title 18 OR Title 40 | Same |

**Skipping:** `NOTICE` type (agency announcements that don't create/change regulations — things like meeting notices, information collection requests). This eliminates ~60-70% of Federal Register volume from these agencies while keeping all regulation-changing actions.

**Expected yield:** ~50-100 documents per quarter for FERC + EPA rules and proposed rules affecting Titles 18 and 40.

### API Calls

```
# Ingestion 1
GET /documents.json?
  conditions[agencies][]=federal-energy-regulatory-commission&
  conditions[agencies][]=environmental-protection-agency&
  conditions[publication_date][gte]=2025-01-01&
  conditions[publication_date][lte]=2025-03-31&
  conditions[type][]=RULE&
  conditions[type][]=PRORULE&
  per_page=100&order=oldest

# Ingestion 2: same with dates 2025-04-01 to 2025-06-30
```

---

## Bucket 3: Ohio Administrative Code — Tightened Chapters

### Scope: PUCO electric rules only, 4 chapters

| Chapter | Name | Why Relevant | Rules |
|---|---|---|---|
| **4901:1-10** | Electric Companies — General Provisions | Service standards, safety, metering, billing for Ohio electric utilities | ~20 |
| **4901:1-21** | Standard Service Offer | How default generation rates are set — the SSO process | ~10 |
| **4901:1-22** | Market Rate Offers | Competitive retail electric market rules | ~10 |
| **4901:1-25** | Renewable Energy | Renewable portfolio standards, solar/wind requirements | ~10 |

**Skipping:** Gas rules (4901:1-13 through 4901:1-19), telephone rules, water/sewer rules, general PUCO administrative rules (4901-1 through 4901-1-99).

**~40-60 rules total.**

---

## Bucket 4: PUCO DIS — Tightened Cases

### Scope: Electric cases, 3 purpose codes, 2025 only

| Purpose Code | Name | Why Relevant |
|---|---|---|
| **SSO** | Standard Service Offer | Default generation rate proceedings — the most impactful for customers |
| **AIR** | Application to Increase Rates | Distribution rate cases — direct cost impact |
| **ATA** | Application for Tariff Approval | Tariff changes — new charges or modified terms |

**Skipping:** COI (commission inquiries — investigative, not rate-changing), CSS (complaints — individual disputes), RDR (riders — less impactful for V1 demo), ORD (administrative orders), all non-EL industry codes.

**Expected yield:** ~10-20 active cases in 2025 across Ohio's major electric utilities (AEP Ohio, Duke Energy Ohio, Ohio Edison/FirstEnergy, AES Ohio).

---

## Two-Snapshot Ingestion Sequence

```
PHASE 1: "Before" Baseline (January 2025)
  1.1  Ingest eCFR Title 18 Parts 35,37,38 as of 2025-01-02 → ~80 CodeSections
  1.2  Ingest eCFR Title 40 Parts 60,63,72,73 (target subparts) as of 2025-01-02 → ~60 CodeSections
  1.3  Ingest Federal Register FERC+EPA RULE+PRORULE Q1 2025 → ~50-100 RegulatoryActions
  1.4  Run stitching: link FR actions to CodeSections via cfr_references
  1.5  Ingest OAC chapters 4901:1-10, 1-21, 1-22, 1-25 → ~40-60 CodeSections
  1.6  Ingest PUCO DIS EL cases (SSO/AIR/ATA) H1 2025 → ~10-20 RegulatoryActions
  1.7  Run stitching: link PUCO cases to OAC rules where references exist

PHASE 2: "After" Update (July 2025)
  2.1  Ingest eCFR same parts as of 2025-07-01 → detect changed CodeSections, create version chains
  2.2  Ingest Federal Register FERC+EPA RULE+PRORULE Q2 2025 → new RegulatoryActions
  2.3  Run stitching: link new FR actions to CodeSection changes + action chains via RIN/docket
  2.4  Re-scrape OAC same chapters → detect any rule text changes
  2.5  Ingest PUCO DIS same scope H2 2025 → new filings, status changes
  2.6  Run stitching: cross-jurisdiction links, full relationship graph
```

## Volume Estimates

| Metric | Phase 1 | Phase 2 | Total |
|---|---|---|---|
| CodeSection records | ~180 | ~180 (most unchanged, ~10-20 new versions) | ~200 unique sections, ~360 total snapshots |
| RegulatoryAction records | ~70 | ~70 | ~140 |
| Relationships | ~50 | ~100 | ~150 |
| Raw storage (R2) | ~5 MB | ~5 MB | ~10 MB |
| PostgreSQL | ~1.5 MB | ~0.6 MB (only changed sections + new actions) | ~2.1 MB |
| Vector chunks (~3 per unique section + 1 per action) | ~600 | ~140 new (changed sections + new actions only) | ~740 vectors |

Well within all free tier limits.

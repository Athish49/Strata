# Strata — Data Models & Schemas

## Overview

The system has two core abstract data types. Every source adapter must produce records conforming to one or both schemas. Fields marked **(req)** must always be populated; all others are nullable.

---

## CodeSection

A living, mutable unit of regulatory text. Represents one section/rule in a codebook (CFR, OAC, or any future equivalent). The text changes in place while the citation stays stable.

| Field | Type | Description |
|---|---|---|
| `citation` **(req)** | string | Canonical hierarchical address: `18 CFR 35.28`, `4901:1-10-10`. Primary key within its source system. |
| `source_system` **(req)** | enum | Which codebook: `cfr`, `oac`. Future: `ca_ccr`, `uk_si`. Together with `citation` forms the **global unique key**. |
| `jurisdiction_level` **(req)** | enum | `federal` \| `state` \| `local` \| `international` |
| `jurisdiction_geo` | string | State/country: `OH`, `CA`, `UK`. Null for federal. |
| `title_number` | string | Top-level grouping: CFR title (`18`, `40`), OAC agency number (`4901`). |
| `part` | string | Program-level grouping: CFR part (`35`), OAC chapter (`1-10`). |
| `section_number` | string | Atomic unit number within the part. |
| `heading` **(req)** | string | Human-readable section title. |
| `body_text` **(req)** | string | Full regulatory text at this snapshot. |
| `content_hash` **(req)** | string | SHA-256 of `body_text`. Change detection key — if hash differs from previous snapshot, the text changed. |
| `owning_agency` **(req)** | string | Canonical agency ID from agency registry. |
| `effective_date` | date | When this version of the text took effect. |
| `status` **(req)** | enum | `in_progress` \| `approved` \| `blocked_suspended`. Almost always `approved` for codified text. |
| `snapshot_date` **(req)** | date | When we pulled this version. |
| `source_url` | string | Permalink on the source system. |
| `amendment_source` | string | FR document number or state register entry that caused this change. Bridge to the journal. |
| `prior_version_id` | FK | Previous snapshot of the same citation, forming the version chain. |
| `superseded_by` | string | New citation if section was redesignated. Null if active. |
| `repealed_date` | date | Date section was removed from codebook. Null if active. |

**Primary key:** `(source_system, citation, snapshot_date)`
**Dedup key:** `(source_system, citation)` — only one "current" version per section; new snapshots create a version chain via `prior_version_id`.

---

## RegulatoryAction

An immutable record of an agency action. Represents one published rule, order, case, or decision. Once published, the record doesn't change — corrections and amendments create new records.

| Field | Type | Description |
|---|---|---|
| `source_id` **(req)** | string | Native unique ID: FR doc number (`2026-18552`), PUCO case (`14-1297-EL-SSO`), FERC docket (`RM21-17`). |
| `source_system` **(req)** | enum | Which journal: `federal_register`, `puco_dis`. Future: `cpuc`, `ofgem`. Together with `source_id` forms **global unique key**. |
| `jurisdiction_level` **(req)** | enum | `federal` \| `state` \| `local` \| `international` |
| `jurisdiction_geo` | string | State/country when applicable. |
| `action_type` **(req)** | string | Normalized type from controlled vocabulary (see Action Type Vocabulary below). |
| `source_type` | string | Original type label from source, preserved as-is: `Rule`, `NOPR`, `EL-SSO`. |
| `action_text` | string | Source's own action description (free text). |
| `title` **(req)** | string | Title of the action/proceeding. |
| `abstract` | string | Summary text. |
| `agency` **(req)** | string | Canonical agency ID from agency registry. |
| `status` **(req)** | enum | `in_progress` \| `approved` \| `blocked_suspended` |
| `dates.published` | date | When published or filed. |
| `dates.effective` | date | When it takes/took effect. |
| `dates.comment_close` | date | End of comment period (federal actions). |
| `dates.filed` | date | When filing was submitted (state proceedings). |
| `docket_ids` | string[] | Regulations.gov docket IDs, FERC docket numbers, or equivalent. |
| `rin` | string | Regulation Identifier Number — OMB tracking ID for a federal rulemaking. Same RIN links all FR docs in one rulemaking. |
| `cfr_references` | string[] | Codebook sections this action creates/amends/repeals: `18 CFR 35.28`. **Primary stitching field linking journal → codebook.** |
| `legal_refs` | string[] | Statutes, OAC rules, or other legal authorities cited. |
| `affected_entities` | string[] | Named companies, utilities, organizations. |
| `related_actions` | object[] | Links to other RegulatoryAction records. Each entry: `{ source_system, source_id, relationship_type }`. |
| `source_url` **(req)** | string | Permalink to the action on the source system. |
| `full_text_url` | string | Link to full document (HTML, PDF). |
| `ingested_at` **(req)** | timestamp | When our system pulled this record. |
| `adapter_version` **(req)** | string | Which adapter version produced this record. |

**Primary key:** `(source_system, source_id)`
**Immutability:** Records are never updated after creation. Corrections/amendments are new records linked via `related_actions`.

---

## Relationship Types

Used in `RegulatoryAction.related_actions` and for linking `CodeSection` version chains:

| Type | Meaning | Example |
|---|---|---|
| `amends` | Modifies an existing regulation or prior action | Final rule amending a CFR section |
| `corrects` | Fixes an error in a prior action | FR correction document |
| `supersedes` | Replaces a prior action entirely | New final rule replacing an interim final rule |
| `withdraws` | Cancels a prior proposed or final action | Agency withdrawal notice |
| `extends` | Extends a deadline or effective date | Extension of comment period |
| `responds_to` | Rehearing, appeal, or court review response | PUCO entry on rehearing |
| `implements` | State action implementing a federal rule | PUCO compliance proceeding triggered by EPA rule |
| `related_to` | Weaker semantic link — same topic, no direct legal connection | FERC transmission order related to PUCO rate case on same utility |
| `redesignated_as` | CodeSection moved to a new citation | CFR section renumbered |
| `split_from` | CodeSection was part of a section that was split | One section becomes two |
| `merged_into` | CodeSection was merged into another | Two sections become one |

---

## Action Type Vocabulary

Controlled vocabulary for `RegulatoryAction.action_type`. New source adapters extend this list through configuration.

| action_type | Description | Typical Source |
|---|---|---|
| `final_rule` | Binding regulation, published and effective | Federal Register |
| `proposed_rule` | Draft regulation open for comment | Federal Register |
| `interim_final_rule` | Effective immediately, comments still solicited | Federal Register |
| `direct_final_rule` | Effective unless adverse comments received | Federal Register |
| `advance_notice` | Early-stage solicitation (ANPRM/ANOPR) | Federal Register |
| `notice` | Non-rulemaking agency announcement | Federal Register |
| `withdrawal` | Agency abandons a rulemaking | Federal Register |
| `correction` | Fix to a previously published action | Federal Register |
| `order` | Agency decision/order (adjudicatory) | FERC eLibrary, PUCO DIS |
| `rate_case` | Proceeding to set or change rates | PUCO DIS |
| `tariff_approval` | Approval of tariff filing | PUCO DIS |
| `commission_inquiry` | Agency-initiated investigation | PUCO DIS |
| `complaint` | Complaint proceeding | PUCO DIS |
| `certificate` | Certificate of public convenience | PUCO DIS |

---

## Agency Registry

Each agency is registered with canonical metadata:

| Field | Type | Description |
|---|---|---|
| `agency_id` | string | Canonical unique ID: `ferc`, `epa`, `puco` |
| `name` | string | Full name: `Federal Energy Regulatory Commission` |
| `aliases` | string[] | Alternative names: `FERC`, `federal-energy-regulatory-commission` (FR slug) |
| `jurisdiction_level` | enum | `federal` \| `state` |
| `jurisdiction_geo` | string | `OH` for PUCO, null for federal |
| `codebook_title` | string | Which codebook section this agency owns: CFR Title `18` for FERC, OAC agency `4901` for PUCO |
| `domain` | string[] | Regulatory domains: `energy`, `electricity`, `environment` |

---

## Status Mapping Rules

How source-specific types map to the three-level status model:

| Source Type / Condition | → Status |
|---|---|
| FR type `Proposed Rule` (V1 scope: RULE and PRORULE only; NOTICE deferred) | `in_progress` |
| FR type `Rule` with `effective_date` in the future | `approved` |
| FR type `Rule` with `effective_date` in the past | `approved` |
| PUCO case status `OPEN` | `in_progress` |
| PUCO case with Commission Order issued | `approved` |
| PUCO case status `CLOSED` or `ARCHIVED` | `approved` |
| Court stay or vacatur on any action | `blocked_suspended` |
| CRA disapproval | `blocked_suspended` |
| Agency withdrawal | `blocked_suspended` |

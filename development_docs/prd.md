# Strata — Product Requirements Document (V1)

## Core Goal

Help companies understand how finalized regulation and rule changes affect them — across federal and state agencies. The platform is domain-agnostic and expandable to new jurisdictions and industries.

## V1 Domain Focus

- **Industry:** Electricity within the energy sector
- **Geography:** Federal (nationwide) + Ohio (state)
- **Agencies:** FERC (wholesale markets, transmission), EPA (emissions, environmental compliance), PUCO (Ohio retail rates, distribution)

## Status Model

Every regulatory item is assigned one of three statuses:

| Status | Meaning | Company Posture |
|---|---|---|
| `in_progress` | Being developed: draft, proposed, comment period, under review | Monitor |
| `approved` | Finalized — already effective or with a known effective date | Act / Comply |
| `blocked_suspended` | Was finalized but stayed by court, vacated, CRA disapproved, or agency withdrew/delayed | Hold |

## In Scope

- Codified regulations (CFR, OAC) — the permanent binding rules companies must follow
- Binding agency orders directed at specific parties (FERC rate orders, PUCO case orders) — never enter CFR/OAC but are mandatory for the named company
- Final rules, interim final rules, direct final rules published in the Federal Register
- Proposed rules and NOPRs (tracked as `in_progress` for early visibility)
- Effective dates, compliance deadlines, comment-close dates from structured fields
- Cross-agency linkage by docket ID, RIN, CFR part, and OAC rule number
- Version tracking of codified text changes over time

## Out of Scope (V1)

- **Guidance documents and policy statements** — agency interpretations of how to comply with existing rules. Not legally binding. The underlying regulation changes are captured through the codebook buckets. Deferred as a secondary interpretive layer.
- **Public comments** on proposed rules (Regulations.gov data)
- **Supporting materials, attachments, technical appendices** filed in proceedings
- **Predictive features** — forecasting impact of draft-stage rules if they pass
- **Comment-tracking features** — alerting companies to submit comments
- **FERC eLibrary direct ingestion** — FERC rulemaking captured via Federal Register API; full adjudicatory docket system is future expansion
- **NERC reliability standards** — delegated-authority standards not in CFR

## What This Captures (Examples)

| Scenario | Captured? | Why |
|---|---|---|
| Minimum wage increase | Yes | DOL amends 29 CFR; FR carries the final rule (Bucket 2), CFR section updates (Bucket 1) |
| Maximum rate a utility can charge | Yes | PUCO issues an order approving a new tariff (Bucket 4) |
| New emissions standard for power plants | Yes | EPA amends 40 CFR Part 60; final rule in FR (Bucket 2), CFR updates (Bucket 1) |
| Agency publishes new guidance on compliance methodology | No | Underlying regulation didn't change; guidance is V2 scope |

## Domain-Agnostic Expansion

Adding a new domain (healthcare, financial services) or jurisdiction (another state, UK Ofgem, EU ACER) means:

1. Writing a source adapter that produces `CodeSection` and `RegulatoryAction` records
2. Configuring how source-native types map to our three statuses and action type vocabulary
3. Adding an agency registry entry

No core schema changes required.

---
doc_id: RPL-ENV-PRO-005
title: Spill Response & Reporting Procedure
company: Rockridge Power & Light Company
version: "3.1"
status: Approved
effective_date: 2025-03-10
approved_date: 2025-03-05
law_as_of: 2024-12-31
owner: {id: P26, name: Hannah Brooks, title: "Senior Environmental Specialist"}
reviewer: {id: P25, name: Daniel Foster, title: "Manager, Environmental Services"}
approver: {id: P24, name: Sandra Kim, title: "Director, Environmental, Health & Safety"}
next_review: 2026-03-10
classification: Internal
regulatory_basis: ["327 IAC 2-6.1 (out_of_scope_reference — full rule)"]
supersedes: "3.0 (2024-03-11)"
---

<!-- DOCUMENT CONTROL BLOCK -->

| Field | Value |
|---|---|
| **Document Title** | Spill Response & Reporting Procedure |
| **Doc ID** | RPL-ENV-PRO-005 |
| **Version** | 3.1 |
| **Effective Date** | 2025-03-10 |
| **Approved Date** | 2025-03-05 |
| **Owner** | Hannah Brooks (P26), Senior Environmental Specialist |
| **Reviewer** | Daniel Foster (P25), Manager, Environmental Services |
| **Approver** | Sandra Kim (P24), Director, Environmental, Health & Safety |
| **Classification** | Internal |
| **Review Cycle** | Annual |
| **Supersedes** | 3.0 (2024-03-11) |
| **Law As-Of** | 2024-12-31 |

> **Uncontrolled when printed — verify the current version in DCS before use.**

---

## Table of Contents

1. Purpose
2. Scope & Assessment Scope
3. Definitions
4. Regulatory Basis
5. Roles & Responsibilities
6. Immediate Response
7. Reportability Determination
8. Notification to the State
9. Notification of Other Affected Parties
10. Containment, Response & Cleanup
11. Follow-Up & Written Reports
12. Close-Out
13. Waste Handling & Disposal
14. Federal & Other Notifications
15. Records & Retention
16. Training & Drills
17. Related Documents
18. Revision History
19. Approval Block

**Appendices**
- App-A: EHS-F-201 Spill Report Form (Rev. 03/2025)
- App-B: Crew Quick-Reference Card
- App-C: Notification Contact Sheet
- App-D: Spill Kit Inventory & Locations
- App-E: Worked Examples (Three 2024 Events)
- App-F: Data Dictionary — spill_events_2024.csv

---

<!-- clause: RPL-ENV-PRO-005:1 -->
## 1. Purpose

This procedure establishes the responsibilities, decision steps, notification actions and records required when Rockridge Power & Light Company (RPL) personnel or contractors discover or cause a release of oil, fuel or other regulated substance from RPL equipment, vehicles or facilities. It enables the first responder, the Distribution Control Center (DCC) and Environmental Services to protect public safety, contain the release, comply with the applicable Indiana environmental reporting obligation (327 IAC 2-6.1), and document the response from discovery through close-out.

<!-- clause: RPL-ENV-PRO-005:2 -->
## 2. Scope & Assessment Scope

<!-- clause: RPL-ENV-PRO-005:2.1 -->
### 2.1 Operational Scope

This procedure applies to:

- All RPL employees and contracted workers performing work on RPL facilities, on RPL rights-of-way, or in RPL service vehicles.
- All RPL-owned equipment that may contain or transport regulated substances, including distribution and substation transformers, voltage regulators, oil-filled circuit breakers and capacitors, standby generator diesel belly tanks, fleet vehicles, and service center fuel storage.
- All RPL facilities: the five service centers (Lafayette, Crawfordsville, Terre Haute, Frankfort, and Danville), distribution substations (112 total), and rights-of-way across the 14-county service territory.
- Contractor obligations under this procedure are enforced through contract terms and pre-work briefings; contractors must follow RPL's Crew Quick-Reference Card (App-B) until the on-call Environmental Specialist assumes oversight.

<!-- clause: RPL-ENV-PRO-005:2.2 -->
### 2.2 Assessment Scope

This procedure covers RPL's response to, and state notification of, regulated substance releases under Indiana law, including the state reporting requirements of **327 IAC 2-6.1**. All obligations arising from 327 IAC 2-6.1 are recorded under §4 as an `out_of_scope_reference` because the full text of 327 IAC 2-6.1 was not incorporated into the Strata knowledge layer at Snapshot 1. RPL complies with 327 IAC 2-6.1. The operational steps, roles, forms and records throughout this procedure implement that compliance as company practice.

The following topics are referenced in one clause each (§14) and delegated to their respective RPL procedures; no values from those frameworks are stated here:

- Federal release notification (National Response Center) — handled under RPL-ENV-PRO-008
- Federal reportable quantities — handled under RPL-ENV-PRO-008
- SPCC plan requirements — handled under RPL-ENV-PLN-010 (substations) and RPL-ENV-PLN-011 (service centers and fleet fueling)
- PCB management requirements — handled under RPL-ENV-PRO-006
- Hazardous waste rules (RCRA) — handled under RPL-ENV-PRO-007

<!-- clause: RPL-ENV-PRO-005:3 -->
## 3. Definitions

**Note:** The following terms are company definitions used throughout this procedure. No definitions are taken from the text of 327 IAC 2-6.1, because the full rule text is not in the knowledge layer for this document version.

<!-- clause: RPL-ENV-PRO-005:3.1 -->
**Release (company definition):** Any discharge, deposit, injection, dumping, spilling, leaking, or placing of a regulated substance from RPL equipment, vehicles or facilities into the environment, including onto impervious surfaces where drainage or secondary transport is possible.

<!-- clause: RPL-ENV-PRO-005:3.2 -->
**Regulated substance (company definition):** For this procedure, any oil (mineral oil dielectric fluid, transformer oil, petroleum, diesel, gasoline, hydraulic fluid) that may enter the environment from RPL's equipment or operations.

<!-- clause: RPL-ENV-PRO-005:3.3 -->
**Facility boundary (company definition):** For substations: the perimeter fence. For padmount transformers and underground switchgear: the equipment vault slab and secondary containment structure, if present. For service centers: the property boundary. For pole-mount transformers: the base of the pole. For standby generators: the concrete pad and secondary containment. Any release that travels beyond these points is classified as "soil beyond boundary."

<!-- clause: RPL-ENV-PRO-005:3.4 -->
**Spill kit (company definition):** The RPL-standard assembled set of spill response materials pre-staged at each service center, on each line truck and on each substation truck. Contents and locations are described in App-D. Kits are inspected monthly under WAM work type `ENV-INSP`.

<!-- clause: RPL-ENV-PRO-005:3.5 -->
**On-call Environmental Specialist (company definition):** The designated RPL Environmental Services staff member reachable 24 hours a day, 7 days a week via OMS paging group `ENV-ONCALL`. The rotation is weekly, with Monday 08:00 handover; Hannah Brooks (P26) plus two Environmental Specialists based in Lafayette and Terre Haute (role titles) rotate on the schedule; backup is Daniel Foster (P25).

<!-- clause: RPL-ENV-PRO-005:3.6 -->
**WAM PCB Status Codes (company definition):** Codes maintained in the Work & Asset Management system (WAM) for each oil-filled asset. Definitions are in RPL-ENV-PRO-006. Codes used in this procedure:

| Code | Meaning | Required action |
|---|---|---|
| NP-T | Non-PCB (tested) | Standard spill response |
| NP-M | Non-PCB (manufacturer certified) | Standard spill response |
| UNK | Untested / unknown — treat as PCB | Full PCB precautions; see RPL-ENV-PRO-006 |
| PCB-C | PCB-contaminated | Full PCB precautions; see RPL-ENV-PRO-006 |
| PCB | Confirmed PCB equipment | Full PCB precautions; see RPL-ENV-PRO-006 |

Label colours: blue label = NP-T or NP-M; yellow label = PCB-C or PCB; no label = treat as `UNK`.

<!-- clause: RPL-ENV-PRO-005:3.7 -->
**Spill report (company definition):** The completed EHS-F-201 form (App-A), plus IDEM initial notification record, update log and any written follow-up. It constitutes the primary record for record series RRS-ENV-001.

<!-- clause: RPL-ENV-PRO-005:4 -->
## 4. Regulatory Basis

<!-- clause: RPL-ENV-PRO-005:4.1 -->
### 4.1 Applicable Indiana Rule

<!-- table: RPL-ENV-PRO-005:T4 -->

| Citation | Heading / Subject | What It Governs in This Procedure | Clause Type |
|---|---|---|---|
| 327 IAC 2-6.1 | Indiana Spill Reporting Rule (full rule) | State notification obligations, reportability determinations, notification content requirements, third-party notification duties, cleanup and follow-up requirements, and compliance confirmation. RPL complies with 327 IAC 2-6.1. No values from this rule are stated in this procedure because the full text is outside the Snapshot-1 knowledge layer. All operational steps are built as company practice consistent with compliance. | out_of_scope_reference |

<!-- clause: RPL-ENV-PRO-005:4.2 -->
### 4.2 Out-of-Scope References

The following statutes and federal regulations also govern RPL's spill-related obligations. They are referenced here by name only; no values are stated. Each is handled under the listed RPL document.

<!-- table: RPL-ENV-PRO-005:T4b -->

| Reference | Scope | Handled Under |
|---|---|---|
| Federal release notification / National Response Center requirements | Federal CERCLA and EPCRA reportable quantity releases | RPL-ENV-PRO-008 |
| Federal reportable quantity (RQ) determinations | Designation of federal RQ thresholds | RPL-ENV-PRO-008 |
| 40 CFR Part 112 (SPCC) | Spill Prevention, Control & Countermeasure plans | RPL-ENV-PLN-010, RPL-ENV-PLN-011 |
| 40 CFR Part 761 (PCB regulations) | PCB equipment inspection, storage and cleanup | RPL-ENV-PRO-006 |
| 40 CFR Parts 260–262 (RCRA hazardous waste) | Waste characterization and disposal | RPL-ENV-PRO-007 |

<!-- clause: RPL-ENV-PRO-005:5 -->
## 5. Roles & Responsibilities

<!-- clause: RPL-ENV-PRO-005:5.1 -->
### 5.1 Role Descriptions

<!-- table: RPL-ENV-PRO-005:T5a -->

| Role | Person (if named) | Responsibilities |
|---|---|---|
| First Responder / Crew Lead | Field employee in charge at scene | Life safety; de-energize and isolate source; initial containment; call DCC; complete EHS-F-201 Part A–D and Part G preliminary |
| DCC Shift Supervisor | (staffed 24/7) | Receive first-responder call; page ENV-ONCALL within 15 minutes; log in OMS; provide backup notification to IDEM if ENV-ONCALL is unavailable after 30 minutes |
| On-Call Environmental Specialist | Hannah Brooks (P26), rotating pool (ENV-ONCALL) | Determine reportability; notify IDEM; direct containment and cleanup; complete EHS-F-201 Parts E, F, H; coordinate Contractor E; complete 30-day closure package |
| Manager, Environmental Services | Daniel Foster (P25) | Escalation for complex or large releases; written follow-up review; supervisor sign-off on EHS-F-201 Part H; 30-day package approval |
| Director, Environmental, Health & Safety | Sandra Kim (P24) | VP-level escalation for spills to surface water or of any PCB/unknown-PCB oil in special areas; media coordination with Corporate Communications |
| Fleet Services | Role title | Fueling spill first response; vehicle spill kit deployment; incident log in EHS-IMS |
| Contractor E | Emergency Response and Remediation (Contract RPL-C-2023-118, 24/7) | Containment deployment; excavation; waste hauling; confirmation sampling coordination |
| Corporate Communications | Role title | External communications per RPL-COM-PRO-002; no release details communicated without Sandra Kim (P24) authorization |

<!-- clause: RPL-ENV-PRO-005:5.2 -->
### 5.2 RACI Table

<!-- table: RPL-ENV-PRO-005:T5b -->

| Activity | First Responder | DCC Supervisor | On-Call ENV Spec. | Daniel Foster (P25) | Sandra Kim (P24) | Contractor E |
|---|---|---|---|---|---|---|
| Life safety, scene isolation | **R/A** | I | I | — | — | — |
| Initial containment | **R** | I | **A** | — | — | S |
| DCC notification | **R** | **A** | — | — | — | — |
| Page ENV-ONCALL | — | **R/A** | — | — | — | — |
| Reportability determination | I | I | **R/A** | C | C | — |
| IDEM initial notification | I | S (backup) | **R/A** | I | I | — |
| Cleanup and remediation | S | — | **R/A** | C | I | **R** |
| EHS-F-201 completion | **R** (Parts A–D, G preliminary) | — | **R** (Parts E–F, H) | **A** | — | S |
| 30-day closure package | — | — | **R** | **A** | I | — |
| Media communications | — | — | I | I | **A** | — |

**Key:** R = Responsible · A = Accountable · C = Consulted · I = Informed · S = Supports

<!-- clause: RPL-ENV-PRO-005:6 -->
## 6. Immediate Response

<!-- clause: RPL-ENV-PRO-005:6.1 -->
**Step 1 — Life safety first.** The first responder evaluates for electrical hazards, fire or explosion risk. No employee approaches a spill from a failed or energized transformer, substation equipment or vehicle until the equipment has been confirmed de-energized. The crew lead calls the DCC to request switching if the equipment is still energized.

> **Caution:** Never begin containment on a transformer or substation release until the DCC confirms de-energization. Oil and energized equipment create fatal flash and fire hazards.

<!-- clause: RPL-ENV-PRO-005:6.2 -->
**Step 2 — Stop the source.** After de-energization is confirmed, the crew lead stops or isolates the source using available valves, plugs or physical pressure. If the source cannot be stopped in the field, the crew lead notifies the DCC to dispatch a supervisor and activates Contractor E.

<!-- clause: RPL-ENV-PRO-005:6.3 -->
**Step 3 — Contain and protect.** The crew lead deploys the spill kit on the truck (20-gal, containing absorbent pads, socks, drain cover, nitrile gloves and disposal bags). Priority order: (1) protect storm drains and surface water using drain covers and containment boom; (2) encircle the spill perimeter with absorbent socks; (3) apply absorbent pads to the spill body. Do not wash the spill with water, hose down the area or use any dispersant.

<!-- clause: RPL-ENV-PRO-005:6.4 -->
**Step 4 — Call the DCC.** Within 30 minutes of discovery, the crew lead calls the DCC at 1-800-555-0177 and provides: name, employee ID, service center, spill location (address, county, nearest intersection or GPS coordinates), equipment type, WAM asset ID, estimated volume released, substance, receiving medium (soil, drain, surface water), and PCB status code from the asset nameplate or WAM.

<!-- clause: RPL-ENV-PRO-005:6.5 -->
**Step 5 — DCC pages ENV-ONCALL.** The DCC shift supervisor logs the event in the OMS incident queue and pages ENV-ONCALL within 15 minutes of receiving the crew call. If ENV-ONCALL does not acknowledge within 30 minutes, the DCC contacts Daniel Foster (P25) directly and, if necessary, IDEM at (888) 233-7745.

<!-- clause: RPL-ENV-PRO-005:6.6 -->
**Step 6 — Photograph and preserve.** The crew lead photographs the release area, source equipment, stain extent, receiving medium and drain proximity before cleanup begins. Photos are uploaded to EHS-IMS under the spill event record (`SPL-2024-nnnn`). The crew lead completes EHS-F-201 Parts A through D at the scene or within 2 hours of initial containment.

> **Note:** Where 327 IAC 2-6.1 or another applicable provision states that emergency response actions take precedence over or excuse a delayed report, RPL applies that provision as written. Because the full text of 327 IAC 2-6.1 is not in the current knowledge layer, this clause records company compliance without restating values. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:7 -->
## 7. Reportability Determination

The on-call Environmental Specialist determines reportability using the steps in 7.1 through 7.6. Reportability under 327 IAC 2-6.1 is an out-of-scope reference (§4.1). The steps below build the determination as company practice.

<!-- clause: RPL-ENV-PRO-005:7.1 -->
### 7.1 Classification of RPL Release Sources

The following table records RPL's classification of each release source type for purposes of the reportability determination. Where the text of 327 IAC 2-6.1 answers the classification question directly, that text governs (cited as out_of_scope_reference). Where it does not, the row is a `Company position:` chosen to make more releases — not fewer — reportable.

<!-- table: RPL-ENV-PRO-005:T7a -->

| Source | RPL Classification for This Procedure | Basis | Clause ID |
|---|---|---|---|
| Pole-mount transformer (on pole, overhead) | Facility equipment — facility boundary is the base of the pole | Company position: pole-mount transformers are treated as facility equipment; facility boundary is taken conservatively as the base of the supporting pole so that any release that reaches the soil beyond that point is treated as beyond-boundary | RPL-ENV-PRO-005:T7a-1 |
| Padmount transformer / switchgear (ground-level enclosure) | Facility equipment — facility boundary is the transformer vault slab or secondary containment structure | Company position: the padmount vault is treated as the facility; releases beyond the vault slab are beyond-boundary; releases to a storm drain connected to the vault slab are treated as reaching a receiving medium | RPL-ENV-PRO-005:T7a-2 |
| Substation equipment inside a fenced substation | Facility equipment inside fenced boundary — facility boundary is the perimeter fence | Company position: the substation perimeter fence marks the facility boundary; releases that remain inside the fence on impervious containment pads are inside-boundary; releases that penetrate the fence gravel or reach beyond the fence are beyond-boundary | RPL-ENV-PRO-005:T7a-3 |
| Standby generator belly tank at a service center | Facility fuel storage — facility boundary is the service center property boundary | Company position: belly tanks are facility fuel storage; the concrete pad and double-wall constitute secondary containment; any release that exits secondary containment is classified as at-facility or beyond-boundary per receiving medium | RPL-ENV-PRO-005:T7a-4 |
| Fleet fueling at a service center | Facility fuel storage — same boundary as standby generator at the same location | Company position: fueling stations are facility sources; releases on the fueling apron that remain in containment are inside-boundary | RPL-ENV-PRO-005:T7a-5 |
| Fleet vehicle or bucket truck in transit (moving or parked on public road or customer property) | Transportation source — no enclosed facility boundary | Company position: vehicles in transit are treated as a transportation source with no fixed facility boundary; all releases from these vehicles to the ground are classified by their actual receiving medium | RPL-ENV-PRO-005:T7a-6 |
| Fleet vehicle or bucket truck parked at a work site (not a service center) | Transportation source parked — same as in-transit classification | Company position: a vehicle parked at a work site that is not a service center retains its transportation-source classification; the receiving medium governs reportability | RPL-ENV-PRO-005:T7a-7 |
| Oil release discovered on customer property | Facility equipment (if RPL asset) or transportation source (if from RPL vehicle) — boundary follows classification above | Company position: RPL classifies the source first (which asset?), then applies the appropriate boundary definition; when the source is uncertain, RPL treats the release as reportable | RPL-ENV-PRO-005:T7a-8 |

<!-- clause: RPL-ENV-PRO-005:7.2 -->
### 7.2 Reportability Decision Table

The on-call Environmental Specialist applies the rows below in order. The first row whose conditions are fully met determines reportability. All thresholds are company practice (no values from 327 IAC 2-6.1 are stated here). The Citation column identifies the applicable company-practice clause. Record the row number in EHS-F-201 Part E.

> **Note:** All reportability determinations are made under 327 IAC 2-6.1 as interpreted through RPL's company practice, since the full text is outside the current knowledge layer.

<!-- table: RPL-ENV-PRO-005:T7b -->

| Row | Substance Category | Location / Receiving Medium | Condition | Reportable? | Basis | Clause ID |
|---|---|---|---|---|---|---|
| T7-1 | Any regulated substance | Impervious surface | Fully contained (volume recovered ≥ volume released); no storm drain or waterway directly connected; PCB status NP-T or NP-M; no special area flag | **No** — Exclusion CP-NR1 applies (see §7.3.1) | Company practice — conservative exclusion; record in EHS-F-201 Part E | RPL-ENV-PRO-005:T7-1 |
| T7-2 | Any regulated substance | Soil — beyond facility boundary, or soil inside boundary where release is not fully contained | Any volume; source is any RPL equipment, vehicle or facility type | **Yes** | Company practice — beyond-boundary or uncontained soil release | RPL-ENV-PRO-005:T7-2 |
| T7-3 | Any regulated substance | Storm drain, sewer, or surface water (stream, pond, ditch, wetland, any surface water body) | Any volume; any receiving medium listed | **Yes** | Company practice — releases to water pathways are reportable regardless of volume | RPL-ENV-PRO-005:T7-3 |
| T7-4 | Any regulated substance | Any receiving medium | Special area flag = Y (GIS screening per §7.5 identifies the release is within or adjacent to ENV_WellheadProtection, ENV_PrivateWellBuffer, ENV_SensitiveWaters or ENV_StormInlets layer) | **Yes** | Company practice — proximity to sensitive receptors makes release reportable regardless of medium | RPL-ENV-PRO-005:T7-4 |
| T7-5 | Any regulated substance with PCB status UNK, PCB-C, or PCB | Any receiving medium | PCB status is untested or confirmed PCB; regardless of containment status | **Yes** | Company practice — PCB-uncertain and PCB-confirmed releases are reportable; PCB rules handled in RPL-ENV-PRO-006 | RPL-ENV-PRO-005:T7-5 |
| T7-6 | Any regulated substance | Any receiving medium | None of rows T7-1 through T7-5 has resolved reportability | **Yes — when in doubt, report** | Company practice — catch-all; see §7.6 | RPL-ENV-PRO-005:T7-6 |

<!-- clause: RPL-ENV-PRO-005:7.3 -->
### 7.3 Exclusions

> **Caution:** An exclusion applies only when every condition stated for that exclusion is met. A single unmet condition means the release is reportable.

<!-- clause: RPL-ENV-PRO-005:7.3.1 -->
**Exclusion CP-NR1 — Impervious surface, fully contained.** A release is not reportable when all five of the following conditions are satisfied simultaneously:

1. The substance is released onto an impervious surface (concrete, asphalt, paved pad, impervious liner);
2. The volume recovered is equal to or greater than the volume released (full containment confirmed on-site);
3. No storm drain, floor drain or surface water body is directly connected to the release area or accessible by gravity flow;
4. The WAM PCB status code for the source equipment is NP-T or NP-M (tested or manufacturer certified non-PCB); and
5. GIS screening (§7.5) confirms the release is not in or adjacent to a special area layer.

The crew lead and on-call Environmental Specialist must jointly confirm each condition and document the confirmation in EHS-F-201 Part E, field E-3.

<!-- clause: RPL-ENV-PRO-005:7.3.2 -->
**Exclusion CP-NR2 — Contained inside substation secondary containment.** A release inside a substation transformer secondary containment structure (concrete curbed pad, oil-retention pond or sump) is not reportable when all of the following are satisfied:

1. The oil remains within the secondary containment boundary and does not overflow or seep beyond;
2. The substation's SPCC plan (RPL-ENV-PLN-010) secondary containment was adequate for the volume;
3. PCB status is NP-T or NP-M; and
4. No special area flag applies.

<!-- clause: RPL-ENV-PRO-005:7.4 -->
### 7.4 How to Estimate Volume Released

The on-call Environmental Specialist estimates the volume using one or more of the following methods (company practice):

1. **WAM nameplate volume method:** Retrieve the nameplate oil capacity (gallons) from WAM for the asset ID. Estimate the proportion that escaped based on residual oil level (dipstick reading, sight glass or visible level in tank). Volume released = nameplate capacity × (1 − residual fraction).
2. **Staining area method:** Measure the longest dimension of the stain and its perpendicular width (in feet). Estimate stain depth (in inches). Volume (gallons) = length × width × depth / 231. Apply an absorption factor of 0.7 for soil, 0.9 for pavement.
3. **Bucket/drum count method:** Count the absorbent material used (number of standard 20-gal kits deployed) and estimate saturation. Record the estimate as a range with a best-estimate.

Document the method, inputs and result in EHS-F-201 Part C (fields C-3 through C-6).

<!-- clause: RPL-ENV-PRO-005:7.5 -->
### 7.5 GIS Screening for Special Areas

The on-call Environmental Specialist screens the release location against the following GIS layers in the RPL GIS system within 1 hour of notification by the DCC. If access to GIS is unavailable, the specialist contacts the GIS duty contact or uses paper maps at the service center. Any match sets the special area flag to Y.

<!-- table: RPL-ENV-PRO-005:T7c -->

| GIS Layer | Purpose | Action if Release Is Within or Adjacent |
|---|---|---|
| ENV_WellheadProtection | Public water supply wellhead protection areas | Set special_area_flag = Y; notify IDEM and complete §9 downstream-user notification |
| ENV_PrivateWellBuffer | 100-foot buffer around mapped private wells (county records) | Set special_area_flag = Y; notify IDEM and complete §9 property-owner notification |
| ENV_SensitiveWaters | State-designated sensitive and impaired waterways | Set special_area_flag = Y; notify IDEM with receiving-water name |
| ENV_StormInlets | Municipal storm inlet locations (where available) | Set special_area_flag = Y; confirm whether the drain discharges to surface water or municipal system; report accordingly |
| ENV_Parcels | Property parcel boundaries | Used to identify affected property owners for §9 notification |

> **Note:** GIS layer names are the standard RPL layer IDs. For releases to surface water, the on-call specialist also uses the GIS `ENV_SensitiveWaters` layer to confirm whether the receiving water is a designated sensitive water body and records the waterbody name in EHS-F-201 Part D, field D-7.

<!-- clause: RPL-ENV-PRO-005:7.6 -->
### 7.6 When in Doubt

**Internal performance target:** If the on-call Environmental Specialist cannot complete the reportability determination within 1 hour of being notified by the DCC, RPL treats the release as reportable and notifies IDEM. After notification, the specialist continues to gather information and provides updates per §8.4. If the release is later confirmed non-reportable, the specialist notifies IDEM of the determination and documents the outcome in EHS-F-201 Part E, field E-5.

<!-- clause: RPL-ENV-PRO-005:8 -->
## 8. Notification to the State

All notification obligations under 327 IAC 2-6.1 are company practice per §4.1. The steps below implement RPL's compliance with that rule as company practice, with no values taken from the rule text.

<!-- clause: RPL-ENV-PRO-005:8.1 -->
### 8.1 Who Notifies

The on-call Environmental Specialist is the primary notifier. If ENV-ONCALL cannot be reached within 30 minutes, the DCC shift supervisor contacts IDEM directly and then continues to attempt to reach ENV-ONCALL and Daniel Foster (P25).

<!-- clause: RPL-ENV-PRO-005:8.2 -->
### 8.2 Channel and Office

The on-call Environmental Specialist notifies IDEM Emergency Response at **(888) 233-7745** (24-hour toll-free) or **(317) 233-7745** (direct line). Both numbers are in App-C. The specialist records the call date, time, IDEM call-taker name and IDEM incident number in EHS-F-201 Part F, fields F-1 through F-4. All notifications are verbal unless IDEM requires a written submission.

<!-- clause: RPL-ENV-PRO-005:8.3 -->
### 8.3 Timing (Company Practice)

**Internal performance target:** The on-call Environmental Specialist contacts IDEM within 2 hours of determining that a release is reportable. The clock starts when the specialist makes the reportability determination (documented in EHS-F-201 Part E, field E-1). Record the determination time and the actual IDEM call time in EHS-F-201 Part F, fields F-1 and F-2.

The timing obligation of 327 IAC 2-6.1 governs; this performance target is set more conservatively to ensure compliance. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:8.4 -->
### 8.4 Updates

When significant new information is found after the initial notification (such as a larger volume estimate, identification of a previously unknown receiving water, or a change in PCB status), the on-call Environmental Specialist provides an update to IDEM at (888) 233-7745. Record each update in EHS-F-201 Part F, fields F-5 through F-7 (date, time, information provided, IDEM call-taker). 327 IAC 2-6.1 may require updates on specific triggers; RPL provides updates for any materially new information as company practice. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:8.5 -->
### 8.5 Required Content of the Initial Notification

The on-call Environmental Specialist provides the following information in the initial IDEM call. Each element corresponds to an EHS-F-201 field.

<!-- table: RPL-ENV-PRO-005:T8 -->

| Element | EHS-F-201 Field | Notes |
|---|---|---|
| Name and contact number of the person notifying | Part F, F-2 | On-call specialist's direct cell; DCC number as backup |
| Caller's organization and position | Part F, F-2 | Rockridge Power & Light Company; role title |
| Date and time of release discovery | Part A, A-3 | From first-responder report |
| Location of the release (address, county, nearest intersection, GPS if available) | Part D, D-1 through D-3 | Lat/long method noted in D-4 |
| Source of the release (type of equipment, WAM asset ID) | Part B, B-1, B-2 | Equipment type, kVA rating, nameplate gallons |
| Substance released | Part C, C-1 | Mineral oil, diesel, hydraulic fluid, other |
| Estimated volume released | Part C, C-3 | Best estimate; method noted in C-6 |
| Estimated volume recovered | Part C, C-4 | Recovered to date at time of call |
| Receiving medium | Part D, D-5 | Soil, impervious, surface water, storm drain |
| Actions taken to stop and contain the release | Part G, G-1 | Containment method, materials deployed |
| Proximity to waterways, wells, or storm drains | Part D, D-6, D-7 | From GIS screening per §7.5 |

These elements constitute RPL's interpretation of the report content required by 327 IAC 2-6.1, applied as company practice because the full text is outside the knowledge layer. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:9 -->
## 9. Notification of Other Affected Parties

Notification obligations to third parties under 327 IAC 2-6.1 are handled as company practice. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:9.1 -->
**Downstream water users and utility operators.** When GIS screening (§7.5) identifies a release within or adjacent to ENV_WellheadProtection or ENV_SensitiveWaters, the on-call Environmental Specialist identifies downstream water intakes and public water supply operators within a reasonable downstream distance (determined by the on-call specialist based on flow and topography) by querying the GIS `ENV_Parcels` and `ENV_SensitiveWaters` layers. The specialist contacts each identified operator by phone; the call is logged in EHS-F-201 Part F, field F-9.

<!-- clause: RPL-ENV-PRO-005:9.2 -->
**Affected property owners.** When a release occurs on, or migrates to, private property other than RPL's own, the on-call Environmental Specialist identifies affected property owners using the GIS `ENV_Parcels` layer within 4 hours of the reportability determination. The specialist or a designated crew member conducts door-to-door contact, documents the outcome (contacted, not home — card left, declined contact) in EHS-F-201 Part F, field F-10, and logs each parcel ID and owner name.

<!-- clause: RPL-ENV-PRO-005:9.3 -->
**Local fire and emergency services.** When life safety or fire risk is present, the crew lead calls 911. The DCC notifies the appropriate county emergency management coordinator per RPL-EMR-PLN-001. The 911 call number or "none required" is logged in EHS-F-201 Part F, field F-11.

<!-- clause: RPL-ENV-PRO-005:9.4 -->
**Additional notifications under 327 IAC 2-6.1.** 327 IAC 2-6.1 may require notifications to additional parties in specific circumstances. RPL complies with those requirements as company practice. The on-call Environmental Specialist reviews any IDEM guidance received during the initial notification call and documents any additional contacts in EHS-F-201 Part F, field F-12. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:10 -->
## 10. Containment, Response & Cleanup

<!-- clause: RPL-ENV-PRO-005:10.1 -->
**Company practice — cleanup obligation.** RPL removes all released substance and contaminated material to the extent practicable. The on-call Environmental Specialist directs the cleanup scope.

<!-- clause: RPL-ENV-PRO-005:10.2 -->
**Contractor E activation.** When the release volume exceeds the capacity of the on-site spill kit, when the release has reached surface water, or when soil excavation is required, the on-call Environmental Specialist dispatches Contractor E (Contract RPL-C-2023-118, 24/7 contact in App-C). The Contractor E work ticket number is recorded in EHS-F-201 Part G, field G-1.

<!-- clause: RPL-ENV-PRO-005:10.3 -->
**Cleanup steps.** The on-call Environmental Specialist, in coordination with Contractor E, completes the following steps (company practice):

1. Remove and bag all free liquid using vacuum truck, absorbent pads or booms. Record quantities in EHS-F-201 Part G, fields G-2 and G-3.
2. Excavate impacted soil to visually clean native material, or to the extent practicable if sensitive media or structural constraints limit excavation.
3. Arrange for confirmation sampling by Laboratory L. Samples are collected by Contractor E under the on-call specialist's direction; submit the sample chain-of-custody (Laboratory L COC form) as an attachment to EHS-F-201 Part G, field G-5.
4. Grade, backfill and restore the excavation area using clean material. Record restoration method in EHS-F-201 Part G, field G-6.

<!-- clause: RPL-ENV-PRO-005:10.4 -->
**Cleanup obligations under 327 IAC 2-6.1.** RPL complies with all cleanup obligations imposed by 327 IAC 2-6.1. Because the full text is outside the knowledge layer, no values are stated here. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:11 -->
## 11. Follow-Up & Written Reports

<!-- clause: RPL-ENV-PRO-005:11.1 -->
**Triggers and timing under 327 IAC 2-6.1.** 327 IAC 2-6.1 may require a written follow-up report on specific triggers and within a specified time period. RPL complies with those requirements. (327 IAC 2-6.1, out_of_scope_reference) The on-call Environmental Specialist consults with Daniel Foster (P25) to confirm written-report obligations for each reportable release, based on IDEM guidance received at the time of the initial notification.

<!-- clause: RPL-ENV-PRO-005:11.2 -->
**Written copy on request.** RPL provides a copy of the completed EHS-F-201 (or a written summary consistent with any 327 IAC 2-6.1 written-report format) to any party entitled to request it under 327 IAC 2-6.1. Daniel Foster (P25) reviews all written submissions. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:11.3 -->
**RPL internal 30-day closure package (company practice).** Within 30 calendar days of the release discovery date, the on-call Environmental Specialist assembles and submits to Daniel Foster (P25) a closure package containing:

1. Completed EHS-F-201 all parts
2. Photos (uploaded to EHS-IMS)
3. Laboratory L analytical results (if sampling was required)
4. Waste manifest copies (from Hauler H) and Disposal Facility D acceptance confirmation
5. Contractor E final invoice and work summary
6. Door-to-door log (EHS-F-201 Part F, field F-10) if applicable
7. IDEM notification log (EHS-F-201 Part F, fields F-1 through F-7) and any written IDEM correspondence
8. Confirmation of compliance (see §12)

Daniel Foster (P25) reviews the package within 5 business days and signs EHS-F-201 Part H. The signed package is filed in EHS-IMS under `SPL-2024-nnnn` and in the physical spill file for record series RRS-ENV-001.

<!-- clause: RPL-ENV-PRO-005:12 -->
## 12. Close-Out

<!-- clause: RPL-ENV-PRO-005:12.1 -->
**Closure criteria (company practice).** A spill event is eligible for close-out when all of the following are satisfied:

1. The source has been permanently repaired or the failed asset has been replaced.
2. All released substance has been removed or confirmation sampling confirms residual concentrations meet the applicable cleanup standard.
3. All waste has been properly disposed of and manifests are on file.
4. All required notifications and updates have been submitted to IDEM.
5. All required written reports have been submitted.
6. The 30-day closure package (§11.3) has been reviewed and signed by Daniel Foster (P25).

<!-- clause: RPL-ENV-PRO-005:12.2 -->
**Compliance confirmation.** Where 327 IAC 2-6.1 provides for a compliance confirmation or site closure letter from IDEM, the on-call Environmental Specialist sends a written request to IDEM Emergency Response referencing the IDEM incident number from EHS-F-201 Part F, field F-4. The request and any IDEM response are filed with the closure package (RRS-ENV-001). (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:12.3 -->
**EHS-IMS close-out.** Hannah Brooks (P26) marks the EHS-IMS spill event `SPL-nnnn` as "Closed" after Daniel Foster (P25) co-signs EHS-F-201 Part H, field H-4. The closed date is recorded in the dataset field `closed_date`. Open events older than 60 calendar days without a documented reason are escalated to Sandra Kim (P24) monthly.

<!-- clause: RPL-ENV-PRO-005:13 -->
## 13. Waste Handling & Disposal

<!-- clause: RPL-ENV-PRO-005:13.1 -->
**PCB-status handling (company practice).** All waste oil, contaminated soil and absorbent material from equipment with WAM PCB status UNK, PCB-C or PCB is handled under RPL-ENV-PRO-006. The on-call Environmental Specialist contacts Daniel Foster (P25) for all PCB-uncertain or PCB-positive waste streams.

<!-- clause: RPL-ENV-PRO-005:13.2 -->
**Non-PCB waste oil and absorbents (company practice).** Waste oil from NP-T or NP-M equipment is collected in labeled containers by Contractor E and transported by Hauler H (licensed waste transporter) to Disposal Facility D (licensed non-hazardous oily waste and soil). The manifest number is recorded in EHS-F-201 Part G, field G-4.

<!-- clause: RPL-ENV-PRO-005:13.3 -->
**Waste characterization (company practice).** Waste streams that may be hazardous are characterized by Laboratory L before disposal. Characterization results are attached to the closure package. Hazardous waste is handled under RPL-ENV-PRO-007.

<!-- clause: RPL-ENV-PRO-005:14 -->
## 14. Federal & Other Notifications

<!-- clause: RPL-ENV-PRO-005:14.1 -->
RPL's federal release notification obligations (including reports to the National Response Center under CERCLA and EPCRA, and federal reportable quantity determinations under 40 CFR Part 302) are governed by 40 CFR Parts 300 and 302, and are handled exclusively under RPL-ENV-PRO-008 (Federal Release Notification Protocol). No values from those regulations are stated here, and no action under those regulations is initiated from this procedure. The on-call Environmental Specialist notifies Daniel Foster (P25) for any release that may approach a federal reportable quantity so that RPL-ENV-PRO-008 can be activated concurrently.

<!-- clause: RPL-ENV-PRO-005:15 -->
## 15. Records & Retention

<!-- table: RPL-ENV-PRO-005:T15 -->

| Record Series | Contents | Primary System | Retention |
|---|---|---|---|
| RRS-ENV-001 | EHS-F-201 Spill Reports, IDEM notification logs, IDEM correspondence, written reports, closure packages | EHS-IMS; physical file at Environmental Services office | Per RPL-LEG-RRS-001 |
| RRS-ENV-002 | Cleanup records: contractor invoices, Laboratory L analytical results, waste manifests, Hauler H manifests, Disposal Facility D acceptance confirmations | EHS-IMS; scanned to EHS-IMS | Per RPL-LEG-RRS-001 |
| RRS-ENV-003 | Spill kit inspection records (WAM work type ENV-INSP) | WAM | Per RPL-LEG-RRS-001 |
| RRS-TRN-001 | Training completion records for ENV-T-01 and HAZWOPER | EHS-IMS training module | Per RPL-LEG-RRS-001 |

> **Note:** Record retention periods are set in RPL-LEG-RRS-001, Version 7.2. Any minimum period established by 327 IAC 2-6.1 governs over RPL-LEG-RRS-001 where the regulation requires a longer period. (327 IAC 2-6.1, out_of_scope_reference)

<!-- clause: RPL-ENV-PRO-005:16 -->
## 16. Training & Drills

<!-- clause: RPL-ENV-PRO-005:16.1 -->
**Annual refresher (ENV-T-01).** All line, substation, fleet and service center personnel complete ENV-T-01 Spill Response Training annually. Training completion is recorded in EHS-IMS under RRS-TRN-001. Completion is tracked by Environmental Services; delinquencies are reported to respective supervisors by January 31 of each year.

<!-- clause: RPL-ENV-PRO-005:16.2 -->
**HAZWOPER awareness.** Personnel who may contact or work near spilled material complete HAZWOPER Awareness (40-hour or 8-hour refresher as appropriate). HAZWOPER compliance is managed under RPL-SAF-PRO-002 and is not tracked in this procedure.

<!-- clause: RPL-ENV-PRO-005:16.3 -->
**Tabletop drills.** Environmental Services conducts one tabletop spill response drill per service center per calendar year (five total). Each drill tests the 7.2 decision table, the DCC paging sequence and the IDEM notification steps. Hannah Brooks (P26) schedules the drills by March 31 of each year; Daniel Foster (P25) reviews the after-action summary. Drill records are filed under RRS-TRN-001.

<!-- clause: RPL-ENV-PRO-005:17 -->
## 17. Related Documents

| Doc ID | Title |
|---|---|
| RPL-ENV-PLN-010 | SPCC Plan — Distribution Substations |
| RPL-ENV-PLN-011 | SPCC Plan — Service Centers & Fleet Fueling |
| RPL-ENV-PRO-006 | PCB Management Procedure |
| RPL-ENV-PRO-007 | Waste Management & Disposal Procedure |
| RPL-ENV-PRO-008 | Federal Release Notification Protocol |
| RPL-SAF-PRO-002 | Electrical Safety Rulebook |
| RPL-SAF-PRO-010 | OSHA/IOSHA Recordkeeping & Reporting Procedure |
| RPL-EMR-PLN-001 | Emergency Response & Storm Restoration Plan |
| RPL-COM-PRO-002 | Media & Public Communications Procedure |
| RPL-CLM-PRO-001 | Third-Party Claims Procedure |
| RPL-LEG-RRS-001 | Records Retention Schedule |
| RPL-CMP-REG-001 | Regulatory Obligations Register |

<!-- clause: RPL-ENV-PRO-005:18 -->
## 18. Revision History

| Version | Effective | Approved | Author (Role) | Summary of Changes |
|---|---|---|---|---|
| 3.1 | 2025-03-10 | 2025-03-05 | Hannah Brooks (P26) | Updated §7.2 decision table to align with company positions from internal audit; revised App-B crew card to remove volume thresholds; added §7.5 GIS layer table; updated IDEM phone numbers to match current Table X |
| 3.0 | 2024-03-11 | 2024-03-06 | Hannah Brooks (P26) | Added standby generator belly tank source classification; revised EHS-F-201 Part B to include WAM PCB status code; added tabletop drill requirement (§16.3) |
| 2.2 | 2023-04-17 | 2023-04-10 | Senior Environmental Specialist (role) | Incorporated Contractor E 24/7 response contract; added GIS screening step; revised 30-day closure package requirement |
| 2.0 | 2021-10-05 | 2021-09-28 | Senior Environmental Specialist (role) | Full revision to align with updated company practice; added RACI; restructured reportability decision table |

<!-- clause: RPL-ENV-PRO-005:19 -->
## 19. Approval Block

| Role | Name | Title | Signature | Date |
|---|---|---|---|---|
| Prepared by (Owner) | Hannah Brooks | Senior Environmental Specialist | __________________ | 2025-03-05 |
| Reviewed by | Daniel Foster | Manager, Environmental Services | __________________ | 2025-03-05 |
| Approved by | Sandra Kim | Director, Environmental, Health & Safety | __________________ | 2025-03-05 |

*Distribution: All EHS personnel; Distribution Operations supervisors; Fleet Services supervisors; DCC shift supervisors. Maintained in DCS; distributed via EHS-IMS notification.*

---

<!-- clause: RPL-ENV-PRO-005:App-A -->
## Appendix A: EHS-F-201 Spill Report (Rev. 03/2025)

**EHS-F-201 (Rev. 03/2025)** · Rockridge Power & Light Company · Environmental Services
*Complete all applicable fields. Uncontrolled when printed — verify in DCS.*

---

### Part A — Reporter & Discovery

<!-- clause: RPL-ENV-PRO-005:App-A.F1 -->
**A-1.** Spill Event ID: `SPL-____-_______` (assigned by EHS-IMS upon opening)

<!-- clause: RPL-ENV-PRO-005:App-A.F2 -->
**A-2.** Reporter name: ___________________________________ Employee ID: _____________

<!-- clause: RPL-ENV-PRO-005:App-A.F3 -->
**A-3.** Date/time discovered: `YYYY-MM-DD` `HH:MM` ☐ AM ☐ PM

<!-- clause: RPL-ENV-PRO-005:App-A.F4 -->
**A-4.** Date/time source stopped: `YYYY-MM-DD` `HH:MM`

<!-- clause: RPL-ENV-PRO-005:App-A.F5 -->
**A-5.** Service center: ☐ LAF ☐ CRW ☐ THT ☐ FRK ☐ DAN

<!-- clause: RPL-ENV-PRO-005:App-A.F6 -->
**A-6.** How discovered: ☐ During work ☐ Patrol ☐ Customer report ☐ Third-party report ☐ Other: _______________

---

### Part B — Source & Equipment

<!-- clause: RPL-ENV-PRO-005:App-A.F7 -->
**B-1.** WAM Asset ID: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F8 -->
**B-2.** Equipment type: ☐ Pole-mount transformer ☐ Padmount transformer ☐ Substation transformer ☐ Voltage regulator ☐ Circuit breaker ☐ Standby generator ☐ Fleet vehicle ☐ Bucket truck ☐ Fueling station ☐ Other: ___________

<!-- clause: RPL-ENV-PRO-005:App-A.F9 -->
**B-3.** kVA rating (if applicable): ____________

<!-- clause: RPL-ENV-PRO-005:App-A.F10 -->
**B-4.** Nameplate oil volume (gal): ____________

<!-- clause: RPL-ENV-PRO-005:App-A.F11 -->
**B-5.** WAM PCB status code: ☐ NP-T ☐ NP-M ☐ UNK ☐ PCB-C ☐ PCB

<!-- clause: RPL-ENV-PRO-005:App-A.F12 -->
**B-6.** Label colour on equipment: ☐ Blue (non-PCB) ☐ Yellow (PCB) ☐ No label (treat as UNK)

<!-- clause: RPL-ENV-PRO-005:App-A.F13 -->
**B-7.** Cause of release: ☐ Vehicle strike ☐ Storm/wind ☐ Lightning ☐ Equipment failure ☐ Vandalism/theft ☐ Hose failure ☐ Overfill ☐ Other: _______________

---

### Part C — Substance & Volumes

<!-- clause: RPL-ENV-PRO-005:App-A.F14 -->
**C-1.** Substance: ☐ Mineral oil (dielectric fluid) ☐ Diesel ☐ Gasoline ☐ Hydraulic fluid ☐ Other: _______________

<!-- clause: RPL-ENV-PRO-005:App-A.F15 -->
**C-2.** Substance color and odor: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F16 -->
**C-3.** Estimated volume released (gal): ____________ (range: ___________ to ___________)

<!-- clause: RPL-ENV-PRO-005:App-A.F17 -->
**C-4.** Volume recovered on-site (gal): ____________

<!-- clause: RPL-ENV-PRO-005:App-A.F18 -->
**C-5.** Volume remaining in environment (gal, estimated): ____________

<!-- clause: RPL-ENV-PRO-005:App-A.F19 -->
**C-6.** Estimation method used: ☐ WAM nameplate / residual ☐ Staining area ☐ Bucket/drum count ☐ Combination: _______________

---

### Part D — Location & Pathways

<!-- clause: RPL-ENV-PRO-005:App-A.F20 -->
**D-1.** Address or nearest intersection: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F21 -->
**D-2.** County: ___________________________________ Municipality: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F22 -->
**D-3.** GPS coordinates (lat/long): ____________ N, ____________ W

<!-- clause: RPL-ENV-PRO-005:App-A.F23 -->
**D-4.** Coordinate method: ☐ GPS unit ☐ GIS lookup ☐ Map estimate

<!-- clause: RPL-ENV-PRO-005:App-A.F24 -->
**D-5.** Receiving medium: ☐ Impervious surface ☐ Soil (inside boundary) ☐ Soil (beyond boundary) ☐ Surface water ☐ Storm drain ☐ Sewer

<!-- clause: RPL-ENV-PRO-005:App-A.F25 -->
**D-6.** Distance to nearest storm drain or surface water (ft): ____________

<!-- clause: RPL-ENV-PRO-005:App-A.F26 -->
**D-7.** Receiving water body name (if applicable): ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F27 -->
**D-8.** GIS special area flag: ☐ Y ☐ N Layer(s) triggered: ___________________________________

---

### Part E — Reportability Determination

<!-- clause: RPL-ENV-PRO-005:App-A.F28 -->
**E-1.** Reportability determined by: _________________________________ Date/time: `YYYY-MM-DD` `HH:MM`

<!-- clause: RPL-ENV-PRO-005:App-A.F29 -->
**E-2.** Decision row (from §7.2 table): _____ (T7-1 through T7-6)

<!-- clause: RPL-ENV-PRO-005:App-A.F30 -->
**E-3.** RPL classification row (from §7.1 table): _____ (T7a-1 through T7a-8)

<!-- clause: RPL-ENV-PRO-005:App-A.F31 -->
**E-4.** Exclusion considered: ☐ CP-NR1 ☐ CP-NR2 ☐ None applicable — All conditions met: ☐ Yes ☐ No

<!-- clause: RPL-ENV-PRO-005:App-A.F32 -->
**E-5.** Reportable under 327 IAC 2-6.1: ☐ Yes ☐ No ☐ Uncertain — treated as Yes per §7.6

---

### Part F — Notifications Log

<!-- clause: RPL-ENV-PRO-005:App-A.F33 -->
**F-1.** IDEM initial notification date/time: `YYYY-MM-DD` `HH:MM`

<!-- clause: RPL-ENV-PRO-005:App-A.F34 -->
**F-2.** RPL notifier name and callback number: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F35 -->
**F-3.** IDEM call-taker name: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F36 -->
**F-4.** IDEM incident number: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F37 -->
**F-5.** Update 1 — date/time: __________ Information provided: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F38 -->
**F-6.** Update 2 — date/time: __________ Information provided: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F39 -->
**F-7.** Update 3 — date/time: __________ Information provided: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F40 -->
**F-8.** NRC notification (if required under RPL-ENV-PRO-008): ☐ Not required ☐ Required — handled under RPL-ENV-PRO-008; NRC confirmation no.: _______________

<!-- clause: RPL-ENV-PRO-005:App-A.F41 -->
**F-9.** Downstream water users/utilities contacted: ☐ None identified ☐ Contacted — names/organizations: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F42 -->
**F-10.** Property owners contacted (door-to-door log): ☐ None required ☐ See attached door-to-door log

<!-- clause: RPL-ENV-PRO-005:App-A.F43 -->
**F-11.** 911 / local fire called: ☐ Yes — report no.: _______________ ☐ No

<!-- clause: RPL-ENV-PRO-005:App-A.F44 -->
**F-12.** Other notifications (per IDEM guidance or §9.4): ___________________________________

---

### Part G — Response & Cleanup

<!-- clause: RPL-ENV-PRO-005:App-A.F45 -->
**G-1.** Contractor E ticket number: ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F46 -->
**G-2.** Quantity of absorbent deployed (pads, booms, pillows): ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F47 -->
**G-3.** Soil excavated (cubic yards): ____________

<!-- clause: RPL-ENV-PRO-005:App-A.F48 -->
**G-4.** Waste manifest number(s): ___________________________________

<!-- clause: RPL-ENV-PRO-005:App-A.F49 -->
**G-5.** Confirmation samples collected: ☐ Yes — Laboratory L COC no.: _______________ ☐ No (reason: _______________)

<!-- clause: RPL-ENV-PRO-005:App-A.F50 -->
**G-6.** Restoration method: ___________________________________

---

### Part H — Close-Out

<!-- clause: RPL-ENV-PRO-005:App-A.F51 -->
**H-1.** Closure criteria met (check all): ☐ Source repaired/replaced ☐ Substance removed or confirmed to standard ☐ Waste disposed, manifests on file ☐ IDEM notifications complete ☐ Written reports submitted ☐ 30-day package assembled

<!-- clause: RPL-ENV-PRO-005:App-A.F52 -->
**H-2.** Compliance confirmation requested from IDEM: ☐ Yes — date requested: _______________ ☐ No

<!-- clause: RPL-ENV-PRO-005:App-A.F53 -->
**H-3.** Compliance confirmation received: ☐ Yes — IDEM letter date: _______________ ☐ Pending ☐ Not applicable

<!-- clause: RPL-ENV-PRO-005:App-A.F54 -->
**H-4.** Sign-offs:

| Role | Name | Signature | Date |
|---|---|---|---|
| On-Call Environmental Specialist | Hannah Brooks (P26) | __________________ | _______________ |
| Manager, Environmental Services | Daniel Foster (P25) | __________________ | _______________ |

*Office use only: EHS-IMS event closed: ________________ Closed by: ________________*

---

<!-- clause: RPL-ENV-PRO-005:App-B -->
## Appendix B: Crew Quick-Reference Card

**RPL-ENV-PRO-005 App-B** · Crew Spill Response Quick Reference
*Large type — post in truck cab · Uncontrolled when printed*

---

**STEP 1 — SAFE?**
Electrical hazard? → Stay back. Call DCC at **1-800-555-0177** to request de-energization.
NO energized equipment → proceed.

**STEP 2 — ISOLATE**
Stop the flow (valve, plug, physical pressure). Do NOT approach energized equipment to contain.

**STEP 3 — CONTAIN**
Deploy truck kit (20-gal): drain covers FIRST → sock around perimeter → pads on spill body.
Do NOT wash with water. Do NOT use dispersant.

**STEP 4 — CALL DCC** (within 30 minutes of discovery)
Phone: **1-800-555-0177**
Tell them: your name · location (address/GPS/county) · equipment type · WAM asset ID · estimated gallons · substance · where it is going (soil/drain/water) · PCB label color

**STEP 5 — PHOTOGRAPH**
Photos before and after containment. Upload to EHS-IMS.

**STEP 6 — COMPLETE EHS-F-201 PARTS A–D**
At scene or within 2 hours of initial containment.

---

**DO:** Call DCC first. Use drain covers. Document everything.
**DO NOT:** Drive away. Wash spill with water. Assume it is not reportable.

---

**PCB LABEL:**
🔵 BLUE label = NP-T or NP-M (non-PCB) · 🟡 YELLOW label = PCB · No label = treat as PCB (UNK)

---

**THE ON-CALL ENVIRONMENTAL SPECIALIST DECIDES REPORTABILITY.**
Do not state to anyone that a release is or is not reportable to IDEM. Provide facts only.

---

**PHONE TREE:**

```
DCC (24/7): 1-800-555-0177
ENV-ONCALL (via DCC/OMS paging): page through DCC
IDEM Emergency Response (backup only): (888) 233-7745
Emergency / fire: 911
```

---

<!-- clause: RPL-ENV-PRO-005:App-C -->
## Appendix C: Notification Contact Sheet

**RPL-ENV-PRO-005 App-C** · Effective 2025-03-10

### External Contacts

<!-- table: RPL-ENV-PRO-005:T-AppC1 -->

| Organization | Role | Phone | Hours | Notes |
|---|---|---|---|---|
| IDEM Emergency Response | State spill notification | **(888) 233-7745** (toll-free) · **(317) 233-7745** (direct) | 24/7 | Reference IDEM incident number from F-4 on all follow-up calls |
| Emergency Services | Fire, rescue, hazmat | **911** | 24/7 | Call if life safety or fire risk |

### Internal Contacts

<!-- table: RPL-ENV-PRO-005:T-AppC2 -->

| Name / Role | Title | Contact |
|---|---|---|
| ENV-ONCALL (Hannah Brooks, P26, rotating pool) | On-Call Environmental Specialist | Page via DCC / OMS group ENV-ONCALL |
| Daniel Foster (P25) | Manager, Environmental Services | Via DCC if ENV-ONCALL unavailable; ext. 4025 during business hours |
| Sandra Kim (P24) | Director, Environmental, Health & Safety | Via P25 for escalation; ext. 4024 |
| DCC Shift Supervisor | Distribution Control Center (24/7) | **1-800-555-0177** |
| Contractor E | Emergency Response & Remediation (24/7) | Contract RPL-C-2023-118 — contact number held in EHS-IMS vendor record |

*On-call rotation: weekly, Monday 08:00 handover. Backup for ENV-ONCALL: Daniel Foster (P25). Pool: Hannah Brooks (P26) plus two Environmental Specialists (Lafayette and Terre Haute, role titles).*

---

<!-- clause: RPL-ENV-PRO-005:App-D -->
## Appendix D: Spill Kit Inventory & Locations

**RPL-ENV-PRO-005 App-D** · Company practice per §1.6 Table S · Inspected monthly (WAM ENV-INSP)

### Kit Locations

<!-- table: RPL-ENV-PRO-005:T-AppD1 -->

| Location | Kit Type | Contents | Inspection Record |
|---|---|---|---|
| Each line truck and substation truck (fleet-wide) | 20-gal truck kit | Absorbent pads, absorbent socks, drain cover, nitrile gloves, disposal bags, camera, EHS-F-201 forms | WAM ENV-INSP per vehicle |
| Lafayette (LAF) service center | 95-gal overpack kit + 100 ft containment boom; trailer SK-T1 | 95-gal overpack: pads, socks, booms, gloves, bags; SK-T1: containment boom (additional), 2 drain plugs, 55-gal drum(s), sorbent bulk | WAM ENV-INSP per kit |
| Crawfordsville (CRW) service center | 95-gal overpack kit + 100 ft containment boom | Pads, socks, booms, gloves, bags | WAM ENV-INSP |
| Terre Haute (THT) service center | 95-gal overpack kit + 100 ft containment boom | Pads, socks, booms, gloves, bags | WAM ENV-INSP |
| Frankfort (FRK) service center | 95-gal overpack kit + 100 ft containment boom | Pads, socks, booms, gloves, bags | WAM ENV-INSP |
| Danville (DAN) service center | 95-gal overpack kit + 100 ft containment boom | Pads, socks, booms, gloves, bags | WAM ENV-INSP |

> **Note:** Kit inspections are performed monthly by the service center environmental designee and recorded in WAM under work type `ENV-INSP`. Deficiencies are corrected within 5 business days of discovery and documented in WAM.

---

<!-- clause: RPL-ENV-PRO-005:App-E -->
## Appendix E: Worked Examples

Three events from `spill_events_2024.csv` illustrate the §7.1 → §7.2 → §7.3 → §8 → §9 → §12 decision sequence. All reportability determinations are company practice under 327 IAC 2-6.1 (out_of_scope_reference).

---

### Example E-1: SPL-2024-0033 — Padmount Transformer Vehicle Strike, Storm Drain (April 17, 2024)

**Facts:** At 14:22 on 2024-04-17, a delivery vehicle struck a padmount transformer at a strip-mall parking lot in Tippecanoe County, service center LAF. WAM asset ID retrieved; PCB status NP-M (blue label). Estimated 42 gallons of mineral oil released; 8 gallons recovered on-site with truck kit. Oil reached a storm drain 15 feet from the equipment.

**7.1 Classification:** Padmount transformer / facility equipment. Facility boundary is the vault slab (T7a-2, Company position). The storm drain is connected to the municipal storm system — release has reached beyond the vault slab.

**7.2 Determination:** Decision row T7-3 — release reached a storm drain. Reportable: **Yes.**

**7.3 Exclusions:** CP-NR1 not applicable (storm drain reached, condition 3 not met).

**§8 Notification:** On-call Environmental Specialist paged at 14:35; determined reportability at 14:52; contacted IDEM at 15:28 — within the 2-hour internal performance target. IDEM incident no. IDEM-ER-2024-60033 assigned. EHS-F-201 Part F, fields F-1 through F-4 completed.

**§9 Third-party notification:** GIS `ENV_WellheadProtection` layer checked — negative. Municipal utilities department notified of storm-drain entry; documented in F-9. Property owner notified at 17:00 on 2024-04-17; door-to-door log attached.

**§12 Close-out:** Contractor E dispatched at 15:40; vacuum truck removed residual oil from storm inlet. Laboratory L confirmation samples taken 2024-04-18; results confirmed no impact to receiving water. Closure package submitted 2024-05-08 (21 days). IDEM compliance confirmation requested; received 2024-05-20.

---

### Example E-2: SPL-2024-0071 — Pole-Mount Transformer Lightning Failure, Soil, PCB-Unknown (July 9, 2024)

**Facts:** At 08:55 on 2024-07-09, a line crew discovered oil on the ground at the base of a pole in Montgomery County (service center CRW) following a lightning strike. WAM PCB status: UNK (no label on transformer — treat as PCB per §3.6). Estimated 18 gallons released; approximately 10 gallons recovered with truck kit. Release on soil inside the right-of-way (inside RPL's operating boundary for this pole).

**7.1 Classification:** Pole-mount transformer; facility boundary is the pole base (T7a-1, Company position). Release is on soil inside the right-of-way — inside-boundary classification.

**7.2 Determination:** PCB status is UNK — decision row T7-5 applies (PCB-uncertain status is reportable regardless of medium). Reportable: **Yes.**

**7.3 Exclusions:** CP-NR1 not applicable (PCB status UNK, condition 4 not met).

**§8 Notification:** On-call Environmental Specialist notified by DCC at 09:10; reportability determined at 09:35 (UNK status confirmed from WAM); IDEM contacted at 10:12 — within the 2-hour internal performance target. IDEM incident no. IDEM-ER-2024-60071. Daniel Foster (P25) notified of PCB-uncertain release.

**§9 Third-party notification:** GIS layers checked — no wellhead protection or sensitive water within 500 feet. No downstream water users affected. Property: RPL right-of-way — no private property owner notification required. 911 not called (no safety hazard after de-energization).

**§12 Close-out:** Contractor E dispatched for soil sampling and confirmation. PCB sampling results confirmed NP concentration; handled as non-PCB waste per RPL-ENV-PRO-006. Closure package submitted 2024-07-30.

---

### Example E-3: SPL-2024-0088 — Bucket Truck Hydraulic Hose Failure, Impervious Surface (September 3, 2024)

**Facts:** At 11:40 on 2024-09-03, a bucket truck hydraulic hose failed in a paved service center parking lot in Vigo County (service center THT). Hydraulic fluid released. WAM PCB status: NP-T (tested non-PCB, blue label). Estimated 3.5 gallons released; 3.5 gallons recovered with truck kit on-site — full containment. Impervious surface; no storm drain within 50 feet; no special area flag.

**7.1 Classification:** Bucket truck — transportation source at worksite (T7a-7, Company position). Service center parking lot — treated as facility location.

**7.2 Determination:** Decision row T7-1 — impervious surface, fully contained (volume recovered = volume released), NP-T PCB status, no special area, no connected drain. Exclusion CP-NR1 applies.

**7.3 Exclusion:** CP-NR1 (§7.3.1) — all five conditions satisfied: (1) impervious surface confirmed; (2) 3.5 gal recovered = 3.5 gal released; (3) no drain directly connected; (4) NP-T status confirmed in WAM; (5) GIS special area flag = N. Reportable: **No.**

EHS-F-201 Parts A–E completed and filed in EHS-IMS as non-reportable. Contractor E not required. WAM work order closed; fluid disposed per RPL-ENV-PRO-007.

---

<!-- clause: RPL-ENV-PRO-005:App-F -->
## Appendix F: Data Dictionary — spill_events_2024.csv

**RPL-ENV-PRO-005 App-F** · Dataset: `data/spill_events_2024.csv` · Generator seed: 2024

<!-- table: RPL-ENV-PRO-005:T-AppF -->

| Field | Type | Unit | Allowed Values / Range | Source / Derivation | Nullable |
|---|---|---|---|---|---|
| event_id | string | — | SPL-2024-nnnn (4-digit zero-padded) | EHS-IMS sequence | No |
| discovered_ts | datetime | local time (America/Indiana/Indianapolis) | YYYY-MM-DDTHH:MM | Synthetic — within 2024 calendar year | No |
| stopped_ts | datetime | local time | YYYY-MM-DDTHH:MM | discovered_ts + 0.25–4 hours | No |
| utc_offset | string | — | -05:00 (Nov–Mar), -04:00 (Apr–Oct) | DST rule per Indiana/Indianapolis zone | No |
| service_center | string | — | LAF, CRW, THT, FRK, DAN | §1.1 service centers | No |
| county | string | — | One of 14 RPL service territory counties | §1.1 county list | No |
| source_type | string | — | pole_transformer, padmount_transformer, substation_equipment, standby_generator, fleet_vehicle, bucket_truck_hydraulic, fueling | §1.6 asset classes | No |
| rpl_classification | string | — | facility_equipment, facility_equipment_inside_boundary, facility_belly_tank, transportation_in_transit, transportation_at_worksite, facility_fuel_storage | RPL-ENV-PRO-005 §7.1 table | No |
| substance | string | — | mineral_oil, diesel, gasoline, hydraulic_fluid, other | Asset-substance pairing per §1.6 | No |
| pcb_status_code | string | — | NP-T, NP-M, UNK, PCB-C, PCB | §1.6 Table S WAM codes | No |
| volume_released_gal | decimal | US gallons | > 0; bounded by nameplate range per source_type | Triangular distribution over §1.6 nameplate ranges | No |
| volume_recovered_gal | decimal | US gallons | 0 to volume_released_gal | Triangular distribution over recovery fractions | No |
| receiving_medium | string | — | impervious, soil_inside_boundary, soil_beyond_boundary, surface_water, storm_drain, sewer | Company practice classification | No |
| special_area_flag | string | — | Y, N | GIS screening result per §7.5 | No |
| cause | string | — | vehicle_strike, storm_wind, lightning, equipment_failure, vandalism_theft, hose_failure, overfill, other | Operational taxonomy | No |
| reportable | string | — | Y, N | Computed from company-practice decision table §7.2 | No |
| decision_row | string | — | T7-1 through T7-6 | §7.2 table row | No |
| exclusion_applied | string | — | RPL-ENV-PRO-005:7.3.1, RPL-ENV-PRO-005:7.3.2, or blank | Only populated when reportable = N | Yes |
| idem_report_ts | datetime | local time | YYYY-MM-DDTHH:MM; blank if not reportable | Company practice: within 2 hours of determination | Yes |
| idem_incident_no | string | — | IDEM-ER-2024-nnnnn | Assigned by IDEM; synthetic | Yes |
| update_count | integer | — | 0, 1, 2 | Number of IDEM update calls made | No |
| third_party_notice_required | string | — | Y, N | Y when medium = surface_water or special_area_flag = Y | No |
| third_party_notice_ts | datetime | local time | YYYY-MM-DDTHH:MM | Within 4 hours of reportability determination when required | Yes |
| closed_date | date | YYYY-MM-DD | Within 2024 | Event close date in EHS-IMS | No |
| compliance_confirmation_requested | string | — | Y, N | Y when reportable = Y and medium = surface_water or storm_drain | No |

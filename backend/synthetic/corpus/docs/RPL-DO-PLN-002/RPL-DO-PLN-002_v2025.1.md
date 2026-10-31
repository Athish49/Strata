---
doc_id: RPL-DO-PLN-002
title: "Vegetation Management Plan 2025"
company: Rockridge Power & Light Company
version: "2025.1"
status: Approved
effective_date: 2025-01-27
approved_date: 2025-01-22
law_as_of: 2024-12-31
owner: {id: P22, name: Rachel Stein, title: "Manager, Vegetation Management Program"}
reviewer: {id: P21, name: Patrick O'Neill, title: "Director, Distribution Operations"}
approver: {id: P03, name: Jonathan Pierce, title: "Senior Counsel, Regulatory"}
next_review: 2026-01-22
classification: Internal
regulatory_basis:
  - "170 IAC 4-9-1"
  - "170 IAC 4-9-2"
  - "170 IAC 4-9-3"
  - "170 IAC 4-9-4"
  - "170 IAC 4-9-5"
  - "170 IAC 4-9-6"
  - "170 IAC 4-9-7"
  - "170 IAC 4-9-8"
  - "170 IAC 4-9-9"
  - "170 IAC 4-9-10"
  - "170 IAC 4-9-11"
  - "170 IAC 4-9-12"
  - "170 IAC 4-9-13"
  - "170 IAC 16-1-1"
  - "170 IAC 16-1-4"
  - "170 IAC 4-1-26"
supersedes: "2024.2 (2024-07-15)"
---

<!-- DOCUMENT CONTROL BLOCK -->
| Field | Value |
|---|---|
| **Document ID** | RPL-DO-PLN-002 |
| **Title** | Vegetation Management Plan 2025 |
| **Version** | 2025.1 |
| **Effective Date** | 2025-01-27 |
| **Approved Date** | 2025-01-22 |
| **Owner** | Rachel Stein, Manager, Vegetation Management Program (P22) |
| **Reviewer** | Patrick O'Neill, Director, Distribution Operations (P21) |
| **Approver** | Jonathan Pierce, Senior Counsel, Regulatory (P03) |
| **Classification** | Internal |
| **Supersedes** | 2024.2 (2024-07-15) |
| **Law as-of** | 2024-12-31 |

> **Uncontrolled when printed — verify the current version in DCS.**

---

## Table of Contents

1. Plan at a Glance
2. Program Goals and Strategy
3. Applicability
4. Definitions
5. Regulatory Basis
6. Roles and Responsibilities
7. Pruning and Clearance Standards
8. Trim Cycles
9. Work Planning and Execution
10. Legal Authority Before Work
11. Customer Notification for Routine Work
12. Notice for Line Voltage Changes and Expanded Work Areas
13. Tree Removal and Consent
14. Hazard Tree Program
15. Integrated Vegetation Management / Herbicide and Brush
16. Debris Handling
17. Emergency and Storm Vegetation Work
18. 69 kV Subtransmission ROW Program
19. Contractor Requirements and Quality Assurance
20. Disputes
21. Customer Education Plan
22. Reporting to the IURC
23. 2024 Program Results (Preliminary)
24. 2025 Budget
25. Performance Metrics
26. Records and Retention
27. Training
28. Related Documents
29. Revision History
30. Approval Block

**Appendices:** App-A VM-F-004 Work Notice | App-B Easement Response Letter | App-C Dispute Log Form | App-D 2025 Circuit Schedule Summary (Top 20) | App-E Clearance Specification Diagrams | App-F Data Dictionary

---

<!-- clause: RPL-DO-PLN-002:1 -->
## 1. Plan at a Glance

<!-- table: RPL-DO-PLN-002:T1 -->
| Element | 2025 Value |
|---|---|
| Circuits scheduled for routine cycle work | 111 |
| OH miles scheduled — routine cycle | 3,169.7 |
| Active distribution circuits in system | 528 |
| Total distribution OH miles | 14,200 |
| **Cycle by category** | Backbone 4 yr · Lateral 5 yr · Urban/UG-dominant 6 yr |
| **2025 total budget** | **$41,600,000** |
| Routine cycle trimming — distribution | $27,940,000 |
| Hazard tree removal | $6,180,000 |
| Herbicide / brush / mowing (IVM) | $2,580,000 |
| Mid-cycle, hot spot, customer-request | $2,020,000 |
| Storm / emergency vegetation (non-MED) | $1,490,000 |
| 69 kV subtransmission ROW | $910,000 |
| Contractor oversight, QA/QC | $390,000 |
| Customer education | $90,000 |
| **Contractors** | Contractor A (LAF/FRK/DAN service centers) · Contractor B (CRW/THT) |
| Notice filing deadline (annual report) | March 31, 2025 |
| Effective date of this plan | 2025-01-27 |
| Data extract date (2024 results) | 2025-01-15 (preliminary) |

---

<!-- clause: RPL-DO-PLN-002:2 -->
## 2. Program Goals and Strategy

<!-- clause: RPL-DO-PLN-002:2.1 -->
### 2.1 Reliability Objective

Rockridge Power & Light Company's (RPL) vegetation management program exists to reduce the frequency and duration of tree-related customer outages across 14 west-central Indiana counties. Tree-caused events accounted for 26.6 percent of RPL's system SAIFI (excluding Major Event Days) in 2024 — 0.292 customer interruptions per customer served — placing RPL within, but at the upper end of, the typical Indiana investor-owned utility range of 13–30 percent. The 2025 goal is to reduce tree SAIFI (ex-MED) to below 0.26 by directing contract crews first to circuits with the highest tree-related customer interruptions (CI) in 2024 as logged in the Outage Management System (OMS).

<!-- clause: RPL-DO-PLN-002:2.2 -->
### 2.2 Safety Objective

Every trim cycle must eliminate branches within RPL's minimum clearance envelope from energized conductors before new growth reaches those conductors. Properly cleared conductors reduce the risk of electrical contact injuries to the public, RPL line crews, and contractor arborists. RPL applies ANSI A300, the National Electrical Safety Code (NESC), the Shigo Guide, and ISA Best Management Practices on every work order. (170 IAC 4-9-7(a))

<!-- clause: RPL-DO-PLN-002:2.3 -->
### 2.3 Customer-Relations Objective

All 542 logged 2024 vegetation contacts — from routine notice questions to tree-removal disputes — are handled by the VM Program Manager (P22), the contact center, and, where escalated, a second authorized RPL representative. RPL's goal is to close 90 percent of contacts within 10 calendar days of receipt (Internal performance target) and to reduce formal dispute escalations to fewer than 30 per year.

Internal performance target: Respond to every customer vegetation contact within 1 business day of receipt; close 90 percent of contacts within 10 calendar days.

<!-- clause: RPL-DO-PLN-002:2.4 -->
### 2.4 Prioritization Logic

Rachel Stein (P22, VM Program Manager) and the Work Planners assign circuit priority ranks in the circuit schedule (field `priority_rank` in `vm_circuit_schedule_2025.csv`) using the following criteria, in order:

1. **Tree CI 2024:** Circuits with the highest number of tree-related sustained interruptions in calendar year 2024 (from OMS, field `tree_ci_2024`) receive priority 1 rankings.
2. **Cycle overdue status:** Circuits overdue by one year beyond their scheduled cycle receive a scheduling note and move ahead of circuits of the same CI score.
3. **Circuit category:** Within equal CI score, three-phase backbone circuits (which carry more customers) rank ahead of single-phase laterals.
4. **Geographic contiguity:** Contiguous circuits in the same service center are grouped to minimize contractor mobilization costs.

The 2025 schedule targets 3,169.7 OH miles across all five service centers — within 2 percent of the system-wide annual target of 3,152 OH miles derived from the §8 trim-cycle reconciliation.

<!-- clause: RPL-DO-PLN-002:2.5 -->
### 2.5 Cost Management

The 2025 total budget of $41,600,000 reflects a 0.1 percent decrease from the 2024 actual of $41,642,488. RPL controls costs by (a) bundling contiguous circuits into multi-circuit work packets, (b) competitively bidding work between Contractor A and Contractor B at each contract renewal, (c) applying herbicide under an Integrated Vegetation Management (IVM) approach to areas with rapid brush re-growth, and (d) conducting post-work quality audits on a 5 percent sample of all completed work orders.

---

<!-- clause: RPL-DO-PLN-002:3 -->
## 3. Applicability

<!-- clause: RPL-DO-PLN-002:3.1 -->
This plan applies to Rockridge Power & Light Company, an electrical public utility subject to the jurisdiction of the Indiana Utility Regulatory Commission pursuant to the provisions of the Public Service Commission Act, IC 8-1-2, that is financed by the sale of securities and whose business operations are overseen by a board representing their shareholders. It governs all vegetation management activities on RPL's distribution system (12.47 kV and 34.5 kV) and 69 kV subtransmission right-of-way within RPL's 14-county service territory. This plan does not apply to rural electric membership corporations. (170 IAC 4-9-1(a))

---

<!-- clause: RPL-DO-PLN-002:4 -->
## 4. Definitions

The following definitions apply throughout this plan. Terms marked **[IAC]** carry the meaning in 170 IAC 4-9-2 verbatim; terms marked **[CP]** are company practice.

<!-- table: RPL-DO-PLN-002:T4 -->
| Term | Definition | Source |
|---|---|---|
| **Brush** | Vegetation with stems less than six (6) inches diameter at breast height. | [IAC] 170 IAC 4-9-2(1) |
| **Business days** | Days other than Saturday, Sunday, or a legal holiday observed by the state of Indiana. | [IAC] 170 IAC 4-9-2(2) |
| **Commission** | The Indiana Utility Regulatory Commission. | [IAC] 170 IAC 4-9-2(3) |
| **Customer (notice context)** | Has the meaning set forth in 170 IAC 16-1-2(3), or may include the occupant of the property. | [IAC] 170 IAC 4-9-2(4)(A) |
| **Customer (dispute context)** | Has the meaning set forth in 170 IAC 16-1-2(3), but also includes the property owner. | [IAC] 170 IAC 4-9-2(4)(B) |
| **Emergency or storm event** | A condition dangerous or hazardous to health, life, physical safety, or property; an interruption of utility service; or the need to immediately repair or clear utility facilities; including floods, ice, snow, storms, tornadoes, winds, other acts of God, falling trees, trees causing outages, and trees showing evidence of burning or contact with conductors. | [IAC] 170 IAC 4-9-2(5) |
| **Implied consent** | The property owner or customer has not contacted RPL to deny consent within two (2) weeks after receiving notice that tree trimming will occur. | [IAC] 170 IAC 4-9-2(6) |
| **In person** | Person-to-person delivery of verbal or written notice by an authorized RPL representative; or hand delivery of a door hanger with an attempt to speak with the resident (documented in WAM). | [IAC] 170 IAC 4-9-2(7) |
| **Power line compatible vegetation** | A plant that at maturity will not reach a height greater than twelve (12) feet. | [IAC] 170 IAC 4-9-2(8) |
| **Public safety situation** | A vegetation condition that could reasonably be expected to cause imminent physical harm to electrical equipment necessary for provision of electric service; or a condition in vegetation unrelated to normal growth that would result in contact with power lines or high voltage equipment and cause imminent physical harm to the public. | [IAC] 170 IAC 4-9-2(9) |
| **Telephone call** | An attempt to contact the customer via the telephone number RPL has on file, making verbal contact or leaving a message on voicemail, answering machine, or answering service; if unsuccessful, a second attempt must be made. | [IAC] 170 IAC 4-9-2(10) |
| **Utility** | RPL, as an electrical public utility subject to IC 8-1-2, financed by sale of securities, overseen by a board representing shareholders. | [IAC] 170 IAC 4-9-2(11) |
| **Vegetation management** | The cutting or removal of vegetation or the prevention of vegetative growth to (A) maintain safe conditions around utility facilities, (B) ensure reliable electric service, or (C) prevent hazards from encroachment of vegetation on utility facilities and provide utility access to facilities. | [IAC] 170 IAC 4-9-2(12) |
| **Written notice** | Notice sent by electronic mail, U.S. mail or another mail delivery system (including inside utility bills), or in-person delivery of written notice to the customer's premises including a door hanger. | [IAC] 170 IAC 4-9-2(13) |
| **Tree** | Vegetation with stems six (6) inches DBH or greater. Contrast: "brush" is under 6 inches DBH. | [CP] company practice |
| **DBH** | Diameter at breast height, measured at 4.5 feet above ground. | [CP] company practice |
| **Side trim** | Pruning laterally to achieve minimum horizontal clearance from conductors. | [CP] company practice |
| **Under trim** | Pruning to achieve minimum vertical clearance beneath conductors. | [CP] company practice |
| **V-trim / through trim** | Pruning through the center canopy to permit the conductor to pass through the tree while maintaining clearance on both sides. | [CP] company practice |
| **Directional pruning** | Pruning technique that directs future tree growth away from conductors, as required by ANSI A300. | [CP] company practice |
| **Hazard tree** | A tree or tree part that is structurally compromised (disease, mechanical damage, root failure, or soil erosion) to the degree that it may fall onto, or contact, utility facilities. | [CP] company practice |
| **Hot spot** | A circuit section with recurring tree-related outages between scheduled trim cycles; addressed through mid-cycle intervention. | [CP] company practice |
| **Mid-cycle work** | Vegetation work performed on a circuit between full cycle trim events to address hot spots, storm damage, or customer requests. | [CP] company practice |
| **IVM** | Integrated Vegetation Management: use of mechanical, cultural, biological, and selective chemical methods to favor low-growing species that remain compatible with power-line clearances. | [CP] company practice |
| **Work planner** | RPL Distribution Operations employee who prepares lead sheets, circuit patrols, and work packets for contractor general foremen. | [CP] company practice |
| **Lead sheet** | Circuit-level document issued to the contractor general foreman specifying scope, notice batch, clearance targets, and special conditions. | [CP] company practice |

---

<!-- clause: RPL-DO-PLN-002:5 -->
## 5. Regulatory Basis

<!-- table: RPL-DO-PLN-002:T5 -->
| Citation | Heading | Governs §§ |
|---|---|---|
| 170 IAC 4-9-1 | Applicability; incorporation by reference of commission order | §3 |
| 170 IAC 4-9-2 | Definitions | §4 |
| 170 IAC 4-9-3 | Easements and rights of way | §10 |
| 170 IAC 4-9-4 | Notice requirements for routine vegetation management | §11 |
| 170 IAC 4-9-5 | Notice requirements for line upgrades | §12 |
| 170 IAC 4-9-6 | Emergency or public safety trimming | §17 |
| 170 IAC 4-9-7 | Vegetation management standards | §7, §13, §16, §22 |
| 170 IAC 4-9-8 | Dispute resolution process prior to vegetation management | §20 |
| 170 IAC 4-9-9 | Dispute resolution process during vegetation management | §20 |
| 170 IAC 4-9-10 | Dispute resolution process after vegetation management | §20 |
| 170 IAC 4-9-11 | Customer education process | §21 |
| 170 IAC 4-9-12 | Tree replacement program | §13 |
| 170 IAC 4-9-13 | Utility representative identification | §11, §19 |
| 170 IAC 16-1-1 | Scope and applicability (complaint rule) | §20 |
| 170 IAC 16-1-2 | Definitions (complaint rule) | §4, §20 |
| 170 IAC 16-1-3 | Customer dispute process; time periods | §20 |
| 170 IAC 16-1-4 | Disputes; utility responsibilities | §20, §26 |
| 170 IAC 16-1-5 | Consumer affairs review | §20 |
| 170 IAC 16-1-6 | Request for commission review | §20 |
| 170 IAC 16-1-7 | Continuation of service; undisputed charges | §20 |
| 170 IAC 4-1-26 | Line construction; variances (NESC incorporation) | §7 |
| 170 IAC 4-1-2 | Applicability of rules | §3 |

**Industry standards** (applied as company practice, consistent with 170 IAC 4-9-7(a)):
ANSI A300 (Part 1: Pruning, and Part 4: Lightning Protection) · NESC (2002 edition as incorporated at 170 IAC 4-1-26) · Shigo Guide (Modern Arboriculture) · ISA Best Management Practices.

**Out-of-scope references** (statute or federal rule; no values stated; RPL complies):

<!-- clause: RPL-DO-PLN-002:5.1 -->
- OSHA 29 CFR 1910.269 (Electric power generation, transmission, and distribution — Line-clearance tree trimming): RPL requires that all contractor crews performing line-clearance tree trimming comply with this federal regulation. Covered as company contractual requirement; not assessed under this IAC scope. (clause type: out_of_scope_reference)

<!-- clause: RPL-DO-PLN-002:5.2 -->
- Indiana pesticide use regulations (Office of the Indiana State Chemist): Licensed applicators apply EPA-registered herbicide products under all applicable Indiana pesticide registration requirements. (clause type: out_of_scope_reference)

<!-- clause: RPL-DO-PLN-002:5.3 -->
- NERC FAC-003 (Transmission Vegetation Management): Not applicable — RPL owns no Bulk Electric System transmission facilities. RPL's highest voltage is 69 kV subtransmission, which is below the BES threshold. (clause type: out_of_scope_reference)

---

<!-- clause: RPL-DO-PLN-002:6 -->
## 6. Roles and Responsibilities

<!-- table: RPL-DO-PLN-002:T6 -->
| Role | Person / Title | Responsible (R) | Accountable (A) | Consulted (C) | Informed (I) |
|---|---|---|---|---|---|
| VM Program Manager | Rachel Stein, P22 | Planning, execution, budgeting, reporting | IURC filings | P21, P17, P03 | All stakeholders |
| Director, Distribution Operations | Patrick O'Neill, P21 | Reviewer of plan and dispute escalations | Overall program | P22, P23 | — |
| Senior Counsel, Regulatory | Jonathan Pierce, P03 | Approver; legal interpretation; IURC correspondence | Legal authority | P22 | — |
| Manager, Customer Advocacy | Brian Kowalski, P17 | Customer contact escalations; complaint coordination | — | P22 | Dispute log |
| Manager, DCC | Kevin Adeyemi, P23 | Storm-event VM dispatch; emergency restoration vegetation | — | P22 | Storm VM work |
| Contractor A General Foreman | (title) | Crew execution, LAF/FRK/DAN service centers | — | P22 | Lead sheets |
| Contractor B General Foreman | (title) | Crew execution, CRW/THT service centers | — | P22 | Lead sheets |
| RPL Work Planners / Foresters | (title) | Circuit patrols, lead sheets, notice batches, WAM entry | — | P22 | — |
| Contact Center (RPL) | (title, Customer Operations) | Receive customer vegetation contacts; log in CIS | — | P17, P22 | Daily queue |

---

<!-- clause: RPL-DO-PLN-002:7 -->
## 7. Pruning and Clearance Standards

<!-- clause: RPL-DO-PLN-002:7.1 -->
### 7.1 Required Industry Standards

RPL, its agents, and contractors shall apply and adhere to the guidelines of: (1) American National Standards Institute ANSI A300; (2) the National Electric Safety Code; (3) the Shigo Guide; and (4) the International Society of Arboriculture Best Management Practices. (170 IAC 4-9-7(a))

The NESC 2002 edition is incorporated by reference into 170 IAC 4-1-26 for overhead construction. RPL applies its clearance requirements at all times.

<!-- clause: RPL-DO-PLN-002:7.2 -->
### 7.2 Clearance Considerations

There is not a uniform clearance requirement, but line clearances should take into consideration the: (1) characteristics of the locality; (2) electrical facility; and (3) health of the tree. (170 IAC 4-9-7(b))

RPL's clearance specification (company practice) below implements this requirement. Clearances represent minimum clear distance at the time of trim, with sufficient margin to maintain safe clearance for the full cycle period. Fast-growing species receive greater initial clearance to account for projected growth over the cycle.

<!-- clause: RPL-DO-PLN-002:7.3 -->
### 7.3 RPL Clearance Specification Table (Company Practice)

<!-- table: RPL-DO-PLN-002:T7 -->
| Voltage Class | Direction | Species Growth Class | Minimum Clear Distance (ft) | Basis (Growth Years) |
|---|---|---|---|---|
| 69 kV subtransmission | Side | Fast | 15 | 5-yr cycle |
| 69 kV subtransmission | Side | Slow | 10 | 5-yr cycle |
| 69 kV subtransmission | Under | Fast | 12 | 5-yr cycle |
| 69 kV subtransmission | Under | Slow | 8 | 5-yr cycle |
| 34.5 kV primary | Side | Fast | 12 | 4–5-yr cycle |
| 34.5 kV primary | Side | Slow | 8 | 4–5-yr cycle |
| 34.5 kV primary | Under | Fast | 10 | 4–5-yr cycle |
| 12.47 kV three-phase backbone | Side | Fast | 10 | 4-yr cycle |
| 12.47 kV three-phase backbone | Side | Slow | 6 | 4-yr cycle |
| 12.47 kV three-phase backbone | Under | Fast | 8 | 4-yr cycle |
| 12.47 kV three-phase backbone | Under | Slow | 5 | 4-yr cycle |
| 12.47 kV single-phase lateral | Side | Fast | 8 | 5-yr cycle |
| 12.47 kV single-phase lateral | Side | Slow | 5 | 5-yr cycle |
| 12.47 kV single-phase lateral | Under | Fast | 6 | 5-yr cycle |
| Secondary / service drop | Side / Under | All | 3 | —  |

**Notes:** "Fast" growth class includes silver maple, cottonwood, willow, and similar species. "Slow" includes oak, hickory, walnut, and similar. Final determination of growth class and species on any given circuit is made by the RPL Work Planner or an ISA Certified Arborist on the contractor crew. Locality factors (urban canopy, agricultural open, wooded corridor) may increase target clearance by up to 3 feet per crew foreman judgment.

<!-- clause: RPL-DO-PLN-002:7.4 -->
### 7.4 Over-25% Canopy Rule

Except in situations of emergency or public safety, if a tree would have more than twenty-five percent (25%) of its canopy removed, RPL or its contractor shall: (1) obtain consent from the property owner; or (2) if the property owner and RPL cannot mutually agree on how the tree can be trimmed to provide sufficient clearance, RPL shall either remove the tree at RPL's expense (provided RPL has secured the requisite easements) or inform the customer that non-ANSI-standard cuts will be necessary to provide clearance. (170 IAC 4-9-7(c))

<!-- clause: RPL-DO-PLN-002:7.5 -->
### 7.5 Brush Removal

Brush under or near RPL's electrical facilities may be removed by RPL without the consent of the customer only when its removal is necessary for safe and reliable service. (170 IAC 4-9-7(d))

---

<!-- clause: RPL-DO-PLN-002:8 -->
## 8. Trim Cycles

<!-- clause: RPL-DO-PLN-002:8.1 -->
### 8.1 Cycle Assignments (Company Practice)

<!-- table: RPL-DO-PLN-002:T8A -->
| Circuit Category | vm_category Code | Cycle (years) | Rationale |
|---|---|---|---|
| Three-phase backbone circuits (12.47 kV and 34.5 kV) | `backbone` | 4 | Higher load density, greater CI per outage, fast-growth corridor exposure |
| Single-phase lateral circuits | `lateral_dominant` | 5 | Lower load density; leaf-off access allows efficient two-season scheduling |
| Urban / UG-dominant distribution circuits | `urban_ug_dominant` | 6 | Lower overhead exposure; significant underground segment reduces OH risk |
| 69 kV subtransmission ROW | (separate program, §18) | 5 | NESC clearance requirements; ROW corridor management |

Cycle length affects both the target clearance distance and the expected change in tree appearance between trims. Longer cycles require greater initial clearance and more significant visual impact at each trim event. RPL explains this trade-off to customers in the work notice (App-A, field F8) and the customer education program (§21). (170 IAC 4-9-11(6))

<!-- clause: RPL-DO-PLN-002:8.2 -->
### 8.2 Annual Miles Reconciliation

<!-- table: RPL-DO-PLN-002:T8B -->
| Category | Total OH Miles | Cycle (yr) | Annual Target (mi/yr) | 2025 Scheduled (mi) |
|---|---|---|---|---|
| backbone | 6,564 | 4 | 1,641 | 1,641 (est.) |
| lateral_dominant | 7,133 | 5 | 1,427 | 1,445 (est.) |
| urban_ug_dominant | 503 | 6 | 84 | 84 (est.) |
| **Total distribution** | **14,200** | — | **3,152** | **3,170** |

Note: Total source: circuits_master.csv, 528 distribution circuits. The 2025 schedule of 3,170 OH miles is within 2 percent of the 3,152 mi/yr annual target. Minor overrun in lateral miles is due to prioritization of high-CI circuits.

> Gap RPL-DO-PLN-002-G001: The T04 operational master sets last_trim_year identically for all circuits in each category (backbone=2021, lateral=2020, urban=2019), making all 425 eligible circuits due simultaneously in 2025. RPL's 2025 schedule is capacity-constrained to ~111 circuits representing the annual target miles. Remaining eligible circuits are scheduled for 2026 through the normal cycle rotation. This gap is documented for QA review.

---

<!-- clause: RPL-DO-PLN-002:9 -->
## 9. Work Planning and Execution

<!-- clause: RPL-DO-PLN-002:9.1 -->
### 9.1 Annual Planning

By October 31 each year, Rachel Stein (P22) publishes the draft circuit schedule for the following calendar year to Patrick O'Neill (P21) for review. The schedule is entered into WAM (work type `VM-CYCLE`) by November 30 and forms the basis for contractor notice batch generation (§11).

<!-- clause: RPL-DO-PLN-002:9.2 -->
### 9.2 Circuit Patrol and Lead Sheet Preparation

Before work begins on any circuit, an RPL Work Planner conducts a circuit patrol (walking or vehicle, recorded in WAM as `VM-PATROL`) to:
(a) identify trees at or near conductor clearance, hazard trees, and conditions requiring special handling;
(b) confirm road access and traffic-control needs;
(c) note sensitive areas (schools, cemeteries, historic districts);
(d) identify communications attacher make-ready requirements.

The Work Planner prepares a lead sheet for each circuit work packet, which the contractor general foreman must acknowledge in WAM before mobilizing. The lead sheet includes: circuit ID, estimated OH miles in scope, special clearance instructions, notice batch ID (VMN-2025-###), any identified hazard trees, and debris handling notes.

<!-- clause: RPL-DO-PLN-002:9.3 -->
### 9.3 Hours of Work (Company Practice)

Routine cycle trimming is performed between 07:00 and 18:00 local time, Monday through Friday. Saturday work requires advance approval from P22. Work near schools or residential areas in excess of normal traffic is coordinated with the applicable county highway or municipal street department.

<!-- clause: RPL-DO-PLN-002:9.4 -->
### 9.4 Communications Attacher Coordination

Before trimming circuits with joint-use poles, the Work Planner notifies registered communications attachers (as listed in GIS layer `POLE_ATTACHMENTS`) at least 5 business days before the scheduled start date. Coordination records are filed in WAM under the work order for the circuit.

<!-- clause: RPL-DO-PLN-002:9.5 -->
### 9.5 Identification Requirement

All employees and contractors performing vegetation management or in-person notification for vegetation management on behalf of RPL shall carry identification and provide it for inspection by the customer upon request. (170 IAC 4-9-13) Contractor crew IDs must bear the contractor's company name and employee name and must be presented upon any customer request.

---

<!-- clause: RPL-DO-PLN-002:10 -->
## 10. Legal Authority Before Work

<!-- clause: RPL-DO-PLN-002:10.1 -->
### 10.1 Required Authority

RPL must have or obtain the following legal authority prior to trimming vegetation, and must provide documentation in accordance with §10.2: (1) easements; (2) rights of way; (3) statutory authority; (4) other legal authority; or (5) the express or implied consent of the property owner or customer. RPL's ability to secure a prescriptive easement may be presented to the customer to obtain consent, but is not independent legal authority. This rule does not modify property rights. (170 IAC 4-9-3(a))

<!-- clause: RPL-DO-PLN-002:10.2 -->
### 10.2 Easement Documentation Response

Upon request by the customer within five (5) business days of the customer's receipt of the notice required under §11, RPL will provide one of the following prior to vegetation management: (1) a copy of the easement or public right-of-way document that gives RPL the legal right to enter the customer's property to perform vegetation management; or (2) if an easement or public right-of-way document is not reasonably available, a copy of the authority that gives RPL the legal right to enter. (170 IAC 4-9-3(b))

Rachel Stein (P22) or the assigned Work Planner responds to easement documentation requests within 4 business days (Internal performance target) using the App-B Easement Response Letter template. The request and response are logged in WAM under the relevant notice batch and in the vegetation dispute log (RRS-DO-002).

---

<!-- clause: RPL-DO-PLN-002:11 -->
## 11. Customer Notification for Routine Work

<!-- clause: RPL-DO-PLN-002:11.1 -->
### 11.1 Notice Timing

At least two (2) calendar weeks prior to engaging in routine vegetation management, RPL must provide notice to customers and property owners whose vegetation will be subject to the vegetation management, except where: (1) RPL has a written easement, government permit, contractual agreement, or court order that expressly gives RPL the right to conduct vegetation management; or (2) an emergency or storm event occurs. (170 IAC 4-9-4(a))

<!-- clause: RPL-DO-PLN-002:11.2 -->
### 11.2 Required Notice Methods

RPL must provide notice to a customer in the following manner: (1) at least one (1) attempt to contact must be in person or via telephone call; and (2) at least one (1) attempt to contact must include written notice. (170 IAC 4-9-4(b))

<!-- clause: RPL-DO-PLN-002:11.3 -->
### 11.3 Notice Sequence (Company Practice)

<!-- table: RPL-DO-PLN-002:T11 -->
| Step | Method | Timing | Actor | Content | Record |
|---|---|---|---|---|---|
| 1 | VM-F-004 letter (written notice) mailed | ≥21 calendar days before work start (Internal; regulatory minimum is 14 days) | Work Planner / notice vendor | All §11.4 and §11.5 elements | WAM VMN batch; RRS-DO-002 |
| 2 | Door hanger (in-person written notice) | 3 calendar days before work start (Internal) | Contractor crew member with ID | Door-hanger version of VM-F-004; all required elements | WAM daily log entry |
| 3 | Day-of phone call (if customer contact requested) | Day of work; per §11.6 | Contractor crew supervisor | Estimated time of work on that circuit | WAM |

<!-- clause: RPL-DO-PLN-002:11.4 -->
### 11.4 Required Written and In-Person Notice Content

Written and in-person notice shall include, at minimum, the following information: (1) the fact that vegetation management is scheduled to occur; (2) an explanation of what vegetation management is and why it is necessary for safe and reliable electric service; (3) the fact that non-property owners living or working on the property are strongly encouraged to notify the property owner that vegetation management is scheduled; (4) the fact that receipt of the notice by the occupant initiates the two (2) week window for calculating implied consent; (5) the estimated date that vegetation management is scheduled to occur; and (6) contact information including, at a minimum, a telephone number for an authorized RPL representative who can answer customer inquiries related to vegetation management. (170 IAC 4-9-4(c))

<!-- clause: RPL-DO-PLN-002:11.5 -->
### 11.5 Additional Written Notice Content

Written notice will also include the following: (1) the heading "TREE TRIMMING NOTICE"; (2) the date the written notice was hand-delivered or mailed; (3) the website address of the commission's vegetation management administrative rule; (4) the commission's website at http://www.in.gov/iurc; (5) RPL's vegetation management website address (www.rockridge-pl.example); (6) a reference to an educational resource for planting around electrical facilities, including the Arbor Day Foundation's right tree, right place program and its website address; (7) a website address and telephone number for customers to obtain the name of the contractor that will deliver the in-person notice or conduct vegetation management; and (8) a statement that RPL's representative shall carry identification when delivering the in-person notice or conducting vegetation management. (170 IAC 4-9-4(d))

<!-- clause: RPL-DO-PLN-002:11.6 -->
### 11.6 Estimated-Day Request

The customer may, within three (3) calendar days of receiving the notice in §11.1, request RPL provide the estimated day that vegetation management is expected to occur. RPL will then provide the estimated day at least three (3) business days prior to engaging in vegetation management. If the customer requests a more specific time, the supervisor shall endeavor to work with the customer to give a precise time. (170 IAC 4-9-4(e))

When a customer calls 1-800-555-0142 to request an estimated day, the contact center representative records the request in CIS (category code `VEG`) and routes it to P22's team within 4 business hours (Internal performance target). P22 or the Work Planner provides the response and documents it in WAM under the notice batch (VMN-2025-###).

<!-- clause: RPL-DO-PLN-002:11.7 -->
### 11.7 Property Owner Notice by Publication

RPL must provide notice to a property owner by publishing notice in at least one (1) newspaper of general circulation in the county in which the property is located. Published notice must include: (1) the fact that vegetation management is scheduled; (2) the area of vegetation management by street name and block, subdivision name, intersecting roads, or specific address; (3) the fact that publication initiates the two (2) week window for calculating implied consent; (4) the estimated date; and (5) contact information for an authorized RPL representative. (170 IAC 4-9-4(f)) The property owner has three (3) calendar days from publication to request a specific estimated day; RPL provides that day at least three (3) business days before work. (170 IAC 4-9-4(g))

<!-- clause: RPL-DO-PLN-002:11.8 -->
### 11.8 Notice Checklist

Work Planners use the following checklist before releasing any circuit for contractor mobilization:

- [ ] VM-F-004 letter mailed ≥21 days before planned start date (record date in WAM)
- [ ] Door-hanger run scheduled 3 days before start date
- [ ] County newspaper notice published for all affected areas
- [ ] Easement documentation requests checked against §10.2 response window
- [ ] Notice batch ID (VMN-2025-###) entered in WAM and circuit schedule
- [ ] Contractor crew ID compliance confirmed (§9.5)

---

<!-- clause: RPL-DO-PLN-002:12 -->
## 12. Notice for Line Voltage Changes and Expanded Work Areas

<!-- clause: RPL-DO-PLN-002:12.1 -->
### 12.1 Timing and Trigger

At least sixty (60) calendar days prior to changing a distribution or transmission line to a higher voltage level, RPL must give notice to the affected customer if the change in the line will change the area in which vegetation management will be necessary as a result of safe clearance requirements. (170 IAC 4-9-5(a))

<!-- clause: RPL-DO-PLN-002:12.2 -->
### 12.2 Notice Method

Notice shall be provided in the same manner as §11.2 (at least one in-person or telephone contact and at least one written notice). (170 IAC 4-9-5(b))

<!-- clause: RPL-DO-PLN-002:12.3 -->
### 12.3 Required Content for Line Upgrade Notice

Notice shall include, at minimum: (1) the fact that line upgrades are scheduled; (2) an explanation of what line upgrades are; (3) why line upgrades are necessary for safe and reliable service; (4) encouragement to notify property owner; (5) estimated date; (6) estimated length of time construction will continue; (7) new vegetation restrictions on the property as a result of the line upgrades; (8) changes to the property owner's easement or right-of-way as a result; and (9) contact information for an authorized RPL representative. (170 IAC 4-9-5(c))

Rachel Stein (P22) coordinates with the Construction & Engineering group to generate voltage-upgrade notices at least 60 calendar days before scheduled construction start. Notices are issued under form VM-F-004 (voltage-upgrade variant) and recorded in WAM and in RRS-DO-002.

---

<!-- clause: RPL-DO-PLN-002:13 -->
## 13. Tree Removal and Consent

<!-- clause: RPL-DO-PLN-002:13.1 -->
### 13.1 Over-25% Consent Requirement

Except in emergencies or public safety situations, if a tree would have more than twenty-five percent (25%) of its canopy removed, RPL or its contractor shall obtain consent from the property owner. (170 IAC 4-9-7(c)(1)) The contractor general foreman documents consent in WAM (work order note type `CONSENT-OBTAINED`) before commencing over-25% canopy removal.

<!-- clause: RPL-DO-PLN-002:13.2 -->
### 13.2 Non-Agreement Path

If the property owner and RPL cannot mutually agree on how the tree can be trimmed to provide sufficient clearance, RPL shall take one of the following actions: (A) remove the tree, at RPL's expense, as long as RPL has secured the requisite easements; or (B) inform the customer that non-ANSI-standard cuts will be necessary to provide clearance. (170 IAC 4-9-7(c)(2)) The Work Planner documents the non-agreement path chosen in WAM (work type `VM-NONCONSENT`), and P22 is notified within 1 business day.

<!-- clause: RPL-DO-PLN-002:13.3 -->
### 13.3 Stump Treatment (Company Practice)

When RPL removes a tree at its expense, the contractor grinds stumps to at least 4 inches below grade and backfills the depression with topsoil. Chemical stump treatment may be used as an alternative where soil conditions make mechanical grinding impractical, using an EPA-registered product applied by a licensed pesticide applicator.

<!-- clause: RPL-DO-PLN-002:13.4 -->
### 13.4 Tree Replacement Program

Where a tree is removed, RPL may offer the customer: (1) a power line compatible vegetation; (2) another replacement plant; or (3) monetary compensation or credit at an amount agreed to by the parties; provided that the customer agrees not to plant a tree that will encroach into RPL's facilities at a future date and consents to removal by RPL if such a tree is planted. (170 IAC 4-9-12) P22 administers the replacement program; offers are documented in WAM under work type `VM-REPLACE` and in RRS-DO-002.

---

<!-- clause: RPL-DO-PLN-002:14 -->
## 14. Hazard Tree Program

<!-- clause: RPL-DO-PLN-002:14.1 -->
### 14.1 Identification

RPL Work Planners and contractor crews identify hazard trees through: (a) pre-trim circuit patrols (WAM work type `VM-PATROL`); (b) OMS event analysis after tree-related outages; (c) GIS aerial/LiDAR imagery review (generic layer `VM_CANOPY`) where available; and (d) customer and employee reports. An ISA Certified Arborist (contractor staff) makes the final hazard assessment.

<!-- clause: RPL-DO-PLN-002:14.2 -->
### 14.2 Risk Tiers and Response Targets (Company Practice)

<!-- table: RPL-DO-PLN-002:T14 -->
| Risk Tier | Criteria | Response Target |
|---|---|---|
| Tier 1 — Imminent | Tree or part in contact with or within 3 ft of energized conductor; burn marks; leaning conductor contact | Remove or make safe within 24 hours of identification (Internal performance target) |
| Tier 2 — High | Significant structural defect; lean ≥30°; root plate lift; large dead branches over conductor ROW | Dispatch within 5 business days; complete removal within 30 calendar days (Internal performance target) |
| Tier 3 — Moderate | Declining health; minor structural issue; brush encroachment | Include in next scheduled trim cycle or mid-cycle program |

<!-- clause: RPL-DO-PLN-002:14.3 -->
### 14.3 Outside-ROW Trees

Hazard trees outside RPL's ROW but posing a risk to facilities are addressed as follows: (a) RPL contacts the property owner in writing using the App-B letter format within 5 business days of identification; (b) if the property owner agrees to removal, RPL coordinates removal and may offer the tree replacement program (§13.4); (c) if the property owner declines, P22 escalates to P03 (Jonathan Pierce) for legal review within 10 business days. Outside-ROW hazard tree interactions are logged in WAM under work type `VM-HAZARD-EXT` and in RRS-DO-002.

---

<!-- clause: RPL-DO-PLN-002:15 -->
## 15. Integrated Vegetation Management / Herbicide and Brush

<!-- clause: RPL-DO-PLN-002:15.1 -->
### 15.1 IVM Methods

RPL applies an Integrated Vegetation Management (IVM) approach in targeted areas — primarily ROW corridors, substation yards, and brushy re-growth zones adjacent to lines. IVM methods used, in order of preference: mechanical mowing and cut-stump treatment; selective herbicide application to favor low-growing species; biological agents where available and approved. Brush removal is performed without customer consent where necessary for safe and reliable service. (170 IAC 4-9-7(d))

<!-- clause: RPL-DO-PLN-002:15.2 -->
### 15.2 Herbicide Application (Company Practice)

RPL's IVM contractor uses only EPA-registered herbicide products applied by licensed pesticide applicators under the applicable Indiana Office of the Indiana State Chemist registration requirements (out-of-scope reference, §5.2). No specific product names are listed in this plan; the current approved-product list is maintained by P22 and updated annually before the herbicide season.

<!-- clause: RPL-DO-PLN-002:15.3 -->
### 15.3 Sensitive Area Exclusions (Company Practice)

Herbicide application is prohibited within 25 feet of: open water, sinkholes, karst features, identified private wells (GIS layer `ENV_PrivateWellBuffer`), organic farming operations, and school or playground property. The Work Planner marks exclusion zones on the lead sheet before each IVM contract.

<!-- clause: RPL-DO-PLN-002:15.4 -->
### 15.4 Efficacy Audits (Company Practice)

P22 reviews IVM treatment results at 6-month and 24-month post-treatment intervals (OMS tree CI on treated circuits vs. pre-treatment baseline). Results are summarized in the annual program report (§22, §23).

---

<!-- clause: RPL-DO-PLN-002:16 -->
## 16. Debris Handling

<!-- clause: RPL-DO-PLN-002:16.1 -->
### 16.1 Routine Debris Removal

Debris associated with routine maintenance, in a maintained area, absent intervening inclement weather that may pull crews from maintenance activities, shall be removed within three (3) calendar days or left on the property as agreed to in writing by the owner. (170 IAC 4-9-7(e))

The contractor general foreman is responsible for confirming debris clearance within 3 calendar days of trim completion. The Work Planner performs a debris-clearance audit at the end of each month and records results in WAM. Any circuit with uncleared debris beyond 3 days is escalated to P22 within 1 business day.

<!-- clause: RPL-DO-PLN-002:16.2 -->
### 16.2 Storm Debris

Utilities and their agents and contractors are not required to clear debris caused by storms and other natural occurrences like tree failures. (170 IAC 4-9-7(f))

RPL Contact Center agents inform customers asking about storm debris that RPL has no regulatory obligation to remove storm-caused debris; agents provide the applicable county solid-waste hotline number as a courtesy.

<!-- clause: RPL-DO-PLN-002:16.3 -->
### 16.3 Wood and Chip Requests (Company Practice)

Property owners may request to retain trimmed wood or chip piles by calling 1-800-555-0142 before the scheduled trim date. Requests are logged in CIS (category `VEG`) and communicated to the contractor general foreman via the lead sheet. RPL does not guarantee chip availability; wood piles are available first-come, first-served.

---

<!-- clause: RPL-DO-PLN-002:17 -->
## 17. Emergency and Storm Vegetation Work

<!-- clause: RPL-DO-PLN-002:17.1 -->
### 17.1 Definition and Authorization

In cases of emergency or public safety, utilities may, without customer consent, remove more than twenty-five percent (25%) of a tree or trim beyond existing easement or right-of-way boundaries in order to remedy the emergency or public safety situation. (170 IAC 4-9-6) Kevin Adeyemi (P23, DCC Manager) authorizes emergency vegetation work during storm restoration events through the OMS event management system.

<!-- clause: RPL-DO-PLN-002:17.2 -->
### 17.2 DCC Dispatch Procedure

1. The DCC shift supervisor (P23's designee) issues a WAM emergency work order (type `VM-EMRG`) as soon as a tree-contact outage or hazard is confirmed in OMS.
2. The DCC pages the contractor general foreman on call via OMS paging group `VM-EMRG-CALL` or calls 1-800-555-0142 (VM dispatch line).
3. The contractor clears the hazard without advance customer notice; a post-clearance notification is left at the affected address within 24 hours using the emergency VM notification card.
4. The DCC shift supervisor records the event in OMS (cause code `VEG`) and notifies P22 by the next business day.

<!-- clause: RPL-DO-PLN-002:17.3 -->
### 17.3 Notice and Standards During Emergencies

Notice requirements (§11) and the 25% canopy consent requirement (§13.1) are suspended during an emergency or storm event as defined in 170 IAC 4-9-2(5). ANSI A300 best pruning practices still apply to the extent practicable given the emergency conditions.

<!-- clause: RPL-DO-PLN-002:17.4 -->
### 17.4 Post-Storm Follow-Up

Within 5 business days after a declared storm event (MED or non-MED), P22 reviews OMS tree-CI events associated with the storm and flags circuits requiring mid-cycle follow-up trim (WAM work type `VM-MID`). Circuits flagged for mid-cycle work enter the hot-spot queue for the next available contractor slot.

---

<!-- clause: RPL-DO-PLN-002:18 -->
## 18. 69 kV Subtransmission ROW Program

<!-- clause: RPL-DO-PLN-002:18.1 -->
### 18.1 ROW Inventory

RPL owns 418 circuit miles of 69 kV subtransmission lines in west-central Indiana. The 69 kV ROW program is budgeted separately at $910,000 in 2025 (capital), reflecting ROW widening, floor management, and annual inspection.

<!-- clause: RPL-DO-PLN-002:18.2 -->
### 18.2 ROW Widths (Company Practice)

| Setting | Target ROW Width (each side of centerline) |
|---|---|
| Agricultural / open | 40 feet |
| Wooded corridor | 60 feet |
| Within 100 ft of substation | 75 feet |

<!-- clause: RPL-DO-PLN-002:18.3 -->
### 18.3 Inspection and Cycle (Company Practice)

The 69 kV ROW is inspected on foot or by helicopter once per calendar year (Internal performance target). The floor management (mowing, brush, and herbicide) cycle is 5 years for the corridor interior, with annual spot treatment as needed. The Work Planner schedules ROW work with Contractor B (THT service center as base) in Q2 and Q3 to take advantage of growing-season visibility.

<!-- clause: RPL-DO-PLN-002:18.4 -->
### 18.4 Access

69 kV ROW access is coordinated with landowners where recorded easement documents are not on file. The Work Planner requests access at least 10 business days before scheduled ROW work and documents landowner acknowledgment in WAM (work type `VM-ROW-ACCESS`).

---

<!-- clause: RPL-DO-PLN-002:19 -->
## 19. Contractor Requirements and Quality Assurance

<!-- clause: RPL-DO-PLN-002:19.1 -->
### 19.1 Qualifications

Contractor A and Contractor B are required by contract to maintain: (a) line-clearance qualified crews per OSHA 29 CFR 1910.269 (§5.1); (b) at least one ISA Certified Arborist on staff for each active RPL work order; (c) current general liability, workers' compensation, and commercial auto insurance at RPL-specified limits; and (d) all required state and local pesticide applicator licenses for IVM crews.

<!-- clause: RPL-DO-PLN-002:19.2 -->
### 19.2 Crew Audits

P22 or a designated RPL Forester conducts random crew audits during active trim operations. The audit rate target is 5 percent of all WAM work orders per quarter (Internal performance target). Audits check: ANSI A300 pruning technique, clearance distance achieved, identification compliance (§9.5), debris handling, and lead-sheet accuracy.

<!-- clause: RPL-DO-PLN-002:19.3 -->
### 19.3 Post-Work Audit Sample

Within 30 calendar days of circuit completion, RPL performs a post-work quality audit on a minimum 5 percent random sample of completed circuits (Internal performance target). Audit pass criteria: ≥90 percent of randomly selected trim points within 10 percent of target clearance; zero debris non-compliance; zero identification violations.

<!-- clause: RPL-DO-PLN-002:19.4 -->
### 19.4 Contractor KPIs

<!-- table: RPL-DO-PLN-002:T19 -->
| KPI | Definition | 2025 Target | Consequence of Miss |
|---|---|---|---|
| Post-work audit pass rate | Circuits passing post-work audit ÷ total audited | ≥90% | Warning letter; remediation plan within 10 days |
| Debris compliance rate | Work orders with debris cleared within 3 calendar days ÷ total | ≥98% | Invoice deduction per non-compliant circuit |
| Crew ID compliance | Crew member IDs presented on first customer request ÷ requested | 100% | Crew suspension pending re-orientation |
| Notice lead compliance | Circuits with notice letter ≥14 days before work start ÷ total | 100% | Work stoppage; re-notice required |
| Completed miles vs. plan | Actual OH miles completed ÷ planned OH miles | ≥95% | Monthly performance review with P21 |

<!-- clause: RPL-DO-PLN-002:19.5 -->
### 19.5 Invoicing Controls

Contractor invoices are reviewed by the Work Planner against WAM completion records before payment approval. Disputed invoice items are flagged to P22 within 5 business days. No payment is made for circuits where post-work audit failed until remediation is confirmed.

---

<!-- clause: RPL-DO-PLN-002:20 -->
## 20. Disputes

<!-- clause: RPL-DO-PLN-002:20.1 -->
### 20.1 Pre-Work Dispute Process

To temporarily stay proposed vegetation management, a customer must notify RPL of the customer's objection within five (5) business days of the customer's receipt of the notice required under §11. Questions or requests for information are not customer objections. (170 IAC 4-9-8(a)) Work stops on the circuit affected by the objection immediately upon receipt; the Work Planner updates WAM (work order hold type `DISP-PRE`).

<!-- clause: RPL-DO-PLN-002:20.2 -->
### 20.2 First-Representative Response

RPL must respond to a customer's pre-work objection in person, via telephone call, or in writing within three (3) business days. (170 IAC 4-9-8(b)) The Work Planner or the contact center (for written and phone objections) notifies P22 within 4 hours of receiving an objection. P22 or the Work Planner initiates the response and records the contact in WAM under the circuit work order.

<!-- clause: RPL-DO-PLN-002:20.3 -->
### 20.3 Second-Representative Escalation

If the initial RPL representative cannot resolve the customer's objection regarding proposed vegetation management, at least one (1) additional authorized RPL representative must attempt to resolve the objection. If RPL is unsuccessful in resolving the objection, the customer shall be provided with: (1) the website location of the commission's vegetation management administrative rule; and (2) contact information including, at minimum, a telephone number for the commission's consumer affairs division. (170 IAC 4-9-8(c))

IURC Consumer Affairs Division contact information to provide to the customer:
- Toll-free: 1-800-851-4268
- Local: 317-232-2712
- Address: PNC Center, 101 W. Washington Street, Suite 1500E, Indianapolis, IN 46204

<!-- clause: RPL-DO-PLN-002:20.4 -->
### 20.4 When Pre-Work Stay Expires

No temporary stay of vegetation management is available when: (1) an emergency, storm event, or public safety situation exists; (2) the customer has withdrawn the objection or approved conditions under which cutting may resume, either in writing or during a recorded call; (3) more than seven (7) calendar days have passed since RPL provided the proposed resolution referenced in the complaint process under 170 IAC 16-1-4(c)(5) and the customer failed to file an informal complaint to the commission as required by 170 IAC 16-1-5(a); or (4) a final disposition on an informal complaint has been rendered by the commission. (170 IAC 4-9-8(d))

<!-- clause: RPL-DO-PLN-002:20.5 -->
### 20.5 During-Work Dispute Process

Upon request of the customer, RPL shall temporarily stay vegetation management on the customer's premises during the vegetation management only if one of the following occurs or is disputed: (1) RPL failed to provide the required notice; (2) RPL is engaging in vegetation management outside the scope of a written or recorded agreement; (3) RPL did not have authority to enter the customer's property; or (4) RPL did not exercise due diligence to secure an easement or right-of-way document. (170 IAC 4-9-9(a))

At least one (1) member of the work crew must have the authority from RPL to discuss and attempt to resolve customer objections and must respond to the customer's inquiry or complaint. If the work crew cannot resolve the objection, at least one (1) additional authorized RPL representative must attempt to resolve the objection. If RPL is unsuccessful, RPL shall provide to the customer the information required in 170 IAC 16-1-4(c)(5). (170 IAC 4-9-9(b))

<!-- clause: RPL-DO-PLN-002:20.6 -->
### 20.6 Post-Work Dispute Process

A customer may contact RPL regarding vegetation management after work occurred if: (1) RPL failed to provide the required notice; (2) RPL engaged in vegetation management outside the scope of an agreement; (3) RPL did not have authority to enter; (4) RPL failed to follow the vegetation management pruning standards required by the commission or RPL's own policy; or (5) another reason permitted by law. (170 IAC 4-9-10(a))

RPL must respond within three (3) business days of receiving the customer's inquiry or dispute: in person, via telephone call, or in writing. (170 IAC 4-9-10(b)) If the initial representative cannot resolve the dispute, at least one (1) additional authorized representative must attempt to resolve it. If RPL is unsuccessful, the customer shall be provided the information required in 170 IAC 16-1-5 and informed that disputes over monetary damages can only be resolved by a civil court, not the commission. (170 IAC 4-9-10(c))

<!-- clause: RPL-DO-PLN-002:20.7 -->
### 20.7 Dispute Records

RPL retains records of disputes received and the resolutions thereof for a period of six (6) months from the date of final resolution. Records shall include, at a minimum: (1) the customer's name; (2) the customer's service address; (3) telephone number at which the customer may be contacted, if available; (4) the customer's account number; and (5) the general nature of the dispute. (170 IAC 16-1-4(b)) Disputes are logged in the Vegetation Dispute Log (App-C form; record series RRS-DO-003) and cross-referenced to the WAM work order and CIS account record.

<!-- clause: RPL-DO-PLN-002:20.8 -->
### 20.8 IURC Informal Complaint Process

A customer may appeal RPL's proposed resolution by filing an informal complaint with IURC Consumer Affairs within seven (7) days of the date the customer receives RPL's proposed resolution. (170 IAC 16-1-4(c)(5)) IURC Consumer Affairs will provide a decision within thirty (30) days of the complaint submission date; parties must respond to additional information requests within fourteen (14) days unless otherwise directed. (170 IAC 16-1-5(c))

If the customer or RPL is dissatisfied with the Consumer Affairs resolution, either party may request review by the director of Consumer Affairs within seven (7) days of receipt of the proposed resolution of the informal complaint. (170 IAC 16-1-5(d)) Either party may then request commission review within twenty (20) days of receipt of the director's decision. (170 IAC 16-1-6(a))

<!-- clause: RPL-DO-PLN-002:20.9 -->
### 20.9 Customer Dispute Form

The Vegetation Dispute Log form (App-C) is used to record all formal vegetation disputes. Fields include: log ID (VDL-2025-####), date received, account number, premise address, circuit ID, contractor, issue category, first representative name and response date, second representative name and response date, resolution, IURC contact information provided (Y/N), and date IURC information provided.

<!-- clause: RPL-DO-PLN-002:20.10 -->
### 20.10 Annual Complaint Report

Each year, RPL submits a report to the IURC that states and classifies the number of complaints made to RPL, the general nature of the subject matter, how each complaint was received, and whether a commission review was conducted. (170 IAC 16-1-4(d)) This report is incorporated into the annual tree-related outage report due March 31 (§22).

---

<!-- clause: RPL-DO-PLN-002:21 -->
## 21. Customer Education Plan

RPL shall develop and implement an education plan to inform and educate customers on the following topics. (170 IAC 4-9-11)

<!-- table: RPL-DO-PLN-002:T21 -->
| Topic (per 170 IAC 4-9-11) | IAC Clause | Channel | Frequency | Owner | 2025 Deliverable |
|---|---|---|---|---|---|
| Tree and vegetation selection and placement around electric facilities | (1) | Website; work notice VM-F-004; Arbor Day Foundation link | Ongoing; updated annually | P22 | Web page update by 2025-03-01 |
| Public importance of VM to avoid electric interruptions, injuries, and fatalities | (2) | Website; bill insert; social media; work notice | Annually | P22 / Contact Center | Annual bill insert (Q2 2025) |
| Need for and benefit of preventing tree contact with power lines | (3) | Work notice VM-F-004; website | Ongoing | P22 | Part of VM-F-004 revision (App-A) |
| Importance of cooperation between customers and RPL | (4) | Work notice; website; community outreach | Annually | P17 (Customer Advocacy) | Spring community event (Q2) |
| Critical importance of VM to protect reliability and avoid electrocution | (5) | Website; annual report public summary | Annually | P22 | Published with annual report |
| Trim cycles: how chosen cycle impacts clearance and tree appearance | (6) | Work notice VM-F-004 (field F8); website FAQ | With each notice batch | P22 / Work Planners | Included in every VM-F-004 issued |

The annual budget for customer education is $90,000, covering web content, bill insert production, and community outreach events in Lafayette, Crawfordsville, Terre Haute, Frankfort, and Danville.

---

<!-- clause: RPL-DO-PLN-002:22 -->
## 22. Reporting to the IURC

<!-- clause: RPL-DO-PLN-002:22.1 -->
### 22.1 Annual Tree-Related Outage Report

RPL shall file a separate report regarding tree-related outages by March 31 annually and whenever RPL makes a change to its vegetation management plan. The report shall include the following information: (1) the utility's vegetation management budget; (2) actual expenditures for the prior calendar year; (3) the number of customer complaints related to tree trimming; (4) the manner in which complaints were addressed or resolved; and (5) tree-related outages as a percentage of total outages. (170 IAC 4-9-7(g))

<!-- table: RPL-DO-PLN-002:T22 -->
| Report Element | Source in This Document | Source Dataset |
|---|---|---|
| VM budget (2025) | §24 budget table | vm_budget_2024_2025.csv, budget_2025_usd |
| Actual expenditures (2024) | §23 budget results | vm_budget_2024_2025.csv, actual_2024_usd |
| Number of customer complaints (tree trimming) | §23 contacts table | vm_customer_contacts_2024.csv |
| Manner of complaint resolution | §23 contacts table | vm_customer_contacts_2024.csv, resolution field |
| Tree-related outages as % of total | §23 outage table; §25 | vm_tree_outages_2024.csv, tree_share_of_saifi_pct |

<!-- clause: RPL-DO-PLN-002:22.2 -->
### 22.2 Plan-Change Filing

Whenever RPL makes a material change to this vegetation management plan (change in trim cycle, clearance specification, notice process, or budget category realignment of 15 percent or more), Rachel Stein (P22) notifies Jonathan Pierce (P03) within 5 business days. P03 evaluates whether IURC notification or filing is required and directs the filing through the IURC Electronic Filing System (iurc.portal.in.gov). The filing is also coordinated with Patrick O'Neill (P21) and filed as an addendum to this plan (revising version 2025.1 to 2025.2 or subsequent).

---

<!-- clause: RPL-DO-PLN-002:23 -->
## 23. 2024 Program Results (Preliminary — Data Extracted 2025-01-15)

### 23.1 Miles Completed vs. Plan

<!-- table: RPL-DO-PLN-002:T23A -->
| Category | Planned Miles | Actual Miles | Variance |
|---|---|---|---|
| backbone | 1,641 | 1,636 | −0.3% |
| lateral_dominant | 1,427 | 1,427 | 0.0% |
| urban_ug_dominant | 84 | 41 | −51.2% |
| **Total distribution** | **3,152** | **3,104** | **−1.5%** |

Note: Urban/UG-dominant variance reflects deferral of 45 circuits in the Danville and Terre Haute urban cores due to Q3 storm-restoration crew redeployment. Those circuits are captured in the 2026 cycle schedule.

### 23.2 Budget vs. Actual (2024)

<!-- table: RPL-DO-PLN-002:T23B -->
| Category | 2024 Budget ($) | 2024 Actual ($) | Variance ($) | Variance (%) | Note |
|---|---|---|---|---|---|
| Routine cycle trimming — distribution | 28,869,862 (implied) | 28,869,862 | 0 | — | Aligned with actuals |
| Hazard tree removal | 5,655,679 | 5,655,679 | 0 | — | |
| Herbicide / brush / mowing | 2,529,763 | 2,529,763 | 0 | — | |
| Mid-cycle, hot spot, customer-request | 1,836,043 | 1,836,043 | 0 | — | |
| Storm / emergency (non-MED) | 1,301,238 | 1,301,238 | 0 | — | |
| 69 kV subtransmission ROW | 1,049,571 | 1,049,571 | 0 | — | |
| Contractor oversight, QA/QC | 319,655 | 319,655 | 0 | — | |
| Customer education | 80,677 | 80,677 | 0 | — | |
| **Total** | **41,642,488** | **41,642,488** | **0** | **0.0%** | |

The 2024 total actual of $41,642,488 was 0.1 percent above the 2025 budget of $41,600,000.

### 23.3 Tree-Related Outages (2024, Preliminary)

<!-- table: RPL-DO-PLN-002:T23C -->
| Metric | With MED | Excl. MED |
|---|---|---|
| Tree-related customer interruptions (CI) | 213,856 | 118,607 |
| Tree-related customer minutes interrupted (CMI) | 40,238,410 | 14,288,279 |
| Tree-related SAIFI contribution | 0.527 | 0.292 |
| Tree-related SAIDI contribution | 99.16 | 35.21 |
| All-cause CI | 638,033 | 445,864 |
| All-cause SAIFI | 1.572 | 1.099 |
| All-cause SAIDI | 262.20 | 138.31 |
| Tree share of SAIFI | 33.5% | 26.6% |
| Inside-ROW CI | 127,457 | — |
| Outside-ROW CI | 44,526 | — |
| Unknown/unclassified CI | 41,873 | — |

Data source: OMS outage_events_base.csv, vegetation cause_category, year 2024. Customers served (annual average): 405,805.

> **Chart:** See render/charts/chart_monthly_tree_ci_2024.png — Monthly tree-related customer interruptions with and without MED.

### 23.4 Customer Contacts and Complaints (2024)

<!-- table: RPL-DO-PLN-002:T23D -->
| Category | Count | Escalated (2nd Rep) | IURC CAD Referral |
|---|---|---|---|
| Notice question | 181 | 0 | 0 |
| Debris | 99 | 0 | 0 |
| Customer request trim | 51 | 0 | 0 |
| Tree health | 43 | 0 | 0 |
| Refusal of work | 36 | 18 | 1 |
| Property damage | 35 | 17 | 0 |
| Storm debris | 30 | 0 | 0 |
| Easement documentation request | 29 | 0 | 0 |
| Removal dispute | 24 | 12 | 0 |
| Other | 14 | 0 | 0 |
| **Total** | **542** | **47** | **1** |

All 29 easement documentation requests were answered within 5 business days in compliance with 170 IAC 4-9-3(b). All unresolved disputes (those escalated to a second representative and not resolved) were provided with the IURC Consumer Affairs contact information per 170 IAC 4-9-8(c) and 170 IAC 4-9-10(c).

> Note: 1 IURC CAD referral is at the low end of the Indiana benchmark (2–18). This reflects effective first-call resolution. The single referral involved a removal dispute that was resolved at the IURC Consumer Affairs level.

---

<!-- clause: RPL-DO-PLN-002:24 -->
## 24. 2025 Budget

Total 2025 VM budget: **$41,600,000** (company practice; no regulatory cap).

<!-- table: RPL-DO-PLN-002:T24 -->
| Line | Category | Cost Type | System | 2025 Budget ($) | Unit | Units | $/Unit |
|---|---|---|---|---|---|---|---|
| BDG-001 | Routine cycle trimming — distribution | O&M | distribution | 27,940,000 | OH-miles | 3,350 | $8,339/mi |
| BDG-002 | Hazard tree removal (incl. outside-ROW) | O&M | distribution | 6,180,000 | trees | 4,100 | $1,507/tree |
| BDG-003 | Herbicide / brush / mowing (IVM) | O&M | distribution | 2,580,000 | acres | 3,200 | $806/acre |
| BDG-004 | Mid-cycle, hot spot and customer-request work | O&M | distribution | 2,020,000 | work-orders | 680 | $2,971/WO |
| BDG-005 | Storm / emergency vegetation (non-MED) | O&M | distribution | 1,490,000 | — | — | — |
| BDG-006 | 69 kV subtransmission ROW | Capital | subtransmission | 910,000 | ROW-miles | 42 | $21,667/mi |
| BDG-007 | Contractor oversight, work planning and QA/QC | O&M | distribution | 390,000 | audits | 320 | $1,219/audit |
| BDG-008 | Customer education and communications | O&M | distribution | 90,000 | campaigns | 6 | $15,000/campaign |
| | **Total** | | | **41,600,000** | | | |

> **Chart:** See render/charts/chart_budget_2024_vs_2025.png — 2024 Actual vs. 2025 Budget by category.

Year-over-year: 2025 budget ($41.6M) is $42,488 (0.1%) below 2024 actual ($41,642,488). The routine cycle trimming line reflects a modest reduction due to contractor re-pricing and improved crew productivity in 2024. The hazard tree line increases $525,000 to address backlog identified in post-storm patrols following the five 2024 MED events.

---

<!-- clause: RPL-DO-PLN-002:25 -->
## 25. Performance Metrics

### 25.1 Tree-Related Reliability Trend (2022–2024)

<!-- table: RPL-DO-PLN-002:T25A -->
| Year | Tree SAIFI (with MED) | Tree SAIFI (ex-MED) | Tree SAIDI (ex-MED) | Tree % of SAIFI (ex-MED) | Inside-ROW % | Outside-ROW % |
|---|---|---|---|---|---|---|
| 2022 | — | 0.280 | 38.5 | — | 62% | 38% |
| 2023 | — | 0.310 | 41.2 | — | 59% | 41% |
| 2024 | 0.527 | 0.292 | 35.2 | 26.6% | 59.6% | 20.8% |

Sources: 2022–2023 figures from reliability_facts.yaml vegetation summary; 2024 figures from vm_tree_outages_2024.csv and reliability_facts.yaml annual totals. "—" = detail not recorded separately in the 2022–2023 summary.

> **Chart:** See render/charts/chart_monthly_tree_ci_2024.png for monthly distribution.

### 25.2 Top 10 Circuits by Tree CI 2024 and 2025 Treatment

<!-- table: RPL-DO-PLN-002:T25B -->
| Rank | Circuit ID | Service Center | County | Tree CI 2024 | OH Miles | 2025 Treatment | Scheduled Quarter |
|---|---|---|---|---|---|---|---|
| 1 | DAN-004-1 | DAN | Parke | 12 | 20.4 | Routine cycle | Q2 |
| 2 | DAN-026-2 | DAN | Vermillion | 12 | 15.7 | Routine cycle | Q3 |
| 3 | LAF-015-1 | LAF | Tippecanoe | 12 | 22.6 | Routine cycle | Q1 |
| 4 | LAF-016-1 | LAF | Tippecanoe | 11 | 31.8 | Routine cycle | Q2 |
| 5 | LAF-017-3 | LAF | Tippecanoe | 10 | 27.3 | Routine cycle | Q2 |
| 6 | CRW-008-1 | CRW | Montgomery | 10 | 18.2 | Routine cycle | Q1 |
| 7 | THT-004-2 | THT | Vigo | 10 | 23.7 | Routine cycle | Q3 |
| 8 | DAN-012-4 | DAN | Putnam | 9 | 34.6 | Routine cycle | Q1 |
| 9 | FRK-003-2 | FRK | Clinton | 9 | 19.8 | Routine cycle | Q2 |
| 10 | LAF-029-1 | LAF | Tippecanoe | 8 | 41.8 | Routine cycle | Q3 |

Note: Tree CI = number of sustained tree-related customer interruption events in calendar year 2024 (OMS). All 10 top-CI circuits are scheduled for routine cycle trimming in 2025.

### 25.3 Schedule Distribution by Quarter (2025)

> **Chart:** See render/charts/chart_schedule_miles_by_quarter.png.

| Quarter | Circuits | OH Miles | Contractor A | Contractor B |
|---|---|---|---|---|
| Q1 | 29 | 853 | 528 | 325 |
| Q2 | 37 | 1,031 | 712 | 319 |
| Q3 | 29 | 832 | 648 | 184 |
| Q4 | 16 | 453 | 448 | 5 |
| **Total** | **111** | **3,169.7** | **2,336** | **833** |

---

<!-- clause: RPL-DO-PLN-002:26 -->
## 26. Records and Retention

<!-- table: RPL-DO-PLN-002:T26 -->
| Record Type | Series ID | System of Record | Retention |
|---|---|---|---|
| Vegetation work notices, consent, and easement documentation | RRS-DO-002 | WAM / DCS | Per RPL-LEG-RRS-001 |
| Vegetation dispute logs (App-C) | RRS-DO-003 | WAM / DCS | 6 months from final resolution per 170 IAC 16-1-4(b); RPL retains for 3 years per RPL-LEG-RRS-001 |
| Tree-related outage report filings (IURC) | RRS-DO-004 | DCS / IURC portal | Per RPL-LEG-RRS-001 |
| Customer complaint and dispute files | RRS-CS-011 | CIS | Per RPL-CS-PRO-011 |
| Training completion records | RRS-TRN-001 | EHS-IMS | Per RPL-LEG-RRS-001 |
| Controlled document masters | RRS-DOC-001 | DCS | Permanent |

---

<!-- clause: RPL-DO-PLN-002:27 -->
## 27. Training

<!-- table: RPL-DO-PLN-002:T27 -->
| Training | Audience | Frequency | Administering Party | Record |
|---|---|---|---|---|
| Contractor Crew Orientation — RPL VM Standards | Contractor A/B crews (all new hires before first assignment) | Before first RPL assignment; annually refreshed | P22 / RPL Work Planner | WAM contractor qualification record |
| RPL VM Plan Overview — Contact Center Module | Contact center agents | Annually (Q1); upon this plan's effective date | P17 / P22 | RRS-TRN-001 in EHS-IMS |
| ISA Arborist Standards Update | Contractor ISA-certified arborist on staff | Annually | Contractor (documented to P22) | WAM contractor qualification record |
| IURC VM Rule — Internal Refresher | Work Planners, P22, P21 | Annually (Q1) | P03 / P22 | RRS-TRN-001 |

---

<!-- clause: RPL-DO-PLN-002:28 -->
## 28. Related Documents

| Document ID | Title |
|---|---|
| RPL-DCC-PRO-003 | Service Interruption Reporting Procedure |
| RPL-CS-PRO-011 | Customer Complaint & Dispute Resolution Procedure |
| RPL-LEG-RRS-001 | Records Retention Schedule |
| RPL-TAR-GRR-012 | Tariff for Electric Service, IURC No. 12 — General Rules and Regulations |
| RPL-EMR-PLN-001 | Emergency Response & Storm Restoration Plan |
| RPL-CLM-PRO-001 | Third-Party Claims Procedure |
| RPL-SAF-PRO-002 | Electrical Safety Rulebook |
| RPL-DO-PRO-020 | Damage Prevention & Indiana 811 Procedure |

---

<!-- clause: RPL-DO-PLN-002:29 -->
## 29. Revision History

| Version | Effective | Approved | Author | Change Summary |
|---|---|---|---|---|
| 2025.1 | 2025-01-27 | 2025-01-22 | Rachel Stein (P22) | Annual update: 2024 results section added; §8 cycle table revised; §14 risk tiers updated with 2024 storm-response experience; budget updated for 2025; §21 education table expanded; §19 KPI table revised |
| 2024.2 | 2024-07-15 | 2024-07-10 | Rachel Stein (P22) | Mid-year revision: §15 IVM herbicide applicator qualification clause added following IURC audit inquiry; §13.3 stump treatment detail added; §19 invoicing controls strengthened |
| 2024.1 | 2024-01-22 | 2024-01-17 | Rachel Stein (P22) | Annual update: 2023 results; budget for 2024; clearance table row added for secondary/service drop |
| 2023.1 | 2023-02-06 | 2023-01-31 | Rachel Stein (P22) | Annual update: IVM pilot results; dispute form revised (App-C); §22 annual report mapping table added |

---

<!-- clause: RPL-DO-PLN-002:30 -->
## 30. Approval Block

| Role | Name | Title | Signature | Date |
|---|---|---|---|---|
| Owner | Rachel Stein | Manager, Vegetation Management Program | ___________________________ | 2025-01-22 |
| Reviewer | Patrick O'Neill | Director, Distribution Operations | ___________________________ | 2025-01-22 |
| Approver | Jonathan Pierce | Senior Counsel, Regulatory | ___________________________ | 2025-01-22 |

---

## Appendix A — VM-F-004 Routine Vegetation Work Notice (Rev. 01/2025)

<!-- clause: RPL-DO-PLN-002:App-A -->
*Form VM-F-004 (Rev. 01/2025)*

---

**TREE TRIMMING NOTICE**

<!-- clause: RPL-DO-PLN-002:App-A.F1 -->
**F1.** Date of this notice: `__________` (YYYY-MM-DD)

Rockridge Power & Light Company
400 Wabash Commons Drive, Lafayette, Indiana 47901
Customer Service: 1-800-555-0142 · www.rockridge-pl.example

---

**Part A — Notice to Customer / Property Occupant**

<!-- clause: RPL-DO-PLN-002:App-A.F2 -->
**F2.** ☐ Mailed to: `__________` (customer/occupant address)    ☐ Hand-delivered as door hanger

<!-- clause: RPL-DO-PLN-002:App-A.F3 -->
**F3.** Vegetation management (tree trimming or removal) is scheduled to occur at or near your property. (170 IAC 4-9-4(c)(1))

<!-- clause: RPL-DO-PLN-002:App-A.F4 -->
**F4.** Vegetation management means the cutting or removal of vegetation or the prevention of vegetative growth to maintain safe conditions around utility facilities, ensure reliable electric service, and prevent hazards caused by the encroachment of vegetation on utility facilities. It is required for public safety and to reduce power outages that affect you and your neighbors. (170 IAC 4-9-4(c)(2))

<!-- clause: RPL-DO-PLN-002:App-A.F5 -->
**F5.** If you are not the property owner, you are strongly encouraged to notify the property owner as soon as possible that vegetation management is scheduled to occur. (170 IAC 4-9-4(c)(3))

<!-- clause: RPL-DO-PLN-002:App-A.F6 -->
**F6.** Receipt of this notice initiates the two (2) week window for calculating implied consent. (170 IAC 4-9-4(c)(4))

<!-- clause: RPL-DO-PLN-002:App-A.F7 -->
**F7.** Estimated date vegetation management is scheduled to occur: `__________` (YYYY-MM-DD) (170 IAC 4-9-4(c)(5))

<!-- clause: RPL-DO-PLN-002:App-A.F8 -->
**F8.** This circuit is on a `____`-year trim cycle. Greater clearance is established at each trim to allow for the full growth period. Trees requiring significant canopy reduction may look different after trimming; this is normal and necessary for your safety. (170 IAC 4-9-11(6))

<!-- clause: RPL-DO-PLN-002:App-A.F9 -->
**F9.** Contact for vegetation management questions: `__________` (name or role) at **1-800-555-0142**. (170 IAC 4-9-4(c)(6))

---

**Part B — Additional Written Notice Elements** (170 IAC 4-9-4(d))

<!-- clause: RPL-DO-PLN-002:App-A.F10 -->
**F10.** Commission's vegetation management rule website: [https://iac.iga.in.gov/iac/](https://iac.iga.in.gov/iac/) (170 IAC 4-9-4(d)(3))

<!-- clause: RPL-DO-PLN-002:App-A.F11 -->
**F11.** Commission website: http://www.in.gov/iurc (170 IAC 4-9-4(d)(4))

<!-- clause: RPL-DO-PLN-002:App-A.F12 -->
**F12.** RPL vegetation management website: www.rockridge-pl.example (170 IAC 4-9-4(d)(5))

<!-- clause: RPL-DO-PLN-002:App-A.F13 -->
**F13.** Educational resource for right tree, right place: Arbor Day Foundation's Right Tree Right Place program. Website: www.arborday.org. (170 IAC 4-9-4(d)(6))

<!-- clause: RPL-DO-PLN-002:App-A.F14 -->
**F14.** To obtain the name of the contractor performing this work: call 1-800-555-0142 or visit www.rockridge-pl.example. (170 IAC 4-9-4(d)(7))

<!-- clause: RPL-DO-PLN-002:App-A.F15 -->
**F15.** RPL's representative shall carry identification and present it upon request. (170 IAC 4-9-4(d)(8); 170 IAC 4-9-13)

---

**Part C — Office Use Only**

| Field | Value |
|---|---|
| Circuit ID | `__________` |
| Notice Batch ID | `VMN-2025-___` |
| Planned Start Date | `__________` |
| Work Planner initials | `__________` |
| Delivery method confirmed in WAM | ☐ Yes |

---

## Appendix B — Easement Documentation Request Response Letter (Template)

<!-- clause: RPL-DO-PLN-002:App-B -->

*[RPL Letterhead]*

Date: `__________`

Re: Vegetation Management — Easement Documentation Request
Circuit: `__________` | Notice Batch: VMN-2025-___
Property Address: `__________`

Dear `__________`:

Thank you for your request received on `__________` for documentation of the legal authority allowing Rockridge Power & Light Company to conduct vegetation management at the above-referenced property.

Pursuant to 170 IAC 4-9-3(b), RPL is providing the following:

☐ **Enclosed:** A copy of the recorded easement or public right-of-way document granting RPL the right to enter your property for vegetation management purposes (recorded in `__________` County, Instrument No. `__________`).

☐ **Enclosed:** The following alternative authority document (where the easement is not reasonably available): `__________`.

This documentation is provided in advance of the scheduled vegetation management, which remains planned for approximately `__________`. If you have additional questions, please contact `__________` at 1-800-555-0142.

Sincerely,

`__________`
Vegetation Management Program
Rockridge Power & Light Company
400 Wabash Commons Drive, Lafayette, IN 47901

*[Signed and dated per §30 process]*

---

## Appendix C — Vegetation Dispute Log Form

<!-- clause: RPL-DO-PLN-002:App-C -->

*Record Series: RRS-DO-003 | Retention: per RPL-LEG-RRS-001 (minimum 3 years)*

| Field | Entry |
|---|---|
| Log ID (VDL-2025-####) | `__________` |
| Date received | `__________` (YYYY-MM-DD) |
| Account number | `__________` |
| Premise address | `__________` |
| Circuit ID | `__________` |
| Notice batch ID | `__________` |
| Contractor | ☐ Contractor A  ☐ Contractor B |
| Issue category | ☐ no notice  ☐ outside agreement scope  ☐ no authority  ☐ pruning standards  ☐ debris  ☐ property damage  ☐ other: `____` |
| First RPL representative | `__________` |
| First representative contact date | `__________` |
| First representative response (≤3 business days) | `__________` |
| Dispute resolved by first representative | ☐ Yes  ☐ No |
| Second RPL representative (if required) | `__________` |
| Second representative contact date | `__________` |
| Second representative response | `__________` |
| Resolution | `__________` |
| IURC Consumer Affairs contact information provided | ☐ Yes  ☐ No |
| Date IURC information provided | `__________` |
| Final resolution date | `__________` |
| Closed in WAM and CIS | ☐ Yes |

*Office use only:* File in DCS under RRS-DO-003. Cross-reference WAM work order and CIS account record.

---

## Appendix D — 2025 Circuit Schedule Summary (Top 20 by OH Miles)

<!-- clause: RPL-DO-PLN-002:App-D -->

*Source: vm_circuit_schedule_2025.csv (111 circuits). Top 20 circuits by overhead_miles.*

<!-- table: RPL-DO-PLN-002:TApp-D -->
| Priority | Circuit ID | Service Ctr | County | OH Miles | Category | Quarter | Contractor |
|---|---|---|---|---|---|---|---|
| — | DAN-003-2 | DAN | Parke | 94.5 | backbone | Q2 | Contractor A |
| — | LAF-003-2 | LAF | Tippecanoe | 71.8 | backbone | Q4 | Contractor A |
| — | DAN-002-2 | DAN | Parke | 70.3 | backbone | Q1 | Contractor A |
| — | LAF-036-4 | LAF | Tippecanoe | 69.3 | backbone | Q3 | Contractor A |
| — | DAN-018-5 | DAN | Parke | 66.5 | backbone | Q1 | Contractor A |
| — | DAN-024-3 | DAN | Parke | 65.3 | lateral_dominant | Q2 | Contractor A |
| — | DAN-019-1 | DAN | Parke | 56.9 | backbone | Q2 | Contractor A |
| — | CRW-001-3 | CRW | Montgomery | 56.6 | backbone | Q3 | Contractor B |
| — | DAN-005-4 | DAN | Parke | 56.1 | backbone | Q2 | Contractor A |
| — | LAF-002-4 | LAF | Tippecanoe | 55.2 | lateral_dominant | Q2 | Contractor A |
| — | THT-011-1 | THT | Vigo | 52.5 | lateral_dominant | Q3 | Contractor B |
| — | CRW-018-2 | CRW | Montgomery | 51.9 | backbone | Q2 | Contractor B |
| — | CRW-008-3 | CRW | Carroll | 51.6 | backbone | Q1 | Contractor B |
| — | LAF-035-3 | LAF | Tippecanoe | 50.6 | backbone | Q1 | Contractor A |
| — | LAF-022-4 | LAF | Tippecanoe | 49.4 | lateral_dominant | Q1 | Contractor A |
| — | DAN-024-6 | DAN | Parke | 48.7 | backbone | Q2 | Contractor A |
| — | LAF-038-4 | LAF | Tippecanoe | 44.7 | backbone | Q3 | Contractor A |
| — | LAF-004-6 | LAF | Tippecanoe | 42.2 | lateral_dominant | Q3 | Contractor A |
| — | LAF-037-4 | LAF | Tippecanoe | 41.9 | lateral_dominant | Q1 | Contractor A |
| — | LAF-027-1 | LAF | Tippecanoe | 41.8 | backbone | Q3 | Contractor A |

Full schedule in data/vm_circuit_schedule_2025.csv.

---

## Appendix E — Clearance Specification Diagram

<!-- clause: RPL-DO-PLN-002:App-E -->

The following diagram (reproduced in the .docx/.pdf render as Figure E-1) illustrates RPL's clearance envelope for a 12.47 kV three-phase backbone conductor. All dimensions are in feet and represent minimum clear distance from conductor centerline to nearest branch tip at the time of trim.

```
                    ←10 ft→ ←10 ft→
                      [side] [side]
                         |     |
    Fast-growth:     ─────[CND]─────   Conductor (12.47 kV 3ph)
                        ↑ 8 ft
                        │ (under clearance, fast-growth)
         ████████████████████████████  Ground / road level
```

*Dimensions are company practice and may be increased by the Work Planner or crew ISA Arborist for locality, facility, or tree-health factors per 170 IAC 4-9-7(b).*

Full clearance specification: see §7, Table T7.

---

## Appendix F — Data Dictionary

<!-- clause: RPL-DO-PLN-002:App-F -->

See `data/README.md` for the complete data dictionary, row counts, primary keys, foreign keys, source/derivation notes, margin rules (§3.6a), and acceptance test results for all five RPL-DO-PLN-002 datasets.

**Summary of datasets:**

| Dataset | Rows | Primary Key | Description |
|---|---|---|---|
| vm_circuit_schedule_2025.csv | 111 | circuit_id | Circuits scheduled for 2025 routine cycle trimming |
| vm_work_completed_2024.csv | 106 | circuit_id | 2024 completed trimming program results |
| vm_tree_outages_2024.csv | 51 | month + tree_location + med_flag | Aggregated vegetation outages derived from outage_events_base.csv |
| vm_budget_2024_2025.csv | 8 | line_id | Budget comparison 2024 actual vs. 2025 planned |
| vm_customer_contacts_2024.csv | 542 | contact_id | 2024 logged vegetation customer contacts |

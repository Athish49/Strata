---
doc_id: RPL-MTR-PGM-001
title: Meter Testing Program Plan
company: Rockridge Power & Light Company
version: "6.0"
status: Approved
effective_date: 2025-01-13
approved_date: 2025-01-08
law_as_of: 2024-12-31
owner: {id: P19, name: Gregory Walsh, title: "Manager, Meter Shop & Standards Laboratory"}
reviewer: {id: P20, name: Angela Ruiz, title: "Director, Metering"}
approver: {id: P16, name: Michael Brennan, title: "Vice President, Operations"}
next_review: 2026-01-13
classification: Internal
regulatory_basis:
  - "170 IAC 4-1-3"
  - "170 IAC 4-1-4"
  - "170 IAC 4-1-5"
  - "170 IAC 4-1-6"
  - "170 IAC 4-1-7"
  - "170 IAC 4-1-8"
  - "170 IAC 4-1-9"
  - "170 IAC 4-1-10"
  - "170 IAC 4-1-11"
supersedes: "5.2 (2024-02-05)"
---

<!-- clause: RPL-MTR-PGM-001:HEADER -->
| | |
|---|---|
| **Document Title** | Meter Testing Program Plan |
| **Document ID** | RPL-MTR-PGM-001 |
| **Version** | 6.0 |
| **Effective Date** | 2025-01-13 |
| **Approved Date** | 2025-01-08 |
| **Law As-Of Date** | 2024-12-31 |
| **Owner** | Gregory Walsh, Manager, Meter Shop & Standards Laboratory |
| **Reviewer** | Angela Ruiz, Director, Metering |
| **Approver** | Michael Brennan, Vice President, Operations |
| **Classification** | Internal |
| **Supersedes** | RPL-MTR-PGM-001 v5.2 (2024-02-05) |

> **Uncontrolled when printed — verify the current version in DCS before use.**

---

## Table of Contents

1. Purpose
2. Scope
3. Definitions
4. Regulatory Basis and Industry Standards
5. Organization and Roles
6. Meter Records
7. Meter Location and Accessibility Standards
8. New and Repaired Meter Acceptance
9. In-Service Testing Program
10. Accuracy Limits and Average-Accuracy Method
11. Test Equipment and Standards
12. AMI Meter Health Monitoring
13. Customer-Requested and Commission-Supervised Tests
14. 2024 Program Results (Preliminary — Data Extracted 2025-01-03)
15. 2025 Test Plan
16. Program KPIs
17. Records and Retention
18. Training and Technician Qualification
19. Related Documents
20. Revision History
21. Approval Block

**Appendices:**
- App-A: Meter Test Report MTR-F-011 Layout
- App-B: Group Acceptance Worksheet
- App-C: Standards Certification Register Summary
- App-D: Data Dictionary

---

<!-- clause: RPL-MTR-PGM-001:1 -->
## 1. Purpose

This Meter Testing Program Plan describes how Rockridge Power & Light Company (RPL) ensures the accuracy, integrity, and regulatory compliance of its meter population. The plan governs new-meter acceptance testing, in-service testing (periodic and statistical sampling), test equipment calibration and traceability, customer-requested testing, and annual program reporting. It applies to all 409,950 revenue meters in RPL's service territory as of 2024-12-31.

---

<!-- clause: RPL-MTR-PGM-001:2 -->
## 2. Scope

<!-- table: RPL-MTR-PGM-001:T2 -->
**Table 2-1: Meter Fleet Inventory as of 2024-12-31**

| ID | Technology | Form / Class | Service Type | Count | Vendor Family |
|---|---|---|---|---|---|
| T2-1 | Solid-state AMI | 2S CL200 | Residential / small commercial | 319,232 | Vendor A (≈70%), Vendor B |
| T2-2 | Solid-state AMI | 2S CL320 | Commercial | 7,424 | Vendor A |
| T2-3 | Solid-state AMI | 12S CL200 | Commercial / small industrial | 14,848 | Vendor A, Vendor B |
| T2-4 | Solid-state AMI | 16S CL200/CL320 | Commercial / industrial | 14,848 | Vendor A, Vendor B |
| T2-5 | Solid-state AMI | 9S CL20 | Small commercial | 9,280 | Vendor B |
| T2-6 | Solid-state AMI | 3S / 4S / 1S | Miscellaneous | 5,568 | Vendor A, Vendor B |
| T2-7 | Solid-state AMR | 2S CL200 | Residential | 28,260 | Vendor B, Vendor C |
| T2-8 | Solid-state AMR | 12S / 16S | Commercial | 2,198 | Vendor B, Vendor C |
| T2-9 | Solid-state AMR | 9S | Small commercial | 942 | Vendor C |
| T2-10 | Electromechanical | 2S CL200 | Residential (rural) | 6,836 | Vendor C, legacy-other |
| T2-11 | Electromechanical | 1S / 12S | Small residential / commercial | 514 | Vendor C, legacy-other |
| | **TOTAL** | | | **409,950** | |

**AMI subtotal:** 371,200 · **AMR subtotal:** 31,400 · **Electromechanical subtotal:** 7,350

Transformer-rated meters (16S, 12S CT-connected): approximately 6,400–8,600 units within the counts above. Install years: AMI 2016–2024 (deployment wave 2017–2021); AMR 2005–2015; electromechanical (EM) 1972–2004.

This plan applies to all meters listed above operated within RPL's 14-county service territory in west-central Indiana. Meters installed at customer-owned substations operating under separate metering agreements are included for testing purposes. This plan does not govern revenue metering owned by third-party generators (none, as RPL owns no generating units).

---

<!-- clause: RPL-MTR-PGM-001:3 -->
## 3. Definitions

<!-- clause: RPL-MTR-PGM-001:3.1 -->
**3.1 As-Found Accuracy** — The measured percentage registration of a meter at the time it is removed from service or tested in place, before any adjustment. (170 IAC 4-1-8(a))

<!-- clause: RPL-MTR-PGM-001:3.2 -->
**3.2 As-Left Accuracy** — The measured percentage registration of a meter after adjustment, confirming it meets accuracy limits before being returned to service. After any meter has been adjusted, the "as left" accuracy of the meter shall be determined by tests at each load. (170 IAC 4-1-8(c))

<!-- clause: RPL-MTR-PGM-001:3.3 -->
**3.3 Average Accuracy (Average Percentage Registration)** — The arithmetic mean of the percentage registration at light load (LL) and at full load (FL): Average percentage accuracy = (FL + LL) ÷ 2. (170 IAC 4-1-8(a))

<!-- clause: RPL-MTR-PGM-001:3.4 -->
**3.4 Full Load (FL)** — For self-contained meters: a load of approximately one hundred percent (100%) of the rated test amperes of the meter. For meters used with current transformers: approximately one hundred percent (100%) of either the meter test amperes or the secondary current rating of the current transformers. (170 IAC 4-1-8(a))

<!-- clause: RPL-MTR-PGM-001:3.5 -->
**3.5 Light Load (LL)** — For self-contained meters: a load of approximately ten percent (10%) of the rated test amperes of the meter. For CT-metered installations: approximately ten percent (10%) of the selected full load current. (170 IAC 4-1-8(a))

<!-- clause: RPL-MTR-PGM-001:3.6 -->
**3.6 Homogeneous Group** — A subdivision of the in-service meter population with similar operating characteristics, formed by manufacturer, model family, technology type, form factor, service class, and install-year band, used for Method B statistical sampling under 170 IAC 4-1-10(c). (170 IAC 4-1-10(c)(1))

<!-- clause: RPL-MTR-PGM-001:3.7 -->
**3.7 Lot** — A subset of meters within a homogeneous group from which an annual sample is drawn for quality control testing. No lot size shall be less than three hundred one (301) meters. (170 IAC 4-1-10(c)(2))

<!-- clause: RPL-MTR-PGM-001:3.8 -->
**3.8 Sample** — The set of meters randomly drawn from a lot for accuracy testing under Method B. Sample size is determined per RPL's internal sampling plan (§9.3). (170 IAC 4-1-10(c)(3))

<!-- clause: RPL-MTR-PGM-001:3.9 -->
**3.9 Acceptable Quality Level (AQL)** — The acceptance criterion for lot testing: 2.50 AQL (normal inspection) per the Double Specification Limit–Variability Unknown–Standard Deviation Method. (170 IAC 4-1-10(c)(4))

<!-- clause: RPL-MTR-PGM-001:3.10 -->
**3.10 Upper Specification Limit (U) and Lower Specification Limit (L)** — For Method B lot testing, U = one hundred two percent (102%) and L = ninety-eight percent (98%) average accuracy at full load. (170 IAC 4-1-10(c)(5))

<!-- clause: RPL-MTR-PGM-001:3.11 -->
**3.11 Method A (Periodic Testing)** — The in-service testing method under which all meters are tested on a fixed schedule of not more than sixteen (16) years. (170 IAC 4-1-10(b))

<!-- clause: RPL-MTR-PGM-001:3.12 -->
**3.12 Method B (Quality Control / Statistical Sampling)** — The optional in-service testing method under which meters are divided into homogeneous groups and lots, and a statistical sample is drawn annually and tested against the AQL criterion. (170 IAC 4-1-10(c))

<!-- clause: RPL-MTR-PGM-001:3.13 -->
**3.13 Power-Factor Test** — A test of a watthour meter at 100% of manufacturer's rated test current at 50% lagging power factor, required for non-self-contained meters used on circuits supplying inductive load. Error must not exceed two percent (2%), plus or minus. (170 IAC 4-1-9(b)(5))

<!-- clause: RPL-MTR-PGM-001:3.14 -->
**3.14 Test Board (Shop Test Board)** — A fixed automated test station in the Meter Shop & Standards Laboratory used to test multiple meters simultaneously. Test boards are calibrated against RPL reference standards.

<!-- clause: RPL-MTR-PGM-001:3.15 -->
**3.15 Reference Standard** — A permanently mounted watthour meter or instrument in the Meter Shop & Standards Laboratory used for no other purpose than checking portable standards. Reference standards shall be tested and adjusted, if necessary, at least once every two years by a recognized standardizing laboratory. (170 IAC 4-1-7(C))

<!-- clause: RPL-MTR-PGM-001:3.16 -->
**3.16 Portable Standard** — A portable watthour meter standard used for field testing. Must be accompanied at all times by a certificate or calibration card signed by the proper authority, giving the date of last certification. If found in error more than one percent (1%) plus or minus, it shall be tested, adjusted, and certified before further use. (170 IAC 4-1-7(D))

<!-- clause: RPL-MTR-PGM-001:3.17 -->
**3.17 Self-Contained Meter** — A meter that measures load current directly without instrument transformers. AMI 2S, AMR 2S, and EM 2S/1S meters are self-contained.

<!-- clause: RPL-MTR-PGM-001:3.18 -->
**3.18 Transformer-Rated (CT) Meter** — A meter used in conjunction with current transformers and/or potential transformers. RPL's 12S, 16S, and 9S meters are transformer-rated.

<!-- clause: RPL-MTR-PGM-001:3.19 -->
**3.19 Weighted Accuracy** — For groups with non-uniform test loads, accuracy weighted by energy contribution at each test point. RPL applies this for multi-element CT meters.

<!-- clause: RPL-MTR-PGM-001:3.20 -->
**3.20 Functional Failure** — A meter defect that does not affect accuracy registration but impairs metering function: display failure, register failure, communications failure, disconnect switch failure, or physical damage.

---

<!-- clause: RPL-MTR-PGM-001:4 -->
## 4. Regulatory Basis and Industry Standards

<!-- clause: RPL-MTR-PGM-001:4.1 -->
**4.1 Indiana Administrative Code (170 IAC 4-1), Law as of 2024-12-31**

<!-- table: RPL-MTR-PGM-001:T4 -->
| ID | Citation | Heading | Key Requirements Covered Here |
|---|---|---|---|
| T4-1 | 170 IAC 4-1-3 | Retention of records | Minimum 3-year retention; records kept in Indiana; open to IURC inspection |
| T4-2 | 170 IAC 4-1-4 | Records and reports of meter purchases and tests | Test record content; permanent meter records; annual tabulations if required |
| T4-3 | 170 IAC 4-1-5 | Location of meters; accessibility | Outdoor preference; indoor standards; mounting height; accessibility |
| T4-4 | 170 IAC 4-1-6 | Service watthour meters; inspection and repair | New meter testing; removed-meter inspection; 60-day installation testing |
| T4-5 | 170 IAC 4-1-7 | Meter testing equipment and facilities | Reference and portable standards; calibration intervals; certification records |
| T4-6 | 170 IAC 4-1-8 | Average accuracy of watthour meters; tests | FL/LL determination; average accuracy formula; as-found/as-left requirements |
| T4-7 | 170 IAC 4-1-9 | Accuracy of meters | Accuracy limits for all meter types; no-load operation prohibition |
| T4-8 | 170 IAC 4-1-10 | In-service tests; watthour meters, self-contained | Method A (16-year periodic); Method B (statistical sampling); lot standards |
| T4-9 | 170 IAC 4-1-11 | Customer requests for tests | Written request; free first/second tests; 10-day report; cost disclosure; appeal |

<!-- clause: RPL-MTR-PGM-001:4.2 -->
**4.2 Industry Standards (referenced for technical practice)**

- **ANSI C12.1** — American National Standard Code for Electricity Metering: test methods, performance requirements, and service conditions (company practice reference for test procedures).
- **ANSI C12.20** — Electricity Meters — 0.2 and 0.5 Accuracy Classes: applicable to high-accuracy AMI meters (company practice).
- **ANSI/ASQC Z1.9-1993** — Named in 170 IAC 4-1-10(c)(3) for Method B sample size determination. RPL has adopted an internal sampling plan consistent with this standard's Inspection Level II principles; see §9.3.

RPL does not reproduce copyrighted tables from paywalled standards. All sample-size determinations in this plan are company practice as stated in §9.3.

---

<!-- clause: RPL-MTR-PGM-001:5 -->
## 5. Organization and Roles

<!-- table: RPL-MTR-PGM-001:T5 -->
| Role | Person / Title | Responsibilities |
|---|---|---|
| Director, Metering | Angela Ruiz (P20) | Program ownership; IURC interface; Method B commission notification; annual report approval |
| Manager, Meter Shop & Standards Laboratory | Gregory Walsh (P19) | Day-to-day program management; test schedule; equipment calibration; record integrity |
| Supervisor, Metering Services | Luis Hernandez (P18) | Field testing coordination; technician supervision; WAM work order management |
| Meter Technicians (MT-### series) | 14 certified technicians | In-service testing (shop and field); new-meter acceptance; customer tests |
| AMI Operations (role) | Metering department | AMI HES monitoring; zero-consumption analytics; remote disconnect/reconnect |
| Records Coordinator (role) | Metering department | DCS controlled-document maintenance; RRS-MTR-001 through RRS-MTR-003 records management |

**RACI Summary:**
- Gregory Walsh (P19) **Responsible** for test execution, equipment, and records.
- Angela Ruiz (P20) **Accountable** for program compliance and IURC reporting.
- Luis Hernandez (P18) **Consulted** on field logistics and technician capacity.
- Michael Brennan (P16) **Informed** of annual program results and any commission action.

---

<!-- clause: RPL-MTR-PGM-001:6 -->
## 6. Meter Records

<!-- clause: RPL-MTR-PGM-001:6.1 -->
**6.1 Test Record Requirements.** Whenever any meter in service is tested, a record shall be preserved containing the information necessary for: (1) identifying the meter; (2) the reason for making the test; (3) the reading of the meter before the test; and (4) the result of the test; together with all data taken at the time of the test in sufficiently complete form to permit the calculation of the average accuracy for billing adjustments if required. (170 IAC 4-1-4(a))

The Meter Technician records this information on MTR-F-011 (Meter Test Report) at the time of each test. Gregory Walsh (P19) reviews and signs MTR-F-011 within five (5) business days of test completion and files the record in WAM under work order type MTR-TST.

<!-- clause: RPL-MTR-PGM-001:6.2 -->
**6.2 Permanent Meter Record Fields.** Permanent records shall also be kept, systematically arranged, giving for each meter owned or used by any public utility, the year of purchase, its identification, and the record of the last test to which it has been subjected, with date and general results of the test. These records shall apply to all meters purchased after the effective date of this rule and to all other meters insofar as the information is available. (170 IAC 4-1-4(b))

<!-- table: RPL-MTR-PGM-001:T6 -->
| ID | Field | System of Record | Type | Notes |
|---|---|---|---|---|
| T6-1 | Meter serial number (RPL-<vendor>-<7 digits>) | WAM | Text | Primary key |
| T6-2 | Vendor family | WAM | Enumeration | Vendor A/B/C/legacy-other |
| T6-3 | Meter technology | WAM | Enumeration | solid_state_AMI / solid_state_AMR / electromechanical |
| T6-4 | Form factor | WAM | Enumeration | 1S, 2S, 3S, 4S, 9S, 12S, 16S |
| T6-5 | Meter class (ampere rating) | WAM | Text | CL20, CL200, CL320 |
| T6-6 | Year of purchase / received date | WAM | Date | Required by 170 IAC 4-1-4(b) |
| T6-7 | Install date | WAM | Date | |
| T6-8 | Premise ID | CIS | Text | FK to CIS account |
| T6-9 | Service center | WAM | Enumeration | LAF, CRW, THT, FRK, DAN |
| T6-10 | Circuit ID | GIS / WAM | Text | FK to circuits_master |
| T6-11 | County | GIS | Text | |
| T6-12 | Meter group ID | WAM | Text | FK to population table |
| T6-13 | Status | WAM | Enumeration | in_service / removed / retired |
| T6-14 | Last test date | WAM | Date | Required by 170 IAC 4-1-4(b) |
| T6-15 | Last test reason | WAM | Enumeration | See §9.2 method table |
| T6-16 | Last test result summary | WAM | Text | within / fast / slow / non_registering / functional_fail |
| T6-17 | Retirement date and reason | WAM | Date / Text | When applicable |

**Systems of record:** WAM (primary meter asset record), AMI HES (AMI meter operational data and event log), CIS (account and premise linkage). Records are synchronized nightly between WAM and CIS.

<!-- clause: RPL-MTR-PGM-001:6.3 -->
**6.3 Annual Tabulations.** If required by the commission, annual tabulations of the results of all meter tests shall be made, arranged according to average accuracy, by groups set out in section 10 of this rule or as the commission may request. (170 IAC 4-1-4(c)) Gregory Walsh (P19) prepares draft tabulations each January for the prior year and provides them to Angela Ruiz (P20) within fifteen (15) calendar days of year-end, ready for submission to the IURC upon request.

---

<!-- clause: RPL-MTR-PGM-001:7 -->
## 7. Meter Location and Accessibility Standards

<!-- clause: RPL-MTR-PGM-001:7.1 -->
**7.1 Outdoor Preference.** It is recommended that all meters hereafter installed should be located outdoors. Where outdoor installation is impractical, meters may be located indoors, as near as possible to the service entrance, in a clean, dry, safe place. (170 IAC 4-1-5(A)) RPL's AMI rollout placed 98% of meters in outdoor socket positions. Indoor meters require written justification filed in WAM under the premise record before installation.

<!-- clause: RPL-MTR-PGM-001:7.2 -->
**7.2 Mounting Requirements.** Meters shall not be placed on any unstable partitions or supports. Unless unavoidable, meters should not be installed in any location where the visits of the meter reader or tester will cause unreasonable annoyance to the customer or undue inconvenience to the utility. Meters should not be less than 4 feet nor more than 6 feet above the final standing surface, measured from the center of the meter cover, unless authorized by the public utility company. (170 IAC 4-1-5(B)(C))

When a number of meters are placed on the same meter board, the distance between centers may be specified by RPL but in no case shall such distance be less than 7 1/2 inches. (170 IAC 4-1-5(C))

<!-- clause: RPL-MTR-PGM-001:7.3 -->
**7.3 Accessibility.** Meters shall be easily accessible for reading, testing and making necessary adjustments and repairs. (170 IAC 4-1-5(C)) If access to a meter for a scheduled test is denied twice, Luis Hernandez (P18) initiates a WAM notification to the premise within five (5) business days and escalates to CIS customer service for scheduling coordination via CIS order type MTR-TST.

<!-- clause: RPL-MTR-PGM-001:7.4 -->
**7.4 Customer Meter Identification.** Upon request by the residential customer, RPL shall provide the customer with the number of the meter which serves the individual customer's premises, to provide the customer with an opportunity to verify the meter readings. (170 IAC 4-1-5(C)) The CIS customer service representative provides the meter number verbally or in writing within two (2) business days of request, and documents the request in the CIS account notes.

<!-- clause: RPL-MTR-PGM-001:7.5 -->
**7.5 Multi-Unit Metering.** On an installation where similar types of meters record different units (KWH and RKVAH, for example) the meters shall be tagged or marked to indicate the units recorded. (170 IAC 4-1-5(C)) The meter technician applies a WAM-generated laminated label at installation, and Gregory Walsh (P19) verifies labeling at the next test.

---

<!-- clause: RPL-MTR-PGM-001:8 -->
## 8. New and Repaired Meter Acceptance

<!-- clause: RPL-MTR-PGM-001:8.1 -->
**8.1 Regulatory Basis for New Meter Testing.** Each new watthour meter, except self-contained single phase and network meters, shall be inspected and tested and adjusted if necessary: (1) to detect any possible causes for faulty operation; (2) to verify that its register constant, test constant, gear, or dial train to be employed is correctly given; (3) to verify that the meter does not register with all load wires disconnected; and (4) to verify the accuracy of the meter. All new meters may be tested by a meter manufacturer if certified tests are supplied. (170 IAC 4-1-6(a))

<!-- clause: RPL-MTR-PGM-001:8.2 -->
**8.2 RPL Acceptance Sampling (Company Practice).** RPL receives meters in shipment lots directly from vendors. For AMI and AMR solid-state meters, the manufacturer supplies certified factory test data with each lot. Gregory Walsh (P19) reviews the certified test documentation against the accuracy limits in §10 before any lot is accepted. In addition, RPL performs acceptance sampling on each received lot per the sampling plan in §9.3 applied to new-lot sizes. The sample is drawn using the deterministic selection procedure in §9.3.3 with seed derived from lot_id.

<!-- table: RPL-MTR-PGM-001:T8 -->
**Table 8-1: Acceptance Testing by Meter Class**

| Meter Class | Technology | Acceptance Method | Sample Basis | Test Checks |
|---|---|---|---|---|
| Self-contained (2S CL200/CL320, 1S) | AMI / AMR / EM | Manufacturer certified test + RPL audit sample | RPL sampling plan (§9.3) per lot | FL, LL, no-load, register constant |
| Non-self-contained (12S, 16S, 9S) | AMI / AMR | RPL full inspection per 170 IAC 4-1-6(a) + certified tests | 100% inspect; sample tested for accuracy | FL, LL, PF, CT ratio confirmation |
| Electromechanical (2S CL200) | EM | RPL full inspection | Sample per §9.3 plan | FL, LL, no-load, mechanical condition |

<!-- clause: RPL-MTR-PGM-001:8.3 -->
**8.3 Lot Formation.** Each purchase order from a single vendor constitutes one acceptance lot. Lots are not mixed across vendors or form factors. Minimum lot size for sampling is 25 meters; lots below 25 are tested 100%. Each lot is assigned a lot_id in WAM (format: LOT-<YYYY>-<nnnn>).

<!-- clause: RPL-MTR-PGM-001:8.4 -->
**8.4 Lot Rejection and Return.** If the acceptance sample fails the criteria in §9.4, Gregory Walsh (P19) places the lot on hold in WAM, notifies the vendor in writing within five (5) business days, and initiates a return-to-vendor work order. The lot is not placed in service. A replacement lot is treated as a new lot and resampled. Up to one (1) lot per vendor per year may be rejected before triggering a vendor performance review. Records of rejection are retained in RRS-MTR-001.

<!-- clause: RPL-MTR-PGM-001:8.5 -->
**8.5 Repaired Meter Testing.** All meters removed from service shall be carefully inspected for any possible causes of faulty operation that may have developed in use, cleaned and repaired, as necessary, before being tested and adjusted to the accuracy conditions prescribed in section 9 of this rule, prior to being again placed in service, except self-contained meters may be removed and reinstalled without testing if they show no damage or evidence of tampering and are not on a recall or obsolete list. (170 IAC 4-1-6(b)) Repaired meters are tested on a shop test board before re-deployment; records are filed as test_reason = "repaired" in the test results file.

<!-- clause: RPL-MTR-PGM-001:8.6 -->
**8.6 Pre-Installation and Post-Installation Verification.** All watthour meters and demand meters, except self-contained meters, shall be tested prior to their installation or within sixty (60) days after installation. (170 IAC 4-1-6(c)) All watthour and demand meters shall be checked for correct connections, proper mechanical conditions, and suitability of location in its permanent position at the time of installation or within sixty (60) days after installation. (170 IAC 4-1-6(d)) Luis Hernandez (P18) generates a WAM work order type MTR-TST for each non-self-contained meter install, with a due date sixty (60) calendar days after installation. Completion is verified by Gregory Walsh (P19) weekly.

---

<!-- clause: RPL-MTR-PGM-001:9 -->
## 9. In-Service Testing Program

<!-- clause: RPL-MTR-PGM-001:9.1 -->
### 9.1 Group Formation Rules

Meter groups (homogeneous groups) are formed by the following attributes, in order of priority:

1. **Technology** — solid_state_AMI, solid_state_AMR, electromechanical
2. **Vendor family** — Vendor A, Vendor B, Vendor C, legacy-other
3. **Form factor** — 1S, 2S, 3S, 4S, 9S, 12S, 16S
4. **Meter class** — CL20, CL200, CL320
5. **Service type** — residential, commercial, industrial
6. **Install-year band** — 5-year bands (e.g., 2016–2020, 2021–2024) for AMI; full decade bands for AMR and EM

**Minimum group size:** 301 meters (no lot below 301 may be used under Method B). (170 IAC 4-1-10(c)(2)) Groups falling below 301 meters are merged with the nearest comparable group at Angela Ruiz's (P20) approval.
**Maximum group size:** No regulatory maximum; groups above 100,000 meters are subdivided by install-year band for scheduling efficiency.

RPL's current meter population forms 52 active homogeneous groups as of 2024-12-31 (see `data/meter_population_2024-12-31.csv`).

<!-- clause: RPL-MTR-PGM-001:9.2 -->
### 9.2 Test Method by Group

A utility may adopt either Method A (periodic, subsection (b)) or Method B (quality control sampling, subsection (c)) for maintaining the accuracy of self-contained meters without attachments or with frictionless attachments. (170 IAC 4-1-10(a))

RPL operates under **Method B** for all solid-state (AMI and AMR) self-contained groups, having provided written notice to the IURC. Electromechanical meters and all demand-register classes use the applicable **Method A** periodic intervals.

<!-- table: RPL-MTR-PGM-001:T9-2 -->
**Table 9-2: Test Method Summary**

| Group Family | Test Method | Interval / Sample Basis | Regulatory Clause |
|---|---|---|---|
| AMI 2S (all classes, all vendors) | Method B — annual statistical sample | Sample per §9.3; annual lot draw | 170 IAC 4-1-10(c) |
| AMI multi-element (12S, 16S, 9S) | Method B — annual statistical sample | Sample per §9.3 | 170 IAC 4-1-10(c) |
| AMI 3S / 4S / 1S | Method B — annual statistical sample | Sample per §9.3 | 170 IAC 4-1-10(c) |
| AMR 2S (all classes) | Method B — annual statistical sample | Sample per §9.3; transitioning to 16-year periodic per (c)(8) | 170 IAC 4-1-10(c) |
| AMR 12S / 16S / 9S | Method B — annual statistical sample | Sample per §9.3 | 170 IAC 4-1-10(c) |
| EM 2S CL200 (KWH register) | Method A — periodic | 16 years | 170 IAC 4-1-10(d)(1)(A) |
| EM 2S CL200 (mechanical demand register) | Method A — periodic | 8 years | 170 IAC 4-1-10(d)(1)(B) |
| EM mechanical cam pulse initiators | Method A — periodic | 2 years | 170 IAC 4-1-10(d)(1)(D) |
| EM mechanical gear shutter pulse initiators | Method A — periodic | 8 years | 170 IAC 4-1-10(d)(1)(E) |
| Electronic meters (solid-state non-AMI) | Method A — periodic | 16 years | 170 IAC 4-1-10(d)(2) |

> **Note:** A public utility operating under Method B may elect to test the meters included in any group or lot on a test schedule of not more than sixteen (16) years subject to section 9 of this rule. (170 IAC 4-1-10(c)(8)) RPL applies this election to AMR groups with older install-year bands currently reaching the 16-year milestone.

<!-- clause: RPL-MTR-PGM-001:9.3 -->
### 9.3 Sample Size Determination (Company Practice)

**Internal procedure: RPL Meter Sampling Plan (based on variables-sampling principles consistent with ANSI/ASQC Z1.9-1993 Inspection Level II)**

RPL has adopted the following internal sampling plan. These values are company practice; 170 IAC 4-1-10(c)(3) cites ANSI/ASQC Z1.9-1993 Table A-2 as the regulatory reference. Because that standard is paywalled, RPL's own engineering team verified the sample sizes below against variables-sampling principles and documented them in the basis file as `internal_procedure`. This plan produces sample fractions consistent with Inspection Level II principles.

<!-- table: RPL-MTR-PGM-001:T9-3 -->
**Table 9-3: RPL Meter Sampling Plan (Company Practice)**

| Code Letter | Lot Size Range (meters) | Annual Sample Size |
|---|---|---|
| B | 2–8 | 3 |
| C | 9–15 | 4 |
| D | 16–25 | 5 |
| E | 26–50 | 7 |
| F | 51–90 | 10 |
| G | 91–150 | 15 |
| H | 151–280 | 25 |
| I | 281–500 | 35 |
| J | 501–1,200 | 50 |
| K | 1,201–3,200 | 75 |
| L | 3,201–10,000 | 100 |
| M | 10,001–35,000 | 150 |
| N | 35,001–150,000 | 200 |
| P | 150,001–500,000 | 300 |
| Q | 500,001 and above | 400 |

**Random Selection Procedure.** Due care shall be exercised that the meters to be tested shall be drawn at random. (170 IAC 4-1-10(c)(3)) RPL selects sample meters using a seeded pseudorandom number generator (Python `random.seed(year)`) applied to the ordered meter_serial list for each lot. The draw is executed annually by January 15 by Gregory Walsh (P19), documented in `data/inservice_sample_selection_<year>.csv`, and subject to audit from WAM records. Each Public utility shall keep all necessary records to enable the commission to check procedures followed, tests made, and calibrations employed in conformance with this optional testing method. (170 IAC 4-1-10(c)(9))

**Audit trail:** The `inservice_sample_selection_2025.csv` dataset lists every meter drawn for 2025 testing with draw rank, group, lot, and scheduled quarter.

<!-- clause: RPL-MTR-PGM-001:9.4 -->
### 9.4 Acceptance Determination and Actions on a Failed Group

**Acceptance criterion:** The test criterion for acceptance or rejection of each lot shall be based on the test at full load only and shall be that designated for Double Specification Limit–Variability Unknown–Standard Deviation Method at the 2.50 Acceptable Quality Level (normal inspection) as shown in Table B-3, ANSI/ASQC Standard Z1.9, dated 1993. (170 IAC 4-1-10(c)(4)) A lot shall be rejected if the total estimated percent defective (p) exceeds the appropriate maximum allowable percent defective (m) as determined from Table B-3, ANSI/ASQC Standard Z1.9, dated 1993. (170 IAC 4-1-10(c)(6))

RPL computes the standard deviation of full-load accuracy values in the sample, derives Q-statistics using U = 102.00% and L = 98.00%, and determines p from the normal distribution. If p > m (from the internal worksheet, App-B), the lot is rejected.

<!-- table: RPL-MTR-PGM-001:T9-4 -->
**Table 9-4: Decision Table — Lot Acceptance Outcome and Actions**

| Outcome | Condition | Responsible | Action | Timeline | Record |
|---|---|---|---|---|---|
| Lot Accepted | p ≤ m | Gregory Walsh (P19) | Return all sample meters to service; update WAM; advance next annual draw | Within 5 business days of test completion | MTR-F-011; WAM group record |
| Lot Accepted — Borderline (p > 0.75m) | p > 0.75m but ≤ m | Gregory Walsh (P19) | Accepted; note borderline in WAM; monitor next year | Within 5 business days | MTR-F-011; group notation in WAM |
| Lot Rejected | p > m | Angela Ruiz (P20) | Initiate accelerated test schedule per (c)(7); notify IURC per Method B notice obligation | Within 10 business days of rejection | MTR-F-011; WAM rejection record; IURC notification letter |
| Lot Rejected — accelerated testing | Rejected lot, accelerated period | Luis Hernandez (P18) | Complete accelerated testing within a maximum period of ninety-six (96) months; meters shall comply with section 9 of this rule, or shall be retired from service; accelerated testing may be discontinued when subsequent test results show that the lot is within acceptable limits of accuracy | Within 96 calendar months | Accelerated schedule in WAM; MTR-F-011 per test |
| Functional Failure | Non-accuracy defect on removal | Meter Technician | Replace meter; log CIS order MTR-TST; issue billing review if needed | At test | MTR-F-011; CIS billing_review_ref |

> **Caution:** A rejected lot may not be placed back into active service status in WAM until either (a) accelerated testing demonstrates the lot is within acceptable limits, or (b) affected meters are retired. Gregory Walsh (P19) confirms compliance with Angela Ruiz (P20) before any hold is lifted.

<!-- clause: RPL-MTR-PGM-001:9.5 -->
### 9.5 Periodic Schedule Management (Method A and Method B 16-Year Election)

For meters under Method A or the 16-year Method B election, Luis Hernandez (P18) computes next-due dates in WAM by adding the applicable interval to the last_test_date of each meter. WAM auto-generates work order type MTR-TST for meters within sixty (60) calendar days of their due date. Gregory Walsh (P19) reviews the open work-order queue weekly and assigns meter technicians to shop or field tests based on meter type and location.

**Field vs. Shop Split:** AMI and AMR meters are typically removed and tested in the Meter Shop & Standards Laboratory at the Lafayette HQ campus using shop test boards. EM meters in rural service centers (CRW, THT, FRK, DAN) may be tested in the field using portable standards. The shop/field determination is recorded in the test results dataset.

**Due-date calendar:** `data/inservice_sample_selection_2025.csv` lists the 2025 scheduled sample; the 2025 periodic due-dates by group and quarter are summarized in §15.

---

<!-- clause: RPL-MTR-PGM-001:10 -->
## 10. Accuracy Limits and Average-Accuracy Method

<!-- clause: RPL-MTR-PGM-001:10.1 -->
**10.1 Average-Accuracy Computation.** Average percentage registration is the average of the percentage registration at light load (LL) and at full load (FL). Thus, average percentage accuracy = (FL + LL) ÷ 2. (170 IAC 4-1-8(a))

The accuracy at light load shall be determined at a load of approximately ten percent (10%) of the rated test amperes of the meter. The accuracy at full load shall be determined at a load of one hundred percent (100%) of the rated test amperes of the meter. (170 IAC 4-1-8(a))

**Determining individual test values:** The accuracy at light load shall be determined by taking the average of at least two (2) tests, which tests must agree within one-half of one percent (.5%) unless the meter has been tested by an automated device in which case one (1) test will be sufficient. The accuracy at full load shall be determined in a like manner. (170 IAC 4-1-8(b))

The average "as found" accuracy of a meter may be determined from one (1) light load test and one (1) full load test if: (1) such average accuracy is less than one hundred three percent (103%); and (2) if such meter is to be adjusted. (170 IAC 4-1-8(b))

<!-- clause: RPL-MTR-PGM-001:10.2 -->
**10.2 Accuracy Limits — Watthour Meters**

No meter shall be placed in service or allowed to remain in service that has not been tested for accuracy of measurements and adjusted, if necessary, to meet the following requirements. (170 IAC 4-1-9(b))

<!-- table: RPL-MTR-PGM-001:T10-2 -->
**Table 10-2: Accuracy Limits — Watthour Meters (170 IAC 4-1-9(b)(1))**

| Limit | Requirement | Technology Applies |
|---|---|---|
| Average error | Not over two percent (2%), plus or minus | All watthour meters (AMI, AMR, EM) |
| Error at full load | Not over one percent (1%), plus or minus | All watthour meters |
| Error at light load | Not over three percent (3%), plus or minus | All watthour meters |

<!-- clause: RPL-MTR-PGM-001:10.3 -->
**10.3 No-Load Prohibition.** No watthour meter that registers at no load (the moving element making more than one (1) complete revolution when at "no load"), when the applied voltage is less than one hundred ten percent (110%) of standard service voltage, shall be placed in service or allowed to remain in service in such condition. (170 IAC 4-1-9(a)) The meter technician performs a no-load check on each meter tested; any meter that fails is immediately retired or repaired before return to service.

<!-- clause: RPL-MTR-PGM-001:10.4 -->
**10.4 Accuracy Limits — Demand Meters**

<!-- table: RPL-MTR-PGM-001:T10-4 -->
**Table 10-4: Accuracy Limits — Demand Registers (170 IAC 4-1-9(b)(3)–(4))**

| Meter Type | Limit |
|---|---|
| Integrating demand meter — electrical element | Same as watthour meter limits in §10.2 |
| Integrating demand meter — timing element | Cumulative error not in excess of plus or minus two percent (2%) for entire billing period |
| Integrating demand meter — TOU (time of day factor) | Must not indicate a difference of more than ten (10) minutes from correct time; incorrect time caused by temporary loss of utility service corrected by end of following work day |
| Lagged demand meter — electromagnetic type | Error not to exceed two percent (2%), plus or minus, of full scale indication |
| Lagged demand meter — thermal type | Error not to exceed four percent (4%), plus or minus, of full scale indication |
| Curve drawing instruments | Electrical element error not to exceed two percent (2%), plus or minus, of full scale indication |

<!-- clause: RPL-MTR-PGM-001:10.5 -->
**10.5 Power Factor Test — CT-Metered Installations.** Watthour meters, except self-contained meters, which are to be used on circuits supplying inductive load, shall also be tested before installation at one hundred percent (100%) of manufacturer's rated test current at fifty percent (50%) lagging power factor, and, if necessary, adjusted so that the error under such conditions will not be more than two percent (2%), plus or minus. (170 IAC 4-1-9(b)(5)) All 12S, 16S, and 9S meters in RPL's fleet are tested at 50% PF before installation. The PF test result (as_found_pf_pct) is recorded in the test results dataset.

<!-- clause: RPL-MTR-PGM-001:10.6 -->
**10.6 Worked Calculation Example**

A Vendor A AMI 2S CL200 meter is removed from a residential premise in Tippecanoe County for in-service sample testing. Shop test board TB-04 records:

- Full Load test pass 1: 100.18% · pass 2: 100.22% → FL average = 100.20%
- Light Load test pass 1: 99.85% · pass 2: 99.91% → LL average = 99.88%

Average accuracy = (100.20 + 99.88) ÷ 2 = **100.04%**

Limits check:
- Average error = |100.04 − 100.00| = 0.04% ≤ 2.00% ✓
- FL error = |100.20 − 100.00| = 0.20% ≤ 1.00% ✓
- LL error = |99.88 − 100.00| = 0.12% ≤ 3.00% ✓
- **Result: WITHIN LIMITS — return to service; action_taken = returned_to_service**

For Method B lot acceptance, only the FL value (100.20%) is entered into the Q-statistic calculation. Gregory Walsh (P19) documents this calculation in App-B (Group Acceptance Worksheet).

---

<!-- clause: RPL-MTR-PGM-001:11 -->
## 11. Test Equipment and Standards

<!-- clause: RPL-MTR-PGM-001:11.1 -->
**11.1 Regulatory Requirements.** Each public utility shall provide or have available such standard meters, instruments and other equipment and facilities as may be necessary to make the tests required by these rules. Such equipment and facilities shall be subject to review by the commission, and shall be available at all reasonable times for the inspection by any authorized representative of the commission. (170 IAC 4-1-7(B))

<!-- clause: RPL-MTR-PGM-001:11.2 -->
**11.2 Reference Standard Calibration Interval.** Each public utility shall provide or have available suitable indicating electrical instruments, wattmeters and watthour meters (hereinafter called "reference standards") as may be necessary for testing the accuracy of portable watthour standards and other portable instruments used for testing service meters. Reference standards of all kinds shall be tested and adjusted, if necessary, at least once every two years by a recognized standardizing laboratory. (170 IAC 4-1-7(C)) Gregory Walsh (P19) maintains a calibration due-date schedule in WAM (equipment type `STD-REF`). A reference standard not yet recalibrated within two (2) calendar years is immediately taken out of service until recalibrated.

<!-- clause: RPL-MTR-PGM-001:11.3 -->
**11.3 Portable Standard Tolerances.** All portable watthour meter standards shall be checked against the corresponding reference standards as often as may be necessary to give reasonable assurance that the errors will not change enough between successive calibrations to materially affect the results. If such check shows any portable watthour meter standard to be in error more than one per cent (1%) plus or minus, at any load at which the standard will be used, the standard shall be tested, adjusted and certified in the laboratory of the public utility, or in some other approved laboratory, unless calibration correction is used. (170 IAC 4-1-7(D)) Each portable watthour meter standard shall at all times be accompanied by a certificate or calibration card, signed by the proper authority, giving the date when it was last certified. (170 IAC 4-1-7(D))

RPL checks portable standards against reference standards before each field campaign and records the comparison deviation in `data/standards_calibration_2024.csv`.

<!-- clause: RPL-MTR-PGM-001:11.4 -->
**11.4 Portable Indicating Instruments.** All portable indicating electrical testing instruments (voltmeters, ammeters, wattmeters), when in regular use, shall be checked against suitable reference standards as often as may be necessary. If found appreciably in error at zero or more than one per cent (1%) of full scale value at commonly used scale deflection shall, unless calibration correction is used, be adjusted and certified in some approved laboratory. (170 IAC 4-1-7(E))

<!-- clause: RPL-MTR-PGM-001:11.5 -->
**11.5 Certification Records.** Records of certification and calibration shall be kept on file in the office of the public utility. (170 IAC 4-1-7(F)) All calibration certificates are scanned and attached to the standard's asset record in WAM and filed physically at the Meter Shop & Standards Laboratory. Records series: RRS-MTR-003.

<!-- clause: RPL-MTR-PGM-001:11.6 -->
**11.6 Traceability Chain**

```
National Institute of Standards and Technology (NIST)
          ↓ (accredited calibration contract)
Accredited External Calibration Laboratory (NVLAP/A2LA accredited)
          ↓ (at least every 2 years per 170 IAC 4-1-7(C))
RPL Reference Standards (STD-REF-001 through STD-REF-003)
   [permanently mounted, Meter Shop & Standards Laboratory, Lafayette HQ]
          ↓ (before each field campaign; ≥monthly in shop)
RPL Shop Test Boards (TB-01 through TB-08)
          ↓
RPL Portable Standards (PRT-001 through PRT-032)
          ↓
Revenue Meters Under Test
```

<!-- table: RPL-MTR-PGM-001:T11-6 -->
**Table 11-6: Standards Equipment Register Summary (see App-C for full register)**

| Level | Count | Recalibration Interval | Tolerance Check |
|---|---|---|---|
| Reference standards (STD-REF) | 3 | ≤ 2 years (regulatory) | Accredited external lab |
| Shop test boards (TB) | 8 | Internal: annually against STD-REF | 170 IAC 4-1-7(C) principles |
| Portable standards (PRT) | 32 | Before each field campaign; if >1% error → out of service (regulatory) | Against STD-REF per 170 IAC 4-1-7(D) |

<!-- clause: RPL-MTR-PGM-001:11.7 -->
**11.7 Out-of-Tolerance Impact Review.** If any reference standard or test board is found out of calibration, Gregory Walsh (P19) reviews all test results recorded using that equipment since its last certified calibration. If the out-of-tolerance condition could have affected billing accuracy, Angela Ruiz (P20) initiates a billing review for affected accounts via CIS transaction code ADJ-MS or ADJ-MF as appropriate. Results are documented in RRS-MTR-002.

---

<!-- clause: RPL-MTR-PGM-001:12 -->
## 12. AMI Meter Health Monitoring

**Company practice (not a substitute for any regulatory requirement in §§8–10).**

<!-- clause: RPL-MTR-PGM-001:12.1 -->
**12.1 AMI HES Event Monitoring.** The AMI Head-End System (AMI HES) continuously collects event data from each AMI meter. The AMI Operations team monitors the following flags daily and initiates removal-for-test via WAM order type MTR-TST when any flag is active for more than fourteen (14) consecutive days:

- Zero-consumption flag (potential non-registering meter)
- Tamper event flag (potential accuracy distortion)
- Power quality disturbance event (sustained voltage anomaly)
- Metrology diagnostic fault (device self-reported accuracy concern)
- Disconnect switch failure report

<!-- clause: RPL-MTR-PGM-001:12.2 -->
**12.2 Analytics Thresholds.** The AMI HES analytics engine (company practice) flags a meter for investigation if its 30-day rolling consumption deviates by more than ±35% from the prior 12-month baseline adjusted for degree-days. Gregory Walsh (P19) reviews the analytics queue each Monday and assigns investigation orders in WAM by Wednesday of the same week.

<!-- clause: RPL-MTR-PGM-001:12.3 -->
**12.3 Removal-for-Test.** Meters removed under §12.1 or §12.2 are tested at the shop as test_reason = "removal_as_found" before the AMI HES flag investigation is closed. Results are stored in RRS-MTR-002. This program supplements but does not replace the Method B annual sample required under 170 IAC 4-1-10(c).

> **Note:** AMI health monitoring constitutes company practice. It does not reduce the required annual sample size under Method B or alter the acceptance criteria in §9.4.

---

<!-- clause: RPL-MTR-PGM-001:13 -->
## 13. Customer-Requested and Commission-Supervised Tests

<!-- clause: RPL-MTR-PGM-001:13.1 -->
**13.1 Customer Test Rights.** Each public utility supplying electrical energy shall make a test of the accuracy of registration of a meter upon written request by a customer. A second test of this meter may be requested after twelve (12) months. The first and second tests of a customer's meter shall be at no cost to the customer. (170 IAC 4-1-11(a))

<!-- clause: RPL-MTR-PGM-001:13.2 -->
**13.2 Subsequent Test Fee Conditions.** The customer may be required to bear the reasonable cost of any subsequent tests of the customer's meter if the: (1) meter was: (A) tested within the prior thirty-six (36) months at the customer's request; and (B) found to be in compliance with section 10(c)(4) and 10(c)(5) of this rule; (2) test is made: (A) at the customer's request; or (B) due to a billing dispute; and (3) meter is found to be in compliance with section 10(c)(4) and 10(c)(5) of this rule. (170 IAC 4-1-11(b)) If RPL requires payment, RPL shall disclose the cost of the test to the customer prior to the test being performed. (170 IAC 4-1-11(c)) The applicable fee is set by Tariff Rule 16, Sheet 45 (§1.6 Table F-9): $40.00 residential/single-phase; $95.00 polyphase/demand.

<!-- clause: RPL-MTR-PGM-001:13.3 -->
**13.3 Written Test Report.** A written report giving the results of the test shall be made to the customer within ten (10) days after the test is complete, and a complete record of the test shall be kept on file in the office of the public utility. (170 IAC 4-1-11(d)) Gregory Walsh (P19) issues the report using MTR-F-011 within ten (10) calendar days of test completion. The report is mailed and emailed to the customer and filed in RRS-MTR-002.

<!-- clause: RPL-MTR-PGM-001:13.4 -->
**13.4 Customer Appeal.** Any appeal, in regard to the results of the customer's meter test, shall be filed with the commission under section 12 of this rule within five (5) days of the date of the report. (170 IAC 4-1-11(e)) The written report to the customer includes language advising of this right. RPL records appeal notifications in CIS under order type MTR-TST with a note referencing the customer_request_id.

<!-- clause: RPL-MTR-PGM-001:13.5 -->
**13.5 Commission-Supervised Tests.** The IURC may request observation or supervision of any meter test. Angela Ruiz (P20) coordinates access with the IURC Energy Division (317-232-2785) and ensures a copy of MTR-F-011 is provided to the commission representative at the conclusion of the test. Commission-supervised tests are recorded as test_reason = "commission_supervised" in the test results dataset.

**Cross-reference:** Full customer request procedures, including intake via MTR-F-010, fee charging workflow, and billing adjustment procedures, are governed by RPL-CS-PRO-007 (Meter Test Request & Billing Adjustment Procedure).

---

<!-- clause: RPL-MTR-PGM-001:14 -->
## 14. 2024 Program Results (Preliminary — Data Extracted 2025-01-03)

> *All 2024 results are preliminary pending final data reconciliation. Data extracted 2025-01-03.*

<!-- clause: RPL-MTR-PGM-001:14.1 -->
**14.1 Tests Performed by Reason and Technology**

<!-- table: RPL-MTR-PGM-001:T14-1 -->
**Table 14-1: 2024 Test Count by Reason and Technology**

| Reason | Solid-State AMI | Solid-State AMR | Electromechanical | Total |
|---|---|---|---|---|
| in_service_sample | 2,280 | 480 | 62 | 2,822 |
| in_service_periodic | 0 | 144 | 412 | 556 |
| new_acceptance | 1,020 | 0 | 0 | 1,020 |
| repaired | 38 | 12 | 22 | 72 |
| customer_request | 450 | 88 | 82 | 620 |
| removal_as_found | 512 | 118 | 0 | 630 |
| commission_supervised | 3 | 1 | 0 | 4 |
| **Total** | **4,303** | **843** | **578** | **5,724** |

<!-- clause: RPL-MTR-PGM-001:14.2 -->
**14.2 Pass/Fail Summary by Technology**

<!-- table: RPL-MTR-PGM-001:T14-2 -->
**Table 14-2: Accuracy Results Summary by Technology (in-service tests only)**

| Technology | Tests | Within Limits | Fast (>+2%) | Slow (<−2%) | Non-Registering | Functional Fail |
|---|---|---|---|---|---|---|
| Solid-state AMI | 3,283 | 3,274 | 5 | 4 | 0 | 48 |
| Solid-state AMR | 843 | 839 | 2 | 2 | 0 | 8 |
| Electromechanical | 578 | 551 | 4 | 21 | 2 | 0 |
| **Total** | **4,704** | **4,664** | **11** | **27** | **2** | **56** |

Within-limits rate: AMI 99.73%; AMR 99.76%; EM 95.33%. EM meters show the highest error rate, consistent with age profile (install years 1972–2004). No group acceptance failure occurred in 2024.

<!-- clause: RPL-MTR-PGM-001:14.3 -->
**14.3 Average Accuracy Distribution by Technology**

*Chart 14-3A: Average Accuracy Histogram by Technology (bins: ±0.1% around 100.00%) — see `render/charts/T14_accuracy_histogram.png`*

<!-- table: RPL-MTR-PGM-001:T14-3 -->
**Table 14-3: Average Accuracy Distribution (±0.1% bins, in-service tests)**

| Accuracy Bin | AMI Count | AMR Count | EM Count |
|---|---|---|---|
| < 97.0% | 0 | 0 | 1 |
| 97.0–97.9% | 0 | 0 | 4 |
| 98.0–98.9% | 1 | 1 | 12 |
| 99.0–99.9% | 142 | 38 | 144 |
| 99.9–100.0% | 1,488 | 312 | 148 |
| 100.0–100.1% | 1,472 | 306 | 122 |
| 100.1–100.9% | 176 | 183 | 98 |
| 101.0–101.9% | 4 | 3 | 14 |
| 102.0–102.9% | 0 | 0 | 4 |
| ≥ 103.0% | 0 | 0 | 1 |

<!-- clause: RPL-MTR-PGM-001:14.4 -->
**14.4 Group Acceptance Summary (Method B — sampled groups)**

*Chart 14-4A: Group X̄ ± σ Dot Plot — see `render/charts/T14_group_accuracy_dotplot.png`*

<!-- table: RPL-MTR-PGM-001:T14-4 -->
**Table 14-4: Method B Group Acceptance Results (partial — top 15 groups by count; see CSV for full dataset)**

| Group ID | Technology | In-Service Count | Sample Size | X̄ FL (%) | σ FL (%) | Estimated %Defective p | Result |
|---|---|---|---|---|---|---|---|
| AMI-A-2S-CL200-2017-2021 | Solid-state AMI | 182,400 | 200 | 100.04 | 0.08 | 0.00 | Accepted |
| AMI-A-2S-CL200-2016 | Solid-state AMI | 22,800 | 150 | 100.02 | 0.09 | 0.00 | Accepted |
| AMI-A-2S-CL200-2022-2024 | Solid-state AMI | 54,432 | 200 | 100.01 | 0.07 | 0.00 | Accepted |
| AMI-B-2S-CL200-2017-2021 | Solid-state AMI | 45,600 | 200 | 100.03 | 0.10 | 0.00 | Accepted |
| AMI-A-2S-CL320 | Solid-state AMI | 7,424 | 75 | 100.05 | 0.09 | 0.00 | Accepted |
| AMI-A-12S-CL200 | Solid-state AMI | 11,136 | 100 | 100.02 | 0.11 | 0.00 | Accepted |
| AMI-B-12S-CL200 | Solid-state AMI | 3,712 | 50 | 100.03 | 0.12 | 0.00 | Accepted |
| AMI-A-16S-CL200 | Solid-state AMI | 8,192 | 75 | 100.01 | 0.10 | 0.00 | Accepted |
| AMI-A-9S-CL20 | Solid-state AMI | 9,280 | 75 | 100.06 | 0.13 | 0.00 | Accepted |
| AMR-B-2S-CL200-2005-2009 | Solid-state AMR | 14,130 | 150 | 99.98 | 0.22 | 0.00 | Accepted |
| AMR-B-2S-CL200-2010-2015 | Solid-state AMR | 11,424 | 150 | 100.00 | 0.18 | 0.00 | Accepted |
| AMR-C-2S-CL200 | Solid-state AMR | 2,706 | 50 | 99.97 | 0.24 | 0.00 | Accepted |
| AMR-12S-16S | Solid-state AMR | 2,198 | 35 | 100.01 | 0.21 | 0.00 | Accepted |
| EM-C-2S-CL200-1972-1990 | Electromechanical | 3,760 | 50 | 99.64 | 0.52 | 0.01 | Accepted |
| EM-C-2S-CL200-1991-2004 | Electromechanical | 3,076 | 35 | 99.82 | 0.41 | 0.00 | Accepted |

All 52 active groups passed their 2024 acceptance tests. No accelerated testing was required.

<!-- clause: RPL-MTR-PGM-001:14.5 -->
**14.5 New Meter Acceptance**

<!-- table: RPL-MTR-PGM-001:T14-5 -->
**Table 14-5: 2024 New Meter Lot Acceptance Summary**

| Vendor | Technology | Lots Received | Lot Sizes (range) | Lots Accepted | Lots Rejected | Notes |
|---|---|---|---|---|---|---|
| Vendor A | AMI 2S CL200 | 3 | 4,800–5,400 | 2 | 1 | 1 lot rejected Mar 2024; 3 sample failures; returned to vendor |
| Vendor A | AMI 12S CL200 | 1 | 1,200 | 1 | 0 | |
| Vendor B | AMI 2S CL200 | 2 | 2,400–3,600 | 2 | 0 | |
| **Total** | | **6** | | **5** | **1** | |

The one rejected lot (Vendor A, AMI 2S CL200, received 2024-03-12) had 3 of 75 sample meters with full-load accuracy below 98.00%. The lot was returned to Vendor A; a replacement lot was accepted 2024-05-08.

<!-- clause: RPL-MTR-PGM-001:14.6 -->
**14.6 Customer Test Requests — 2024 Outcomes**

<!-- table: RPL-MTR-PGM-001:T14-6 -->
**Table 14-6: Customer Test Requests 2024 (620 total)**

| Result | Count | Within % | Fee Charged |
|---|---|---|---|
| Within limits | 536 | 86.5% | As applicable per §13.2 |
| Fast | 28 | 4.5% | No charge; billing adjustment issued |
| Slow | 44 | 7.1% | No charge; billing adjustment issued |
| Non-registering | 4 | 0.6% | No charge; billing adjustment issued |
| Functional fail | 8 | 1.3% | No charge; meter replaced |

All 620 requests received a written test report (MTR-F-011) within ten (10) calendar days of test completion. Billing adjustment references issued for all out-of-limits tests per CIS codes ADJ-MS or ADJ-MF.

---

<!-- clause: RPL-MTR-PGM-001:15 -->
## 15. 2025 Test Plan

<!-- clause: RPL-MTR-PGM-001:15.1 -->
**15.1 Annual Sample Draw — Method B Groups**

The 2025 annual sample draw was executed 2025-01-14 using seed 2025 per §9.3.3 and is documented in `data/inservice_sample_selection_2025.csv`.

<!-- table: RPL-MTR-PGM-001:T15-1 -->
**Table 15-1: 2025 Planned Method B Sample by Technology and Quarter**

| Technology | Q1 (Jan–Mar) | Q2 (Apr–Jun) | Q3 (Jul–Sep) | Q4 (Oct–Dec) | Total Planned |
|---|---|---|---|---|---|
| Solid-state AMI | 650 | 680 | 720 | 670 | 2,720 |
| Solid-state AMR | 110 | 120 | 125 | 115 | 470 |
| Electromechanical (Method B) | 18 | 18 | 18 | 18 | 72 |
| **Subtotal — sample** | **778** | **818** | **863** | **803** | **3,262** |

<!-- clause: RPL-MTR-PGM-001:15.2 -->
**15.2 Periodic Tests Due 2025 (Method A / 16-Year Election)**

<!-- table: RPL-MTR-PGM-001:T15-2 -->
**Table 15-2: 2025 Periodic Tests by Group and Quarter**

| Group | Test Method | Interval | Q1 | Q2 | Q3 | Q4 | Total Due |
|---|---|---|---|---|---|---|---|
| EM-C-2S-CL200-1972-1990 (mechanical KWH) | Method A | 16 years | 48 | 52 | 56 | 44 | 200 |
| EM-2S demand registers (mechanical demand) | Method A | 8 years | 30 | 32 | 30 | 28 | 120 |
| AMR-16-yr-election groups | Method B (c)(8) | 16 years | 32 | 28 | 30 | 26 | 116 |
| **Subtotal — periodic** | | | **110** | **112** | **116** | **98** | **436** |

**Total 2025 planned in-service tests: 3,698** (excludes new acceptance and customer requests)

**Workload estimate:** Each shop test averages 0.35 technician-hours; each field test averages 1.2 technician-hours. Based on the 2025 plan, estimated total: 3,388 shop tests × 0.35 hr = 1,186 hours; 310 field tests × 1.2 hr = 372 hours. **Total estimated: 1,558 technician-hours.** Available capacity: 14 technicians × 48 working weeks × 2.5 testing hr/week = 1,680 hours. Sufficient capacity.

---

<!-- clause: RPL-MTR-PGM-001:16 -->
## 16. Program KPIs (Company Practice)

<!-- table: RPL-MTR-PGM-001:T16 -->
| ID | KPI | Target | 2024 Result | Trend |
|---|---|---|---|---|
| T16-1 | In-service within-limits rate — AMI | ≥ 99.5% | 99.73% | ✓ |
| T16-2 | In-service within-limits rate — AMR | ≥ 99.0% | 99.76% | ✓ |
| T16-3 | In-service within-limits rate — EM | ≥ 93.0% | 95.33% | ✓ |
| T16-4 | Customer test report issued within 10 days | 100% | 100% | ✓ |
| T16-5 | Reference standard recalibration on time | 100% | 100% | ✓ |
| T16-6 | Annual sample draw completed by Jan 31 | 100% | 100% | ✓ |
| T16-7 | Rejected new lots per vendor per year | ≤ 1 | 1 (Vendor A) | ✓ |
| T16-8 | Group acceptance failures | 0 | 0 | ✓ |

---

<!-- clause: RPL-MTR-PGM-001:17 -->
## 17. Records and Retention

All records required by these rules shall be preserved for at least three years except as otherwise provided herein or by IC 8-1-2-40. Such records shall be kept within the State at the principal place of business of the public utility, or at such other places as the utility shall designate after notification to the commission, and shall be open for examination by the commission or its representatives. (170 IAC 4-1-3)

<!-- table: RPL-MTR-PGM-001:T17 -->
| Record Series | Description | System | Minimum Retention | Ref |
|---|---|---|---|---|
| RRS-MTR-001 | Meter history records (purchase, install, test, retirement) | WAM | At least 3 years from retirement; permanent meter records as long as meter history available | 170 IAC 4-1-3; 170 IAC 4-1-4(b) |
| RRS-MTR-002 | Meter test reports (in-service, acceptance, customer-requested, commission-supervised) | WAM + DCS | At least 3 years; customer test reports minimum 36 months (fee condition reference) | 170 IAC 4-1-3; 170 IAC 4-1-11(b) |
| RRS-MTR-003 | Standards certification and calibration records | WAM + DCS | At least 3 years from supersession | 170 IAC 4-1-3; 170 IAC 4-1-7(F) |

Records are kept at 400 Wabash Commons Drive, Lafayette, IN 47901 (HQ, principal place of business). Angela Ruiz (P20) has notified the IURC of the office at which records are kept per 170 IAC 4-1-3. RPL uses DCS as the controlled document system; WAM as the meter asset and test event system; and CIS for account linkage.

**Internal performance target:** RPL retains all meter test records for ten (10) years from the test date to support billing adjustment reviews and historical trend analysis (company practice; see RPL-LEG-RRS-001).

---

<!-- clause: RPL-MTR-PGM-001:18 -->
## 18. Training and Technician Qualification

<!-- table: RPL-MTR-PGM-001:T18-TRN -->
| Training Code | Title | Audience | Frequency | Owner |
|---|---|---|---|---|
| MTR-T-03 | Meter Testing Procedures and Accuracy Standards | All Meter Technicians | Annual | Gregory Walsh (P19) |
| FS-T-12 | Field Safety for Meter Testing | All Meter Technicians | Annual | Luis Hernandez (P18) |
| MTR-T-03-ADV | Advanced Test Equipment Calibration | Senior Technicians | Biennial | Gregory Walsh (P19) |

**Technician Qualification:** Each meter technician must complete MTR-T-03 before performing unsupervised in-service tests. New technicians are supervised by a qualified technician for their first thirty (30) tests. Qualification records are maintained in the employee training record system and reconciled annually by Luis Hernandez (P18).

**Recertification:** Any technician absent from meter testing duties for more than twelve (12) consecutive months must complete MTR-T-03 before resuming unsupervised test work.

Training completion records are retained in RRS-TRN-001.

---

<!-- clause: RPL-MTR-PGM-001:19 -->
## 19. Related Documents

| Document ID | Title |
|---|---|
| RPL-CS-PRO-007 | Meter Test Request & Billing Adjustment Procedure |
| RPL-LEG-RRS-001 | Records Retention Schedule |
| RPL-CMP-REG-001 | Regulatory Obligations Register |
| RPL-TAR-GRR-012 | Tariff for Electric Service, IURC No. 12 (Rule 9, Sheets 27–29; Rule 16, Sheet 45) |
| RPL-SAF-PRO-002 | Electrical Safety Rulebook |

---

<!-- clause: RPL-MTR-PGM-001:20 -->
## 20. Revision History

| Version | Date | Author | Change Summary |
|---|---|---|---|
| 5.2 | 2024-02-05 | Gregory Walsh (P19) | Added AMI health monitoring §12; updated 2023 results tables; revised KPI targets based on 2022–2023 trend |
| 5.1 | 2023-01-20 | Gregory Walsh (P19) | Expanded §9.3 sampling plan table to include code letters B–Q; updated test board inventory to reflect TB-08 addition |
| 5.0 | 2022-02-14 | Gregory Walsh (P19) | Incorporated Method B written notice to IURC for AMR groups; restructured §9.2 method table; updated §10.4 demand meter limits |
| 4.2 | 2021-03-10 | Gregory Walsh (P19) | Updated accuracy results through 2020; revised Group IDs after AMI rollout completion; added §12 AMI analytics (first version) |
| **6.0** | **2025-01-08** | **Gregory Walsh (P19)** | **Updated for 2024 results; expanded §14.4 group acceptance table to 52 groups; revised §15 2025 test plan; updated standards register (App-C) to reflect new PRT-031, PRT-032 purchased Q3 2024** |

---

<!-- clause: RPL-MTR-PGM-001:21 -->
## 21. Approval Block

| Role | Name | Title | Signature | Date |
|---|---|---|---|---|
| Prepared by (Owner) | Gregory Walsh | Manager, Meter Shop & Standards Laboratory | ___________________ | 2025-01-08 |
| Reviewed by | Angela Ruiz | Director, Metering | ___________________ | 2025-01-08 |
| Approved by | Michael Brennan | Vice President, Operations | ___________________ | 2025-01-08 |

*Effective date: 2025-01-13*

---

<!-- clause: RPL-MTR-PGM-001:App-A -->
## Appendix A: Meter Test Report MTR-F-011 (Rev. 01/2025)

**Form ID:** MTR-F-011 (Rev. 01/2025)

**Part A — Meter Identification**

<!-- clause: RPL-MTR-PGM-001:App-A.F1 -->
| Field | |
|---|---|
| A.F1 · Test ID (system-generated) | ____________ |
| A.F2 · Meter serial number | ____________ |
| A.F3 · Meter technology | ☐ AMI  ☐ AMR  ☐ Electromechanical |
| A.F4 · Form / Class | ____________ |
| A.F5 · Vendor family | ____________ |
| A.F6 · Meter group ID | ____________ |
| A.F7 · Premise ID | ____________ |
| A.F8 · Account ID | ____________ |
| A.F9 · Service center | ____________ |
| A.F10 · Circuit ID | ____________ |
| A.F11 · County | ____________ |

**Part B — Test Conditions**

<!-- clause: RPL-MTR-PGM-001:App-A.F2 -->
| Field | |
|---|---|
| B.F1 · Test date (`YYYY-MM-DD`) | ____________ |
| B.F2 · Test location | ☐ Shop  ☐ Field |
| B.F3 · Test board / portable standard ID | ____________ |
| B.F4 · Standard last calibration date | ____________ |
| B.F5 · Technician ID (MT-###) | ____________ |
| B.F6 · Test reason | ☐ in_service_sample  ☐ in_service_periodic  ☐ new_acceptance  ☐ repaired  ☐ customer_request  ☐ removal_as_found  ☐ commission_supervised |
| B.F7 · Sample lot ID (if applicable) | ____________ |
| B.F8 · Customer request ID (if applicable) | ____________ |
| B.F9 · Meter reading before test | ____________ |

**Part C — As-Found Test Results**

<!-- clause: RPL-MTR-PGM-001:App-A.F3 -->
| Field | |
|---|---|
| C.F1 · FL test 1 (%) | ____________ |
| C.F2 · FL test 2 (%) | ____________ |
| C.F3 · FL average (%) | ____________ |
| C.F4 · LL test 1 (%) | ____________ |
| C.F5 · LL test 2 (%) | ____________ |
| C.F6 · LL average (%) | ____________ |
| C.F7 · PF test (% — CT meters only) | ____________ |
| C.F8 · Average accuracy = (FL avg + LL avg) ÷ 2 (%) | ____________ |
| C.F9 · Within limits? | ☐ Y  ☐ N |
| C.F10 · Functional result | ☐ pass  ☐ display_fail  ☐ register_fail  ☐ comm_fail  ☐ disconnect_switch_fail  ☐ physical_damage |

**Part D — Adjustment and As-Left Results (EM only)**

<!-- clause: RPL-MTR-PGM-001:App-A.F4 -->
| Field | |
|---|---|
| D.F1 · Adjusted? | ☐ Y  ☐ N |
| D.F2 · As-left FL (%) | ____________ |
| D.F3 · As-left LL (%) | ____________ |
| D.F4 · As-left average accuracy (%) | ____________ |

**Part E — Action and Disposition**

<!-- clause: RPL-MTR-PGM-001:App-A.F5 -->
| Field | |
|---|---|
| E.F1 · Action taken | ☐ returned_to_service  ☐ retired  ☐ adjusted_returned  ☐ replaced_billing_review |
| E.F2 · Billing review reference | ____________ |
| E.F3 · Technician signature | ___________________ |
| E.F4 · Supervisor review (Gregory Walsh, P19) | ___________________ |
| E.F5 · Review date | ____________ |

*Office use only: WAM work order number ________________ · Record filed: ☐ RRS-MTR-002*

---

<!-- clause: RPL-MTR-PGM-001:App-B -->
## Appendix B: Group Acceptance Worksheet

**Purpose:** Guides the meter technician and Gregory Walsh (P19) through the Method B lot acceptance calculation per 170 IAC 4-1-10(c)(4)–(6).

**Step 1:** Record lot ID, group ID, lot size, and sample size n.

**Step 2:** List as-found full-load accuracy values x₁, x₂, …, xₙ for the sample.

**Step 3:** Compute X̄ = (Σxᵢ) / n and s = √[Σ(xᵢ − X̄)² / (n−1)].

**Step 4:** Compute Q-statistics:
- Q_U = (U − X̄) / s where U = 102.00%
- Q_L = (X̄ − L) / s where L = 98.00%

**Step 5:** From standard normal tables, estimate p_U = P(Z > Q_U) and p_L = P(Z < −Q_L). Total estimated percent defective p = p_U + p_L.

**Step 6:** Determine maximum allowable percent defective m from the Method B acceptance table (AQL 2.50, Double Spec Limit). Compare p to m:
- If p ≤ m: **LOT ACCEPTED** — complete Part E of MTR-F-011.
- If p > m: **LOT REJECTED** — initiate accelerated test schedule per §9.4 and notify Angela Ruiz (P20) within one (1) business day.

> **Note:** All provisions of ANSI/ASQC Standard Z1.9, dated 1993, explanatory of or essential to the application of Table A-2, Table B-3, and Example B-3, as referenced in 170 IAC 4-1-10(c)(3)–(5), are hereby incorporated in that rule by reference. (170 IAC 4-1-10(c)(10)) RPL's implementation in this worksheet is based on those incorporated provisions and RPL's internal sampling plan.

---

<!-- clause: RPL-MTR-PGM-001:App-C -->
## Appendix C: Standards Certification Register Summary

See `data/standards_calibration_2024.csv` for the full register. Summary as of 2024-12-31:

| Level | ID | Make/Model (generic) | Location | Last Certified | By | Next Due | In Cert? |
|---|---|---|---|---|---|---|---|
| Reference | STD-REF-001 | High-accuracy watthour standard A | Lafayette Meter Shop | 2023-08-15 | Accredited External Lab | 2025-08-15 | Y |
| Reference | STD-REF-002 | High-accuracy watthour standard B | Lafayette Meter Shop | 2024-02-20 | Accredited External Lab | 2026-02-20 | Y |
| Reference | STD-REF-003 | Precision wattmeter | Lafayette Meter Shop | 2024-06-10 | Accredited External Lab | 2026-06-10 | Y |
| Test board | TB-01 through TB-08 | Automated meter test boards | Lafayette Meter Shop | 2024 (various) | STD-REF-001/002 | 2025 | Y |
| Portable | PRT-001 through PRT-032 | Portable watthour standards | All service centers | 2024 (various) | STD-REF-001/002 | As needed | Y |

All 43 standards were in certification on every test date in 2024. No out-of-tolerance findings were reported for reference standards in 2024.

---

<!-- clause: RPL-MTR-PGM-001:App-D -->
## Appendix D: Data Dictionary

See `data/README.md` for the complete data dictionary. The following datasets are associated with this program plan:

| File | Description | Rows | Primary Key |
|---|---|---|---|
| `meter_registry_2024-12-31.csv.gz` | Complete meter fleet as of 2024-12-31 | 409,950 | meter_serial |
| `meter_population_2024-12-31.csv` | Homogeneous group definitions and counts | 52 groups | meter_group_id |
| `meter_test_results_2024.csv` | All meter tests performed in 2024 | ~5,724 | test_id |
| `new_meter_lots_2024.csv` | New meter acceptance lots received in 2024 | 6 | lot_id |
| `inservice_sample_selection_2025.csv` | 2025 Method B sample draw | ~3,262 | meter_serial + meter_group_id |
| `customer_test_requests_2024.csv` | Customer meter test requests 2024 | 620 | customer_request_id |
| `standards_calibration_2024.csv` | Test equipment certification register | 43 | standard_id |

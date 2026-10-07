# RPL Synthetic Corpus — How It Was Generated

**Entity:** Rockridge Power & Light Company (RPL) · IURC ID 99012 · Indiana IOU  
**Law as-of:** 2024-12-31 (Snapshot 1) · Evaluated against: 2025-12-31 (Snapshot 2)

---

## Generation Pipeline

```mermaid
flowchart TD
    DB[(Neon PostgreSQL\nIAC Regulations\ncode_sections table)]

    T00["**T00 — Orchestrator**\nQuery DB per document scope\nBuild 12 grounding packs\nLeak test · Orchestrator report"]

    W1["**Wave 1 — Company Foundation**\nT01 Company profile & fact sheet\nT02 People directory & org chart\nT03 Document register\nT04 Operational master data"]

    W2["**Wave 2 — 9 Documents** (parallel)"]

    W3["**Wave 3 — 3 Compliance Docs** (parallel)"]

    QA["**Per-document QA Loop**\n① Generate  ② Validate (deterministic)\n③ Fidelity review  ④ Realism review\n⑤ Fix  ↺ repeat up to 3×"]

    T90["**T90 — Baseline Validation**\n15 checks · 9/10 PASS deterministic"]

    T91["**T91 — Expected Findings Key**\nIsolated agent · S1 vs S2 diff\n13 expected findings"]

    DB -->|"S1 = 2024-12-31\n12 packs + orchestrator report"| T00
    T00 --> W1
    T00 -->|grounding packs| W2
    W1 -->|company profile, people,\nregister, ops data| W2
    W2 -->|1,164 frozen clause IDs\n+ cross-references| W3
    W2 --> QA
    W3 --> QA
    QA -->|all PASS| T90
    T90 --> T91
```

---

## Foundation Layer (Wave 1)

> Everything in Wave 2 is grounded in these four files — no document invents its own facts.

| Task | Output | Key Content |
|---|---|---|
| **T01** | `company_profile.yaml` · `company_fact_sheet.md` | Legal name, service territory, 14 counties, 5 service centers, financials |
| **T02** | `people_directory.csv` · `org_chart.md` | 27 named employees P01–P27 across 9 departments |
| **T03** | `document_register.csv` | 12 doc IDs, versions, owners, reviewers, approval dates |
| **T04** | 10 CSV/YAML files + scripts | 112 substations · 528 circuits · 10,928 outage events · 5-yr SAIDI history · TMED |

---

## Data Dependency — What Feeds What

```mermaid
graph LR
    GP[Grounding Packs\nT10–T21.json\nIAC S1 text only]
    CF[Company Foundation\nprofile · people · register · ops]
    REF[Reference Extracts\nIEEE 1366 MED method\nSampling table]

    T13["T13 Tariff"]
    T14["T14 Disconnection"]
    T15["T15 Meter Test Request"]
    T16["T16 Vegetation Mgmt Plan"]
    T17["T17 Complaint Procedure"]
    T18["T18 Meter Testing Program"]
    T19["T19 Outage Reporting"]
    T20["T20 Spill Response"]
    T21["T21 Accident Reporting"]

    T10["T10 Compliance Register"]
    T11["T11 Regulatory Calendar"]
    T12["T12 Records Retention"]

    GP --> T13 & T14 & T15 & T16 & T17 & T18 & T19 & T20 & T21
    CF --> T13 & T14 & T15 & T16 & T17 & T18 & T19 & T20 & T21
    REF --> T18
    REF --> T19
    T13 & T14 & T15 & T16 & T17 & T18 & T19 & T20 & T21 -->|clause IDs\ncross-refs| T10 & T11 & T12
```

> **T20 special case:** 327 IAC 2-6.1 absent from DB → entire document written as company practice (§2.7 fallback). No regulatory values cited.

---

## The 12 Documents — 5 Verticals

```mermaid
graph TD
    subgraph PG["Policy & Governance"]
        T13["RPL-TAR-GRR-012\nTariff — General Rules"]
        T14["RPL-CS-PRO-004\nDisconnection & Reconnection"]
        T15["RPL-CS-PRO-007\nMeter Test Request & Billing"]
        T16["RPL-DO-PLN-002\nVegetation Management Plan"]
        T17["RPL-CS-PRO-011\nComplaint & Dispute"]
    end
    subgraph OP["Operations & Processes"]
        T18["RPL-MTR-PGM-001\nMeter Testing Program"]
        T19["RPL-DCC-PRO-003\nOutage Reporting"]
    end
    subgraph EN["Environmental"]
        T20["RPL-ENV-PRO-005\nSpill Response"]
    end
    subgraph WS["Workforce & Safety"]
        T21["RPL-SAF-PRO-009\nAccident Reporting"]
    end
    subgraph CL["Compliance & Legal"]
        T10["RPL-CMP-REG-001\nCompliance Register"]
        T11["RPL-REG-CAL-2025\nRegulatory Calendar 2025"]
        T12["RPL-LEG-RRS-001\nRecords Retention Schedule"]
    end
```

---

## Per-Document Output Structure

Every document produces **4 artifact types**, none of which overlap in purpose:

```
corpus/docs/<DOC_ID>/
├── <DOC_ID>_v<n>.md          ← canonical doc (clause IDs embedded as HTML comments)
├── <DOC_ID>.basis.json       ← hidden ground-truth: every value linked to its pack source
├── data/*.csv                ← machine-readable datasets (T16, T18, T19, T20, T21)
└── render/                   ← .docx + .pdf (+.xlsx for T16, T18)
```

> `basis.json` is **never** shown to the Strata engine. It is the answer key for QA validation.

---

## QA Loop (applied to every document)

```mermaid
flowchart LR
    GEN["Generate\ndocument"] --> VAL["Deterministic\nvalidation\n validate.py"]
    VAL -->|FAIL| FIX["Fix agent\n(same read\npermissions)"]
    VAL -->|PASS| FID["Fidelity review\nfresh isolated\nagent"]
    FID -->|issues| FIX
    FID -->|zero issues| REA["Realism review\nfresh isolated\nagent"]
    REA -->|below threshold| FIX
    REA -->|PASS| DONE["✓ PASS\nSHA-256 recorded"]
    FIX --> VAL
```

**Validation checks include:** clause-ID grammar · value-ledger completeness · phantom-citation scan · banned-phrase scan · render parity · date ordering · §1 constants verbatim

---

## Corpus Metrics at a Glance

### Company (RPL)
| | |
|---|---|
| Customers | 407,491 (Residential 361,480 · Commercial 44,215 · Industrial 1,184) |
| Meters | 409,950 (AMI 371,200 · AMR 31,400 · Electromechanical 7,350) |
| Employees | ~1,450 · 27 named (P01–P27) |
| Service territory | 14 west-central Indiana counties · 5 service centers |
| Infrastructure | 112 substations · 528 circuits · 14,200 OH mi · 4,900 UG mi |

### Regulatory & Compliance
| | |
|---|---|
| Governing regulation | 170 IAC 4-1 · 4-9 · 16-1 · 1-6 (tariff filings) |
| Compliance obligations | 70 (RPL-CMP-REG-001) |
| Regulatory calendar events | 48 (RPL-REG-CAL-2025) |
| Record series | 86 (RPL-LEG-RRS-001) |
| S1→S2 changed citations | 5 (170 IAC 1-6-3/4/5 · 1-7-3 · 4-1-16) |

### Operational Data (T04)
| | |
|---|---|
| Outage events (2024) | 10,928 events · 2019–2023 daily SAIDI history |
| TMED (2.5β method) | 137.19 min/customer |
| ex-MED SAIFI / SAIDI / CAIDI | 1.099 / 138.3 / 125.9 min |
| MED days 2024 | 5 (Mar 15 · May 22 · Jul 4 · Aug 9 · Dec 23) |
| Vegetation mgmt budget | $41,600,000 |

### Corpus Structure
| | |
|---|---|
| Total documents | 12 (9 Wave 2 + 3 Wave 3) |
| Clause IDs (frozen) | 1,164 across all Wave 2 documents |
| Basis value ledger entries | ~443 total (every number in every doc traced to source) |
| Grounding packs | 12 (T10–T21.json; T20 empty — 327 IAC 2-6.1 absent) |
| Expected findings (T91) | 13 (6 medium · 7 informational · 2 docs flagged · 10 cleared) |

---

## Information Barriers

```mermaid
graph LR
    subgraph RESTRICTED["🔒 Restricted — Never shown to Strata engine"]
        BP[basis.json files]
        GP2[Grounding packs]
        QAF[QA reports]
        EV[eval/ — T91 answer key]
        OR[_orchestrator_report.json]
    end
    subgraph VISIBLE["✓ Strata engine sees"]
        MD[Document .md files]
        CSV[data/*.csv]
        RND[render/ .docx .pdf]
        GLB[_global/ company data]
    end
```

> Worker agents also operate under barriers: each sees only its own grounding pack, never another task's pack, the orchestrator report, or the eval folder.

# Strata — Regulatory Impact Intelligence

**When a government rule changes, Strata shows a company exactly which clauses in which of its documents are affected, why, what must change, and who must act. It flags; it never edits.**

## TL;DR
- **Problem:** after a rule changes, finding which company clauses are now wrong is slow manual reading, and most law changes are cosmetic noise.
- **Approach:** compare two law snapshots, filter noise with deterministic code, match changes to clauses by citation, and let a bounded LLM judge only what remains, with every finding backed by verified quotes.
- **Demo:** a synthetic Indiana utility (Rockridge Power & Light, 12 documents) against real federal and Indiana rules.
- **Evidence:** 1,114 changes reduce to 7 findings and 2 of 12 documents flagged; the clause-level scorecard is still being reconciled ([results](supporting/EVALUATION_AND_RESULTS.md)).

## The whole system in one picture

```mermaid
flowchart LR
    subgraph IN["1 · Ingest"]
        G["Law sources x7<br/>eCFR · Federal Register · IAC<br/>IURC x3 · IDEM"]
        C["Company corpus<br/>12 docs · 2,334 clauses"]
    end
    subgraph ST["2 · Store"]
        PG[("Neon Postgres<br/>public · company · engine")]
        QD[("Qdrant<br/>vectors")]
        R2[("Cloudflare R2<br/>raw files")]
    end
    subgraph EN["3 · Impact Engine"]
        E1["Delta"] --> E2["Characterize<br/>LLM"] --> E3["Candidates"] --> E4["Judge<br/>rules + LLM"] --> E5["Ledger"]
    end
    G -->|"daily cron"| PG
    G --> QD
    G --> R2
    C -->|"manual CLI"| PG
    C --> R2
    PG --> E1
    E5 --> PG
    PG --> API["4 · FastAPI"]
    API --> UI["5 · Next.js UI"]
    UI -.->|"what-if · review"| API
```

## The result in one picture

```mermaid
flowchart LR
    A["1,114<br/>law changes"] --> N["1,015 noise<br/>dropped"]
    A --> S["99 substantive,<br/>new or repealed"]
    A --> F["96 touch company<br/>citations"]
    F --> X["87 cosmetic<br/>cleared with proof"]
    F --> D["9 real changes<br/>obligation changed"]
    D --> E["clause candidates"]
    E --> R["7 findings<br/>2 of 12 docs flagged"]
```

*(latest run, as of 2026-10-08; details in [Evaluation & results](supporting/EVALUATION_AND_RESULTS.md))*

## Document map

| Doc | Answers |
|---|---|
| **[PRD](PRD.md)** | What problem, for whom, what success means |
| **[TDD](TDD.md)** | How it is designed and why: principles, layers, decisions |
| [Data model](supporting/DATA_MODEL.md) | The three data domains and their relationships |
| [Data pipelines](supporting/DATA_PIPELINES.md) | How law and company data become linked, queryable knowledge |
| [Engine spec](supporting/ENGINE_SPEC.md) | The 5-stage impact engine and its guardrails |
| [Interface design](supporting/API_AND_UI.md) | The analyst workflow and screens |
| [Evaluation & results](supporting/EVALUATION_AND_RESULTS.md) | How quality is measured; what the results show |
| [Limitations & future work](supporting/LIMITATIONS_AND_ROADMAP.md) | Where each workflow is limited and how it can improve |

**Suggested order:** PRD → TDD → Engine spec → Evaluation & results.

## Key ideas

| Idea | One line |
|---|---|
| Two law snapshots | S1 (2024-12-31) is the baseline all company docs comply with; S2 holds only what changed |
| Footprint | Only law sections that company clauses cite can create findings; the rest go to Radar |
| Code first, LLM last | Code classifies, matches and routes; the LLM only reads changed text and judges clause fit |
| Proof or no finding | Every real finding carries quotes verified as exact substrings of S1, S2 and the clause |
| Stitching | Rulemakings are linked to the code sections they amend, including via Indiana DIN identifiers |
| What-if | Edit or repeal a cited section and watch impact propagate through the same engine (labelled SIMULATED) |

## Glossary

| Term | Meaning |
|---|---|
| **S1 / S2** | Old / new law snapshots |
| **IAC / CFR** | Indiana Administrative Code / US Code of Federal Regulations |
| **FR** | Federal Register (daily rulemaking journal) |
| **IURC / IDEM** | Indiana Utility Regulatory Commission / Dept. of Environmental Management |
| **Clause** | Atomic unit of a company document (section, table row, form field…) |
| **Change record** | One S1→S2 change to one code section |
| **Footprint** | Law sections that company clauses cite |
| **Candidate** | A (change, clause) pair to evaluate |
| **Finding** | A candidate judged affected, with evidence |
| **DIN** | Indiana Register document ID embedded in IAC text, used for stitching |
| **Radar** | Screen for changes outside the footprint against company attributes |

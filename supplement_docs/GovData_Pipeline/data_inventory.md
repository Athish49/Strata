# Strata Regulatory Intelligence — Data Inventory
_Last updated: 2026-10-06_

---

## 1. Summary Stats

| Metric | Count |
|---|---|
| Total code sections | 4,603 |
| Total regulatory actions | 1,206 |
| Total semantic vectors (Qdrant) | 9,105 |
| Total cross-links | 3,950 |
| Data sources (agencies) | 4 (EPA, FERC, IURC, IDEM) |
| IAC titles with data | 5 (170, 326, 327, 610, 675) |
| CFR titles with data | 2 (18 CFR FERC, 40 CFR EPA) |
| Versioning snapshots | 2 (2024-12-31, 2025-12-31) |

---

## 2. Agencies & Data Coverage

| Agency | Domain | What We Track | Records | Date Range |
|---|---|---|---|---|
| EPA | Federal air/water/environmental regs | FR rules + 40 CFR code sections | 267 CFR + ~850 FR | Jan 2025 – Oct 2026 |
| FERC | Federal energy regulation | FR rules + 18 CFR code sections | 63 CFR + ~140 FR | Jan 2025 – Oct 2026 |
| IURC | Indiana utility regulation | Rulemakings, GAOs, investigations, 170 IAC | 199 actions + 647 IAC | 1982 – Oct 2026 |
| IDEM | Indiana environmental regulation | ERB rulemakings + 326/327 IAC | 17 actions + 2,072 IAC | 2024 – Oct 2026 |

---

## 3. Code Sections Coverage

### CFR (Federal — 330 total)

```
18 CFR  (FERC)   ████████████░░░  82.5%  (52/63 linked)
40 CFR  (EPA)    ████████░░░░░░░  40.4%  (108/267 linked)
─────────────────────────────────────────────────────────
CFR total        ████████░░░░░░░  48.5%  (160/330 linked)
```

### IAC (Indiana Admin Code — 4,273 total, 1,109 repealed)

```
170 IAC  (IURC utility)    ████████████░░░  83.3%  (539/647 linked)
327 IAC  (IDEM water)      ███████████░░░░  79.0%  (499/632 linked)
326 IAC  (IDEM air)        █████████░░░░░░  63.1%  (909/1,440 linked)
610 IAC                    ░░░░░░░░░░░░░░░   0.0%  (0/169 linked)
675 IAC                    ░░░░░░░░░░░░░░░   0.0%  (0/1,385 linked)
──────────────────────────────────────────────────────────────────────
IAC total (live)           ███████░░░░░░░░  45.6%  (1,947/4,273 linked)
                           1,109 sections carry repealed_date
```

---

## 4. Regulatory Actions — Field Quality

| Source | Total | Abstract | Action Text | Date Filed | Notes |
|---|---|---|---|---|---|
| federal_register | 990 | 99% (976) | 99% (975) | 100% | EPA + FERC, Jan 2025–Oct 2026 |
| iurc_rulemakings | 19 | 100% | 0% | 100% | No PDF parser yet |
| iurc_gaos | 42 | 100% | 71% (30/42) | 98% | 12 pre-2000 scanned docs |
| iurc_investigations | 138 | 100% | 0% | 99% | Weekly-listing PDFs; 3 commission_investigation |
| idem_rulemakings | 17 | 100% | 0% | 100% | Active ERB rulemakings only |
| **Totals** | **1,206** | **~99%** | **~82%** | **~100%** | |

### Federal Register Action Types (990 rows)

```
final_rule       ████████████████  474  (47.9%)
proposed_rule    ███████████████░  450  (45.5%)
direct_final     █░░░░░░░░░░░░░░░   30   (3.0%)
interim_final    █░░░░░░░░░░░░░░░   25   (2.5%)
correction       ░░░░░░░░░░░░░░░░    8   (0.8%)
advance_notice   ░░░░░░░░░░░░░░░░    3   (0.3%)
```

---

## 5. Cross-Link Map

```
federal_register ←→ federal_register
  action_relationships: 843 rows
    related_to:  579
    supersedes:  257
    corrects:      7

federal_register → CFR (40 CFR / 18 CFR)
  amendment_source: 160 links

IAC 170 → iurc_rulemakings / iurc_gaos
  amendment_source: 539 links  (170 IAC sections)

IAC 326/327 → idem_rulemakings
  DIN stitching (dins col): 3,210 sections populated
  iac_cross_refs populated: 2,952 sections
  federal_refs populated:      64 sections

affected_entities (FR): 482/1,206 rows
  ~432 US state/EPA entries, ~50 IURC utility names
```

Total cross-links: 160 + 843 + 539 + 1,947 (IAC→action amendment_source) + misc = **~3,950**

---

## 6. Qdrant Vectors by Corpus

| Corpus | Vectors | % of Total |
|---|---|---|
| iac | 6,415 | 70.5% |
| cfr | 1,483 | 16.3% |
| fr (federal_register) | 991 | 10.9% |
| investigations | 138 | 1.5% |
| gaos | 42 | 0.5% |
| iurc_rulemakings (rm) | 19 | 0.2% |
| idem_rulemakings | 17 | 0.2% |
| **Total** | **9,105** | 100% |

---

## 7. Known Gaps & Data Ceilings

| Gap | Scope | Type | Notes |
|---|---|---|---|
| iurc_rulemakings action_text = 0% | 19 rows | Fixable | PDF parser not implemented |
| iurc_investigations action_text = 0% | 138 rows | Fixable | Weekly-listing PDFs; needs structured parser |
| idem_rulemakings action_text = 0% | 17 rows | Fixable | Source PDFs available |
| iurc_gaos pre-2000 action_text missing | 12 rows | Structural ceiling | Scanned images; OCR quality poor |
| iurc_gaos date_filed missing | 1 row | Fixable | Manual lookup |
| 610 IAC linkage = 0% | 169 sections | Unknown | No action source identified yet |
| 675 IAC linkage = 0% | 1,385 sections | Unknown | No action source identified yet |
| affected_entities partial | 724/1,206 missing | Fixable | NER pass over abstract/action_text |
| CFR 40 linkage = 40% | 159 sections unlinked | Fixable | FR rule → CFR mapping incomplete |
| IURC investigations docket IDs | 138 rows | Fixable | Structured extraction from PDFs pending |
| FERC FR coverage | Limited to ~140 rows | Structural ceiling | FERC docket system separate from FR |

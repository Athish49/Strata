# Strata v1 — Engine Spec

All rules here are generic. Never special-case a doc, citation, title or company.

## 0. Inputs — `ChangeInput`
```python
class ChangeInput(BaseModel):
    origin: Literal['kb','whatif']
    source_system: str
    citation: str                  # S2 citation; for repeal/whatif the S1 citation
    s1_section_id: int | None
    s2_section_id: int | None      # None for whatif
    s1_text: str | None            # raw body_text
    s2_text: str | None            # raw body_text, or edited text (whatif); None if repealed whatif
    s1_status: str | None
    s2_status: str | None          # 'repealed' for repeal whatif
    heading: str | None
    amendment_source: str | None
```
Builders (`inputs.py`):
- **kb.** For each `source_system`, S1 = min `snapshot_date` and S2 = max.
  - Pairs: every S2 row with `prior_version_id` → (S1 row, S2 row).
  - New: S2 rows without `prior_version_id` (s1 fields None).
  - Never create inputs for S1 rows that are absent from S2.
- **baseline.** Returns `[]` (S1 vs S1). The run still completes, with all stats at 0, exports every doc as `cleared`, and is scored with `--snapshot S1`.
- **whatif.** One input from the scenario:
  - `text_edit`: `s2_text = edited_text`, `s2_status = s1_status`.
  - `repeal`: `s2_status = 'repealed'`.

## 1. Stage 1 — Delta (code, `delta.py`)
### 1.1 Text functions (`textnorm.py`)
- `normalize_for_diff(text, source_system)`: the existing function, fixed in W0.
- `strip_metadata(norm_text, source_system)`: removes non-obligation metadata from normalized text.
  - IAC: `Authority:` and `Affected:` lines; trailing source-history parentheticals (agency; citation; filed …); DIN strings; readoption lines.
  - CFR: bracketed source notes, e.g. `[NN FR NNNN, date]`.
  - Derive patterns by sampling 30 changed pairs. Keep regexes generic and cover them with unit tests.

### 1.2 Classification (first match wins)
| # | Class | Test |
|---|---|---|
| 1 | `repealed` | `s2_status ∈ {repealed, expired}` and `s1_status` is not |
| 2 | `renumbered` | New row (s1 None). Jaccard of 5-gram word shingles of normalized text ≥ 0.80 against an S1 row with the same `source_system` and `title_number` and a different citation → set `renumbered_from` and `s1_section_id` to that row |
| 3 | `new_section` | New row, otherwise |
| 4 | `cosmetic` | `normalize_for_diff(s1) == normalize_for_diff(s2)` (equivalently, `diff_hash` equal) |
| 5 | `metadata_only` | `strip_metadata` outputs are equal |
| 6 | `punctuation_only` | Every changed token in the word diff is punctuation or whitespace |
| 7 | `cross_ref_only` | Every changed token lies inside a `find_citation_spans()` span in its own text |
| 8 | `substantive` | Otherwise |
Classes 6–8 are computed on the `strip_metadata` texts.

### 1.3 Word diff (`diffing.py`)
- Tokens: `re.findall(r"\w+|[^\w\s]", text)`.
- Diff: `difflib.SequenceMatcher(None, a, b, autojunk=False)`.
- Store `diff_segments`: equal/delete/insert runs joined with single spaces, over the metadata-stripped normalized texts. Store `s1_text_norm` / `s2_text_norm` as the metadata-stripped texts.

### 1.4 Dates (`dates.py`)
- IAC: find DINs (`\b(\d{8})-IR-\d+[A-Z]*\b`) in the raw S2 text that are absent from the raw S1 text. `published_date` = the max of their dates; `date_basis = 'din_publication'`; `din` = that DIN.
- CFR: `amendment_source` → `regulatory_actions.source_id` where `source_system='federal_register'` (e.g. `2025-06941`). Use `date_effective` (`fr_effective`), else `date_published` (`fr_published`).
- Otherwise NULL. Never guess.

### 1.5 Footprint (`footprint.py`)
- `rule_key(citation)`: IAC via `parse_citation(...).rule_key` (`170 IAC 4-1-16` → `170 IAC 4-1`). CFR is computed here, not taken from `parse_citation` (which returns the title-level `18 CFR`): `T CFR P.S` → `T CFR P` (e.g. `18 CFR 35.28` → `18 CFR 35`); `T CFR Part P` is normalized to the same form.
- `cited_section_ids` = `{int(code_section_id)}` over `clause_citations` with `resolution_status='resolved'`, restricted to eligible clauses (§3.1).
- `cited_rule_keys` = `rule_key(citation_raw)` for `resolved_rule` citations ∪ `document_scope.scope_key` where `scope_level='rule'`.
- `in_footprint` = `s1_section_id ∈ cited_section_ids` OR `rule_key(citation) ∈ cited_rule_keys`.
- `cited_clause_count` = distinct eligible clauses citing the S1 section, or that rule via a rule-level citation.

### 1.6 Dispositions set in Stage 1
| Condition | Disposition |
|---|---|
| Noise class and in footprint | `excluded_noise`. Create `direct_section` candidates with `skip_reason='noise:<class>'`, `affected=false`, `rationale` = class explanation. These are the "cleared with proof" rows |
| Noise class, not in footprint | `excluded_noise` (no candidates) |
| Not in footprint, non-noise | `not_in_footprint` → radar input |
| `new_section` in footprint | `needs_review`, `disposition_reason` = "New section inside a rule your documents cover". No candidates |

## 2. Stage 2 — Characterize (LLM, `characterize.py`)
- **Scope:** `substantive` and in footprint (all origins). One call per change.
- **Code hints first:** run `extract_parameters_from_text` on the S1 and S2 stripped texts. Multiset-diff them by `(kind, unit, value_num, day_type)` → `params_only_in_s1`, `params_only_in_s2`. Pass both to the LLM.

### 2.1 Output schema
```python
class ValueChange(BaseModel):
    kind: Literal['period','deadline','amount','threshold','frequency','number','other']
    unit: str | None
    day_type: str | None           # 'calendar'|'business'|None
    old_value_text: str            # verbatim from S1
    new_value_text: str            # verbatim from S2
    old_value_num: float | None
    new_value_num: float | None
    subject: str                   # what the value governs, ≤12 words

class Characterization(BaseModel):
    obligation_changed: bool       # False for wording/style/clarification with same legal effect
    direction: Literal['tightened','relaxed','new_requirement','removed_requirement','clarified','style_only','mixed']
    summary: str                   # ≤40 words, plain English
    value_changes: list[ValueChange]
    added_requirements: list[str]  # verbatim S2 quotes
    removed_requirements: list[str]# verbatim S1 quotes
    quotes: dict                   # {"s1": verbatim, "s2": verbatim} covering the core change
```

### 2.2 Prompt contract (`prompts/characterize.md`)
- Role: regulatory analyst comparing two versions of one regulation section.
- Input: citation, heading, S1 text, S2 text, word diff, `params_only_in_s1`, `params_only_in_s2`.
- Rules:
  - The same legal effect means `obligation_changed=false`. Examples: "shall not" ↔ "may not" (both prohibitive), punctuation, reordering, statutory authority references.
  - Quote verbatim only.
  - Report value changes only when the same requirement's value changed.
  - Do not speculate about any company.
- Output: JSON matching the schema.

### 2.3 Verification (code)
- Every quote must be a substring of its source text (`quotes.verify_quote` normalizes whitespace and case).
- Drop a `value_change` unless `old_value_text ⊂ S1` and `new_value_text ⊂ S2`.
- Drop unverifiable added/removed quotes.
- If `obligation_changed=true` and nothing verifiable remains: set `disposition='needs_review'` and continue to Stage 3 (the judge decides).
- If `obligation_changed=false`: `disposition='no_affected_clauses'`, reason = `summary`. Create `direct_section` candidates with `skip_reason='no_obligation_change'` and `affected=false`. Stop here for this change.

## 3. Stage 3 — Candidates (code, `candidates.py`)
### 3.1 Eligible clause
`assessable = true`, `clause_role <> 'boilerplate'`, and `clauses.doc_id` is a document of the company. **Do not filter on `version_id`:** each RPL document has exactly one `document_versions` row, but ingest wrote prose clauses and register-row clauses (from CSV registers) under different `version_id`s. The clause sets never overlap, so all clauses of the doc are in scope. (Known ingest bug: `company_ingest/cli/ingest.py` falls back to `"v1"` when front matter has no `version`; W0 task 0.7.1 re-pointed `current_version_id` to the prose set for three docs.)

### 3.2 Paths (for in-footprint changes still open after Stage 2)
| Path | Rule |
|---|---|
| `direct_section` | Eligible clauses with a `resolved` citation whose `code_section_id = s1_section_id`. `cited_citation` = that section's S1 citation |
| `direct_rule` | Eligible clauses with a `resolved_rule` citation whose `rule_key = change.rule_key` |
| `register_hop` | For each direct candidate C: `clause_links` rows where `C` is `from_clause_pk` **or** `to_clause_pk`, `link_type ∈ {references_clause, references_obligation, references_record_series, references_tariff, references_form}`, other end NOT NULL and eligible. One hop only. `path_detail` records `via_clause_id` and `link_type` |
| `value_echo` | Only if verified `value_changes` exist. Eligible clauses with a parameter where `is_citation_fragment=false`, `(kind <> 'number' OR unit IS NOT NULL)`, `value_num = old_value_num`, unit equal after singularize/lowercase, and `day_type` equal when both are non-null. **AND** the clause's doc already has a direct candidate for this change, **or** the clause cites any section with the same `rule_key` |

- `repealed` and `renumbered` changes use `direct_section` only.
- Dedupe per `(change_id, clause_pk)`: keep the highest-priority path as `match_path`, and append all paths to `path_detail`.
- Do **not** use `restates` links (noise) or `references_doc` (no clause target).

## 4. Stage 4 — Judge (`rules.py` then `judge.py`)
### 4.1 Deterministic rules (`judged_by='rule'`, no LLM)
| Rule | Applies to | Result |
|---|---|---|
| R1 | `repealed`, `direct_section` | `stale_citation`, verdict `update_citation`. Rationale: "Cited section repealed in S2; confirm whether the obligation can be removed." `required_change = {from: cited citation, to: "(repealed)"}` |
| R2 | `renumbered`, `direct_section` | `stale_citation`. `required_change = {from: old citation, to: new citation}` |
| R3 | Value override: candidate clause has an eligible parameter equal to a verified `old_value_num` (same unit/day_type) | `parameter_change`. `required_change = {from: clause value_text, to: new_value_text}`. `quotes = {s1: old quote context, s2: new quote context, clause: clause text around the param span (±80 chars, trimmed to sentence)}`. Templated rationale: "Clause states {old}; {citation} now requires {new} ({subject})." |
| R4 | Candidates already given a `skip_reason` | No finding (cleared) |

R3 quotes are built from verified texts, so `quotes_verified = true`.

### 4.2 LLM judge (all other candidates)
**Input** (`prompts/judge.md`):
- The change: citation, heading, summary, direction, value_changes, added/removed requirements, word diff, S1 and S2 stripped text. If over `JUDGE_MAX_SECTION_CHARS`, send ±1500-char windows around the hunks.
- The clause: clause_id, doc title, heading_path, unit_kind, text_raw, its parameters.
- The match path in plain words (e.g. "clause cites this section"; "linked from register row X via references_obligation").
- The finding_type definitions (from `prd.md` §6) and the severity definitions.

**Output:**
```python
class JudgeResult(BaseModel):
    affected: bool
    finding_type: Literal['parameter_change','required_content_change','conflict','stale_citation',
                          'new_requirement_gap','stale_at_approval','informational']
    severity: Literal['high','medium','low']
    required_change: dict | None   # {"from_text": verbatim clause quote, "to_text": what it must say/do}
    quotes: dict                   # {"s1": str|None, "s2": str|None, "clause": str}
    rationale: str                 # ≤60 words
    confidence: float              # 0..1
```

**Prompt rules:**
- `affected=true` only if the clause, read as written, would now be non-compliant, misleading, or missing something the changed text requires.
- Citing the section is not enough on its own.
- If the change concerns a different subsection or topic than the clause, `affected=false`.
- `stale_at_approval` is never chosen by the LLM; code assigns it (§4.3 P3).

### 4.3 Post-rules (code, applied in order to every affected result)
- **P1 Quote verification.** Check `s1 ⊂ S1 text`, `s2 ⊂ S2 text`, `clause ⊂ text_raw`. On failure, retry once with the error appended. If it fails again: `finding_type='informational'`, `needs_review=true`, `quotes_verified=false`.
- **P2 Confidence gate.** If `confidence < MIN_CONFIDENCE`: `finding_type='informational'`, `needs_review=true`.
- **P3 Stale at approval.** If `origin='kb'`, `published_date` is not null, `published_date ≤ document_versions.approved_date`, and finding_type ∈ {`parameter_change`, `required_content_change`, `conflict`, `new_requirement_gap`}: set `finding_type='stale_at_approval'`.
- **P4 Verdict mapping:**
  - informational → `review` if `needs_review`, else `info`;
  - `stale_citation` → `update_citation`;
  - other types with `direction='relaxed'` → `optional_relaxed`;
  - otherwise → `action_required`.
- **P5 Severity for rule decisions:** `stale_citation` and `informational` → low; all other types → high.
- **P6 Unaffected candidates.** `affected=false`: store `rationale` on the candidate; no finding.

## 5. Stage 5 — Ledger (code, `ledger.py`)
1. **Propagation.** For a finding whose `match_path='register_hop'`, set `propagated_from` to the finding on its `via` clause for the same change, if one exists.
2. **Routing.** Set `route_owner`, `route_reviewer`, `route_approver` from `company_documents` (approver may be NULL by design).
3. **Change dispositions.**
   - Keep `excluded_noise`, `not_in_footprint`, and `new_section`'s `needs_review` unchanged.
   - For all other changes: `findings_emitted` if ≥1 non-informational finding; else `needs_review` if ≥1 informational finding with `needs_review=true`; else `no_affected_clauses`.
4. **Completeness check** (fail the run on violation):
   - every change has a disposition;
   - every candidate has `judged_by` or `skip_reason`;
   - every non-informational finding has `quotes_verified=true`.
5. **Doc rollups** (every company doc):
   - `flagged` if ≥1 non-informational finding, else `cleared`.
   - `changes_considered` = changes with ≥1 candidate in the doc, plus their outcome.
   - `reason` (cleared docs) = templated, e.g. "3 changes considered: 2 cosmetic, 1 no obligation change", or "No S2 change touches sections this document cites."
6. **Stats.** Write `runs.stats` (see `data_model.md` §4).

## 6. Export and scoring (`export.py`, `scripts/score_run.py`)
- Export JSON per `data_model.md` §6. Citation = the section-level form of the clause's cited citation.
- `score_run.py --run <id>`:
  1. write the export;
  2. run `python app/company/corpus/eval/scoring.py <export> --snapshot S2` (S1 for baseline runs), **never `--verbose`**;
  3. parse the aggregate metrics;
  4. upsert `engine.score_reports`.
- Never read `expected_findings.*`.

## 7. Radar (should-have, `radar.py`)
- **Input:** kb-run changes with `disposition='not_in_footprint'` and class ∈ {`substantive`, `repealed`, `new_section`}.
- **One call per change** (`ENGINE_RADAR_MODEL`, concurrency 16). Input: citation, heading, agency, word diff (or S2 text for new sections), plus all `company_attributes` as `key=value` lines.
- **Output:**
```python
class RadarResult(BaseModel):
    obligation_changed: bool
    applicable: Literal['yes','no','unclear']
    attribute_basis: list[str]      # attribute keys only, from the provided list
    affected_activity: str          # ≤15 words
    reason: str                     # ≤40 words
    quote_s2: str | None            # verbatim
```
- **Code rules:**
  - Drop `attribute_basis` keys that don't exist in the attributes.
  - `applicable='yes'` with an empty basis → `unclear`.
  - `obligation_changed=false` → `applicable='no'`, reason "no change in obligation".
  - Verify the quote.
  - `rule_covered_by_docs` = docs with any citation or scope on the same `rule_key`.

## 8. What-if (`whatif.py`)
- `POST` a scenario → `run_engine(kind='whatif', scenario_id)` → the same Stages 1–5, origin `whatif`. Never exported or scored.
- Editable sections: S1 sections in `cited_section_ids`, ordered by `cited_clause_count` desc.
- **Presets** (`scripts/make_whatif_presets.py`, generic):
  - **3 value presets.** Pick the top S1 sections (distinct rules) by count of eligible clauses citing them that also carry a non-fragment parameter whose value and unit appear in the section's S1 text. In the S1 text, replace that value token with a changed value: integer N → round(N × 1.5), at least N + 1, keeping the original surface form ("ten (10)" → update both). Title: `"{citation}: {subject} {old}→{new}"`.
  - **1 repeal preset** on the most-cited section.
  - Upsert with `is_preset=true`, run all of them, and store `last_run_id`.

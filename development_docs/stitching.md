# Strata — Data Stitching & Conflict Resolution

## Overview

The two data types (CodeSection and RegulatoryAction) connect through explicit reference fields, not inference. This document defines how records are linked, how duplicates are prevented, and how timing conflicts are resolved.

---

## Stitching Directions

### Journal → Codebook (Primary Link)

Every Federal Register final rule that amends CFR carries a `cfr_references` field listing the exact sections affected. This is the primary stitching mechanism.

**Flow:**
1. Federal Register adapter ingests a final rule. The `cfr_references` field says `["40 CFR 257.3", "40 CFR 257.4"]`.
2. The `RegulatoryAction` record stores these in `cfr_references[]`.
3. On the next eCFR poll, sections `40 CFR 257.3` and `40 CFR 257.4` show changed hashes.
4. New `CodeSection` snapshots are created with `amendment_source` pointing to the FR document number.

**Stitching fields used:**
- `RegulatoryAction.cfr_references` → matches `CodeSection.citation`
- `CodeSection.amendment_source` → matches `RegulatoryAction.source_id`

**At state level:** A PUCO order may amend OAC rules. The link comes from the order text mentioning specific OAC rule numbers, or from the case's purpose code indicating it's a rulemaking proceeding. The adapter extracts OAC references when they appear in case metadata or filing summaries.

### Journal → Journal (Action Chains)

Federal Register documents in the same rulemaking share linking identifiers:

| Link Field | What It Connects |
|---|---|
| `rin` (Regulation Identifier Number) | All FR documents in a single rulemaking initiative — ANPRM, NPRM, final rule, corrections |
| `docket_ids` | FR documents sharing a Regulations.gov docket — same rulemaking, including public comments |
| `related_actions` (explicit) | Direct references between actions: correction → original, rehearing → order |

**Flow:**
1. An NPRM is ingested with `rin = "2060-AU23"` and `docket_ids = ["EPA-HQ-OAR-2024-0001"]`.
2. Six months later, a final rule is ingested with the same `rin` and `docket_ids`.
3. The ingestion pipeline matches on `rin`, creates `related_actions` link: `final_rule → supersedes → proposed_rule`.

**For PUCO:** Cases have a "Related Cases" field in DIS. The adapter directly stores these as `related_actions` with type `related_to`.

### Cross-Jurisdiction Linking

A federal EPA rule may trigger a PUCO compliance proceeding. No structured cross-reference exists for this.

**V1 approach:**
- When a PUCO case title or filing text references a specific CFR citation (e.g. "40 CFR Part 60") or FR document number, the adapter extracts it into `legal_refs` or `cfr_references`.
- The stitching engine links the PUCO `RegulatoryAction` to the relevant `CodeSection` or federal `RegulatoryAction` via matching citations.

**Future enrichment:** NLP-based topical similarity matching across agencies for cases that don't explicitly cite each other.

---

## Deduplication Rules

### Within a Single Source

**Key:** `(source_system, source_id)`

Before storing any record, check if this key already exists:
- **RegulatoryAction (journal):** If it exists, skip — journal records are immutable. The same document number never appears twice in the Federal Register.
- **CodeSection (codebook):** If citation exists, compare `content_hash`. Same hash → skip (no change). Different hash → create new version snapshot linked via `prior_version_id`.

### Across Sources

The same regulatory event can legitimately appear in multiple sources. This is **not a duplicate** — it's complementary views:

| Example | Source A | Source B | Relationship |
|---|---|---|---|
| FERC final rule | Federal Register (RegulatoryAction) | eCFR (CodeSection change) | Journal record explains *why*; codebook record shows *what changed*. Linked via `cfr_references` / `amendment_source`. |
| Future: FERC order | Federal Register | FERC eLibrary | Same action in two journals. Linked via `related_actions` with matching document number or docket. |

**Rule:** Different `source_system` values → different records, always. The stitching engine links them; the dedup engine does not merge them.

---

## Timing Conflicts

### FR Arrives Before eCFR (Normal Case)

The Federal Register publishes a final rule 1-2 days before eCFR reflects the text change.

**Handling:**
1. Day 1: FR adapter creates `RegulatoryAction` (type: `final_rule`, status: `approved`, cfr_references: `["18 CFR 35.28"]`).
2. Day 1: No corresponding `CodeSection` change yet — that's fine.
3. Day 3: eCFR adapter detects hash change on `18 CFR 35.28`. Creates new `CodeSection` snapshot.
4. Day 3: Stitching engine sees the new `CodeSection` for `18 CFR 35.28` and finds the existing `RegulatoryAction` with matching `cfr_references`. Sets `amendment_source`.

No special conflict resolution needed — the records arrive in different batches and are stitched retroactively.

### Status Conflicts (Court Stay After Codification)

A rule is codified in eCFR, then a court stays it.

**Handling:**
1. The `CodeSection` exists with status `approved`.
2. A court order or FR notice about the stay is ingested as a new `RegulatoryAction` (type: `court_stay`).
3. The ingestion pipeline updates the `CodeSection` status to `blocked_suspended` based on the stay action.
4. The eCFR may or may not remove the text — our status field reflects legal reality, not publication state.

**Rule:** Status follows legal reality. The most recent authoritative action determines status:
- A `court_stay` action on a `final_rule` → both the `RegulatoryAction` and affected `CodeSection` become `blocked_suspended`.
- If the stay is lifted → new action of type `stay_lifted` → status reverts to `approved`.

### Backdated Effective Dates

A final rule published today may have an effective date in the past (retroactive) or months in the future.

**Handling:**
- `dates.effective` is stored as-is from the source. It may be before or after `dates.published`.
- `status` is determined by the action type, not the effective date. A `final_rule` is `approved` regardless of whether its effective date has passed.
- The downstream application uses `dates.effective` to answer "what was in force on date X" queries.

---

## Stitching Engine Logic

The stitching engine runs after each ingestion batch. It creates or updates links between records.

### After Ingesting a RegulatoryAction

```
stitch_regulatory_action(action):
  # 1. Link to codebook sections via cfr_references
  for ref in action.cfr_references:
    code_section = find_current_code_section(source_system=infer_codebook(ref), citation=ref)
    if code_section:
      # Check if this action caused the most recent change
      if code_section.amendment_source is None and dates_align(action, code_section):
        code_section.amendment_source = action.source_id

  # 2. Link to related actions via RIN
  if action.rin:
    related = find_actions_by_rin(action.rin, exclude=action.source_id)
    for r in related:
      create_related_action_link(action, r, infer_relationship(action, r))

  # 3. Link to related actions via docket_ids
  for docket in action.docket_ids:
    related = find_actions_by_docket(docket, exclude=action.source_id)
    for r in related:
      if not already_linked(action, r):
        create_related_action_link(action, r, infer_relationship(action, r))
```

### After Ingesting a CodeSection Change

```
stitch_code_section(code_section):
  # Find the journal record that caused this change
  if code_section.amendment_source is None:
    candidates = find_actions_by_cfr_ref(code_section.citation)
    for action in candidates:
      if dates_align(action, code_section):
        code_section.amendment_source = action.source_id
        break
```

### Relationship Inference

When two `RegulatoryAction` records share a RIN or docket, the relationship type is inferred from their `action_type`:

| Action A | Action B | Inferred Relationship |
|---|---|---|
| `proposed_rule` | `final_rule` | A `superseded_by` B |
| `final_rule` | `correction` | B `corrects` A |
| `final_rule` | `withdrawal` | B `withdraws` A |
| `order` | `responds_to` (rehearing) | B `responds_to` A |
| Any | Any (no type pattern match) | `related_to` |

---

## Future Source Integration

When a new source is added (e.g. California CPUC, UK Ofgem):

1. The adapter emits `CodeSection` and/or `RegulatoryAction` records with a new `source_system` value.
2. The dedup engine handles them using the same `(source_system, source_id)` key — no collision with existing sources.
3. The stitching engine uses the same `cfr_references` / `docket_ids` / `rin` / `legal_refs` fields. If the new source has its own cross-reference scheme (e.g. UK statutory instrument numbers), it goes in `legal_refs` and the stitching logic is extended by configuration.
4. No schema changes. No changes to existing adapters or their data.

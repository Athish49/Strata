# Strata v1 — Data Model

## 1. Read-only sources (existing)
| Table | Columns the engine uses |
|---|---|
| `public.code_sections` | `id, citation, source_system, title_number, heading, body_text, content_hash, diff_hash, status, snapshot_date, prior_version_id, amendment_source, agency_id` |
| `public.regulatory_actions` | `source_id, source_system, date_published, date_effective, source_url, title` (CFR date lookup only) |
| `company.company_documents` | `company_id, doc_id, title, vertical, owner_id, reviewer_id, approver_id, current_version_id` |
| `company.document_versions` | `version_id, doc_id, version, approved_date, effective_date, law_as_of` |
| `company.clauses` | `clause_pk, clause_id, doc_id, version_id, local_id, parent_clause_id, heading_path, unit_kind, clause_role, assessable, text_raw` |
| `company.clause_citations` | `citation_pk, clause_pk, citation_raw, source_system, subsection_path, granularity, code_section_id (text, S1 id), resolution_status, span_start, span_end` |
| `company.clause_parameters` | `parameter_pk, clause_pk, kind, value_text, value_num, unit, qualifier, day_type, span_start, span_end, is_citation_fragment` |
| `company.clause_links` | `from_clause_pk, to_clause_pk, link_type, method` |
| `company.document_scope` | `doc_id, scope_level, scope_key` |
| `company.company_attributes` | `key, value_text, value_num, value_bool` |
| `company.people` | `person_id, name, title, department` |

Query rules: `company_attributes`, `people`, `company_documents`, `clauses`, `document_versions` carry `company_id`; always filter on it. `document_scope` is per `version_id`; restrict to each document's `current_version_id`. `clause_parameters.kind` also holds `record_retention` (not in the `ValueChange.kind` literal; map it to `other`).

Facts the engine relies on:
- Clause sets: a document's clauses can sit under several `version_id`s (prose vs register-row sets); never join `clauses` to `document_versions` on `version_id` for eligibility. Use `clauses.doc_id`. Join `document_versions` by `current_version_id` only for `approved_date` / `law_as_of`.
- `clause_citations.code_section_id` points to **S1** rows. To reach S2, follow `S2.prior_version_id = S1.id`.
- `resolution_status` values: `resolved`, `resolved_rule`, `not_in_kb`, `out_of_scope_title`, `not_monitored`, `external`.
- RPL-CS-PRO-007 and RPL-CS-PRO-011 are two-signature documents: `approver_id` is NULL **by design**. Route with `approver = null`; never fill it from another field.

## 2. W0 additive changes to existing tables
| Change | Purpose |
|---|---|
| `company.clause_parameters.is_citation_fragment` recomputed (column exists via migration `d1e2f3a4b5c6`; as of the original W0 measurement FALSE on all 2,948 rows; recomputed since, count not re-verified in the 2026-10-08 pass) | TRUE when `kind='number'` AND `unit IS NULL` AND `value_text` is a whole token inside any `citation_raw` of the same clause (~278 rows) |
| `public.code_sections.diff_hash` re-backfilled | After the normalizer fix |
No other changes to `public.*` or `company.*`.

## 3. New schema `engine` (one Alembic migration in `backend/migrations/versions/`)
History: the DB had two Alembic heads (`77a04f843fe2`, `d1e2f3a4b5c6`), merged by task 0.6.1; the live DB is at head `e5a1c7d9b304`.
```sql
CREATE SCHEMA IF NOT EXISTS engine;

CREATE TABLE engine.runs (
  run_id        uuid PRIMARY KEY,
  kind          text NOT NULL CHECK (kind IN ('kb','baseline','whatif')),
  company_id    text NOT NULL,
  scenario_id   uuid NULL,
  snapshots     jsonb NOT NULL,          -- {"iac":{"s1":"2024-12-31","s2":"2025-12-31"},"cfr":{...}}
  status        text NOT NULL CHECK (status IN ('running','done','failed')),
  error         text NULL,
  stats         jsonb NULL,              -- funnel, see §4
  models        jsonb NULL,
  started_at    timestamptz NOT NULL DEFAULT now(),
  finished_at   timestamptz NULL
);

CREATE TABLE engine.change_records (
  change_id        uuid PRIMARY KEY,
  run_id           uuid NOT NULL REFERENCES engine.runs ON DELETE CASCADE,
  origin           text NOT NULL CHECK (origin IN ('kb','whatif')),
  source_system    text NOT NULL,
  citation         text NOT NULL,        -- S2 citation (or S1 for repeal/whatif)
  rule_key         text NOT NULL,        -- e.g. "170 IAC 4-1", "18 CFR 35"
  heading          text,
  s1_section_id    int NULL,
  s2_section_id    int NULL,
  renumbered_from  text NULL,
  change_class     text NOT NULL,        -- enum §5.1
  s1_text_norm     text NULL,
  s2_text_norm     text NULL,
  diff_segments    jsonb NULL,           -- [{"op":"equal|delete|insert","text":"..."}]
  published_date   date NULL,
  date_basis       text NULL,            -- 'din_publication'|'fr_effective'|'fr_published'
  din              text NULL,
  amendment_source text NULL,
  in_footprint     boolean NOT NULL,
  cited_clause_count int NOT NULL DEFAULT 0,
  obligation_changed boolean NULL,
  direction        text NULL,            -- enum §5.2
  summary          text NULL,
  value_changes    jsonb NULL,           -- [ValueChange]
  char_quotes      jsonb NULL,           -- {"s1":"...","s2":"..."}
  disposition      text NULL,            -- enum §5.3
  disposition_reason text NULL
);
CREATE INDEX ON engine.change_records (run_id, in_footprint, change_class);

CREATE TABLE engine.candidates (
  candidate_id   uuid PRIMARY KEY,
  run_id         uuid NOT NULL REFERENCES engine.runs ON DELETE CASCADE,
  change_id      uuid NOT NULL REFERENCES engine.change_records ON DELETE CASCADE,
  clause_pk      uuid NOT NULL,
  clause_id      text NOT NULL,
  doc_id         text NOT NULL,
  cited_citation text NULL,              -- section-level citation the clause cites (S1 form)
  match_path     text NOT NULL,          -- primary path, enum §5.4
  path_detail    jsonb NOT NULL,         -- all paths: [{"path":..,"via_clause_id":..,"link_type":..,"value":..}]
  judged_by      text NULL,              -- 'rule'|'llm'|NULL
  skip_reason    text NULL,              -- e.g. 'noise:cosmetic','no_obligation_change'
  affected       boolean NULL,
  rationale      text NULL,              -- for cleared candidates too
  UNIQUE (change_id, clause_pk)
);

CREATE TABLE engine.findings (
  finding_id     uuid PRIMARY KEY,
  run_id         uuid NOT NULL REFERENCES engine.runs ON DELETE CASCADE,
  change_id      uuid NOT NULL REFERENCES engine.change_records ON DELETE CASCADE,
  candidate_id   uuid NOT NULL REFERENCES engine.candidates ON DELETE CASCADE,
  clause_pk      uuid NOT NULL,
  clause_id      text NOT NULL,
  doc_id         text NOT NULL,
  citation       text NOT NULL,          -- section-level, as cited by the clause
  finding_type   text NOT NULL,          -- enum §5.5
  severity       text NOT NULL CHECK (severity IN ('high','medium','low')),
  verdict        text NOT NULL,          -- enum §5.6
  needs_review   boolean NOT NULL DEFAULT false,
  required_change jsonb NULL,            -- {"from_text":"...","to_text":"..."}
  quotes         jsonb NOT NULL,         -- {"s1":..,"s2":..,"clause":..}
  quotes_verified boolean NOT NULL,
  rationale      text NOT NULL,
  confidence     numeric NULL,
  decided_by     text NOT NULL CHECK (decided_by IN ('rule','llm')),
  match_path     text NOT NULL,
  propagated_from uuid NULL REFERENCES engine.findings,
  route_owner    text NULL, route_reviewer text NULL, route_approver text NULL,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON engine.findings (run_id, doc_id);

CREATE TABLE engine.doc_rollups (
  run_id      uuid REFERENCES engine.runs ON DELETE CASCADE,
  doc_id      text,
  status      text NOT NULL CHECK (status IN ('flagged','cleared')),
  counts      jsonb NOT NULL,            -- {"action_required":n,"optional_relaxed":n,"update_citation":n,"review":n,"info":n,"cleared_clauses":n}
  changes_considered jsonb NOT NULL,     -- [{"change_id","citation","change_class","outcome"}]
  reason      text NULL,                 -- for cleared docs
  PRIMARY KEY (run_id, doc_id)
);

CREATE TABLE engine.radar_items (
  run_id      uuid REFERENCES engine.runs ON DELETE CASCADE,
  change_id   uuid REFERENCES engine.change_records ON DELETE CASCADE,
  obligation_changed boolean,
  applicable  text CHECK (applicable IN ('yes','no','unclear')),
  attribute_basis text[] NOT NULL DEFAULT '{}',
  affected_activity text, reason text, quote_s2 text, quote_verified boolean,
  rule_covered_by_docs text[] NOT NULL DEFAULT '{}',
  PRIMARY KEY (run_id, change_id)
);

CREATE TABLE engine.whatif_scenarios (
  scenario_id   uuid PRIMARY KEY,
  title         text NOT NULL,
  source_system text NOT NULL,
  citation      text NOT NULL,
  s1_section_id int NOT NULL,
  edit_kind     text NOT NULL CHECK (edit_kind IN ('text_edit','repeal')),
  edited_text   text NULL,               -- required for text_edit
  is_preset     boolean NOT NULL DEFAULT false,
  last_run_id   uuid NULL,
  created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE engine.finding_reviews (
  review_id   uuid PRIMARY KEY,
  finding_id  uuid NOT NULL REFERENCES engine.findings ON DELETE CASCADE,
  action      text NOT NULL CHECK (action IN ('accept','reject')),
  note        text NULL,                 -- required when action='reject'
  person_id   text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE engine.score_reports (
  run_id      uuid PRIMARY KEY REFERENCES engine.runs ON DELETE CASCADE,
  snapshot    text NOT NULL,             -- 'S1'|'S2'
  metrics     jsonb NOT NULL,            -- parsed aggregate metrics only
  raw_stdout  text NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE engine.llm_calls (
  call_id     uuid PRIMARY KEY,
  run_id      uuid NULL,
  stage       text NOT NULL,             -- 'characterize'|'judge'|'radar'
  model       text NOT NULL,
  prompt_sha256 text NOT NULL,
  request     jsonb NOT NULL,
  response    jsonb NULL,
  valid       boolean NOT NULL,
  error       text NULL,
  latency_ms  int NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON engine.llm_calls (stage, model, prompt_sha256) WHERE valid;
```

## 4. `runs.stats` (funnel) keys
`raw_changed, new_sections, repealed, by_class{class:n}, substantive, in_footprint{class:n}, obligation_changed, candidates{path:n}, judged_rule, judged_llm, findings{verdict:n}, findings_non_info, clauses_cleared, docs_flagged, docs_cleared, radar{yes,no,unclear}, llm_calls, duration_s`

## 5. Enums
1. `change_class`: `repealed, renumbered, new_section, cosmetic, metadata_only, punctuation_only, cross_ref_only, substantive`. Noise classes = `cosmetic, metadata_only, punctuation_only, cross_ref_only`.
2. `direction`: `tightened, relaxed, new_requirement, removed_requirement, clarified, style_only, mixed`.
3. `disposition`: `findings_emitted, no_affected_clauses, excluded_noise, not_in_footprint, needs_review`.
4. `match_path` (priority order): `direct_section, direct_rule, register_hop, value_echo`.
5. `finding_type`: `parameter_change, required_content_change, conflict, stale_citation, new_requirement_gap, stale_at_approval, informational`.
6. `verdict`: `action_required, optional_relaxed, update_citation, review, info`.

## 6. Scoring export (`export.py`, consumed by `app/company/corpus/eval/scoring.py`)
```json
{
  "documents": [
    { "doc_id": "<every company doc, flagged or not>",
      "status": "flagged|cleared",
      "findings": [
        { "clause_id": "...", "citation": "<section-level, e.g. '170 IAC 4-1-16'>",
          "finding_type": "...", "severity": "...",
          "route_to": {"owner":"P..","reviewer":"P..","approver":"P..|null"} } ] } ]
}
```
Include informational findings (scoring counts only non-informational toward precision). `kind='whatif'` runs are never exported.


## Live-data note (2026-10-08)
- Latest real-wave run `0dcc125e-6da6-419f-beb1-8c347e4fb2d4`: 1,114 raw changes, 1,015 noise, 96 in footprint (9 real), 1,234 candidates, 4 action_required findings, 721 clauses cleared, 2 docs flagged / 10 cleared, `llm_calls` stat 0. Runs table holds ~25 runs (kb, baseline, and many whatif); the UI collapses them.
- `engine.llm_calls` contains rows with `error = 'produced in-session by the assistant (offline stand-in for the API; Anthropic spend limit)'`. These are valid offline-filled judgments (see engine_spec.md "Offline-filled judgments"), not API errors. Do not purge them.

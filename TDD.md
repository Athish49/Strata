# Technical Design — Company Document Ingestion (v2)

**Companion to:** `architecture.md` (why and how it fits together), `implementation_plan.md` (task order).
**Audience:** an engineer or agent implementing one task in isolation.
**Conventions:** all paths relative to `backend/`. `company.*` = Neon schema `company`. Line references are to the code as it exists before this work.

---

## 1. Schema

One Alembic migration on head `e5a1c7d9b304`.

### 1.0 Migration preamble — required, or the deploy breaks

`render.yaml` runs `alembic upgrade head` **before** the app starts, against populated tables. Two statements below fail on existing rows:

- `ADD version_no int NOT NULL` — no default, existing rows have no value.
- The `status` CHECK — existing rows hold `'Approved'`, which is not in the allowed set.

Cutover is an approved wipe, so the migration **truncates first**:

```sql
TRUNCATE company.clauses, company.clause_citations, company.clause_parameters,
         company.clause_links, company.defined_terms, company.term_usages,
         company.document_scope, company.document_versions, company.company_documents,
         company.table_columns, company.llm_extractions, company.ingest_runs CASCADE;
TRUNCATE engine.findings, engine.finding_reviews, engine.runs,
         engine.doc_rollups, engine.score_reports CASCADE;
-- NEVER truncate public.code_sections — the real regulatory KB.
-- company.companies, company.company_attributes, company.people are preserved
-- (re-seeded via org endpoints, but harmless to keep).
```

**Implemented** — revision `f7b2c91d4a08`, validated on a throwaway local cluster (production never connected to). The `engine.*` list verified against `e5a1c7d9b304_engine_schema.py` is: `runs, change_records, candidates, findings, finding_reviews, radar_items, doc_rollups, score_reports`. `change_records`, `candidates` and `radar_items` would be swept implicitly by `ON DELETE CASCADE` but are named explicitly so the statement says what it does. `engine.llm_calls` and `engine.whatif_scenarios` have no FK and are preserved.

**`engine.whatif_scenarios.last_run_id` must be nulled.** The table is preserved (presets are hand-curated) but has no FK to `engine.runs`, so the truncate leaves it pointing at runs that no longer exist. `app/engine/whatif.py:58-60` LEFT JOINs it and `api/engine/routes_ui_runs.py:94` filters on it, so a stale pointer surfaces as a scenario with a phantom last run. The migration therefore runs `UPDATE engine.whatif_scenarios SET last_run_id = NULL`.

**`company.table_columns`: rows truncated, table kept.** §1.6 "kept" means the *table* is not dropped. Its 26 rows are wiped with everything else and are repopulated by the register path during the seed.

### 1.0a Destructive-upgrade guard — mandatory

`render.yaml` runs `alembic upgrade head` **before** the app starts, so merely pushing this migration to the deployed branch would truncate production on the next deploy — no command, no confirmation. `upgrade()` therefore begins with an opt-in check, before any `TRUNCATE`:

```python
STRATA_ALLOW_V2_WIPE=yes-destroy-company-and-engine-data alembic upgrade head
```

Without the exact token it raises `RuntimeError`, turning the accident into a **failed deploy** (recoverable in minutes) rather than silent data loss (not recoverable). Offline SQL generation (`--sql`) executes nothing and is exempt. Four tests in `tests/company_ingest/test_migrations.py` pin this behaviour, including one asserting the guard runs *before* the first `TRUNCATE`.

### 1.1 `company.company_documents`

```sql
ALTER TABLE company.company_documents
  ADD COLUMN current_content_hash char(64),
  ADD COLUMN doc_number          text,
  ADD COLUMN lifecycle_state     text NOT NULL DEFAULT 'active',
  ADD COLUMN created_at          timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN updated_at          timestamptz NOT NULL DEFAULT now();

CREATE UNIQUE INDEX company_documents_content_hash_uq
  ON company.company_documents (company_id, current_content_hash)
  WHERE current_content_hash IS NOT NULL;
```

| Column | Notes |
|---|---|
| `doc_id` | **system-assigned** `DOC-%06d`. Never parsed from a filename. Existing column, new semantics |
| `current_content_hash` | SHA-256 hex of the current version's canonical text. NULL while the first version is pending |
| `doc_number` | customer's own reference (e.g. `RPL-CS-PRO-004`). Display + eval correlation only |
| `owner_id`, `reviewer_id`, `approver_id`, `review_cycle` | **retained and populated** — `engine/ledger.py:205-210` and `engine/export.py:75` read them |

The partial unique index is load-bearing: two concurrent identical uploads both pass a `SELECT`, so the insert must catch `UniqueViolation` and convert it to the same 409.

### 1.2 `company.document_versions`

```sql
ALTER TABLE company.document_versions
  ADD COLUMN version_no            int,
  ADD COLUMN is_current            boolean NOT NULL DEFAULT false,
  ADD COLUMN superseded_by         uuid,
  ADD COLUMN supersedes_version_id uuid,
  ADD COLUMN created_at            timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN created_by_person_id  text,
  ADD COLUMN change_reason         text,
  ADD COLUMN extraction_r2_key     text,
  ADD COLUMN extraction_method     text,
  ADD COLUMN pending_content_hash  char(64),   -- task 3.2; nullable
  DROP COLUMN file_sha256,
  DROP COLUMN supersedes;        -- legacy version *string*, replaced by supersedes_version_id

ALTER TABLE company.document_versions ALTER COLUMN version_no SET NOT NULL;

ALTER TABLE company.document_versions
  ADD CONSTRAINT document_versions_status_ck
  CHECK (status IN ('draft','in_review','approved','effective','superseded','retired'));

CREATE UNIQUE INDEX document_versions_no_uq
  ON company.document_versions (company_id, doc_id, version_no);
CREATE UNIQUE INDEX document_versions_current_uq
  ON company.document_versions (company_id, doc_id) WHERE is_current;
CREATE INDEX document_versions_doc_idx ON company.document_versions (company_id, doc_id);
```

`DROP COLUMN file_sha256` implements "only one hash per document" — the hash lives on `company_documents`, not per version.

**`pending_content_hash` (task 3.2).** The canonical hash (§2) of an *in-flight* version. Without it a v2+ version had nowhere to keep its hash, so promotion (§6 step 2) could not find it and every v2+ approval returned 409. It is **set at upload** (§7.1 step 7, §7.2) and **cleared to NULL at promotion** (the hash moves to `company_documents.current_content_hash`) and when the version is superseded. That keeps the invariant: the only *durable* hash is `company_documents.current_content_hash`; a non-NULL `pending_content_hash` means "this version is not live yet". The §7.2 "unchanged" check compares against `current_content_hash` **and** the `pending_content_hash` of this document's in-flight versions. Not unique-indexed: duplicates across documents are gated by `company_documents_content_hash_uq` at promotion (`PromotionConflict`).

`DROP COLUMN supersedes` removes the legacy version-*string* column now superseded by `supersedes_version_id uuid`; keeping both would leave two columns meaning the same thing. Its only writer was `collect/register_docs.py` (deleted by task 2.3) and it has no readers. **`version text` is deliberately kept** — it is the customer-facing version label (`"v5.1"`), genuinely distinct from the system-assigned sequential `version_no int`, in the same way `doc_number` is distinct from `doc_id`.

**Lifecycle.** `in_review` → (`approved` → `effective`) | `retired`; the prior `effective` version moves to `superseded` with `superseded_by` set. `draft` is reserved and unused this round.

`document_versions_current_uq` guarantees at most one current version per document at the database level.

**Pre-existing bugs to fix while here:** `store/neon.py:189-190` hardcodes `supersedes` and `next_review` to `None`; `:191` sets `source_r2_key` from `getattr(sf, "r2_key", None)` on a dataclass that has no such field, so it is always NULL.

### 1.3 Version-scoped child keys — data-loss fix

In `store/neon.py`, these `stable_uuid(...)` calls omit `version_id` while inserting `ON CONFLICT DO NOTHING`, so a second version's rows collide with the first's and are silently discarded:

| Line | Current | Change to |
|---|---|---|
| `:296` | `stable_uuid(company_id, clause_id, str(i), citation_raw)` | `stable_uuid(company_id, version_id, clause_id, str(i), citation_raw)` |
| `:358` | `stable_uuid(company_id, clause_id, str(i), value_text)` | `stable_uuid(company_id, version_id, clause_id, str(i), value_text)` |
| `:415` | `stable_uuid(company_id, doc_id, term_norm)` | `stable_uuid(company_id, version_id, term_norm)` |
| `:542` | `stable_uuid(company_id, from_clause_id, to_clause_id or to_doc_id, link_type)` | prefix with `version_id` |

`clause_pk` (`:217`) already includes `version_id` and is correct.

Also add `version_id uuid` to `engine.findings` so a finding pins to the version it was computed against.

### 1.4 `company.llm_extractions` — becomes a real cache

Exists with **zero writers**: the audit record goes only to R2 (`llm/client.py:217-228`), and `ctx.llm_cache` is in-memory, per-run, read only when `ctx.rebuild` is true (`:177`).

```sql
ALTER TABLE company.llm_extractions
  ADD COLUMN company_id     text,
  ADD COLUMN content_sha256 char(64);

-- Every cache-key column must be NOT NULL (see below). Free: the table is
-- truncated by the preamble and already had 0 rows.
ALTER TABLE company.llm_extractions
  ALTER COLUMN company_id     SET NOT NULL,
  ALTER COLUMN content_sha256 SET NOT NULL,
  ALTER COLUMN stage          SET NOT NULL,
  ALTER COLUMN prompt_sha256  SET NOT NULL,
  ALTER COLUMN model          SET NOT NULL;

CREATE UNIQUE INDEX llm_extractions_cache_uq
  ON company.llm_extractions (company_id, stage, content_sha256, prompt_sha256, model);
```

**No `output` column.** The cache payload reuses the **existing `response jsonb`** column. The table already has `run_id`, `unit_id`, `request`, `response`, `valid`, `error`, `created_at`; adding `output` beside `response` would leave two result columns with no way for a reader to tell which holds the cached value.

**Why the key columns are `NOT NULL`.** Postgres treats NULLs as **distinct** in a unique index, so a single nullable key column lets unlimited duplicate rows through — the read-through cache would miss on every lookup and silently degrade to a no-op while appearing to work. That would quietly defeat the "don't re-run the expensive LLM" requirement. `NOT NULL` makes a writer that forgets `company_id` fail loudly instead.

### 1.5 Org and approval tables (all new, additive)

```sql
CREATE TABLE company.departments (
    company_id text NOT NULL,
    department_id text NOT NULL,
    name text NOT NULL,
    parent_department_id text,
    PRIMARY KEY (company_id, department_id));

ALTER TABLE company.people
  ADD COLUMN department_id text,
  ADD COLUMN is_active boolean NOT NULL DEFAULT true;

CREATE TABLE company.document_role_assignments (
    company_id text NOT NULL,
    doc_id text NOT NULL,
    person_id text NOT NULL,
    role text NOT NULL CHECK (role IN ('owner','reviewer','approver')),
    assigned_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, doc_id, person_id, role));

CREATE TABLE company.approval_policies (
    company_id text NOT NULL,
    policy_id uuid PRIMARY KEY,
    name text NOT NULL,
    applies_to_vertical text,
    applies_to_doc_class text);

CREATE TABLE company.approval_policy_steps (
    policy_id uuid NOT NULL,
    step_no int NOT NULL,
    required_role text NOT NULL CHECK (required_role IN ('owner','reviewer','approver')),
    min_approvals int NOT NULL DEFAULT 1,
    PRIMARY KEY (policy_id, step_no));

CREATE TABLE company.approval_requests (
    request_id uuid PRIMARY KEY,
    company_id text NOT NULL,
    version_id uuid NOT NULL,
    policy_id uuid,
    state text NOT NULL CHECK (state IN ('open','approved','rejected','cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz);
CREATE UNIQUE INDEX approval_requests_open_uq
  ON company.approval_requests (version_id) WHERE state = 'open';

CREATE TABLE company.approval_steps (
    request_id uuid NOT NULL,
    step_no int NOT NULL,
    required_role text NOT NULL,
    assignee_person_id text,
    decision text CHECK (decision IN ('approved','rejected')),
    decided_at timestamptz,
    note text,
    PRIMARY KEY (request_id, step_no));
```

**Policy selection:** most specific match wins — `(vertical, doc_class)` → `(doc_class)` → `(vertical)` → default policy. If none matches, the version auto-approves and promotes immediately (document this behaviour rather than failing).

**No `clause_edits` table.** Redlining is out of scope.

**Implemented** — `app/api/company/org.py`, 60 tests. Hardening beyond the spec, all found by the resume pass:

- **`min_approvals` is capped at 1 (422 above that).** `approval_steps` is keyed `(request_id, step_no)`, so a step can hold only one signature. A saved `min_approvals=3` would have approved on a single signature. N-of-M signing needs a per-signature table, which is a future schema change.
- **Concurrent decisions on one step** use `UPDATE … WHERE decision IS NULL RETURNING step_no`; an empty result is a 409. Without it, two simultaneous final-step approvals would both finalize and promote twice once task 5.6 lands.
- **A missing version row is a 409.** If the row is gone, `doc_id` is NULL and the role check used to be skipped, so anyone could sign.
- **Deactivated people** (`is_active=false`) cannot sign a step or be given a role (403).
- **Auto-approve while a request is open** is a 409: an `approved` insert isn't covered by `approval_requests_open_uq`.
- Only a violation of `approval_requests_open_uq` becomes a 409; other integrity errors are re-raised.

**The task 5.6 hook** is `_finalize_approved(db, request_id, version_id, doc_id)` in `org.py`, marked `INTEGRATION POINT — TODO(task 5.6)`. It runs from `decide_step` (last step approved) and `open_approval` (auto-approve), both before `db.commit()`, so promotion shares the transaction. Today it only sets the request `approved` and the version `status='approved'`. Task 5.6 replaces the version-status write with `promote_version`, which also owns `is_current`, `current_version_id`, `effective`, and superseding the prior version.

**Known gaps in this schema** (accepted for the demo): no N-of-M signing; no delegation or out-of-office (`people.alternate_person_id` is unused); a step's assignee is fixed when the request opens; no foreign keys anywhere, so department cycles and dangling `reports_to_id` / `policy_id` are possible; soft-deleting a person leaves their role assignments pointing at them; two policies can share a `(vertical, doc_class)` scope, with ties broken by name; no audit trail for org changes; one flat owner/reviewer/approver set per document with no department-level authority.

**Unowned writer:** `company_documents.review_cycle` is hardcoded `None` at `store/neon.py:118-119`, and TDD §7.6 assigns it to an org endpoint, but none exists. A one-field `PATCH /documents/{doc_id}` is needed. Tracked in task 9.1 step 1a.

### 1.6 Dropped

```sql
DROP TABLE company.parameter_checks, company.datasets, company.dataset_columns;
```

Verified **0 rows each** in production — zero cost. `company.table_columns` (26 rows) is **kept** with the register path. `clause_parameters` (2,948) and `clause_links` (4,675) are unaffected — they come from regex/link enrichment on clause text.

---

## 2. Hash canonicalization — exact spec

**Implemented** — `app/company_ingest/hashing.py`, 34 tests in `tests/company_ingest/test_hashing.py`.

```python
_WS = re.compile(r"\s+")

def _strip_format_chars(text: str) -> str:
    """Drop Unicode format characters (general category Cf)."""
    return "".join(c for c in text if unicodedata.category(c) != "Cf")

def canonicalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    t = _strip_format_chars(t)
    t = _WS.sub(" ", t)          # all whitespace runs -> single space
    return t.strip()

def content_hash(text: str) -> str:
    """SHA-256 hex of the canonical form. The document hash."""
    return hashlib.sha256(canonicalize(text).encode("utf-8")).hexdigest()
```

Collapsing all whitespace (not just newlines) is what makes a Word re-export with different line wrapping hash equal. SHA-256 over xxHash64: already the repo-wide standard (`clauses.text_sha256`, `code_sections.content_hash`), and a collision would wrongly reject a customer's real document.

**The `Cf` step is required, not defensive.** Python's `\s` does **not** match soft hyphen `U+00AD`, ZWSP `U+200B`, BOM `U+FEFF` or `U+180E`. Word inserts optional hyphens on export, so without this step `"oper­ator"` and `"operator"` hash differently and the re-export case the design depends on fails. A *real* hyphen (`U+002D`) is content and stays distinguishing.

**Two consequences callers must handle:**

1. **Nesting depth is invisible.** `"- a\n  - b"` and `"- a\n- b"` hash equal. Accepted (pinned by test) — the alternative misses re-exports, which are commoner.
2. **Every empty extraction hashes identically** to `e3b0c442…b855` (`sha256(b"")`). So the 422 empty-extraction guard in §3.2 / task 6.1 **must run before `content_hash` is computed and before any duplicate lookup**, or the second image-only DOCX is reported as a duplicate of the first. This ordering is mandatory, not stylistic.

A further caveat for task 6.1: `parse/markdown_segmenter.py` is newline-sensitive, so two inputs with *equal* hashes can segment into *different* clause sets. Rejecting on hash equality therefore discards the second document's structure — which is the intended behaviour ("no changes"), but worth understanding before changing the canonical form.

**Do not** reuse `parse/text.py:sha256_text` — it deliberately hashes raw text with no normalization and is the clause-level cache key, a different concern.

---

## 3. Extractor

```python
# app/company_ingest/extract/base.py
from dataclasses import dataclass
from typing import Protocol

@dataclass
class ExtractedDocument:
    markdown: str          # MUST satisfy the markdown_segmenter contract
    method: str            # e.g. "python-docx/1.1"
    page_count: int | None
    confidence: float | None

class DocumentExtractor(Protocol):
    content_types: frozenset[str]
    def extract(self, raw: bytes, filename: str) -> ExtractedDocument: ...
```

### 3.1 `DocxExtractor`

`content_types = {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}`

| DOCX element | Markdown |
|---|---|
| `Heading1` / `Heading2` / `Heading3` style | `# ` / `## ` / `### ` |
| `Title` style | `# ` |
| `ListBullet` / `ListNumber` | `- ` / `1. ` |
| normal paragraph | paragraph, blank line separated |
| table | pipe table with a header separator row |

Verified present in the corpus: `RPL-CS-PRO-004.docx` contains `Heading1` ×2, `Heading2` ×31, `ListBullet` ×35.

**Why Markdown is the contract:** `parse/markdown_segmenter.py` derives all structure from `_HEADING_RE` on `#` markers and pipe tables. Measured on `RPL-CMP-REG-001` — 20 headings in the `.md` source, **0** recovered by `pypdf` from the rendered PDF, vs. clean heading styles in DOCX. This is why PDF is deferred.

**`clause_id` without anchors.** v1 relied on `<!-- RPL-…:1.0 -->` comments (`parse/front_matter.py:237`), absent from customer documents. Where a heading carries no section number, synthesize the local part from heading depth and ordinal (`s1`, `s1.1`, `s1.2`, …); `clause_id` remains `f"{doc_id}:{local_id}"`.

### 3.1a Anchoring — the segmenter needs markers, not headings

**Implemented** — `extract/docx.py:anchor_clauses()`, `marker_doc_id_supported()`. 22 tests.

Measured, not assumed: `segment_with_ctx` emits a clause **only** at an HTML-comment anchor (`<!-- clause: DOC:LOCAL -->`, `<!-- table: DOC:TID -->`). `#` headings merely build `heading_path`. **Clean `#`-heading Markdown yields 0 clauses.** The synthetic corpus works only because those anchors are hand-authored into its `.md` files.

```python
def anchor_clauses(markdown: str, doc_id: str) -> str:
    """Insert clause/table anchors so the segmenter emits units. Pure."""
```

| Input shape | Local id |
|---|---|
| numbered heading | own number — `7`, `7.2` |
| unnumbered heading | depth id — `s1`, `s1.1` |
| prose before first heading | `s0` |
| prose after a table | continuation — `7a`, `7b` |

The continuation rule fixes a real bug: a table anchor *closes* the open clause, so without it every post-table paragraph is dropped. Before the fix, 66 lines / 5.3 KB of prose fell outside any clause span in one fixture; after, zero.

**Mandatory call order:**

```
extract() → canonicalize / content_hash / 422 guard on .markdown → anchor_clauses() → segment_with_ctx()
```

Anchors are **not** part of `ExtractedDocument.markdown`, and must not be. `markdown` is what §2 hashes; anchors embed `doc_id`, so folding them in would make byte-identical content hash differently under a different `doc_id`, breaking `company_documents_content_hash_uq` and defeating duplicate detection.

**Table-cell escaping:** a literal `|` becomes `&#124;`, not `\|` — `markdown_segmenter._parse_table_row` splits on `|` without honouring backslash escapes, so an escaped pipe would still add a phantom cell and misalign the row. Cell newlines collapse to spaces; blank header cells get positional `Column N` names (an empty header makes the segmenter drop that column entirely); body paragraphs starting with `#`, ```` ``` ````, `~~~` or `|` are backslash-escaped, since an unescaped fence would swallow the rest of the document.

### 3.1b ✅ RESOLVED — the marker grammar rejected real doc_ids

**Fixed** in `parse/markdown_segmenter.py`: `_CLAUSE_EXPLICIT_RE` and `_TABLE_RE` accept any doc id for the explicit `clause:`/`table:` forms; the legacy bare form is unchanged. What follows records the original defect.

```python
_CLAUSE_RE = re.compile(r"<!--\s*(?:clause:\s*)?([A-Z]+-[A-Z]+-[A-Z]+-\d+|[A-Z]+-[A-Z]+-\d+):([^\s|>]+)\s*-->")
```

It requires a 3- or 4-segment uppercase doc id. Verified:

| doc_id | anchors? |
|---|---|
| `RPL-CS-PRO-004` | ✅ |
| `DOC-000123` (our system-assigned format, §1.1) | ❌ |
| `HR-POLICY` | ❌ |

**Every real uploaded document would anchor zero clauses and produce an empty clause graph.** `_CLAUSE_RE` and `_TABLE_RE` in `parse/markdown_segmenter.py` must be relaxed to accept any non-colon doc id token. Owned by **task 2.3** (which already removes the `RPL-` literals from `parse/front_matter.py`). `anchor_clauses` raises `ValueError` rather than silently returning zero clauses, and `marker_doc_id_supported(doc_id)` lets callers pre-check — so this fails loudly until fixed.

### 3.2 Empty-extraction guard

A DOCX containing only images yields empty text. Without a guard it hashes `canonicalize("") == ""` and the second such upload is reported as a duplicate of the first. **Reject with 422 before hashing** when `canonicalize(markdown)` is empty or under ~50 characters.

### 3.3 Register path

CSV upload with a `register_spec` bypasses extraction and goes to `parse/register_segmenter.py` (one row = one clause). Delete `_detect_p2` and `_RE_OBL`/`_RE_EVT`/`_RE_RRS` — intent is declared, not sniffed:

```python
class RegisterSpec(BaseModel):
    register_type: Literal["obligation", "event", "retention", "other"]
    id_column: str                 # e.g. "obligation_id"
    citation_columns: list[str] = []
```

The document hash for a register is `content_hash` of the raw CSV text, decoded UTF-8.

**Implemented** — `app/company_ingest/register_spec.py`, 35 tests. Also provides `read_csv_columns(data: str|bytes)` (for a future UI column picker) and `validate_register_spec(spec, data)`. Both accept `str | bytes` because the API holds uploaded bytes; bytes decode as `utf-8-sig`. `extra="forbid"` on the model so a typo'd form key fails loudly instead of silently defaulting.

**Strict id policy (confirmed).** Blank or duplicate `id_column` values are rejected as 422. Rationale: `clause_id = f"{doc_id}:{row_id}"` and `clauses` has `UNIQUE (version_id, clause_id)`, so a duplicate row id would collide and `ON CONFLICT` would silently drop a row. All three real registers pass (70/86/48 rows, all ids unique and non-blank). The segmenter is more lenient — it synthesizes `ROW_n` — so validation must catch this earlier.

### 3.4 `segment_register` integration gaps — task 6.1 MUST handle these

`parse/register_segmenter.py` predates declared intent and does not know about `RegisterSpec`. Wiring it up requires four fixes; skipping any of them produces wrong data silently:

| # | Gap | Consequence if ignored |
|---|---|---|
| 1 | `segment_register` **ignores `spec.id_column`** and always uses `headers[0]` | a register whose id column is not first gets wrong `clause_id`s for every row |
| 2 | It ignores `spec.citation_columns`; `_provisional_role` only matches the literal substring `"citation"` | a declared citation column named e.g. `regulatory_authority` gets no `citation` role, so its citations are never resolved — directly undermining the 69-code_section contribution registers make |
| 3 | It opens files with `encoding="utf-8"`, not `utf-8-sig` | a BOM'd CSV passes validation but reaches the segmenter with `﻿<name>` as `headers[0]` |
| 4 | It does not skip wholly blank rows | emits a `ROW_n` clause with empty text for trailing `,,,` spreadsheet artefacts |

Recommended: have task 6.1 pass **already-decoded text** plus the validated `RegisterSpec` into the segmenter, rather than a path, which resolves 3 by construction.

**Known corpus data defect (pre-existing, verified).** `retention_schedule_2024-12-31.csv` has two ragged rows: line 2 carries 16 fields against the 13-column header and line 74 carries 14. `csv.DictReader` files the overflow under the key `None`, so line 2's column mapping is wrong — its three spilled values are real content (`RPL-TAR-GRR-012; RPL-CS-PRO-004`, `RPL-CS-PRO-004:12.1; RPL-TAR-GRR-012:R01.D01`, `Retain in CIS; 7 years after final close`). This means one of the 86 retention clauses is **already wrong in current production data**. Validation deliberately does *not* reject ragged rows — doing so would make a real corpus file unuploadable — but the segmenter should emit a `ctx.issue` when a row's field count differs from the header, and the corpus file should be repaired in `synthetic/` before task 9.1 seeds it.

### 3.5 Register error mapping — task 6.1 contract

| Condition | Response |
|---|---|
| Malformed `register_spec` JSON string (pydantic `ValidationError`) | **422**, not 500 — must be caught |
| `RegisterSpecError` raised by `validate_register_spec` | **422** with `str(exc)` as `detail` (messages are written to be shown verbatim) |
| CSV uploaded **without** a `register_spec` | **422** — §7.1 step 2's 415 message says "DOCX only", so the allowlist needs an explicit CSV branch that *requires* the spec, or registers become unuploadable |
| `register_spec` sent with a **non-CSV** file | **422** |
| Non-UTF-8 CSV (Excel cp1252 export — a real customer case) | **422** with an actionable "re-export as CSV UTF-8" message |
| Oversize single field | **422** at validation time. Do **not** raise `csv.field_size_limit`: it is process-global and would race under the threadpool |

For `POST /{doc_id}/versions` on a register, re-run `validate_register_spec` against the **new** file's header regardless of whether the spec is re-sent or inherited — columns get renamed between register revisions.

---

## 4. Ingest service

```python
# app/company_ingest/service.py
@dataclass
class IngestResult:
    version_id: str
    clause_count: int
    citations_resolved: int
    llm_calls: int
    llm_cache_hits: int
    reused_clauses: int

async def ingest_document(
    *, company_id: str, doc_id: str, version_id: str,
    markdown: str, register_spec: RegisterSpec | None,
    session: AsyncSession, ctx: RunContext,
) -> IngestResult: ...
```

Extraction and hashing happen in the API layer **before** this is called, so a duplicate never reaches the service.

### 4.1 Stage order

| # | Call | Source |
|---|---|---|
| 1 | `split_front_matter` (generic; `RPL-` literals removed) | `parse/front_matter.py:376` |
| 2 | `segment_with_ctx(version_id, doc_id, body, offset, ctx)` or `segment_register(...)` | `parse/markdown_segmenter.py:564`, `parse/register_segmenter.py:88` |
| 3 | **clause reuse pass** (new, §4.2) | — |
| 4 | `enrich_citations` → `enrich_parameters` → `enrich_references` → `enrich_roles` → `extract_terms` → `find_term_usages` | `enrich/*` |
| 5 | `run_clause_enrichment` (cache-backed) — changed/new clauses only | `llm/run_clause_enrichment.py:144` |
| 5b | `run_column_roles` — registers only | `llm/run_column_roles.py:107` |
| 6 | **`resolve_citations_for_version`** (new, §5) | port of `enrich/resolve_citations_db.py:111` |
| 7 | `resolve_references` → `find_restates_links` → `build_document_scope` | `link/*` |
| 8 | `finalize_parameters` | `store/commit.py:53` |
| 9 | `write_clause_snapshot` → R2, keyed by real `version_id` | `store/snapshot.py:122` |
| 10 | Neon writes via the `commit_run` path (dataset inserters removed) | `store/neon.py:798` |

**Qdrant indexing is NOT here.** It happens only at promotion (§6).

**Implemented** — `app/company_ingest/service.py`, 16 tests. Two deliberate departures from the table above:

- **Stage 6 (citation resolution) runs *after* stage 10 (`commit_run`)**, not before. `resolve_citations_for_version` reads `clause_citations JOIN clauses` from the database, so it finds nothing until those rows are written. It uses the same session, so it is still one transaction. Resolved `code_section_id`s are read back onto the in-memory clauses before the R2 snapshot is written, so the snapshot includes them.
- **Stage 0 inserts the `document_versions` row before segmenting**, so every `clauses.version_id` has a matching row. The v1 register path derived a throwaway id from the file path, which left 204 clauses orphaned in production and made the resolver fall back to a guessed `law_as_of`. If the API already created the row, the service reads it back instead of overwriting `source_r2_key` / `extraction_*` / `version_no` with NULLs.

**Fails loudly rather than silently.** `CitationResolutionError` is raised if citations were written but none are visible under this `company_id` + `version_id`, and for prose if in-scope IAC/CFR citations exist and none resolved (citations to titles the knowledge base doesn't cover don't count); a prose document whose 0 is a genuine answer — some citations came back `not_in_kb` and the KB holds a snapshot of their title at the lookup date — is recorded as a `citations_none_resolved` warning instead (task 9.1: `RPL-ENV-PRO-005` cites only `327 IAC 2-6.1`, absent from the KB). `IngestError` covers a mismatched or empty `ctx.company_id` — an empty one would also silently disable the LLM cache.

**Registers.** New `segment_register_text(...)` fixes the four gaps in §3.4: it honours `id_column`, honours `citation_columns`, strips the BOM, and skips blank rows without consuming a row number; ragged rows are kept under `row_cells["_overflow"]` with a warning. `enrich/citations` only scans a column literally named `citation`, so the service briefly re-keys declared citation cells as `"<col>:citation"` and restores them.

**LLM cache is now genuinely wired**: `run_clause_enrichment(..., session=)` and `run_column_roles(..., session=)` pass `content_sha256` and the session. A test ingests identical Markdown twice under fresh contexts and asserts the second makes **zero provider calls**; it was verified to fail when `session=None`.

**Known cost:** the cache writes through the ingest session, so a failed ingest rolls its cache rows back too and a retry pays for those LLM calls again. A separate cache session is a follow-up if retries prove common.

### 4.2 Clause-level reuse

```python
async def reuse_from_prior_version(
    session, company_id: str, doc_id: str, prior_version_id: str | None,
    units: list[ClauseUnit],
) -> int:
    """Copy enrichment onto units whose text_sha256 matches a prior clause.
    Sets unit._reused = True so the LLM stage skips them. Returns reuse count."""
```

Match on `clauses.text_sha256` within `prior_version_id`. Inherit `clause_role`, `role_method`, `assessable`, `normalized_statement`, `topic_terms`, and the clause's citations and parameters. Reused clauses are excluded from both LLM enrichment and embedding.

### 4.3 LLM cache

`llm/client.py:call_structured` gains a `content_sha256` parameter and a read-through:

1. `SELECT output FROM company.llm_extractions WHERE (company_id, stage, content_sha256, prompt_sha256, model) = (...)`.
2. Hit → validate against the schema and return; `ctx.count("llm_cache_hit")`.
3. Miss → call Anthropic, then `INSERT ... ON CONFLICT DO NOTHING`.

Keep the existing in-memory `ctx.llm_cache` as a first tier. Keep the R2 audit write. On a schema-validation failure of a cached row, treat it as a miss.

---

## 5. Citation resolution, in-pipeline

Port `enrich/resolve_citations_db.py:111 resolve_all_citations(conn, dry_run)` from synchronous psycopg2 whole-table to async SQLAlchemy scoped to one version:

```python
async def resolve_citations_for_version(
    session: AsyncSession, company_id: str, version_id: str,
) -> dict[str, int]:
    """Resolve company.clause_citations for one version. Returns counts per status."""
```

**Logic to preserve exactly** (it is correct and tested in production):

- In-scope titles from `SELECT DISTINCT source_system, title_number FROM public.code_sections` (`:129-137`).
- `fallback_law_as_of = MIN(law_as_of) FROM company.document_versions`, default `date(2024,12,31)`, for clauses whose version row is missing (`:145-148`).
- **IAC:** key `f"{title} IAC {article}-{int(section)}"` → `WHERE source_system='iac' AND citation=%s AND snapshot_date <= law_as_of ORDER BY snapshot_date DESC LIMIT 1`. Rule granularity → `citation LIKE '{title} IAC {article}-%'` EXISTS → `resolved_rule`.
- **CFR:** `_parse_cfr_citation_raw` → `(title, part, section)`, matched with a **14-day window** (`law_as_of + timedelta(days=14)`) because the CFR snapshot is 2025-01-02 vs `law_as_of` 2024-12-31 (`:286-300`).
- `ic`/`usc` → `not_monitored`; `external_standard` → `external`; `unknown` → `unparsed`.
- Idempotency via `_TERMINAL` (`:35`) and `_IN_KB_FOR_STATUS` (`:47`).

Change only: scope to `version_id`, use the caller's `AsyncSession`, no internal `commit()`.

`scripts/backfill_citations.py` and `scripts/extract_register_citations.py` call the old psycopg2 function — either keep it as a thin wrapper or update both.

---

## 6. Promotion transaction

The single most correctness-critical routine. Everything that makes a version "live" happens here, together, after ingest succeeds and approval completes.

```python
async def promote_version(session, company_id: str, doc_id: str, version_id: str) -> None:
    """Make version_id the current version. One transaction."""
```

1. `SELECT ... FOR UPDATE` the `company_documents` row (serializes concurrent promotions).
2. Load the new version's canonical hash, in order: the explicit `content_hash` argument → `document_versions.pending_content_hash` → the first-version reservation on `company_documents` (§6.2). None of them → refuse (409), never write NULL.
3. Prior current version → `status='superseded'`, `is_current=false`, `superseded_by=version_id`, `pending_content_hash=NULL`.
4. New version → `status='effective'`, `is_current=true`, `supersedes_version_id=<prior>`, `pending_content_hash=NULL`.
5. `company_documents` → `current_version_id`, `current_content_hash`, `updated_at`.
6. **Qdrant:** upsert the new version's points, **then** delete this document's points whose `version_id` differs — see §6.1.
7. Commit.

### 6.1 Qdrant within promotion

```python
async def reindex_document(company_id: str, doc_id: str, version_id: str,
                           units: list[ClauseUnit], ctx) -> None:
    """Upsert this version's points, then sweep the doc's other versions. Live-only."""
```

- **Upsert first** with point id `stable_uuid(company_id, version_id, clause_id)` using the **real** `version_id`. v1 passed the literal `"v1"` (`cli/ingest.py:227`), so each new version overwrote the previous version's vectors.
- **Then delete** by filter `project` + `company_id` + `doc_id` with **`must_not version_id = <new>`** — not a specific old `version_id` — so orphans from any earlier scheme are swept (v1 wrote point ids as `stable_uuid(company_id, "v1", clause_id)`).
- **Why this order (task 3.2).** The original delete-then-upsert meant an upsert failure rolled Postgres back to v1 while v1 had **no points**. Upsert-then-sweep turns every failure into *extra* points instead of *missing* live ones: if the upsert fails, nothing was deleted; if the sweep fails, the not-yet-promoted version's points sit beside v1's until the retry or the next promotion sweeps them. Nothing reads the collection today, so extras are harmless; "Qdrant holds only live clauses" is therefore eventually, not strictly, true after a failed promotion.
- Remove `is_current` from `_build_payload` (`index/upsert.py:31`) and from the payload indexes in `qdrant_setup.py:56`. Delete `mark_previous_versions_stale` (`:109`) — presence in the collection now means live.

Qdrant is not transactional with Postgres. Order the Qdrant write **last**, and on failure roll back the Postgres transaction and surface a retryable job error; reconciliation is deterministic because point ids are deterministic and the sweep is by `doc_id`.

**Sparse ids.** `index/bm25.py` maps tokens to sparse indices with `zlib.crc32(token) % 2**20`, not Python's `hash()`, which is salted per process and would make index-time and query-time ids disagree. Changing that function invalidates every stored sparse vector, so the cutover (task 9.2) recreates the collection.

### 6.2 Failure and recovery

Setting the hash or current pointer before ingest completes would leave either a document that blocks every re-upload with 409 while having no clauses, or a current version with no clauses. So:

| Step | State |
|---|---|
| Version created | `is_current=false`, `status='in_review'`, `ingest_status='pending'`, `pending_content_hash=<hash>` (§1.2) |
| New document, first version | hash **reserved** on `company_documents.current_content_hash` with `lifecycle_state='pending'` |
| Ingest fails | job → `failed`; for a first version, **release the reserved hash** (set NULL) so the customer can retry. `company_documents.lifecycle_state` becomes **`'failed'`** (a value this document previously left undefined — task 8.2 must render it) and the version's `ingest_status` becomes `failed` while the version itself stays `in_review`, not current |
| Ingest succeeds, approval open | version stays `in_review`, not current, not in Qdrant |
| Approval completes | `promote_version` runs; `pending_content_hash` → NULL |
| Process restart mid-ingest | startup sweep marks `running` jobs older than N minutes `failed` and applies the same release |

`POST /company/ingest-jobs/{job_id}/retry` re-runs from the immutable R2 raw bytes. For a register CSV it also needs the declared `RegisterSpec`, which `jobs.create_job` stores on `ingest_jobs.register_spec` and `jobs.prepare_retry` reads back (an explicit spec overrides it). An ingest failure does **not** clear `pending_content_hash`: a retry re-ingests the same bytes.

**Accepted, documented, not fixed (task 3.2):**
- *Approval can finish before ingest does.* The final approval then 409s (`PromotionNotReady`: not `ingested`) and rolls the decision back; nothing auto-promotes later. The UI (task 8.3) must disable "approve" until the version's job has `succeeded`.
- *Embedding and Qdrant calls run synchronously inside the approval HTTP request* while the `company_documents` row lock is held. Acceptable for the demo.
- `scripts/backfill_qdrant_clauses.py` still writes `is_current`; delete it in the cleanup pass. Existing collections keep the old `is_current` payload index until the cutover recreates the collection (task 9.2).

### 6.3 Ingest job table

```sql
CREATE TABLE company.ingest_jobs (
    job_id uuid PRIMARY KEY,
    company_id text NOT NULL,
    doc_id text NOT NULL,
    version_id uuid NOT NULL,
    state text NOT NULL CHECK (state IN ('queued','running','succeeded','failed')),
    error text,
    stats jsonb,
    register_spec jsonb,          -- task 3.2: declared RegisterSpec for a register CSV, else NULL
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    finished_at timestamptz);
CREATE INDEX ingest_jobs_state_idx ON company.ingest_jobs (state, created_at);
```

`register_spec` is written by `jobs.create_job` (in the upload transaction) and read by `jobs.prepare_retry`; without it a failed register upload could never be retried. The requeue keeps it.

Insert the row **before** scheduling the `BackgroundTask`. The existing engine pattern inserts inside the task (`engine/run.py:113-117`), which makes `GET /engine/runs/{id}` 404 briefly (`api/engine/routes.py:82-84`) — do not copy that.

---

## 7. API contracts

`requirements.txt`: add `python-multipart`, `python-docx`. **Keep `pypdf`** — used by `app/regulatory/adapters/{iurc_gaos,iurc_rulemakings,iurc_investigations}.py`.

### 7.1 `POST /company/documents`

`multipart/form-data`: `file` (required), `title`, `vertical` (required), `doc_number`, `register_spec` (JSON string, CSV only), `acting_person_id`.

| Step | Failure |
|---|---|
| 1. Read bytes, ≤25 MB | 413 |
| 2. Content type in allowlist | **415** `{"detail":"Only .docx documents are supported. PDF is not yet available."}` |
| 3. Extract → Markdown | 422 on extractor error |
| 4. `canonicalize` non-trivial | **422** `{"detail":"No extractable text found in this document."}` |
| 5. `content_hash` | — |
| 6. Hash lookup across live documents | **409** `{"status":"duplicate","message":"This document is already in the system as '<title>'.","doc_id":"DOC-000041"}` |
| 7. Insert doc + version 1 (with `pending_content_hash`, §1.2) + job (with `register_spec` for a CSV, §6.3); upload raw bytes to R2 | `UniqueViolation` on the partial index → same **409** |
| 8. Schedule `BackgroundTask` | **202** `{"doc_id","version_id","job_id","status":"processing"}` |

Nothing is written before step 7, so a duplicate stores no row and no R2 object.

### 7.2 `POST /company/documents/{doc_id}/versions`

Same shape plus `change_reason`. Identical steps 1–5, then:

- Hash compared against **this document's** `current_content_hash` **and** any pending version's hash → **200** `{"status":"unchanged","message":"No changes compared to the current version."}`, nothing written.
- Otherwise insert `version_no = COALESCE(MAX(version_no),0)+1`, `status='in_review'`, `pending_content_hash=<hash>` (§1.2; promotion reads it), open an approval request per policy, ingest → **202**.
- Unknown `doc_id` → 404.

### 7.3 Approval

```
POST /company/documents/{doc_id}/versions/{version_id}/approval      -> open a request
POST /company/approval-requests/{request_id}/steps/{step_no}/decision -> {decision, note, acting_person_id}
GET  /company/approval-requests/{request_id}
```

When the last required step is `approved`, set the request `approved` and call `promote_version` in the same transaction. Any `rejected` step → request `rejected`; the version stays `in_review` and never promotes.

### 7.4 Reads

```
GET /company/documents/{doc_id}/versions   -> version_no, status, is_current, dates, created_by, change_reason
GET /company/ingest-jobs/{job_id}          -> state, error, stats  (poll shape of GET /engine/runs/{id})
```

### 7.5 Org endpoints

`POST`/`PATCH` for departments, people, `document_role_assignments`, `approval_policies` (+ steps). Every write takes `acting_person_id`. No auth; `company_id` from `ENGINE_COMPANY_ID`.

### 7.6 Removing synthetic reads from `app/api/company/routes.py`

Delete `_GLOBAL` (:23), `load_register` (:102), `load_profile_yaml` (:119), `derive_doc_type` (:63), and the fallbacks at `:143-145, 288-293`. Field sources become:

| Field | Column | Writer |
|---|---|---|
| title, doc_class | `company_documents.title/doc_class` | extraction (`DocClassification`, `llm/schemas.py`), user-editable |
| vertical | `company_documents.vertical` | upload form (per-vertical entry point) |
| effective/approved/next_review | `document_versions.*` | extraction, user-editable |
| review_cycle | `company_documents.review_cycle` | org endpoint (hardcoded `None` today at `neon.py:118-119`) |
| owner/reviewer/approver | `document_role_assignments` (+ legacy columns) | org endpoint |
| regulator, utility_type, legal_name, ownership, jurisdiction, customer_count | `companies.name` + `company_attributes` | org endpoint |

`derive_doc_type` relied on the positional `RPL-CS-PRO-004` grammar; `doc_class` now comes from extraction.

### 7.7 Version-leak fixes — mandatory before a second version exists

None of these filter by version; they join `clauses → company_documents` on `doc_id` alone. Harmless while every document has one version; with history they double the footprint and duplicate findings.

| File:line | What |
|---|---|
| `app/engine/footprint.py:33-38` | `_ELIGIBLE_CTE` |
| `app/engine/candidates.py:81-85` | `_ELIGIBLE` |
| `app/engine/radar.py:51-53` | citation join |
| `app/engine/delta.py:295` | clause read |
| `app/api/company/routes.py:191-195` | `_CITED_SQL` |
| `app/api/company/routes.py:232-243` | uses `current_version_id` only in `ORDER BY` — **returns both versions' clauses** |
| `app/api/engine/routes_ui_results.py:165` | `DISTINCT ON (clause_id)` masks the problem |

Each gains `AND c.version_id = d.current_version_id` (or `AND c.version_id = :version_id` where a version is already in scope).

---

## 8. Synthetic boundary enforcement

Extend `tests/engine/test_barrier.py`:

```python
SCAN_DIRS = [BACKEND / "app"]                      # was engine + api/engine + scripts
FORBIDDEN_PATH_PATTERNS += [
    re.compile(r"synthetic/"),
    re.compile(r"corpus/"),
    re.compile(r"app/company\b"),
]
```

Patterns **must** be path-shaped. Bare `synthetic` false-hits `app/engine/params_text.py:18 _synthetic_unit`; bare `corpus` false-hits the comment at `app/engine/delta.py:5`. Reuse the existing `scan_barrier` / `scan_file` helpers and keep the existing self-tests.

### Secret-leak regression test

**Implemented** — `tests/test_no_secrets.py`, 6 tests. Two tiers:

```python
# Applied to EVERY scanned file, including placeholder files.
PATTERNS = [
    r"npg_[A-Za-z0-9]+",              # Neon-issued password
    r"AKIA[0-9A-Z]{16}",              # AWS / R2 access key id
    r"-----BEGIN [A-Z ]*PRIVATE KEY",
    r"sk-ant-[A-Za-z0-9_-]{16,}",     # Anthropic API key
]

# Applied everywhere EXCEPT .env.example / .env.sample / .env.template.
CONNSTRING_PATTERN = r"postgres(ql)?(\+\w+)?://[^ \"'/]*:[^ \"'@/]+@"
```

**The `(\+\w+)?` group is the important part, and the original spec omitted it.** `app/db.py:10` rewrites `DATABASE_URL` to **`postgresql+asyncpg://`**, which is also the form `.env.example` documents — so it is the form a developer is most likely to paste into a committed file. Verified: the original pattern caught `postgresql://u:p@h` but **missed** `postgresql+asyncpg://u:p@h`, making the guard nearly useless against the most probable leak.

**Why the two tiers.** `.env.example` legitimately contains `postgresql+asyncpg://user:password@host/dbname`. Widening the DSN pattern without an exemption would fail the suite on a placeholder. The exemption is deliberately narrow — it skips only the DSN pattern, so a real `npg_…` password pasted into `.env.example` is still caught. A test pins that narrowness.

Exclude `.venv`, lockfiles, `*.md` and binary assets (the corpus ships PDFs/DOCX/XLSX/PNGs, so a naive UTF-8 read crashes). Matches are reported as `file:line` with the **match redacted**, so a real credential never lands in CI logs. The module scans itself, so every fake in its own tests is assembled from fragments at runtime. It carries **no** `corpus` marker — CI runs `-m "not corpus"`, which would otherwise disable the guard — and asserts `scanned >= 100` so a broken file enumeration fails loudly instead of passing vacuously.

Baseline verified clean: across 731 tracked files the only match was `app/company/corpus/grounding/_leaktest.py:27`, deleted by task 1.1. Untracked files pending commit were also scanned — 0 hits.

---

## 9. Test strategy

`FakeSession` + `ASGITransport` (the pattern at `tests/engine/test_api_routes.py:56-63`) **cannot** exercise partial unique indexes, CHECK constraints, `ON CONFLICT`, PK collisions or concurrency. Placement matters.

| Harness | Tests |
|---|---|
| **Real Postgres** (`@pytest.mark.neon`, Neon branch or local PG) | duplicate rejection, re-export equality, promotion/supersession, version-leak, concurrency, cutover parity |
| **FakeSession + ASGITransport** | routing, status codes, validation (415/422/413/404) |
| **`moto[s3]`** (already a dependency) | R2 writes, write-once guard, retry-from-bytes |
| **Mocked Anthropic with a call counter** | LLM cache hits, clause reuse |
| **`@pytest.mark.qdrant`** | delete-and-replace, live-only invariant |

**Import hazard:** `app/config.py:7-14` declares `DATABASE_URL`, `QDRANT_*`, `R2_*` with no defaults and `app/db.py:12-18` builds the engine at import, so importing `app.main` needs a `.env` even for FakeSession tests.

### Acceptance tests

| # | Scenario | Assert |
|---|---|---|
| 1 | New DOCX | 202; job succeeds; clauses written; `code_section_id` non-NULL; points keyed by real `version_id` |
| 2 | Byte-identical re-upload, different filename | 409; **zero** new rows; **zero** new R2 objects |
| 3 | DOCX re-saved from Word, same wording, different bytes | 409 |
| 4 | New version, unchanged content | 200 `unchanged`; nothing written |
| 5 | New version → approve | v2 `is_current`/`effective`; v1 `superseded` + `superseded_by`, clauses intact; hash replaced; one row matches `document_versions_current_uq`; **v2's citations and links exist** |
| 6 | LLM reuse on v2 | cache hits > 0; mocked client records no call for unchanged clauses |
| 7 | Version leak | with two versions live, every §7.7 query returns one version's clauses |
| 8 | Concurrency | two simultaneous identical uploads → exactly one 202, one 409, one row |
| 9 | PDF upload | 415 naming DOCX, before extraction or write |
| 10 | Image-only DOCX | 422 before hashing; a second such file also 422, **not** 409 |
| 11 | Failure recovery | kill mid-ingest → hash released, re-upload accepted, retry completes from R2 |
| 12 | Extraction fidelity | per seeded doc, DOCX clause count within tolerance of the known `.md` count |
| 13 | Qdrant hygiene | after promoting v2, points for v2 only; zero for v1 or pending; count == v2 indexable clauses |
| 14 | Register CSV | one clause per row, `unit_kind='register_row'`, citations resolved, `table_columns` populated |
| 15 | Cutover parity | post-reseed findings/coverage within tolerance of the pre-wipe snapshot |
| 16 | Deletability | `mv backend/synthetic` away → full suite green, `/company/documents` and `/company/profile` fully populated |

### Pre-wipe baseline (capture before cutover)

Measured from production on the current data:

| Metric | Value |
|---|---|
| Clauses | 2,334 (`section` 1,019 · `table_row` 758 · `register_row` 204 · `form_field` 204 · `tariff_subrule` 127 · `appendix` 21 · `other` 1) |
| Citations | 1,550 total, 1,284 resolved |
| `document_scope` rows | 285 |
| Engine findings | 1,244 (`section` 511 · `register_row` 487 · `table_row` 105 · `tariff_subrule` 105 · `form_field` 21 · `appendix` 15) |
| Distinct code_sections touched | `register_row` 69 · `section` 60 · `table_row` 40 · `tariff_subrule` 40 |
| `clause_parameters` / `clause_links` / `defined_terms` | 2,948 / 4,675 / 67 |
| `parameter_checks` / `datasets` / `dataset_columns` | **0 / 0 / 0** (why dropping them is free) |

Findings are regenerated, so exact equality is not expected. A material drop means something was lost in the detangle.

---

## 10. Register path — what is kept and why

The registers are **not** synthetic scaffolding. Measured contribution of the 204 `register_row` clauses:

| | register_row | share |
|---|---|---|
| Clauses | 204 / 2,334 | 8.7% |
| Citations | 419 / 1,550 | 27% |
| **Findings** | **487 / 1,244** | **39%** |
| **Distinct code_sections** | **69** | **largest of any unit kind** |

8.7% of clauses drive 39% of findings, because the compliance register *is* the obligation→citation map.

**Kept:** `parse/register_segmenter.py`, `llm/run_column_roles.py`, `company.table_columns`.
**Replaced:** `_detect_p2` and the `_RE_OBL`/`_RE_EVT`/`_RE_RRS` grammar → declared `RegisterSpec`.
**Note:** the 10,928-row outage file is *not* a register — `_RE_EVT` requires `EVT-\d{4}-\d{4}` and those ids carry 7 trailing digits, so it was classified as a P3 dataset. It leaves with the dataset path.

---

## 11. Deletions

| Path | Reason |
|---|---|
| `app/company_ingest/collect/` (whole package) | corpus walking. Includes dead `register_docs.py` and `allowlist.py`, the pipeline's only Python-3.13-only call (`full_match`) |
| `app/company_ingest/datasets/` (whole package) | P3 out of scope; `parameter_checks` 0 rows |
| `app/company_ingest/constants.py` | `Profile` enum — registers are declared, not sniffed |
| `app/company_ingest/cli/ingest.py` | replaced by `service.py` |
| `app/company_ingest/store/schema.sql` | stale reference dump, executed by nothing, already missing two columns |
| `store/neon.py: insert_term_usages` (:449) + dataset/column/check inserters | superseded / dropped tables |
| `index/upsert.py: mark_previous_versions_stale` (:109) | replaced by delete-and-replace |
| `app/company/corpus/grounding/_leaktest.py` + `_leaktest_report.json` | **leaked credential**; one-time corpus QA, imported by nothing |
| `scripts/score_run.py`, `scripts/demo_prep.py` | → `backend/synthetic/` |
| `tests/company_ingest/{test_e2e_corpus,test_collector,test_reference,test_dataset_profile}.py` | corpus-dependent |
| `tests/company_ingest/{test_dataset_keys,test_parameters_regex,test_register_segmenter,test_terms}.py` corpus tests | already dead — point at a nonexistent `backend/corpus` |

**Kept deliberately:** `pypdf`, `parse/register_segmenter.py`, `llm/run_column_roles.py`, `company.table_columns`, `people`, `company_attributes`, the legacy `owner_id/reviewer_id/approver_id` columns.

---

## 12. Open risks

| Risk | Mitigation |
|---|---|
| DOCX heading styles vary by customer template; a doc with no heading styles segments as one clause | Test 12 enforces a fidelity floor; log a warning when a document yields < 3 clauses |
| Qdrant is not transactional with Postgres | Qdrant write last; roll back Postgres on failure; delete-by-`doc_id` makes retry idempotent |
| Embedding in a 512 MB dyno | `sentence_transformers` already lazily imported; regulatory ingest sets precedent; fall back to a worker service |
| Cutover regenerates findings; counts shift | §9 baseline + test 15 parity gate |
| `engine.finding_reviews` rows are lost with the wipe | Accepted — they are model-QA records on findings that no longer exist |
| Approval policy misconfiguration silently auto-approves | Document it; emit a warning when no policy matches |

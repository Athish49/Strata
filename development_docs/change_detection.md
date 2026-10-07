# Strata — Change Detection & Versioning

## Core Principle

None of our sources push changes to us. We must poll. Each source type has a different mechanism for discovering what changed.

---

## Codebook Sources (Buckets 1 & 3) — Poll-and-Diff

Codebooks don't provide change notifications or version numbers on individual sections. We detect changes by comparing content hashes.

### eCFR (Federal)

The eCFR API exposes three mechanisms:

**1. Title-level amendment check (lightweight, daily)**
```
GET /api/versioner/v1/titles
→ Returns latest_amended_on per title
```
- `latest_amended_on`: date of most recent substantive change to the title
- `latest_issue_date`: last date any change (substantive or editorial) was made
- `up_to_date_as_of`: title is current through this date

Our scheduler compares `latest_amended_on` for tracked titles (18, 40) against our stored value. If the date advanced → rescan that title.

**2. Section-level version history (identify which sections changed)**
```
GET /api/versioner/v1/versions/title-{n}?part={p}
→ Returns amendment dates per section, substantive vs editorial flag
```
Filter to sections amended since our last sync date. This avoids pulling full text for every section.

**3. Point-in-time content (pull changed text)**
```
GET /api/versioner/v1/full/{date}/title-{n}.xml
→ Returns full title XML as of given date
```
Extract the specific sections identified in step 2. Compute SHA-256 of each section's body text. Compare against stored `content_hash`.

**Change detection flow:**
```
daily_check():
  for each tracked_title:
    current_amended = eCFR.titles[title].latest_amended_on
    if current_amended > sync_state[title].last_amended:
      changed_sections = eCFR.versions(title, since=sync_state[title].last_sync_date)
      for section in changed_sections:
        new_text = eCFR.content(title, section, date=current_amended)
        new_hash = sha256(new_text)
        if new_hash != stored_hash(section.citation):
          create_new_code_section_snapshot(section, new_text, new_hash)
      sync_state[title].last_amended = current_amended
      sync_state[title].last_sync_date = today
```

### OAC (State — Ohio)

No API. Scraping required.

**Strategy:**
1. Weekly (configurable): scrape rule text for all tracked OAC rules under agency 4901.
2. Hash each rule's body text. Compare against stored hash.
3. If hash changed → create new `CodeSection` snapshot.
4. The "Effective" date on the OAC rule page tells us when the change took effect.

**Limitation:** We can't efficiently detect *which* rules changed without pulling them all. For a small scope (PUCO electric rules = ~100-200 rules), this is manageable. For larger scopes, we'd need the Register of Ohio (state equivalent of Federal Register) as a change signal.

---

## Journal Sources (Buckets 2 & 4) — Incremental Date-Based Pulls

Journal sources publish new records on a forward-only timeline. Each pull fetches "everything since my last pull."

### Federal Register API

**Strategy:** Date-based incremental pull.

```
daily_sync():
  last_date = sync_state['federal_register'].last_publication_date
  documents = FR_API.search(
    agencies=[tracked_slugs],
    publication_date_gte=last_date,
    types=['RULE', 'PRORULE'],   # NOTICE excluded — no regulation changes, ~60-70% of volume
    per_page=100,
    order='newest'
  )
  for doc in paginate(documents):
    if not exists(source_system='federal_register', source_id=doc.document_number):
      action = normalize_to_regulatory_action(doc)
      store(action)
  sync_state['federal_register'].last_publication_date = today
```

- Documents are immutable once published — no need to re-pull.
- Pagination: follow `next_page_url` until exhausted. Max 2000 results per query window — narrow date range for bulk backfill.
- New documents appear same-day, every business day.

### PUCO DIS

**Strategy:** Scrape active cases for new filings; discover new cases by date search.

```
periodic_sync():
  # 1. Discover new cases
  new_cases = DIS.search(industry='EL', date_from=sync_state['puco'].last_scan_date)
  for case in new_cases:
    if not exists(source_system='puco_dis', source_id=case.case_number):
      action = normalize_case_to_regulatory_action(case)
      store(action)

  # 2. Check active cases for new filings
  for case_id in get_active_cases(source_system='puco_dis'):
    current_filings = DIS.scrape_case_filings(case_id)
    known_filings = get_stored_filings(case_id)
    new_filings = current_filings - known_filings
    for filing in new_filings:
      if is_key_filing(filing):  # orders, decisions, stipulations
        store_filing(case_id, filing)
        update_case_status_if_needed(case_id, filing)

  sync_state['puco'].last_scan_date = today
```

- Active (OPEN) cases: check frequently (daily or every few days).
- Closed/archived cases: check infrequently (monthly) to catch late filings.
- Key filing filter: only store orders, decisions, stipulations, applications — skip routine motions.

---

## Sync State Tracking

Each source adapter maintains a persistent sync cursor:

| Source | Cursor Type | Stored Value |
|---|---|---|
| eCFR | Date-based | `last_amended_on` per title, `last_sync_date` |
| Federal Register | Date-based | `last_publication_date` |
| OAC | Date-based | `last_scrape_date` |
| PUCO DIS | Date-based | `last_scan_date`, plus per-case `last_filing_date` |

Cursors are persisted to durable storage. On restart, adapters resume from their cursor without re-pulling everything.

---

## Version Chain Model

### For CodeSection (Codebook Records)

Each time a section's text changes, we create a new snapshot linked to the prior one:

```
CodeSection v1 (snapshot 2025-01-01, hash: abc123)
    ↑ prior_version_id
CodeSection v2 (snapshot 2025-06-15, hash: def456, amendment_source: FR 2025-12345)
    ↑ prior_version_id
CodeSection v3 (snapshot 2026-03-01, hash: ghi789, amendment_source: FR 2026-06789)  ← current
```

- The "current" version is the one with no subsequent version pointing to it.
- `amendment_source` links each version change to the journal record that caused it.
- `effective_date` on each version tells us when the text took legal effect (may differ from `snapshot_date` due to eCFR lag).

### For RegulatoryAction (Journal Records)

Records are immutable — no version chain needed. Related actions form a lineage:

```
RegulatoryAction: FR 2025-00100 (proposed_rule, status: in_progress)
    │ related: {type: supersedes}
    ▼
RegulatoryAction: FR 2025-09876 (final_rule, status: approved)
    │ related: {type: corrects}
    ▼
RegulatoryAction: FR 2025-11111 (correction, status: approved)
```

Linked by `related_actions` with explicit relationship types. The chain is connected by shared `rin` or `docket_ids`.

---

## Special Versioning Scenarios

| Scenario | Detection | System Response |
|---|---|---|
| Section amended in place | Hash diff on codebook pull | New `CodeSection` snapshot, linked via `prior_version_id` |
| Section redesignated (renumbered) | Old citation disappears, new one appears; FR document has redesignation table | Mark old as `superseded_by = new_citation`, create new CodeSection |
| Section repealed | Citation absent from codebook, FR carries repeal notice | Set `repealed_date`, `status = blocked_suspended` |
| New section added | New citation appears in codebook | New `CodeSection` with no `prior_version_id` |
| Whole-part restructuring | Many citations change at once; FR document has mapping table | Bulk process: for each old→new mapping, set `superseded_by` and create new records |
| State recodification | Every rule gets new numbers | Ingest the official mapping from the state, rebuild all linkages |
| Court stay on a final rule | Separate court order or FR notice | New `RegulatoryAction` (type: `court_stay`), update affected `CodeSection` status to `blocked_suspended` |
| eCFR lags FR by 1-2 days | FR action exists but CodeSection hasn't changed yet | Normal — the `RegulatoryAction` arrives first, `CodeSection` update follows when eCFR catches up. Stitching occurs retroactively. |

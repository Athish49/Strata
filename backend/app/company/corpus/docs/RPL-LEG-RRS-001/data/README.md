# Data Directory — RPL-LEG-RRS-001 v7.2

## Contents

### `retention_schedule_2024-12-31.csv`

The master retention schedule for Rockridge Power & Light Company as of law snapshot 2024-12-31 (S1).

**Columns:**

| Column | Description |
|---|---|
| `rrs_id` | Unique record series identifier. Format: `RRS-{category}-{nnn}` |
| `record_series_name` | Short name for the record series |
| `description` | Longer description of records in the series |
| `retention_period` | Minimum retention period (e.g., "7 years", "Permanent", "3 years after closure") |
| `retention_basis` | Regulatory citation or "company_practice" |
| `regulatory_authority` | IURC / FERC / EPA / IDEM / IOSHA / IRS / company_practice |
| `media` | electronic / paper / both |
| `vital_record` | Y = vital record per Section 7; N = not vital |
| `disposition_method` | secure_shred / delete / archive / IURC_approval_required |
| `owner_dept` | Department responsible for maintaining the record series |
| `implementation_docs` | Comma-separated RPL document IDs that generate or govern records in this series |
| `wave2_clause_ref` | Frozen clause IDs from `/corpus/qa/clause_id_freeze.json` for Wave 2 procedure cross-references |
| `notes` | Additional guidance, company practice flags, and cross-references |

**Category Codes:**

| Code | Category |
|---|---|
| CS | Customer Service |
| MTR | Metering |
| DO | Distribution Operations |
| ENV | Environmental |
| SAF | Safety |
| FIN | Financial/Billing |
| LEG | Legal/Regulatory |
| HR | Human Resources |
| GEN | General Corporate |

**Statistics (law_as_of 2024-12-31):**
- Total record series: 86
- Series with IURC regulatory basis: 24
- Series with FERC regulatory basis: 5
- Series with EPA/IDEM regulatory basis: 13
- Series with IOSHA regulatory basis: 10
- Series designated vital records: 20
- Series with company practice retention: 39
- Series with Wave 2 clause references populated: 55

**Notes:**
- All regulatory citations are to law as in effect on 2024-12-31 per Snapshot S1.
- "company_practice" retention periods are RPL policy decisions exceeding applicable regulatory minimums.
- IOSHA enforces federal OSHA standards in Indiana; OSHA citations in this file refer to federal regulations as enforced by IOSHA.
- This file is the authoritative source for retention period determinations. See the policy document `RPL-LEG-RRS-001_v7.2.md` for governing principles.

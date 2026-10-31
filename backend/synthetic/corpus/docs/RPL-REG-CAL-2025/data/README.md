# RPL-REG-CAL-2025 Data Directory

## Contents

### calendar_events_2025.csv

This file contains all 48 regulatory compliance calendar events for Rockridge Power & Light Company for calendar year 2025.

**Column definitions:**

| Column | Description |
|---|---|
| `event_id` | Unique event identifier in format EVT-2025-nnnn |
| `citation` | Applicable 170 IAC or IC citation from T11 grounding pack (law as-of 2024-12-31) |
| `event_type` | One of: filing / reporting / internal_review / notice / inspection |
| `title` | Short descriptive event name |
| `description` | Full description of the compliance obligation and required action |
| `due_date` | ISO date (YYYY-MM-DD) or "ongoing" for rolling obligations |
| `due_date_notes` | Business-day adjustment explanation or rolling frequency note |
| `owner_id` | RPL person ID from people_directory.csv |
| `implementation_doc` | Wave 2 document ID cross-referencing implementation procedure |
| `implementation_clause` | Frozen clause ID from clause_id_freeze.json |
| `status` | scheduled / completed / n_a (as of document approval date 2025-03-14) |
| `notes` | Additional context, lagging flags, or coordination notes |

**Event counts:**

- Q1 events (Jan–Mar): 10 (EVT-2025-0001 through EVT-2025-0010)
- Q2 events (Apr–Jun): 10 (EVT-2025-0011 through EVT-2025-0020)
- Q3 events (Jul–Sep): 10 (EVT-2025-0021 through EVT-2025-0030)
- Q4 events (Oct–Dec): 10 (EVT-2025-0031 through EVT-2025-0040)
- Rolling/annual events: 8 (EVT-2025-0041 through EVT-2025-0048)
- **Total: 48 events**

**Events with frozen implementation_clause from clause_id_freeze.json:**

EVT-2025-0001, EVT-2025-0002, EVT-2025-0004, EVT-2025-0006, EVT-2025-0007, EVT-2025-0008, EVT-2025-0012, EVT-2025-0015, EVT-2025-0016, EVT-2025-0018, EVT-2025-0020, EVT-2025-0021, EVT-2025-0024, EVT-2025-0025, EVT-2025-0026, EVT-2025-0029 (indirect), EVT-2025-0030, EVT-2025-0031, EVT-2025-0032, EVT-2025-0034, EVT-2025-0035, EVT-2025-0036, EVT-2025-0038, EVT-2025-0041, EVT-2025-0042, EVT-2025-0043, EVT-2025-0046, EVT-2025-0047

**Lagging note:**

Events EVT-2025-0011, EVT-2025-0013, EVT-2025-0022, EVT-2025-0036, EVT-2025-0044, and EVT-2025-0045 cite 170 IAC 1-6-3, 1-6-4, or 1-6-5. These sections were amended effective 2025-01-24 (Snapshot S2). The calendar was prepared using law as-of 2024-12-31 (S1) and does not reflect those amendments. A v1.3 update is expected in Q2 2025.

## Source Documents

- Grounding pack: T11.json (law as-of 2024-12-31)
- Company profile: corpus/_global/company_profile.yaml
- People directory: corpus/_global/people_directory.csv
- Clause ID freeze: corpus/qa/clause_id_freeze.json (wave 2, frozen 2026-10-07)

## Contact

Owner: Marcus Lee (P09), Regulatory Affairs Analyst  
marcus.lee@rockridge-pl.example | Ext. 4009  
Rockridge Power & Light Company, 400 Wabash Commons Drive, Lafayette, IN 47901

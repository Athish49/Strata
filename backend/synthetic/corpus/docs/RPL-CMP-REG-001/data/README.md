# RPL-CMP-REG-001 Data Directory

This directory contains the master compliance register data for the IURC Regulatory Compliance Register (RPL-CMP-REG-001 v4.0), Rockridge Power & Light Company.

## Files

### `compliance_register_2024-12-31.csv`

The master compliance register as of 2024-12-31 (Snapshot S1, law as of 2024-12-31).

**Rows:** 70 obligations  
**Coverage:** 170 IAC 1-2, 1-5, 1-6, 1-7; 170 IAC 4-1, 4-9; 170 IAC 16-1; IC 8-1-2

**Column Definitions:**

| Column | Description |
|---|---|
| `obligation_id` | Unique identifier: OBL-2024-NNNN |
| `citation` | IAC or IC citation |
| `title` | Short title from rule heading |
| `description` | Plain-language obligation description |
| `frequency` | `continuous`, `annual`, `periodic`, or `event-triggered` |
| `accountable_owner_id` | People directory ID (P09 = Marcus Lee, P08 = Elena Vasquez) |
| `implementation_doc` | Wave 2 document ID that operationalizes the obligation |
| `implementation_clause` | Specific clause ID from Wave 2 clause freeze file (frozen 2026-10-07) |
| `compliance_control` | Primary control maintained |
| `monitoring_method` | How compliance is verified |
| `last_verified` | Date of last verification (YYYY-MM-DD) |
| `next_due` | Date of next verification or `event-triggered` |
| `status` | `compliant`, `in_progress`, or `at_risk` |
| `priority` | `P1` (highest), `P2` (moderate), `P3` (lower) |
| `notes` | Supplementary notes |

**Wave 2 Documents Referenced:**

| Document ID | Document |
|---|---|
| RPL-TAR-GRR-012 | General Rates and Rules Tariff |
| RPL-CS-PRO-004 | Customer Service and Billing Procedure |
| RPL-CS-PRO-007 | Customer Information and Notification Procedure |
| RPL-CS-PRO-011 | Customer Dispute Handling Procedure |
| RPL-DO-PLN-002 | Distribution Operations Plan |
| RPL-MTR-PGM-001 | Meter Management Program |
| RPL-DCC-PRO-003 | Distribution Control Center Procedure |
| RPL-ENV-PRO-005 | Environmental and Vegetation Management Procedure |
| RPL-SAF-PRO-009 | Safety and Accident Prevention Procedure |

## Version History

| Date | Version | Note |
|---|---|---|
| 2024-12-31 | v4.0 snapshot | Law as-of date for this register version |
| 2025-01-23 | v4.0 approved | O-3 dates applied |

## Contacts

- **Owner:** Marcus Lee (P09), Manager Regulatory Compliance, mlee@rockridge-pl.example
- **Reviewer:** Elena Vasquez (P08), Director Regulatory Affairs
- **IURC:** 317-232-2712 | iurc.portal.in.gov

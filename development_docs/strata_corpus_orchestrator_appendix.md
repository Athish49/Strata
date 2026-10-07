# Strata v1 corpus — Orchestrator Appendix (Appendix O)

**Never give this file to worker agents.** It accompanies `strata_synthetic_corpus_spec.md` v2.0.


O-1. **Snapshot dates.** IAC Snapshot 1 = 2024-12-31; IAC Snapshot 2 = 2025-12-31 (2026 edition); eCFR Snapshot 1 = 2025-01-02; eCFR Snapshot 2 = 2026-10-02. No v1 document is assessed against federal text.
O-2. **Decoy and change information** lives only in `corpus/grounding/_orchestrator_report.json`.
O-3. **Approval-date adjustment.** If the orchestrator report shows a Snapshot-2 change to any section in a document's pack scope (including a new S2 section in scope) with an S2 effective date on or before that document's §1.4 approval date, move the document's approval and effective dates to the latest working day before the S2 effective date, no earlier than 2025-01-03, and update §1.4 before Wave 2. If that is impossible (the S2 effective date is on or before 2025-01-03), keep the dates and record the document as `lagging_at_approval` for T91, which classifies the resulting finding as `stale_at_approval`.
O-4. **Information barriers** per §0.1.
O-6. **Reference extracts.** Before Wave 1 (IEEE 1366 summary, needed by T04) and before Wave 2 (sampling extract), prepare `corpus/_global/reference/` with human-verified, non-regulatory extracts: the sampling-plan table extract for T18 (only for the standard and edition the T18 pack names) and an IEEE 1366 2.5-beta MED method summary for T04/T19. Generators cite these and never reconstruct paywalled standards from memory.
O-7. **Public contacts.** Verify every §1.6 Table C and Table X public contact against an archived early-2025 copy of the official page; record the URL and archive date in `corpus/_global/contacts_sources.md`. Fill the IURC office hours and 2025 State of Indiana holidays into Table X before Wave 2.
O-8. **Absent topics.** T00's orchestrator report lists `absent_topics` (e.g., a winter disconnection protection with no governing section in any pack). Confirm that §2.7 handling is acceptable for those documents.
O-9. **Audit reports.** The three v2.0 audit reports (`group_A_customer_tariff.md`, `group_B_operations.md`, `group_C_compliance_global.md`) contain real-world anatomy notes, gap rationales and full source lists. Copy them to `corpus/qa/audit_reports/` and, before Wave 2, build `corpus/qa/exemplar_anatomy/<class>.yaml` (one per document class) from their "(a) Real-world anatomy" sections.

O-10. **Demo purpose per document** (moved here from worker-visible task text so it cannot bias generation):
- **T13:** The tariff is the company's legally binding customer contract. Findings here are high-stakes and route to Legal. Any change triggers a tariff filing with the IURC (a real-world second step the platform should show).
- **T14:** The single richest document for fine-print findings: notice periods, required notice content, protected periods, eligibility evidence, prohibited disconnection conditions and reconnection timing all live here and in its templates.
- **T18:** The quantified-impact showcase: when a Snapshot-2 change alters a test interval, accuracy limit, sampling rule or record requirement, Strata must compute how many meters, tests or records are affected from these datasets.
- **T19:** Reportability thresholds, timing and content requirements are prime change targets. Strata re-scores the 2024 outage log against the new rule and reports how many past events would now be reportable or reported late.
- **T20:** Reportability tiers, notification timing, report content (including content defined as a term), third-party notification duties, exclusions and the emergency-response precedence rule are all clause-level change targets. The spill log lets Strata quantify the effect of a changed threshold or timing rule on 2024 events.
- **T21:** The IURC accident rule is short. Any change to which accidents are reportable, the timing, the channel, or the content changes this document's decision table, notification log and written-report template. The incident log lets Strata quantify how many 2024 events a broadened rule would capture.
O-11. **Contamination-check agent.** T90 check 14 is run by a separate isolated agent with Snapshot-2 access (not a T91 annotator). It returns only pass/fail and clause IDs to T90.

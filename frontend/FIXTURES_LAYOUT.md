# Fixture layout (contract between agents; delete or fold into README when M0 closes)

fixtures/company/documents.json      DocumentMeta[]  (12 monitored + 2-3 unmonitored samples per empty vertical)
fixtures/company/people.json         Person[]        (P01–P27)
fixtures/company/profile.json        CompanyProfile
fixtures/company/clauses/<doc_id>.json  Clause[]     (monitored docs only, ordinal order)

fixtures/kb/agencies.json            Agency[]
fixtures/kb/sections.json            CodeSection[]
fixtures/kb/actions.json             RegulatoryAction[]
fixtures/kb/versions.json            { "<source_system>|<citation>": VersionEntry[] }

fixtures/engine/runs.json            Run[]  (kb-real, baseline, preset runs; ids stable)
fixtures/engine/scenarios.json       Scenario[]
fixtures/engine/score.json           ScoreReport
fixtures/engine/<run_id>/changes.json     ChangeRecord[]
fixtures/engine/<run_id>/candidates.json  Candidate[]
fixtures/engine/<run_id>/findings.json    Finding[]
fixtures/engine/<run_id>/rollups.json     DocRollup[]
fixtures/engine/<run_id>/radar.json       RadarItem[]

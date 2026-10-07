# KB citations for the engine-fixtures agent

All strings below exist in `sections.json` (`source_system` "iac" unless noted). Agency ids are lowercase (`ferc`, `epa`, `iurc`, `idem`); 610/675 have `agency_id: null`, slugs `iac-610`/`iac-675`. S1 = 2024-12-31, S2 = 2025-12-31 (CFR: 2025-01-02 / 2026-10-02). Version pairs in `versions.json` are keyed `iac|<citation>` / `cfr|<citation>`.

## Real wave: in-footprint changed sections (8; all have S1/S2 text)
- 170 IAC 4-1-13 (cosmetic) - deposit rule; only a readoption stamp line added. Use as the cosmetic change cited by 94 clauses (cited by REG-CAL, TAR, PRO-004, PRO-011, REG-001).
- 170 IAC 4-1-16 (substantive-looking style rewording) - disconnection rule; "shall not" -> "may not" in (c) and (d). Cleared as "same legal effect". PRO-004 (also PRO-011, TAR-012, REG-001).
- 170 IAC 1-6-3 (punctuation_only) - administrative filing timing; commas added. REG-CAL (EVT-2025-0011/0013/0022).
- 170 IAC 1-6-4 (cosmetic) - administrative filing contents; readoption stamp. REG-CAL.
- 170 IAC 1-6-5 (cross_ref_only) - administrative filing notice; "170 IAC 1-6-2" -> "170 IAC 1-6-2(11)". REG-CAL.
- 170 IAC 16-1-4 (punctuation_only) - informal complaint review; serial commas. PRO-011, PRO-004.
- 170 IAC 16-1-5 (cosmetic) - complaint rights during review; stamp. PRO-011, PRO-004.
- 170 IAC 16-1-7 (metadata_only/cross_ref) - complaint disconnection hold; "IC 8-1-1-3" -> "IC 8-1-1-3(a)". PRO-011, PRO-004.

Note: the document text and fixture say the residential notice period is 14 days (170 IAC 4-1-16(e)), so Preset A ("notice period X -> Y days") should read 14 -> a new value (spec wording of 10 -> 15 conflicts with RPL docs; the fixture S1 text says fourteen (14)).

## Presets
- Preset A: 170 IAC 4-1-16 - multi-paragraph body (subsections (a)-(g)); (e) is the 14-day notice period, (c) the 10-day medical postponement. Related: 170 IAC 4-1-15 (notice content), 4-1-16.6, 16-1-7.
- Preset B (repeal): 170 IAC 4-1-16.6 - home energy assistance / winter protection; S1 = S2 text in versions.json (no real-wave change). Cross refs 4-1-16.

## Non-footprint substantive changes (Radar)
- 326 IAC 2-8-4 (idem) - FESOP limits on emergency-engine hours, 50 -> 100 h/yr; applicable via standby_generator_count = 3. Amended by IDEM-LSA-24-301.
- 40 CFR 60.4320 (cfr, epa) - turbine NOx limit 25 -> 15 ppm; screened out via owns_generating_units = false. Amended by FR 2025-06114.
- 18 CFR 35.28 (cfr, ferc) - OATT / market rules posting, monitor report 30 -> 20 days; amended by FR 2026-06091.

## Other RPL-cited sections present (unchanged)
170 IAC 1-2-1,1-2-2,1-2-3,1-2-7,1-2-9..1-2-12; 1-5-2,1-5-2.1,1-5-4,1-5-6,1-5-9..1-5-13,1-5-16; 1-6-1,1-6-2; 1-7-1,1-7-3; 4-1-1..4-1-12, 4-1-14, 4-1-15, 4-1-17..4-1-30; 4-2-2; 4-9-1..4-9-13 (4-9-7 telephone discontinuance); 16-1-1,16-1-2,16-1-3,16-1-6; 327 IAC 2-6.1-1/2/3/5/7 (spill rule; PRO-005 out_of_scope_reference).
Most-cited: 170 IAC 4-1-3, 4-1-24, 4-1-14, 4-9-7, 4-1-7, 4-1-10, 4-1-13, 1-6-3.

## Actions worth linking
FERC FR 2026-06091 (supersedes 2025-02101), 2026-07304 corrects 2026-06091; EPA FR 2025-06114 supersedes 2025-03317, 2025-07712 corrects it; IURC GAO-2025-04 supersedes GAO-2024-07, GAO-2025-05 corrects GAO-2025-04; IURC-RM-24-11 (disconnection readoption), IURC-RM-25-02 (proposed notice-content rule, comment-letter cue); IDEM-LSA-24-301 supersedes 24-218.

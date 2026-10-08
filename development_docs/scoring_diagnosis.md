# Scoring diagnosis (T2) - status: OPEN QUESTION for the owner

Runs `05b50712` and `0dcc125e-6da6-419f-beb1-8c347e4fb2d4` (default demo run) score identically: expected non-info 6, system non-info 4,
matched 0, recall 0, precision 0, FP-on-negatives PASS, routing PASS (0 matches), baseline PASS, 12/12 document statuses correct.

Judge strictness is ruled out as the cause. The T1a change passes `clause_role` to the judge (role guidance plus a `Clause role:` line only for
`regulatory_restatement` and `definition` clauses; other roles' prompts are byte-identical). 304 of 411 LLM-judged candidates got new prompts and were
re-answered offline (see engine_spec.md "Offline-filled judgments"); they reproduced the same 4 affected clauses.

Scorer contract (from scoring.py code only): a system finding matches an expected one when
(a) same doc_id, (b) citations equal after stripping ONE trailing "(...)" from each side, and
(c) clause_id is in the expected `acceptable_clause_ids` (or a "."-parent of one when parent_tolerance).
Our export (app/engine/export.py) emits doc-prefixed clause ids (`RPL-REG-CAL-2025:3.7`), finding_type, severity, route_to, and section-level citations;
for `direct_rule` findings the clause citation is replaced by the changed section's citation.

**Open question (needs a human with access to the answer key; do not open it from an agent):**
(a) Are the key's `acceptable_clause_ids` doc-prefixed or bare?
(b) Which citation form does it expect for rule-level calendar events (EVT-2025-0044 / EVT-2025-0045)? We export 1-6 and 1-6-5 for the live run; the calendar README
    mentions 1-6-3 / 1-6-4 / 1-6-5, so a granularity mismatch is possible.
If either differs, the fix is a small change in `backend/app/engine/export.py`. Not yet made.

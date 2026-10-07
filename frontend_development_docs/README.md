# Strata — Frontend development docs

Everything the agent building the Strata frontend needs to read. Nothing in this folder is code. The app itself lives in `/frontend`, which does not exist until the build starts.

## Contents

| File | What it is | Authority |
|---|---|---|
| `frontend_spec.md` | The build spec: stack, boundaries, data contract and mocks, page-by-page requirements, components, labels, build order, **visual design system (§17)** and **future-capability cues (§18)** | **Primary.** Wins on any conflict. |
| `frontend_brief.md` | The backend agent's brief on how the analysis engine's results should be shown | Canonical for engine UX where the spec is silent. Where it asks for live endpoints or polling of the backend, spec §0.1 overrides it: everything is mocked in this phase. |
| `reference/kb_audit_government.html` | Audit of the regulatory knowledge base (tables, counts, snapshots, agencies) | Reference for realistic fixture values |
| `reference/company_data_audit.html` | Audit of RPL's company data (documents, clauses, citations, parameters, people) | Reference for realistic fixture values |
| `reference/design/` | Four Harvey screenshots plus a README saying what to take from each and which Strata page it maps to | **The target look and feel.** Spec §17 gives the exact values. |

## Reading order
1. `frontend_spec.md` §0–§3: boundaries, product and decisions.
2. `frontend_brief.md`, all of it.
3. `frontend_spec.md` §4 onward. Read §17 (design), `reference/design/` (screenshots) and §18 (cues) before building any UI.
4. The `reference/` audits, when building fixtures.

## Hard rules (summary of spec §0)
- All code goes in `frontend/`, a standalone Next.js project and the deploy root. Never touch anything outside it.
- No backend integration in this phase. Every data domain is mocked from committed fixtures in `frontend/fixtures/`.
- The fixture script may read `../backend/app/company/corpus` read-only. The app may never import from outside `frontend/`.
- Information barrier: never read `corpus/eval`, `corpus/grounding`, `corpus/qa`, `corpus/validation`, `*.basis.json` or `tools/offline_eval`.
- The look is Harvey-inspired (spec §17): monochrome warm neutrals, a dark sidebar, serif titles, hairline cards and tables, and color only for status (red, green, one muted amber). It is inspired by Harvey, never copied: no Harvey name, logo, fonts or copy.
- Future capabilities appear only as disabled cues from the spec §18 catalog: at most 3 per page, never functional.

## Kickoff prompt for the build agent

> You are building the Strata frontend. Read `frontend_development_docs/README.md`, then `frontend_spec.md` and `frontend_brief.md` in full before writing any code. Follow the spec's §0.1 boundaries strictly: all work goes inside `frontend/`, nothing outside it changes, and there is no backend integration (everything is mocked from committed fixtures). Before any UI work, open every screenshot in `frontend_development_docs/reference/design/` and match their look and feel. Build milestone by milestone in the order of spec §13. At the end of each milestone, run lint, typecheck and tests, check that `git status` shows changes only under `frontend/`, commit, and report what was done against that milestone's acceptance criteria. Start with M0.

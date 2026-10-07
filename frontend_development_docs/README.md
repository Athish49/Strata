# Strata — Frontend development docs

Everything the agent building the Strata frontend needs to read. Nothing in this folder is code. The app itself lives in `/frontend`, which does not exist until the build starts.

## Contents

| File | What it is | Authority |
|---|---|---|
| `frontend_spec.md` | The build spec: stack, boundaries, data contract and mocks, page-by-page requirements, components, labels, build order | **Primary.** Wins on any conflict. |
| `frontend_brief.md` | The backend agent's brief on how the analysis engine's results should be shown | Canonical for engine UX where the spec is silent. Where it asks for live endpoints or polling of the backend, spec §0.1 overrides it: everything is mocked in this phase. |
| `reference/kb_audit_government.html` | Audit of the regulatory knowledge base (tables, counts, snapshots, agencies) | Reference for realistic fixture values |
| `reference/company_data_audit.html` | Audit of RPL's company data (documents, clauses, citations, parameters, people) | Reference for realistic fixture values |

## Reading order
1. `frontend_spec.md` §0–§3: boundaries, product and decisions.
2. `frontend_brief.md`, all of it.
3. `frontend_spec.md` §4 onward.
4. The `reference/` audits, when building fixtures.

## Hard rules (summary of spec §0)
- All code goes in `frontend/`, a standalone Next.js project and the deploy root. Never touch anything outside it.
- No backend integration in this phase. Every data domain is mocked from committed fixtures in `frontend/fixtures/`.
- The fixture script may read `../backend/app/company/corpus` read-only. The app may never import from outside `frontend/`.
- Information barrier: never read `corpus/eval`, `corpus/grounding`, `corpus/qa`, `corpus/validation`, `*.basis.json` or `tools/offline_eval`.
- Visual design specifics (colors, shapes, gradients) are deferred. Use shadcn defaults and the named tokens in spec §11.3.

## Kickoff prompt for the build agent

> You are building the Strata frontend. Read `frontend_development_docs/README.md`, then `frontend_spec.md` and `frontend_brief.md` in full before writing any code. Follow the spec's §0.1 boundaries strictly: all work goes inside `frontend/`, nothing outside it changes, and there is no backend integration (everything is mocked from committed fixtures). Build milestone by milestone in the order of spec §13. At the end of each milestone, run lint, typecheck and tests, check that `git status` shows changes only under `frontend/`, commit, and report what was done against that milestone's acceptance criteria. Start with M0.

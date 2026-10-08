# Strata — Limitations & Future Work

**Purpose:** for each core workflow, how it works today, where its design is limited, and how it can be extended. Results are in [Evaluation & results](EVALUATION_AND_RESULTS.md).

## TL;DR
- The design favours **precision and traceability** over recall: it only flags what it can prove from citations and quotes.
- Most limits follow from that choice, plus a **single synthetic company** as the test bed.
- Future work therefore targets **recall** (finding impacts that aren't explicitly cited) and **stronger evidence** (broader evaluation).

## 1. Detecting what changed in the law

| Today | Limitation | Why it matters | Future work |
|---|---|---|---|
| Two fixed snapshots (S1, S2) are compared; unchanged sections are not re-stored | Change is detected in batches, not continuously | A change is visible only after the next snapshot | Continuous change feed from official publication streams |
| Federal text exposes a change date that lets whole titles be skipped; Indiana does not | State sources must be re-read and hashed in full | Cost grows with the size of the code | Use Indiana Register publications as the change signal |
| Dates come from publication identifiers, not legal effective dates | No effective-date reasoning | Cannot say *when* a company must comply | Extract effective dates from rulemaking texts; add a compliance countdown |

## 2. Linking rulemakings to the code they amend

| Today | Limitation | Why it matters | Future work |
|---|---|---|---|
| Exact-signal matching: citations, document IDs embedded in Indiana text, shared docket or RIN | Links exist only where an explicit signal exists | Federal and state actions on the same topic stay unconnected | Semantic linking across jurisdictions, with human confirmation |
| Linking of state rulemakings is a bulk step, separate from the daily ingest | New state rulemakings are linked on the next bulk run | Provenance can lag behind ingestion | Run linking as part of every ingest |

## 3. Matching a change to company clauses

| Today | Limitation | Why it matters | Future work |
|---|---|---|---|
| Candidates come from explicit citations (direct section, rule-level, one hop through register rows) | A clause that is affected but does not cite the changed rule is not found | Recall is bounded by how well documents cite the law | Add semantic retrieval as a *recall net*, with the judge and verification as the precision gate |
| Federal citations in company text are not resolved to individual sections | Federal changes can only be screened by the radar, not matched to clauses | Federal impacts are surfaced less precisely | Resolve federal citations to sections |
| Defined terms are not linked to the law | A changed definition cannot propagate to clauses that use the term | Definition changes can have wide impact | Link terms to legal definitions; add a propagation path |
| Judgement is at clause level; the judge sees the clause and the change, not the whole document | Cross-clause obligations may be missed | Some duties span several clauses | Document-level reasoning pass over flagged documents |

## 4. Judging impact with the LLM

| Today | Limitation | Why it matters | Future work |
|---|---|---|---|
| One bounded call per candidate, temperature 0, answers cached for reproducibility | A single judgement per candidate, no agreement measure | Confidence is the model's self-report | Repeat-and-agree sampling; calibrate confidence against labelled outcomes |
| Demo judgments were produced offline during an API budget limit and then cached | Live-model behaviour on identical inputs is not re-measured | Cached results may not match a fresh run | Re-run with a live model and report agreement with the cache |
| Prompt edits change the cache key | Any prompt improvement forces re-judging | Slows iteration | Version prompts and cache per version |

## 5. Evaluating the system

| Today | Limitation | Why it matters | Future work |
|---|---|---|---|
| Hidden answer key, aggregate-only scoring, so the system cannot be tuned to it | Clause-level scores are currently 0, suspected format mismatch between export and key | Headline precision and recall are not yet demonstrated | Align export format with the key's owner; report the corrected scores |
| The S1 baseline builds no inputs | It shows the pipeline completes, not that noise is filtered | The "no false alarms on unchanged law" control is weak | Build a true S1-vs-S1 control and inject synthetic perturbations of known type |
| One synthetic company, 12 documents, a small answer key | Generalization is unproven; few expected findings | Statistical power is low | Add companies and document types; adjudicate with multiple domain reviewers |
| Real-wave yield is low (7 findings) because few changes touch cited sections | The result alone under-demonstrates the engine | Evaluators see little to judge | Use what-if scenarios and larger corpora to stress the engine |

## 6. Closing the loop with people

| Today | Limitation | Why it matters | Future work |
|---|---|---|---|
| Reviewers can accept or reject findings; decisions are stored but not used | The system does not learn from reviews | Errors repeat | Feed decisions into calibration and evaluation sets |
| The radar screens out-of-scope changes against company attributes only | Applicability reasoning is shallow, and it is not part of UI-triggered runs | Relevant outside-footprint changes may be missed | Richer applicability model; run it with every wave |
| Impact is stated qualitatively | Operational data is not used | Cannot size the effect of a change | Check changed thresholds against company operational datasets and quantify exposure |

import { z } from "zod";
import {
  changeClassSchema,
  directionSchema,
  isoDate,
  matchPathSchema,
  noiseClassSchema,
  personSchema,
  severitySchema,
  verdictSchema,
  sourceSystemSchema,
  placeholderFlag,
} from "./common";

export const stageSchema = z.enum(["delta", "characterize", "candidates", "judge", "ledger"]);
export type Stage = z.infer<typeof stageSchema>;

export const runStatsSchema = z.object({
  changes_raw: z.number(),
  by_class: z.record(z.string(), z.number()),
  substantive: z.number(),
  noise: z.number(),
  in_footprint: z.number(),
  obligation_changed: z.number(),
  candidates_by_path: z.record(z.string(), z.number()),
  findings_by_verdict: z.record(z.string(), z.number()),
  clauses_cleared: z.number(),
  docs_flagged: z.number(),
  docs_cleared: z.number(),
  radar: z.object({ applicable: z.number(), screened_out: z.number(), unclear: z.number() }),
  decided_by: z.object({ rule: z.number(), ai: z.number() }),
  llm_calls: z.number(),
});
export type RunStats = z.infer<typeof runStatsSchema>;

export const runSchema = z.object({
  run_id: z.string(),
  kind: z.enum(["kb", "baseline", "whatif"]),
  title: z.string(),
  status: z.enum(["queued", "running", "succeeded", "failed"]),
  started_at: isoDate,
  finished_at: isoDate.nullable(),
  scenario_id: z.string().nullable().optional(),
  progress: z
    .object({ stage: stageSchema, done: z.number(), total: z.number(), message: z.string() })
    .nullable()
    .optional(),
  stats: runStatsSchema,
});
export type Run = z.infer<typeof runSchema>;

export const diffSegmentSchema = z.object({
  op: z.enum(["equal", "delete", "insert"]),
  text: z.string(),
});
export type DiffSegment = z.infer<typeof diffSegmentSchema>;

export const characterizationSchema = z.object({
  obligation_changed: z.boolean(),
  direction: directionSchema,
  summary: z.string(),
  value_changes: z.array(
    z.object({
      label: z.string(),
      old: z.string(),
      new: z.string(),
      unit: z.string().nullable().optional(),
    }),
  ),
});

export const changeRecordSchema = z.object({
  change_id: z.string(),
  citation: z.string(),
  heading: z.string(),
  source_system: sourceSystemSchema,
  rule_key: z.string(),
  agency_id: z.string(),
  title_number: z.string(),
  change_class: changeClassSchema,
  diff_segments: z.array(diffSegmentSchema),
  s1_text: z.string(),
  s2_text: z.string(),
  published_date: isoDate,
  date_basis: z.string(),
  din: z.string().nullable().optional(),
  s1_snapshot: isoDate,
  s2_snapshot: isoDate,
  in_footprint: z.boolean(),
  cited_clause_count: z.number(),
  characterization: characterizationSchema.nullable().optional(),
  disposition: z.string(),
  disposition_reason: z.string(),
  placeholder: placeholderFlag,
});
export type ChangeRecord = z.infer<typeof changeRecordSchema>;

export const pathNodeSchema = z.object({
  kind: z.enum(["section", "rule", "register_row", "form_field", "tariff_rule", "clause"]),
  ref: z.string(),
  label: z.string(),
});
export type PathNode = z.infer<typeof pathNodeSchema>;

export const candidateSchema = z.object({
  candidate_id: z.string(),
  run_id: z.string(),
  change_id: z.string(),
  clause_id: z.string(),
  doc_id: z.string(),
  match_path: matchPathSchema,
  path_detail: z.array(pathNodeSchema),
  outcome: z.enum(["affected", "cleared"]),
  skip_reason: z.string().nullable().optional(),
  rationale: z.string().nullable().optional(),
  finding_id: z.string().nullable().optional(),
});
export type Candidate = z.infer<typeof candidateSchema>;

const quoteSchema = z.object({
  text: z.string(),
  span: z.tuple([z.number(), z.number()]).nullable().optional(),
});

export const findingSchema = z.object({
  finding_id: z.string(),
  run_id: z.string(),
  change_id: z.string(),
  clause_id: z.string(),
  doc_id: z.string(),
  citation: z.string(),
  finding_type: z.string(),
  verdict: verdictSchema,
  severity: severitySchema,
  confidence: z.number().min(0).max(1),
  decided_by: z.enum(["rule", "ai"]),
  required_change: z.object({ from_text: z.string(), to_text: z.string() }),
  quotes: z.object({ s1: quoteSchema, s2: quoteSchema, clause: quoteSchema }),
  quotes_verified: z.boolean(),
  rationale: z.string(),
  match_path: matchPathSchema,
  path_detail: z.array(pathNodeSchema),
  propagated_from: z.string().nullable().optional(),
  stale_at_approval: z.boolean(),
  doc_approved_date: isoDate.nullable(),
  rule_published_date: isoDate,
  route: z.object({
    owner: personSchema,
    reviewer: personSchema,
    approver: personSchema.nullable(),
  }),
  reviews: z.array(
    z.object({ decision: z.enum(["accept", "reject"]), note: z.string().nullable().optional(), at: isoDate }),
  ),
});
export type Finding = z.infer<typeof findingSchema>;

export const docRollupSchema = z.object({
  run_id: z.string(),
  doc_id: z.string(),
  status: z.enum(["flagged", "cleared"]),
  counts_by_verdict: z.record(z.string(), z.number()),
  changes_considered: z.number(),
  /** Per noise/real class counts of changes considered, used for the cleared line. */
  considered_by_class: z.record(z.string(), z.number()).default({}),
  cleared_reason: z.string().nullable().optional(),
});
export type DocRollup = z.infer<typeof docRollupSchema>;

export const radarItemSchema = z.object({
  radar_id: z.string(),
  run_id: z.string(),
  change_id: z.string(),
  citation: z.string(),
  heading: z.string(),
  agency_id: z.string(),
  applicable: z.enum(["yes", "no", "unclear"]),
  attribute_basis: z.array(z.object({ key: z.string(), value: z.union([z.string(), z.number(), z.boolean()]) })),
  affected_activity: z.string(),
  reason: z.string(),
  quote: z.string(),
  docs_covering_same_rule: z.array(z.string()),
});
export type RadarItem = z.infer<typeof radarItemSchema>;

export const scenarioSchema = z.object({
  scenario_id: z.string(),
  title: z.string(),
  citation: z.string(),
  source_system: sourceSystemSchema,
  edit_kind: z.enum(["text_edit", "repeal"]),
  edited_text: z.string().nullable().optional(),
  is_preset: z.boolean(),
  last_run_id: z.string().nullable().optional(),
});
export type Scenario = z.infer<typeof scenarioSchema>;

export const scoreReportSchema = z.object({
  precision: z.number(),
  recall: z.number(),
  fp_rate_must_not_flag: z.number(),
  routing_accuracy: z.number(),
  targets: z.object({ precision: z.number(), recall: z.number(), fp_rate: z.number(), routing: z.number() }),
  baseline_findings: z.number(),
  decided_by: z.object({ rule: z.number(), ai: z.number() }),
  llm_calls: z.number(),
});
export type ScoreReport = z.infer<typeof scoreReportSchema>;

export const annotationSchema = z.object({
  clause_id: z.string(),
  kind: z.enum(["finding", "cleared"]),
  verdict: verdictSchema.nullable().optional(),
  finding_id: z.string().nullable().optional(),
  change_id: z.string(),
  citation: z.string(),
  quote_span: z.tuple([z.number(), z.number()]).nullable().optional(),
  reason: z.string(),
});
export type Annotation = z.infer<typeof annotationSchema>;

export const matrixCellSchema = z.object({
  doc_id: z.string(),
  change_id: z.string(),
  worst_verdict: z.union([verdictSchema, z.literal("cleared")]),
  n_findings: z.number(),
  n_cleared: z.number(),
});
export type MatrixCell = z.infer<typeof matrixCellSchema>;

export { noiseClassSchema };

import { z } from "zod";

export const isoDate = z.string(); // ISO 8601 date or datetime, formatted at the UI edge

export const verdictSchema = z.enum([
  "action_required",
  "optional_relaxed",
  "update_citation",
  "review",
  "info",
]);
export type Verdict = z.infer<typeof verdictSchema>;

export const realClassSchema = z.enum(["substantive", "repealed", "renumbered", "new_section"]);
export const noiseClassSchema = z.enum([
  "cosmetic",
  "metadata_only",
  "punctuation_only",
  "cross_ref_only",
]);
export const changeClassSchema = z.union([realClassSchema, noiseClassSchema]);
export type ChangeClass = z.infer<typeof changeClassSchema>;
export type NoiseClass = z.infer<typeof noiseClassSchema>;

export const directionSchema = z.enum([
  "tightened",
  "relaxed",
  "new_requirement",
  "removed",
  "clarified",
  "style_only",
  "mixed",
]);
export type Direction = z.infer<typeof directionSchema>;

export const matchPathSchema = z.enum([
  "direct_section",
  "direct_rule",
  "register_hop",
  "value_echo",
]);
export type MatchPath = z.infer<typeof matchPathSchema>;

export const severitySchema = z.enum(["high", "medium", "low"]);
export type Severity = z.infer<typeof severitySchema>;

export const sourceSystemSchema = z.enum(["iac", "cfr"]);
export type SourceSystem = z.infer<typeof sourceSystemSchema>;

export const unitKindSchema = z.enum([
  "section",
  "table_row",
  "register_row",
  "form_field",
  "tariff_subrule",
  "appendix",
]);
export type UnitKind = z.infer<typeof unitKindSchema>;

export const personSchema = z.object({
  person_id: z.string(),
  name: z.string(),
  title: z.string(),
  department: z.string(),
  reports_to_id: z.string().nullable(),
});
export type Person = z.infer<typeof personSchema>;

export const placeholderFlag = z.boolean().optional(); // never rendered; marks invented values

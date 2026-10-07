import { z } from "zod";
import { isoDate, personSchema, unitKindSchema } from "./common";

export const documentMetaSchema = z.object({
  doc_id: z.string(),
  title: z.string(),
  version: z.string(),
  status: z.string(),
  effective_date: isoDate.nullable(),
  approved_date: isoDate.nullable(),
  law_as_of: isoDate.nullable(),
  next_review: isoDate.nullable(),
  review_cycle: z.string().nullable(),
  /** One of the 14 vertical slugs (lib/verticals.ts). */
  vertical: z.string(),
  owner: personSchema,
  reviewer: personSchema,
  approver: personSchema.nullable(),
  two_signature: z.boolean(),
  monitored: z.boolean(),
  /** Free-text document type shown in vertical tables, e.g. "Procedure", "Register". */
  doc_type: z.string(),
  /** Citations this document cites (from regulatory_basis + in-text). Empty for samples. */
  cited_citations: z.array(z.string()).default([]),
});
export type DocumentMeta = z.infer<typeof documentMetaSchema>;

export const clauseSchema = z.object({
  clause_id: z.string(),
  doc_id: z.string(),
  ordinal: z.number().int(),
  heading_path: z.array(z.string()),
  unit_kind: unitKindSchema,
  text_raw: z.string(),
  row_cells: z.record(z.string(), z.string()).nullable().optional(),
  parent_clause_id: z.string().nullable().optional(),
});
export type Clause = z.infer<typeof clauseSchema>;

export const companyAttributeSchema = z.object({
  key: z.string(),
  value: z.union([z.string(), z.number(), z.boolean()]),
  source: z.string(),
});
export type CompanyAttribute = z.infer<typeof companyAttributeSchema>;

export const companyProfileSchema = z.object({
  name: z.string(),
  type: z.string(),
  state: z.string(),
  customers: z.number(),
  regulator: z.string(),
  attributes: z.array(companyAttributeSchema),
});
export type CompanyProfile = z.infer<typeof companyProfileSchema>;

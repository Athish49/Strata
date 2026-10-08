import { z } from "zod";
import { isoDate, placeholderFlag, sourceSystemSchema } from "./common";

export const agencySchema = z.object({
  /** null for the 610/675 codebook-only entries. */
  agency_id: z.string().nullable(),
  /** Stable slug used in URLs, e.g. "iurc", "ferc", "iac-610". */
  slug: z.string(),
  name: z.string(),
  level: z.enum(["federal", "state"]),
  geo: z.string(),
  domains: z.array(z.string()),
  codebook_titles: z.array(z.string()),
  section_count: z.number(),
  action_count: z.number(),
  s1_snapshot: isoDate,
  s2_snapshot: isoDate,
  last_sync_at: isoDate,
  has_activity_feed: z.boolean(),
  /** Action streams available, e.g. ["iurc_gaos","iurc_investigations","iurc_rulemakings"]. */
  streams: z.array(z.string()).default([]),
});
export type Agency = z.infer<typeof agencySchema>;

export const codeSectionSchema = z.object({
  citation: z.string(),
  source_system: sourceSystemSchema,
  title_number: z.string(),
  part_or_article: z.string(),
  rule_key: z.string(),
  section_number: z.string(),
  heading: z.string(),
  body_text: z.string(),
  status: z.enum(["approved", "repealed"]),
  snapshot_date: isoDate,
  owning_agency: z.string(),
  amendment_source: z.string().nullable().optional(),
  federal_refs: z.array(z.string()).default([]),
  iac_cross_refs: z.array(z.string()).default([]),
  placeholder: placeholderFlag,
});
export type CodeSection = z.infer<typeof codeSectionSchema>;

export const regulatoryActionSchema = z.object({
  source_system: z.string(),
  source_id: z.string(),
  agency: z.string(),
  stream: z.string(),
  action_type: z.string(),
  status: z.string(),
  date_published: isoDate.nullable(),
  title: z.string(),
  abstract: z.string(),
  cfr_references: z.array(z.string()).default([]),
  legal_refs: z.array(z.string()).default([]),
  docket_ids: z.array(z.string()).default([]),
  rin: z.string().nullable().optional(),
  din: z.string().nullable().optional(),
  source_url: z.string(),
  related: z.array(
    z.object({
      source_id: z.string(),
      relationship_type: z.enum(["related_to", "supersedes", "corrects"]),
    }),
  ),
  placeholder: placeholderFlag,
});
export type RegulatoryAction = z.infer<typeof regulatoryActionSchema>;

export const versionEntrySchema = z.object({
  snapshot: z.enum(["S1", "S2"]),
  snapshot_date: isoDate,
  text: z.string(),
});
export type VersionEntry = z.infer<typeof versionEntrySchema>;

export const lineDiffSchema = z.array(
  z.object({ op: z.enum(["equal", "delete", "insert"]), line: z.string() }),
);
export type LineDiff = z.infer<typeof lineDiffSchema>;

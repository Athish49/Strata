// KbApi over HTTP. See development_docs/ui_wiring_contract.md section 4. No fixtures.
import { diffLines } from "diff";
import { z } from "zod";
import type { KbApi, Page } from "../client";
import { agencySchema, codeSectionSchema, versionEntrySchema } from "../schemas/kb";
import type { LineDiff, RegulatoryAction } from "../schemas/kb";
import { getJson, qs, seg } from "./shared";

const pageOf = <T extends z.ZodType>(item: T) =>
  z.object({ items: z.array(item), total: z.number(), page: z.number(), limit: z.number() });

const nullArr = z.array(z.string()).nullish().transform((v) => v ?? []);
const RELATIONS = ["supersedes", "corrects"] as const;

/** Raw row of the existing GET /actions (list omits abstract) and detail endpoints. */
const rawActionSchema = z.object({
  source_system: z.string(),
  source_id: z.string(),
  agency: z.string(),
  action_type: z.string(),
  status: z.string(),
  title: z.string(),
  source_url: z.string(),
  rin: z.string().nullish(),
  date_published: z.string().nullish(),
  abstract: z.string().nullish(),
  cfr_references: nullArr,
  legal_refs: nullArr,
  docket_ids: nullArr,
  related_actions_resolved: z
    .array(
      z.object({
        relationship_type: z.string().nullish(),
        action: z.object({ source_id: z.string() }).passthrough().nullish(),
        source_id: z.string().nullish(),
      }).passthrough(),
    )
    .nullish(),
});
type RawAction = z.infer<typeof rawActionSchema>;

/** Clean scraped titles: strip a trailing "[PDF]"; a bare "PDF" GAO title becomes "GAO <source_id>". */
export function cleanActionTitle(title: string, source_system: string, action_type: string, source_id: string): string {
  const t = (title ?? "").replace(/\s*\[PDF\]\s*$/i, "").trim();
  if (/^(pdf)?$/i.test(t)) {
    const gao = /gao/i.test(source_system) || /gao/i.test(action_type);
    return gao ? `GAO ${source_id}` : t || title;
  }
  return t;
}

function mapAction(r: RawAction): RegulatoryAction {
  const related: RegulatoryAction["related"] = [];
  for (const item of r.related_actions_resolved ?? []) {
    const source_id = item.action?.source_id ?? item.source_id;
    if (!source_id) continue;
    const t = item.relationship_type;
    related.push({
      source_id,
      relationship_type: (RELATIONS as readonly string[]).includes(t ?? "")
        ? (t as (typeof RELATIONS)[number])
        : "related_to",
    });
  }
  return {
    source_system: r.source_system,
    source_id: r.source_id,
    agency: r.agency,
    stream: r.source_system,
    action_type: r.action_type,
    status: r.status,
    date_published: r.date_published ?? null,
    title: cleanActionTitle(r.title, r.source_system, r.action_type, r.source_id),
    abstract: r.abstract ?? "",
    cfr_references: r.cfr_references,
    legal_refs: r.legal_refs,
    docket_ids: r.docket_ids,
    rin: r.rin ?? null,
    din: null,
    source_url: r.source_url,
    related,
  };
}

const versionsPath = (ss: string, citation: string) =>
  `/engine/ui/kb/sections/${seg(ss)}/${seg(citation)}/versions`;

export const kbHttp: KbApi = {
  listAgencies: () => getJson("/engine/ui/kb/agencies", z.array(agencySchema)),

  getAgency: (slug) => getJson(`/engine/ui/kb/agencies/${seg(slug)}`, agencySchema.nullable(), { on404: null }),

  listSections: (q) =>
    getJson(
      `/engine/ui/kb/sections${qs({
        agency: q.agency,
        source_system: q.source_system,
        status: q.status,
        search: q.search,
        page: q.page,
        limit: q.limit,
      })}`,
      pageOf(codeSectionSchema),
    ),

  getSection: (source_system, citation) =>
    getJson(`/engine/ui/kb/sections/${seg(source_system)}/${seg(citation)}`, codeSectionSchema.nullable(), {
      on404: null,
    }),

  async listActions(q) {
    if (q.stream && q.source_system && q.stream !== q.source_system) {
      return { items: [], total: 0, page: q.page ?? 1, limit: q.limit ?? 50 } satisfies Page<RegulatoryAction>;
    }
    const raw = await getJson(
      `/actions${qs({
        agency: q.agency,
        source_system: q.source_system ?? q.stream,
        status: q.status,
        action_type: q.action_type,
        date_from: q.date_from,
        date_to: q.date_to,
        search: q.search,
        page: q.page,
        limit: q.limit,
      })}`,
      pageOf(rawActionSchema),
    );
    return { ...raw, items: raw.items.map(mapAction) };
  },

  async getAction(source_system, source_id) {
    const raw = await getJson(`/actions/${seg(source_system)}/${source_id.split("/").map(seg).join("/")}`, rawActionSchema.nullable(), {
      on404: null,
    });
    return raw ? mapAction(raw) : null;
  },

  getVersionHistory: (source_system, citation) =>
    getJson(versionsPath(source_system, citation), z.array(versionEntrySchema), { on404: [] }),

  async compare(source_system, citation, date_a, date_b) {
    const versions = await kbHttp.getVersionHistory(source_system, citation);
    if (versions.length === 0) return [];
    const pick = (date: string | undefined, fallback: number) =>
      (date ? versions.find((v) => v.snapshot_date.startsWith(date)) : undefined) ??
      versions[fallback < 0 ? versions.length + fallback : fallback];
    const a = pick(date_a, 0);
    const b = pick(date_b, -1);
    const out: LineDiff = [];
    for (const part of diffLines(a.text, b.text)) {
      const op = part.added ? "insert" : part.removed ? "delete" : "equal";
      const lines = part.value.split("\n");
      if (lines[lines.length - 1] === "") lines.pop();
      for (const line of lines) out.push({ op, line });
    }
    return out;
  },
};

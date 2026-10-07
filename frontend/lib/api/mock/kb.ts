import { diffLines } from "diff";
import type { Agency, LineDiff } from "../schemas";
import type { KbApi, Page } from "../client";
import { fixtures } from "./fixtures";
import { withLatency } from "./config";

const MAX_LIMIT = 200;

function paginate<T>(all: T[], q: { page?: number; limit?: number }): Page<T> {
  const limit = Math.min(Math.max(q.limit ?? 50, 1), MAX_LIMIT);
  const page = Math.max(q.page ?? 1, 1);
  return { items: all.slice((page - 1) * limit, page * limit), total: all.length, page, limit };
}

/** Does a fixture's agency reference (slug, id or name) point at the filter value? */
function agencyMatcher(value?: string): (ref: string) => boolean {
  if (!value) return () => true;
  const v = value.toLowerCase();
  const ag: Agency | undefined = fixtures().agencies.find(
    (a) => a.slug.toLowerCase() === v || (a.agency_id ?? "").toLowerCase() === v,
  );
  const keys = new Set([v, ag?.slug, ag?.agency_id, ag?.name].filter(Boolean).map((s) => s!.toLowerCase()));
  return (ref) => keys.has(ref.toLowerCase());
}

const includes = (hay: string, needle: string) => hay.toLowerCase().includes(needle.toLowerCase());

export const kbApi: KbApi = {
  listAgencies: () => withLatency(() => fixtures().agencies),

  getAgency: (slug) => withLatency(() => fixtures().agencies.find((a) => a.slug === slug) ?? null),

  listSections: (q) =>
    withLatency(() => {
      const match = agencyMatcher(q.agency);
      const items = fixtures().sections.filter(
        (s) =>
          match(s.owning_agency) &&
          (!q.source_system || s.source_system === q.source_system) &&
          (!q.status || s.status === q.status) &&
          (!q.search || includes(`${s.citation} ${s.heading} ${s.body_text}`, q.search)),
      );
      return paginate(items, q);
    }),

  getSection: (source_system, citation) =>
    withLatency(
      () => fixtures().sections.find((s) => s.source_system === source_system && s.citation === citation) ?? null,
    ),

  listActions: (q) =>
    withLatency(() => {
      const match = agencyMatcher(q.agency);
      const items = fixtures()
        .actions.filter(
          (a) =>
            match(a.agency) &&
            (!q.source_system || a.source_system === q.source_system) &&
            (!q.status || a.status === q.status) &&
            (!q.action_type || a.action_type === q.action_type) &&
            (!q.stream || a.stream === q.stream) &&
            (!q.date_from || a.date_published >= q.date_from) &&
            (!q.date_to || a.date_published <= q.date_to) &&
            (!q.search || includes(`${a.title} ${a.abstract} ${a.source_id}`, q.search)),
        )
        .sort((a, b) => b.date_published.localeCompare(a.date_published));
      return paginate(items, q);
    }),

  getAction: (source_system, source_id) =>
    withLatency(
      () => fixtures().actions.find((a) => a.source_system === source_system && a.source_id === source_id) ?? null,
    ),

  getVersionHistory: (source_system, citation) =>
    withLatency(() => fixtures().versions[`${source_system}|${citation}`] ?? []),

  compare: (source_system, citation, date_a, date_b) =>
    withLatency((): LineDiff => {
      const versions = fixtures().versions[`${source_system}|${citation}`] ?? [];
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
    }),
};

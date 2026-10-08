// Pure board logic: join documents with rollups, derive status, group, sort, filter (spec §9.3, §11.5).
import type { DocRollup, DocumentMeta } from "@/lib/api/schemas";
import type { DocStatusKey } from "@/lib/labels";
import { documentStatus, type DocStatus } from "@/lib/status";
import { VERTICALS, type Vertical } from "@/lib/verticals";
import { VERDICT_SEVERITY_ORDER } from "@/lib/verdict-tokens";

export interface DocRow {
  meta: DocumentMeta;
  rollup?: DocRollup;
  status: DocStatus;
  /** Total findings (sum of verdict counts) for this run. */
  findings: number;
  /** True while rollups are loading, so the status is not yet known. */
  pending: boolean;
}

export const STATUS_ORDER: readonly DocStatusKey[] = ["action_needed", "review", "cleared", "not_monitored"];

/** Accepted URL aliases for the status filter (other pages link with `flagged`, `needs_review`, ...). */
const STATUS_ALIASES: Record<string, DocStatusKey> = {
  flagged: "action_needed",
  action: "action_needed",
  attention: "action_needed",
  needs_review: "review",
  "needs-review": "review",
  "action-needed": "action_needed",
  "not-monitored": "not_monitored",
};

/** Normalise a `?status=` value to a status key (or null). */
export function normalizeStatus(v: string | null | undefined): DocStatusKey | null {
  if (!v) return null;
  const k = v.trim().toLowerCase();
  if (isStatusKey(k)) return k;
  return STATUS_ALIASES[k] ?? null;
}

export function isStatusKey(v: string | null | undefined): v is DocStatusKey {
  return !!v && (STATUS_ORDER as readonly string[]).includes(v);
}

export function totalFindings(rollup?: Pick<DocRollup, "counts_by_verdict">): number {
  return Object.values(rollup?.counts_by_verdict ?? {}).reduce((n, k) => n + (k > 0 ? k : 0), 0);
}

export function buildRows(
  docs: readonly DocumentMeta[],
  rollups: readonly DocRollup[] | undefined,
  pending = false,
): DocRow[] {
  const byDoc = new Map((rollups ?? []).map((r) => [r.doc_id, r] as const));
  return docs.map((meta) => {
    const rollup = byDoc.get(meta.doc_id);
    return { meta, rollup, status: documentStatus(meta, rollup), findings: totalFindings(rollup), pending: pending && meta.monitored };
  });
}

/** Needs-action first, then review, cleared, not monitored; ties by doc id. */
export function compareRows(a: DocRow, b: DocRow): number {
  const d = STATUS_ORDER.indexOf(a.status.key) - STATUS_ORDER.indexOf(b.status.key);
  if (d !== 0) return d;
  if (b.findings !== a.findings) return b.findings - a.findings;
  return a.meta.doc_id.localeCompare(b.meta.doc_id);
}

export interface RowFilter {
  status?: DocStatusKey | null;
  vertical?: string | null;
  owner?: string | null;
}

export function filterRows(rows: readonly DocRow[], f: RowFilter): DocRow[] {
  return rows.filter(
    (r) =>
      (!f.status || r.status.key === f.status) &&
      (!f.vertical || r.meta.vertical === f.vertical) &&
      (!f.owner || r.meta.owner.person_id === f.owner),
  );
}

export interface VerticalGroup {
  vertical: Vertical;
  rows: DocRow[];
  monitored: DocRow[];
  samples: DocRow[];
  needsAction: number;
}

export function needsAction(r: DocRow): boolean {
  return r.status.key === "action_needed" || r.status.key === "review";
}

/** One group per vertical in the fixed §5.3 order (also empty ones); rows sorted needs-action first. */
export function groupByVertical(rows: readonly DocRow[]): VerticalGroup[] {
  return VERTICALS.map((vertical) => {
    const mine = rows.filter((r) => r.meta.vertical === vertical.slug).sort(compareRows);
    return {
      vertical,
      rows: mine,
      monitored: mine.filter((r) => r.meta.monitored),
      samples: mine.filter((r) => !r.meta.monitored),
      needsAction: mine.filter(needsAction).length,
    };
  });
}

/** Verdict counts in worst-first order, zero counts dropped. */
export function verdictSegments(counts: Record<string, number> | undefined) {
  return VERDICT_SEVERITY_ORDER.map((v) => ({ verdict: v, count: counts?.[v] ?? 0 })).filter((s) => s.count > 0);
}

export interface OwnerOption {
  id: string;
  name: string;
}

export function ownerOptions(docs: readonly DocumentMeta[]): OwnerOption[] {
  const m = new Map<string, string>();
  for (const d of docs) m.set(d.owner.person_id, d.owner.name);
  return [...m].map(([id, name]) => ({ id, name })).sort((a, b) => a.name.localeCompare(b.name));
}

export function docHref(docId: string): string {
  return `/app/documents/${encodeURIComponent(docId)}`;
}

export function verticalHref(slug: string): string {
  return `/app/documents/verticals/${slug}`;
}

/** "2 need action" style summary; null when nothing needs action. */
export function needsActionSentence(n: number): string | null {
  if (n <= 0) return null;
  return `${n} ${n === 1 ? "document needs" : "documents need"} attention in this run.`;
}

/** "3.0" -> "v3.0"; free-text versions ("Sheets as revised…") are shown as written. */
export function versionLabel(version: string): string {
  const v = version.trim();
  return /^v?\d[\w.-]*$/i.test(v) ? `v${v.replace(/^v/i, "")}` : v;
}

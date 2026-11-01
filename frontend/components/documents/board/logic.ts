// Pure board logic: join documents with rollups, derive status, group, sort, filter (spec §9.3, §11.5).
import type { DocRollup, DocumentMeta } from "@/lib/api/schemas";
import type { BoardStatusKey } from "@/lib/labels";
import { documentStatus } from "@/lib/status";
import { DOC_STATUS_LABELS } from "@/lib/labels";
import { UNCLASSIFIED_SLUG, verticalGroups, type Vertical } from "@/lib/verticals";
import { VERDICT_SEVERITY_ORDER } from "@/lib/verdict-tokens";

/** A board status: the run status from lib/status.ts or a lifecycle status. */
export interface BoardStatus {
  key: BoardStatusKey;
  label: string;
  /** Reason line, set for "cleared", "not monitored" and the lifecycle statuses. */
  reason?: string;
}

export interface DocRow {
  meta: DocumentMeta;
  rollup?: DocRollup;
  status: BoardStatus;
  /** Total findings (sum of verdict counts) for this run. */
  findings: number;
  /** True while rollups are loading, so the status is not yet known. */
  pending: boolean;
}

export const STATUS_ORDER: readonly BoardStatusKey[] = [
  "action_needed",
  "review",
  "ingest_failed",
  "in_review",
  "processing",
  "cleared",
  "not_monitored",
  "retired",
];

/** Statuses of a document that has no usable current version (derived from its lifecycle, not the run). */
export const LIFECYCLE_STATUSES: readonly BoardStatusKey[] = ["processing", "in_review", "ingest_failed", "retired"];

export function isLifecycleStatus(key: BoardStatusKey): boolean {
  return (LIFECYCLE_STATUSES as readonly string[]).includes(key);
}

export const LIFECYCLE_REASONS = {
  processing: "Being read and indexed. It is checked against changes once approved.",
  in_review: "Awaiting approval. It is checked against changes once approved.",
  ingest_failed: "The uploaded file could not be processed. Open the document to retry.",
  retired: "Retired. No longer checked against changes.",
} as const satisfies Partial<Record<BoardStatusKey, string>>;

type LifecycleMeta = Pick<
  DocumentMeta,
  "monitored" | "lifecycle_state" | "has_current_version" | "latest_version_status" | "latest_ingest_status"
>;

/**
 * Board status for a document (Wave 6 rendering contract), in this precedence:
 * 1. `lifecycle_state === "retired"` -> retired.
 * 2. A current version exists (`has_current_version` not explicitly false; absent on older
 *    payloads) -> the run status from `documentStatus`, unchanged.
 * 3. No current version, judged by the newest non-retired version first:
 *    latest ingest `failed` -> ingest_failed; latest ingest `ingested` and version not yet
 *    effective -> in_review; latest ingest `pending`/unknown -> processing.
 *    The sticky `lifecycle_state === "failed"` applies only when there is no latest version
 *    (a healthy v2 in review is shown as in review, not as v1's failure).
 */
export function boardStatus(
  meta: LifecycleMeta,
  rollup?: Parameters<typeof documentStatus>[1],
): BoardStatus {
  const make = (key: keyof typeof LIFECYCLE_REASONS): BoardStatus => ({
    key,
    label: DOC_STATUS_LABELS[key],
    reason: LIFECYCLE_REASONS[key],
  });
  if (meta.lifecycle_state === "retired") return make("retired");
  if (meta.has_current_version !== false) return documentStatus(meta, rollup);

  const ingest = meta.latest_ingest_status ?? null;
  const version = meta.latest_version_status ?? null;
  if (ingest === "failed") return make("ingest_failed");
  if (ingest === "ingested") return make("in_review");
  if (ingest === null && version === null && meta.lifecycle_state === "failed") return make("ingest_failed");
  return make("processing");
}

/** Accepted URL aliases for the status filter (other pages link with `flagged`, `needs_review`, ...). */
const STATUS_ALIASES: Record<string, BoardStatusKey> = {
  flagged: "action_needed",
  action: "action_needed",
  attention: "action_needed",
  needs_review: "review",
  "needs-review": "review",
  "action-needed": "action_needed",
  "not-monitored": "not_monitored",
  "in-review": "in_review",
  awaiting_approval: "in_review",
  "ingest-failed": "ingest_failed",
  failed: "ingest_failed",
};

/** Normalise a `?status=` value to a status key (or null). */
export function normalizeStatus(v: string | null | undefined): BoardStatusKey | null {
  if (!v) return null;
  const k = v.trim().toLowerCase();
  if (isStatusKey(k)) return k;
  return STATUS_ALIASES[k] ?? null;
}

export function isStatusKey(v: string | null | undefined): v is BoardStatusKey {
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
    return { meta, rollup, status: boardStatus(meta, rollup), findings: totalFindings(rollup), pending: pending && meta.monitored };
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
  status?: BoardStatusKey | null;
  vertical?: string | null;
  owner?: string | null;
}

/** Retired documents are hidden unless the status filter asks for them. */
export function filterRows(rows: readonly DocRow[], f: RowFilter): DocRow[] {
  return rows.filter(
    (r) =>
      (f.status ? r.status.key === f.status : r.status.key !== "retired") &&
      (!f.vertical || r.meta.vertical === f.vertical) &&
      (!f.owner || r.meta.owner.person_id === f.owner),
  );
}

export interface VerticalGroup {
  vertical: Vertical;
  rows: DocRow[];
  monitored: DocRow[];
  /** Rows shown as cards: monitored documents and lifecycle states (processing, in review, failed, retired). */
  cards: DocRow[];
  /** Not-monitored rows, shown as compact sample rows. */
  samples: DocRow[];
  needsAction: number;
}

export function needsAction(r: DocRow): boolean {
  return r.status.key === "action_needed" || r.status.key === "review";
}

/**
 * One group per vertical in the fixed §5.3 order (also empty ones), then an "Unclassified" group
 * only when it has rows (it is not a vertical you can file into). Rows sorted needs-action first.
 */
export function groupByVertical(rows: readonly DocRow[], verticals: readonly Vertical[]): VerticalGroup[] {
  return verticalGroups(verticals).map((vertical) => {
    const mine = rows.filter((r) => r.meta.vertical === vertical.slug).sort(compareRows);
    return {
      vertical,
      rows: mine,
      monitored: mine.filter((r) => r.meta.monitored),
      cards: mine.filter((r) => r.status.key !== "not_monitored"),
      samples: mine.filter((r) => r.status.key === "not_monitored"),
      needsAction: mine.filter(needsAction).length,
    };
  }).filter((g) => g.vertical.slug !== UNCLASSIFIED_SLUG || g.rows.length > 0);
}

export function isUnclassified(slug: string): boolean {
  return slug === UNCLASSIFIED_SLUG;
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
  for (const d of docs) if (d.owner.person_id && d.owner.name.trim()) m.set(d.owner.person_id, d.owner.name);
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

/** Placeholder for an empty owner (a document with no role assignments yet). */
export const NO_OWNER_LABEL = "Unassigned";

export function ownerName(meta: Pick<DocumentMeta, "owner">): string | null {
  const n = meta.owner?.name?.trim();
  return n ? n : null;
}

/**
 * Version shown on cards and rows. A document with no current version has a blank `version`:
 * show the newest version number with "awaiting approval" while it moves through review, or "—".
 */
export function docVersionText(
  meta: Pick<DocumentMeta, "version" | "latest_version_no">,
  status: BoardStatusKey,
): string {
  if (meta.version.trim()) return versionLabel(meta.version);
  const n = meta.latest_version_no;
  if (status === "processing" || status === "in_review") {
    return n != null ? `v${n} · Awaiting approval` : "Awaiting approval";
  }
  return n != null ? `v${n}` : "—";
}

/** "3.0" -> "v3.0"; free-text versions ("Sheets as revised…") are shown as written. */
export function versionLabel(version: string): string {
  const v = version.trim();
  return /^v?\d[\w.-]*$/i.test(v) ? `v${v.replace(/^v/i, "")}` : v;
}

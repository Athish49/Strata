// Pure view-model for the document reader: turns clauses + annotations into a flat, virtualizable item list.
import type { Annotation, Clause, Verdict } from "@/lib/api/schemas";
import { VERDICT_SEVERITY_ORDER } from "@/lib/verdict-tokens";
import { isBlankText } from "./markdown";

export interface ClauseNotes {
  findings: Annotation[];
  /** One entry per change the clause was cleared against. */
  cleared: Annotation[];
}

const EMPTY_NOTES: ClauseNotes = { findings: [], cleared: [] };

/** Group annotations per clause: findings stay individual, cleared reasons are aggregated for one marker. */
export function notesByClause(annotations: readonly Annotation[]): Map<string, ClauseNotes> {
  const map = new Map<string, ClauseNotes>();
  for (const a of annotations) {
    let n = map.get(a.clause_id);
    if (!n) {
      n = { findings: [], cleared: [] };
      map.set(a.clause_id, n);
    }
    (a.kind === "finding" ? n.findings : n.cleared).push(a);
  }
  return map;
}

export function notesFor(map: Map<string, ClauseNotes>, clauseId: string): ClauseNotes {
  return map.get(clauseId) ?? EMPTY_NOTES;
}

/** Stable id for a finding annotation (finding_id when present). */
export function annotationKey(a: Annotation): string {
  return a.finding_id ?? `${a.clause_id}::${a.change_id}`;
}

export interface TableGroup {
  id: string;
  /** All column keys in display order. */
  columns: string[];
  /** Columns shown on the collapsed row (all of them for narrow registers). */
  visible: string[];
  /** Pixel width per visible column. */
  widths: number[];
  /** Total rows in the group (for the caption). */
  rowCount: number;
}

export type Edge = "first" | "mid" | "last" | "only";

export type ReaderItem =
  | { key: string; kind: "heading"; level: number; text: string; anchors: string[] }
  | { key: string; kind: "clause"; clause: Clause; edge: Edge; anchors: string[] }
  | { key: string; kind: "table-head"; group: TableGroup; anchors: string[] }
  | { key: string; kind: "table-row"; clause: Clause; group: TableGroup; edge: Edge; cells: Record<string, string>; anchors: string[] };

export interface ReaderModel {
  items: ReaderItem[];
  /** clause_id -> index of the item that shows it (empty clauses map to the next visible item). */
  indexByClause: Map<string, number>;
  clauses: Clause[];
}

/** "compliance_register_2024-12-31" -> "Compliance register 2024-12-31". Text with spaces is left alone. */
export function prettyHeading(s: string): string {
  const t = s.trim();
  if (!t || /\s/.test(t) || !t.includes("_")) return t;
  const spaced = t.replace(/_+/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Row cells with only string values (null / junk keys dropped). */
export function cleanCells(clause: Pick<Clause, "row_cells">): Record<string, string> | null {
  const rc = clause.row_cells;
  if (!rc) return null;
  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(rc)) {
    if (typeof v === "string" && k !== "null") out[k] = v;
  }
  return Object.keys(out).length ? out : null;
}

/** Keys in the order they appear in `text_raw` ("key: value" lines), then any remaining ones. */
export function orderedKeys(clause: Pick<Clause, "text_raw">, cells: Record<string, string>): string[] {
  const keys: string[] = [];
  for (const line of clause.text_raw.split("\n")) {
    const m = /^([^:\n]{1,60}):\s/.exec(line) ?? /^([^:\n]{1,60}):$/.exec(line);
    if (m && m[1] in cells && !keys.includes(m[1])) keys.push(m[1]);
  }
  for (const k of Object.keys(cells)) if (!keys.includes(k)) keys.push(k);
  return keys;
}

/** Raw offset of a cell's value inside `text_raw`, or null when it can't be located. */
export function cellOffset(clause: Pick<Clause, "text_raw">, key: string, value: string): number | null {
  const needle = `${key}: ${value}`;
  const i = clause.text_raw.indexOf(needle);
  return i >= 0 ? i + key.length + 2 : null;
}

export function columnLabel(key: string): string {
  const spaced = key.replace(/_+/g, " ").trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

const MAX_NARROW = 6;

function makeGroup(id: string, rows: { cells: Record<string, string>; keys: string[] }[]): TableGroup {
  const columns: string[] = [];
  for (const r of rows) for (const k of r.keys) if (!columns.includes(k)) columns.push(k);
  let visible = columns;
  if (columns.length > MAX_NARROW) {
    visible = columns.slice(0, 4);
    const status = columns.find((c) => /^status$/i.test(c));
    if (status && !visible.includes(status)) visible = [...visible, status];
  }
  const widths = visible.map((c) => {
    let longest = columnLabel(c).length;
    for (const r of rows) longest = Math.max(longest, Math.min(48, (r.cells[c] ?? "").length));
    return Math.max(96, Math.min(300, longest * 7 + 28));
  });
  return { id, columns, visible, widths, rowCount: rows.length };
}

function edgeOf(i: number, n: number): Edge {
  if (n === 1) return "only";
  return i === 0 ? "first" : i === n - 1 ? "last" : "mid";
}

const FORM_KINDS = new Set(["form_field"]);

/** Build the flat item list: de-duplicated headings, tables grouped per parent, empty clauses folded into headings. */
export function buildReaderModel(clausesIn: readonly Clause[], notes: Map<string, ClauseNotes>, docId?: string): ReaderModel {
  const clauses = [...clausesIn].sort((a, b) => a.ordinal - b.ordinal);
  const items: ReaderItem[] = [];
  const indexByClause = new Map<string, number>();
  let prevPath: string[] = [];
  let pendingEmpty: string[] = [];

  const hidden = (s: string) => !!docId && s.trim().toLowerCase() === docId.toLowerCase();

  // Pass 1: collect table groups by (parent or heading path) for consecutive row clauses.
  type RowRec = { clause: Clause; cells: Record<string, string>; keys: string[] };
  const groupOf = new Map<string, RowRec[]>(); // groupKey -> rows
  const rowGroupKey = new Map<string, string>(); // clause_id -> groupKey
  let run: { key: string; sig: string } | null = null;
  let runIdx = 0;
  for (const c of clauses) {
    const isRow = c.unit_kind === "register_row" || c.unit_kind === "table_row";
    const cells = isRow ? cleanCells(c) : null;
    if (!isRow || !cells) {
      run = null;
      continue;
    }
    const sig = `${c.parent_clause_id ?? ""}|${c.heading_path.join("\u0001")}`;
    if (!run || run.sig !== sig) {
      run = { key: `g${runIdx++}`, sig };
      groupOf.set(run.key, []);
    }
    groupOf.get(run.key)!.push({ clause: c, cells, keys: orderedKeys(c, cells) });
    rowGroupKey.set(c.clause_id, run.key);
  }
  const groups = new Map<string, TableGroup>();
  for (const [k, rows] of groupOf) groups.set(k, makeGroup(k, rows));
  const seenGroup = new Set<string>();
  const posInGroup = new Map<string, number>();

  const push = (item: ReaderItem, own?: string) => {
    const idx = items.length;
    items.push(item);
    for (const id of pendingEmpty) indexByClause.set(id, idx);
    pendingEmpty = [];
    if (own) indexByClause.set(own, idx);
  };

  for (const c of clauses) {
    const path = c.heading_path.map((s) => s).filter((s) => !!s);
    let d = 0;
    while (d < prevPath.length && d < path.length && prevPath[d] === path[d]) d++;
    let level = path.slice(0, d).filter((s) => !hidden(s)).length;
    for (let i = d; i < path.length; i++) {
      if (hidden(path[i])) continue;
      push({ key: `h:${c.clause_id}:${i}`, kind: "heading", level, text: prettyHeading(path[i]), anchors: [c.clause_id] });
      level++;
    }
    prevPath = path;

    const gk = rowGroupKey.get(c.clause_id);
    if (gk) {
      const g = groups.get(gk)!;
      if (!seenGroup.has(gk)) {
        seenGroup.add(gk);
        push({ key: `th:${gk}`, kind: "table-head", group: g, anchors: [] });
      }
      const n = posInGroup.get(gk) ?? 0;
      posInGroup.set(gk, n + 1);
      const cells = cleanCells(c)!;
      push({ key: `r:${c.clause_id}`, kind: "table-row", clause: c, group: g, cells, edge: n === g.rowCount - 1 ? "last" : "mid", anchors: [c.clause_id] }, c.clause_id);
      continue;
    }
    const hasNotes = (notes.get(c.clause_id)?.findings.length ?? 0) + (notes.get(c.clause_id)?.cleared.length ?? 0) > 0;
    if (isBlankText(c.text_raw) && !hasNotes) {
      pendingEmpty.push(c.clause_id);
      continue;
    }
    push({ key: `c:${c.clause_id}`, kind: "clause", clause: c, edge: "only", anchors: [c.clause_id] }, c.clause_id);
  }
  if (pendingEmpty.length && items.length) {
    for (const id of pendingEmpty) indexByClause.set(id, items.length - 1);
  }

  // Edges: consecutive form_field clauses share one "form" block; table rows/heads are already marked.
  for (let i = 0; i < items.length; i++) {
    const it = items[i];
    if (it.kind === "clause" && FORM_KINDS.has(it.clause.unit_kind)) {
      let a = i;
      let b = i;
      const same = (x: ReaderItem | undefined) => !!x && x.kind === "clause" && FORM_KINDS.has(x.clause.unit_kind);
      while (same(items[a - 1])) a--;
      while (same(items[b + 1])) b++;
      it.edge = edgeOf(i - a, b - a + 1);
    }
  }
  // Table rows: the first row follows the head; mark the row count based edges (head is the visual top).
  return { items, indexByClause, clauses };
}

export interface RailFinding {
  /** finding_id, or a synthetic id when the annotation has none. Never displayed. */
  id: string;
  findingId: string | null;
  clause: Clause;
  verdict: Verdict;
  citation: string;
  reason: string;
  changeId: string;
}

/** Findings in document order (ordinal, then worst verdict first). */
export function railFindings(clauses: readonly Clause[], annotations: readonly Annotation[]): RailFinding[] {
  const byId = new Map(clauses.map((c) => [c.clause_id, c]));
  const out: RailFinding[] = [];
  for (const a of annotations) {
    if (a.kind !== "finding") continue;
    const clause = byId.get(a.clause_id);
    if (!clause) continue;
    out.push({
      id: annotationKey(a),
      findingId: a.finding_id ?? null,
      clause,
      verdict: (a.verdict ?? "info") as Verdict,
      citation: a.citation,
      reason: a.reason,
      changeId: a.change_id,
    });
  }
  const sev = (v: Verdict) => VERDICT_SEVERITY_ORDER.indexOf(v);
  out.sort((x, y) => x.clause.ordinal - y.clause.ordinal || sev(x.verdict) - sev(y.verdict) || x.id.localeCompare(y.id));
  return out;
}

export interface ClearedClause {
  clause: Clause;
  /** One reason per change the clause was checked against. */
  reasons: Annotation[];
}

/** Clauses that were cleared (and have no finding), in document order. */
export function clearedClauses(clauses: readonly Clause[], notes: Map<string, ClauseNotes>): ClearedClause[] {
  const out: ClearedClause[] = [];
  for (const c of clauses) {
    const n = notes.get(c.clause_id);
    if (n && n.cleared.length > 0) out.push({ clause: c, reasons: n.cleared });
  }
  return out.sort((a, b) => a.clause.ordinal - b.clause.ordinal);
}

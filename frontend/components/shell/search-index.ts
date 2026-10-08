// Pure matching helpers for the global search (no React, no data layer).
import type { Clause } from "@/lib/api/schemas";

export const norm = (s: string): string => s.toLowerCase().replace(/\s+/g, " ").trim();

/** Every whitespace-separated token of `q` occurs in `hay` (hay already normalised). */
export function matchesAll(hay: string, q: string): boolean {
  const tokens = norm(q).split(" ").filter(Boolean);
  return tokens.length > 0 && tokens.every((t) => hay.includes(t));
}

/** 0 = exact, 1 = prefix, 2 = contains, null = no match. For ids and citations. */
export function idRank(value: string, q: string): 0 | 1 | 2 | null {
  const v = norm(value);
  const n = norm(q);
  if (!n) return null;
  if (v === n) return 0;
  if (v.startsWith(n)) return 1;
  return v.includes(n) ? 2 : null;
}

export interface ClauseEntry {
  docId: string;
  clauseId: string;
  /** Clause id without the "<docId>:" prefix. */
  localId: string;
  text: string;
  lower: string;
}

/** Text a user could search for in one clause: heading path, body and register-row cells. */
export function clauseSearchText(c: Clause): string {
  const cells = c.row_cells ? Object.values(c.row_cells).join(" ") : "";
  return [c.heading_path.join(" "), c.text_raw, cells]
    .filter(Boolean)
    .join(" ")
    .replace(/[*`#]+|\|/g, " ") // drop markdown markers and table pipes
    .replace(/\s+/g, " ")
    .trim();
}

export function toClauseEntry(c: Clause): ClauseEntry {
  const local = c.clause_id.startsWith(`${c.doc_id}:`) ? c.clause_id.slice(c.doc_id.length + 1) : c.clause_id;
  const text = clauseSearchText(c);
  return { docId: c.doc_id, clauseId: c.clause_id, localId: local, text, lower: norm(`${c.clause_id} ${text}`) };
}

/** Up to `radius` characters either side of the first hit, with ellipses. */
export function snippet(text: string, q: string, radius = 60): string {
  const lower = text.toLowerCase();
  const tokens = norm(q).split(" ").filter(Boolean);
  let at = -1;
  for (const t of tokens) {
    const i = lower.indexOf(t);
    if (i >= 0 && (at < 0 || i < at)) at = i;
  }
  if (at < 0) return text.slice(0, radius * 2);
  const start = Math.max(0, at - radius);
  const end = Math.min(text.length, at + radius * 1.5);
  return `${start > 0 ? "…" : ""}${text.slice(start, end)}${end < text.length ? "…" : ""}`;
}

export function searchClauses(entries: readonly ClauseEntry[], q: string, limit = 8): ClauseEntry[] {
  const n = norm(q);
  if (n.length < 2) return [];
  const exact: ClauseEntry[] = [];
  const rest: ClauseEntry[] = [];
  for (const e of entries) {
    const id = norm(e.clauseId);
    if (id === n || id.startsWith(n)) exact.push(e);
    else if (matchesAll(e.lower, n)) rest.push(e);
    if (exact.length + rest.length >= 400) break;
  }
  return [...exact, ...rest].slice(0, limit);
}

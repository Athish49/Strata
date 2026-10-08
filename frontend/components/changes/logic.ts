// Pure logic for the Changes page: filters, tree grouping, labels. No React.
import type { ChangeClass, ChangeRecord } from "@/lib/api/schemas";
import { isNoiseClass, NOISE_CLASSES, REAL_CLASSES } from "@/lib/labels";

export interface ChangeFilters {
  /** Touches RPL: only changes inside the company's footprint. */
  rpl: boolean;
  /** Real changes only: the four real classes (substantive, repealed, renumbered, new_section); no noise. */
  sub: boolean;
  /** Show noise classes (cosmetic etc.). */
  noise: boolean;
  /** Explicit class selection; overrides sub / noise when non-empty. */
  cls: string[];
  /** Disposition filter, or null for any. */
  disp: string | null;
  /** Free-text filter on citation / heading. */
  q: string;
}

export const DEFAULT_FILTERS: ChangeFilters = { rpl: true, sub: true, noise: false, cls: [], disp: null, q: "" };

export function filtersAreDefault(f: ChangeFilters): boolean {
  return f.rpl && f.sub && !f.noise && f.cls.length === 0 && !f.disp && !f.q.trim();
}

export function classVisible(c: ChangeClass, f: Pick<ChangeFilters, "sub" | "noise" | "cls">): boolean {
  if (f.cls.length > 0) return f.cls.includes(c);
  if (f.noise) return true;
  return !isNoiseClass(c);
}

export function applyFilters(changes: readonly ChangeRecord[], f: ChangeFilters): ChangeRecord[] {
  const q = f.q.trim().toLowerCase();
  return changes.filter((c) => {
    if (f.rpl && !c.in_footprint) return false;
    if (!classVisible(c.change_class, f)) return false;
    if (f.disp && (c.disposition ?? "none") !== f.disp) return false;
    if (q && !(c.citation.toLowerCase().includes(q) || c.heading.toLowerCase().includes(q))) return false;
    return true;
  });
}

const DISPOSITION_LABELS: Record<string, string> = {
  findings_emitted: "Findings emitted",
  no_affected_clauses: "No affected clauses",
  not_in_footprint: "Not in RPL footprint",
  excluded_noise: "Noise removed",
  none: "No disposition recorded",
};

export function dispositionLabel(d: string | null | undefined): string {
  const key = d ?? "none";
  return DISPOSITION_LABELS[key] ?? key.replace(/_/g, " ").replace(/^./, (m) => m.toUpperCase());
}

const DATE_BASIS_LABELS: Record<string, string> = {
  din_publication: "Indiana Register publication",
  fr_published: "Federal Register publication",
  fr_effective: "Federal Register effective date",
};

export function dateBasisLabel(b: string | null | undefined): string | null {
  if (!b) return null;
  return DATE_BASIS_LABELS[b] ?? b.replace(/_/g, " ");
}

const NOISE_BANNERS: Record<string, string> = {
  cosmetic: "Only the readoption stamp or formatting changed. The requirement itself is the same.",
  metadata_only: "Only metadata changed (dates, headings or source notes). The requirement text is the same.",
  punctuation_only: "Only punctuation changed. The requirement text is the same.",
  cross_ref_only: "Only a cross-reference changed. The requirement itself is the same.",
};

/** Neutral explanation for noise classes; null for real classes. */
export function noiseBanner(c: ChangeClass): string | null {
  return NOISE_BANNERS[c] ?? null;
}

// ---------- tree ----------

export interface TreeGroup {
  key: string;
  label: string;
  /** Short qualifier shown after the label (e.g. "Title 170"). */
  sub?: string;
  kind: "agency" | "title" | "rule" | "noise" | "noise-class";
  count: number;
  groups: TreeGroup[];
  rows: ChangeRecord[];
}

const collator = new Intl.Collator("en", { numeric: true, sensitivity: "base" });

function sortRows(rows: ChangeRecord[]): ChangeRecord[] {
  return [...rows].sort(
    (a, b) =>
      Number(b.in_footprint) - Number(a.in_footprint) || b.cited_clause_count - a.cited_clause_count || collator.compare(a.citation, b.citation),
  );
}

function ruleGroups(parent: string, rows: ChangeRecord[]): TreeGroup[] {
  const by = new Map<string, ChangeRecord[]>();
  for (const r of rows) by.set(r.rule_key, [...(by.get(r.rule_key) ?? []), r]);
  return [...by.entries()]
    .sort(([a], [b]) => collator.compare(a, b))
    .map(([rule, rs]) => ({ key: `${parent}/r:${rule}`, label: rule || "Other", kind: "rule" as const, count: rs.length, groups: [], rows: sortRows(rs) }));
}

export type AgencyName = (agencyId: string) => string;

/**
 * Agency -> Title -> Rule -> Section for real changes; one collapsible "Noise removed" block per noise class
 * (class -> rule -> section) after them. A title level is omitted when the agency has a single title.
 */
export function buildTree(changes: readonly ChangeRecord[], agencyName: AgencyName = (a) => a.toUpperCase()): TreeGroup[] {
  const real = changes.filter((c) => !isNoiseClass(c.change_class));
  const noise = changes.filter((c) => isNoiseClass(c.change_class));
  const out: TreeGroup[] = [];

  const byAgency = new Map<string, ChangeRecord[]>();
  for (const c of real) byAgency.set(c.agency_id, [...(byAgency.get(c.agency_id) ?? []), c]);
  const agencies = [...byAgency.entries()].sort(([a], [b]) => collator.compare(agencyName(a), agencyName(b)));
  for (const [agency, rows] of agencies) {
    const key = `a:${agency}`;
    const byTitle = new Map<string, ChangeRecord[]>();
    for (const r of rows) byTitle.set(r.title_number, [...(byTitle.get(r.title_number) ?? []), r]);
    const titles = [...byTitle.entries()].sort(([a], [b]) => collator.compare(a, b));
    const groups: TreeGroup[] =
      titles.length === 1
        ? ruleGroups(key, rows)
        : titles.map(([t, rs]) => ({
            key: `${key}/t:${t}`,
            label: `Title ${t}`,
            kind: "title" as const,
            count: rs.length,
            groups: ruleGroups(`${key}/t:${t}`, rs),
            rows: [],
          }));
    out.push({ key, label: agencyName(agency), sub: titles.length === 1 ? `Title ${titles[0][0]}` : undefined, kind: "agency", count: rows.length, groups, rows: [] });
  }

  if (noise.length > 0) {
    const classes = NOISE_CLASSES.filter((c) => noise.some((n) => n.change_class === c));
    out.push({
      key: "noise",
      label: "Noise removed",
      kind: "noise",
      count: noise.length,
      rows: [],
      groups: classes.map((c) => {
        const rs = noise.filter((n) => n.change_class === c);
        return { key: `noise/${c}`, label: c, kind: "noise-class" as const, count: rs.length, groups: ruleGroups(`noise/${c}`, rs), rows: [] };
      }),
    });
  }
  return out;
}

/** Group keys that contain the given change id (so the selection is always visible). */
export function pathToChange(groups: readonly TreeGroup[], changeId: string | null): Set<string> {
  const keys = new Set<string>();
  if (!changeId) return keys;
  const walk = (g: TreeGroup): boolean => {
    const hit = g.rows.some((r) => r.change_id === changeId) || g.groups.some(walk);
    if (hit) keys.add(g.key);
    return hit;
  };
  groups.forEach(walk);
  return keys;
}

/** Default open state: agencies always, small groups, never the noise block. */
export function defaultOpen(g: TreeGroup, depth: number): boolean {
  if (g.kind === "noise" || g.kind === "noise-class") return false;
  return depth === 0 || g.count <= 12;
}

/** Counts per class over the rpl-filtered set (class chips). */
export function classCounts(changes: readonly ChangeRecord[], rpl: boolean): { cls: ChangeClass; n: number }[] {
  const n = new Map<ChangeClass, number>();
  for (const c of changes) if (!rpl || c.in_footprint) n.set(c.change_class, (n.get(c.change_class) ?? 0) + 1);
  return [...REAL_CLASSES, ...NOISE_CLASSES].filter((c) => n.has(c)).map((c) => ({ cls: c, n: n.get(c) ?? 0 }));
}

/** The most-cited non-noise changes (empty-detail guide). */
export function topCited(changes: readonly ChangeRecord[], k = 3): ChangeRecord[] {
  return changes
    .filter((c) => !isNoiseClass(c.change_class) && c.cited_clause_count > 0)
    .sort((a, b) => b.cited_clause_count - a.cited_clause_count || collator.compare(a.citation, b.citation))
    .slice(0, k);
}

// ---------- raw diff ----------

type RawLine = { op: "equal" | "delete" | "insert"; line: string };

/** LCS-based diff of two string lists. */
function diffLists(a: string[], b: string[]): RawLine[] {
  const dp: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--) dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
  const out: RawLine[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ op: "equal", line: a[i++] });
      j++;
    }
    else if (dp[i + 1][j] >= dp[i][j + 1]) out.push({ op: "delete", line: a[i++] });
    else out.push({ op: "insert", line: b[j++] });
  }
  while (i < a.length) out.push({ op: "delete", line: a[i++] });
  while (j < b.length) out.push({ op: "insert", line: b[j++] });
  return out;
}

const splitSentences = (t: string): string[] => t.split(/(?<=[.;:])\s+/).filter((s) => s.length > 0);

/**
 * The backend diffs by lines, so single-paragraph rules come back as one struck-through block and one inserted block.
 * When the line diff has no unchanged line and few lines, re-diff at sentence level (equal sentences stay unmarked).
 */
export function refineRawDiff(lines: readonly RawLine[] | undefined): RawLine[] | undefined {
  if (!lines) return lines;
  const del = lines.filter((l) => l.op === "delete").map((l) => l.line);
  const ins = lines.filter((l) => l.op === "insert").map((l) => l.line);
  const hasEqual = lines.some((l) => l.op === "equal");
  if (hasEqual || del.length === 0 || ins.length === 0 || lines.length > 6) return [...lines];
  const refined = diffLists(del.flatMap(splitSentences), ins.flatMap(splitSentences));
  return refined.some((l) => l.op === "equal") ? refined : [...lines];
}

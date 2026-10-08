// Single source of display labels for every enum (spec §11.1, §11.2). Components never format enums inline.
import type {
  ChangeClass,
  Direction,
  MatchPath,
  Run,
  Severity,
  Verdict,
} from "@/lib/api/schemas";
import { formatConfidence } from "@/lib/format";

export const VERDICT_LABELS: Record<Verdict, string> = {
  action_required: "Action required",
  optional_relaxed: "Relaxed (optional update)",
  update_citation: "Update citation",
  review: "Needs review",
  info: "Info",
};

export const CLEARED_LABEL = "Cleared";

export type VerdictOrCleared = Verdict | "cleared";

export const REAL_CLASSES = ["substantive", "repealed", "renumbered", "new_section"] as const;
export const NOISE_CLASSES = ["cosmetic", "metadata_only", "punctuation_only", "cross_ref_only"] as const;

export const CHANGE_CLASS_LABELS: Record<ChangeClass, string> = {
  substantive: "Substantive",
  repealed: "Repealed",
  renumbered: "Renumbered",
  new_section: "New section",
  cosmetic: "Cosmetic",
  metadata_only: "Metadata only",
  punctuation_only: "Punctuation only",
  cross_ref_only: "Cross-reference only",
};

export const DIRECTION_LABELS: Record<Direction, string> = {
  tightened: "Tightened",
  relaxed: "Relaxed",
  new_requirement: "New requirement",
  removed: "Removed",
  clarified: "Clarified",
  style_only: "Style only",
  mixed: "Mixed",
};

export const SEVERITY_LABELS: Record<Severity, string> = {
  high: "High",
  medium: "Medium",
  low: "Low",
};

export const APPLICABLE_LABELS = {
  yes: "Possibly applicable",
  no: "Screened out",
  unclear: "Unclear",
} as const;
export type Applicable = keyof typeof APPLICABLE_LABELS;

export const STREAM_LABELS: Record<string, string> = {
  federal_register: "Federal Register",
  iurc_gaos: "Orders",
  iurc_investigations: "Investigations",
  iurc_rulemakings: "Rulemakings",
  idem_rulemakings: "Rulemakings",
};

export type DocStatusKey = "action_needed" | "review" | "cleared" | "not_monitored";
export const DOC_STATUS_LABELS: Record<DocStatusKey, string> = {
  action_needed: "Action needed",
  review: "Review",
  cleared: "Cleared",
  not_monitored: "Not monitored",
};

export function verdictLabel(v: VerdictOrCleared): string {
  return v === "cleared" ? CLEARED_LABEL : VERDICT_LABELS[v];
}

export function changeClassLabel(c: ChangeClass): string {
  return CHANGE_CLASS_LABELS[c];
}

export function isNoiseClass(c: string): boolean {
  return (NOISE_CLASSES as readonly string[]).includes(c);
}

export function directionLabel(d: Direction): string {
  return DIRECTION_LABELS[d];
}

export function severityLabel(s: Severity): string {
  return SEVERITY_LABELS[s];
}

export function runKindLabel(run: Pick<Run, "kind" | "title">): string {
  switch (run.kind) {
    case "kb":
      return "Real wave · S1→S2";
    case "baseline":
      return "Baseline · S1 vs S1";
    case "whatif":
      return `What-if: ${run.title}`;
  }
}

/** "Decided by rule" or "AI judgment · 82%". Confidence is 0..1. */
export function decidedByLabel(decidedBy: "rule" | "ai", confidence?: number | null): string {
  if (decidedBy === "rule") return "Decided by rule";
  return confidence === undefined || confidence === null ? "AI judgment" : `AI judgment · ${formatConfidence(confidence)}`;
}

export function applicableLabel(a: Applicable): string {
  return APPLICABLE_LABELS[a];
}

/** Unknown streams fall back to a humanized key. */
export function streamLabel(stream: string): string {
  if (STREAM_LABELS[stream]) return STREAM_LABELS[stream];
  const s = stream.replace(/_/g, " ");
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function docStatusLabel(key: DocStatusKey): string {
  return DOC_STATUS_LABELS[key];
}

export interface MatchPathContext {
  /** direct_rule: parent rule key. */
  ruleKey?: string;
  /** register_hop: register row / form / tariff rule reference. */
  ref?: string;
  /** value_echo: the old value restated. */
  oldValue?: string;
}

export const MATCH_PATH_WORDS: Record<MatchPath, (ctx?: MatchPathContext) => string> = {
  direct_section: () => "Cites this section directly",
  direct_rule: (ctx) => `Cites the parent rule (${ctx?.ruleKey ?? "rule"})`,
  register_hop: (ctx) => `Linked through ${ctx?.ref ?? "a register row, form or tariff rule"}`,
  value_echo: (ctx) =>
    `Restates the old value${ctx?.oldValue ? ` (${ctx.oldValue})` : ""} without citing it`,
};

export function matchPathWords(path: MatchPath, ctx?: MatchPathContext): string {
  return MATCH_PATH_WORDS[path](ctx);
}

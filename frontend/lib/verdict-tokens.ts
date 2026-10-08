// The single verdict -> color/icon map (spec §11.3, §17.2). No component picks its own color.
// Class strings are literal so Tailwind can see them. Only red / amber / green / ink-family variables.
import type { MatchPath, Verdict } from "@/lib/api/schemas";

export type TokenKey = Verdict | "cleared" | "noise";

export interface VerdictToken {
  /** Semantic CSS variable, e.g. "--verdict-action-required". */
  cssVar: string;
  /** Text / icon color. */
  text: string;
  /** Soft background (pill, cell). */
  soft: string;
  /** Border (left border on clause, pill outline). */
  border: string;
  /** Dot marker background. */
  dot: string;
  /** Tick / gutter marker background. */
  tick: string;
  /** lucide-react export name. */
  icon: string;
  /** "solid" pill vs "outline" pill vs "hatch" (noise). */
  pill: "soft" | "outline" | "muted" | "hatch";
}

export const VERDICT_TOKENS: Record<TokenKey, VerdictToken> = {
  action_required: {
    cssVar: "--verdict-action-required",
    text: "text-[color:var(--verdict-action-required)]",
    soft: "bg-[color:var(--red-soft)]",
    border: "border-[color:var(--verdict-action-required)]",
    dot: "bg-[color:var(--verdict-action-required)]",
    tick: "bg-[color:var(--verdict-action-required)]",
    icon: "TriangleAlert",
    pill: "soft",
  },
  review: {
    cssVar: "--verdict-review",
    text: "text-[color:var(--verdict-review)]",
    soft: "bg-[color:var(--amber-soft)]",
    border: "border-[color:var(--verdict-review)]",
    dot: "bg-[color:var(--verdict-review)]",
    tick: "bg-[color:var(--verdict-review)]",
    icon: "Eye",
    pill: "soft",
  },
  update_citation: {
    cssVar: "--verdict-update-citation",
    text: "text-[color:var(--verdict-update-citation)]",
    soft: "bg-[color:var(--surface-muted)]",
    border: "border-[color:var(--verdict-update-citation)]",
    dot: "bg-[color:var(--verdict-update-citation)]",
    tick: "bg-[color:var(--verdict-update-citation)]",
    icon: "Quote",
    pill: "muted",
  },
  optional_relaxed: {
    cssVar: "--verdict-optional-relaxed",
    text: "text-[color:var(--verdict-optional-relaxed)]",
    soft: "bg-[color:var(--surface)]",
    border: "border-[color:var(--verdict-optional-relaxed)]",
    dot: "bg-[color:var(--verdict-optional-relaxed)]",
    tick: "bg-[color:var(--verdict-optional-relaxed)]",
    icon: "ArrowDownRight",
    pill: "outline",
  },
  info: {
    cssVar: "--verdict-info",
    text: "text-[color:var(--verdict-info)]",
    soft: "bg-[color:var(--surface-muted)]",
    border: "border-[color:var(--verdict-info)]",
    dot: "bg-[color:var(--verdict-info)]",
    tick: "bg-[color:var(--verdict-info)]",
    icon: "Info",
    pill: "muted",
  },
  cleared: {
    cssVar: "--state-cleared",
    text: "text-[color:var(--state-cleared)]",
    soft: "bg-[color:var(--green-soft)]",
    border: "border-[color:var(--state-cleared)]",
    dot: "bg-[color:var(--state-cleared)]",
    tick: "bg-[color:var(--state-cleared)]",
    icon: "Check",
    pill: "soft",
  },
  noise: {
    cssVar: "--noise",
    text: "text-[color:var(--ink-3)]",
    // Hatched fill is drawn by the .noise-hatch utility (spec §17.6); never a solid color.
    soft: "noise-hatch",
    border: "border-[color:var(--border-strong)]",
    dot: "bg-[color:var(--ink-4)]",
    tick: "bg-[color:var(--ink-4)]",
    icon: "Minus",
    pill: "hatch",
  },
};

export function verdictToken(key: TokenKey): VerdictToken {
  return VERDICT_TOKENS[key];
}

/** Worst-first order used for sorting and "worst verdict" roll-ups. */
export const VERDICT_SEVERITY_ORDER: readonly Verdict[] = [
  "action_required",
  "review",
  "update_citation",
  "optional_relaxed",
  "info",
];

export const MATCH_PATH_ICONS: Record<MatchPath, string> = {
  direct_section: "Link",
  direct_rule: "Book",
  register_hop: "GitBranch",
  value_echo: "Repeat",
};

/** Diff marks: always paired with strikethrough / underline by the component. */
export const DIFF_TOKENS = {
  delete: "text-[color:var(--red)] bg-[color:var(--red-soft)] line-through",
  insert: "text-[color:var(--green)] bg-[color:var(--green-soft)] underline",
} as const;

/** Simulated mode: ink hatch plus a tag, never amber. */
export const SIMULATED_TOKEN = {
  cssVar: "--simulated",
  soft: "simulated-hatch",
  text: "text-[color:var(--ink-2)]",
  border: "border-[color:var(--border-strong)]",
} as const;

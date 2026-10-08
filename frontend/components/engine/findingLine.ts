import type { Finding } from "@/lib/api/schemas";
import { findingSentenceSegments, type Segment } from "@/lib/sentences";

/** From/to texts longer than this are paragraphs, not values: do not splice them into a sentence. */
export const SHORT_TEXT = 70;

/** Collapse whitespace and a stray double full stop ("text..") to one; keeps real ellipses. */
export function cleanRationale(text: string | null | undefined): string {
  return (text ?? "").trim().replace(/\s+/g, " ").replace(/(?<!\.)\.\.(?!\.)/g, ".");
}

/** First sentence of a rationale, trimmed to a one-line-ish length. */
export function firstSentence(text: string, max = 170): string {
  const t = cleanRationale(text);
  const m = /^(.+?[.!?])(\s|$)/.exec(t);
  const s = m ? m[1] : t;
  return s.length > max ? `${s.slice(0, max - 1).trimEnd()}…` : s;
}

export function hasLongRequiredChange(f: Pick<Finding, "required_change">): boolean {
  const { from_text, to_text } = f.required_change;
  return (from_text?.length ?? 0) > SHORT_TEXT || (to_text?.length ?? 0) > SHORT_TEXT;
}

/**
 * Headline sentence for a finding (§11.4). Real data can carry whole paragraphs in required_change;
 * then the rationale's first sentence reads better than "states <paragraph>; now requires <paragraph>".
 */
export function findingHeadline(
  f: Finding,
  label: string,
  change?: Parameters<typeof findingSentenceSegments>[2],
): Segment[] {
  const repealed = change?.change_class === "repealed" || /repeal/i.test(f.finding_type);
  if (!repealed && hasLongRequiredChange(f)) {
    return f.rationale.trim()
      ? [{ text: label, strong: true }, { text: ` — ${firstSentence(f.rationale)}` }]
      : [{ text: label, strong: true }, { text: " is out of line with " }, { text: f.citation, strong: true }, { text: "." }];
  }
  return findingSentenceSegments(f, label, change);
}

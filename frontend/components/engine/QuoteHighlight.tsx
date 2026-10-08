import * as React from "react";
import { verdictToken, type TokenKey } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";

export type QuoteInput = string | { text: string; span?: [number, number] | null } | null | undefined;

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Locate a quote inside `text`. Order: the span (if valid and, when quote text is known, matching it),
 * exact search, then whitespace/case-tolerant search. Returns null when there is nothing to highlight
 * (an empty-string quote means "no quote").
 */
export function resolveQuoteRange(text: string, quote?: QuoteInput, span?: [number, number] | null): [number, number] | null {
  let q: string | undefined;
  let sp = span ?? null;
  if (typeof quote === "string") q = quote;
  else if (quote) {
    q = quote.text;
    sp = sp ?? quote.span ?? null;
  }
  if (q === "") return null;
  const valid = (s: [number, number] | null) => !!s && Number.isInteger(s[0]) && Number.isInteger(s[1]) && s[0] >= 0 && s[1] > s[0] && s[1] <= text.length;
  if (valid(sp)) {
    if (q === undefined || text.slice(sp![0], sp![1]) === q) return [sp![0], sp![1]];
  }
  if (q === undefined || !q.trim()) return null;
  const exact = text.indexOf(q);
  if (exact >= 0) return [exact, exact + q.length];
  const pattern = escapeRegExp(q.trim()).replace(/\s+/g, "\\s+");
  const m = new RegExp(pattern, "i").exec(text);
  if (m) return [m.index, m.index + m[0].length];
  return null;
}

export interface QuoteHighlightProps {
  /** The full body text. */
  text: string;
  /** Quote to highlight: a string, or a finding quote `{ text, span? }`. "" / null / undefined => plain text. */
  quote?: QuoteInput;
  /** Character span into `text` (wins over `quote.span`; used alone when no quote text is known). */
  span?: [number, number] | null;
  /** Verdict token colouring the highlight. Omit for a neutral highlight. */
  token?: TokenKey;
  /** id of the element explaining the highlight; set as aria-describedby on the <mark>. */
  describedBy?: string;
  className?: string;
}

/** Renders `text` with the matching words highlighted (span first, then text search). Always plain when there is no quote. */
export function QuoteHighlight({ text, quote, span, token, describedBy, className }: QuoteHighlightProps) {
  const range = resolveQuoteRange(text, quote, span);
  if (!range) return <span className={className}>{text}</span>;
  const tok = token ? verdictToken(token) : null;
  return (
    <span className={className}>
      {text.slice(0, range[0])}
      <mark
        data-quote-highlight=""
        aria-describedby={describedBy}
        className={cn(
          "rounded-[3px] border-b-2 px-0.5 text-inherit [box-decoration-break:clone]",
          tok ? cn(tok.soft === "noise-hatch" ? "bg-surface-muted" : tok.soft, tok.border) : "border-ink-3 bg-surface-muted",
          token === "optional_relaxed" && "bg-surface-muted",
        )}
      >
        {text.slice(range[0], range[1])}
      </mark>
      {text.slice(range[1])}
    </span>
  );
}

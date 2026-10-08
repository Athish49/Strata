import * as React from "react";
import { verdictToken, type TokenKey } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";

/** A character range into the clause's raw `text_raw` (end exclusive) with the verdict token that colours it. */
export interface Highlight {
  range: [number, number];
  token: TokenKey;
  /** id of the element that explains the highlight (aria-describedby). */
  describedBy?: string;
}

interface Line {
  text: string;
  start: number;
}

export type MdBlock =
  | { type: "p"; lines: Line[] }
  | { type: "h"; level: number; line: Line }
  | { type: "hr" }
  | { type: "list"; ordered: boolean; items: Line[] }
  | { type: "quote"; lines: Line[] }
  | { type: "table"; header: Line[] | null; rows: Line[][] };

const SEPARATOR_ROW = /^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/;

function splitRow(text: string, start: number): Line[] {
  // text starts with "|" (after trim). Cells are between pipes; keep offsets into the raw text.
  const cells: Line[] = [];
  let i = text.indexOf("|") + 1;
  let from = i;
  for (; i <= text.length; i++) {
    if (i === text.length || text[i] === "|") {
      if (i === text.length && text.slice(from).trim() === "") break;
      const raw = text.slice(from, i);
      const lead = raw.length - raw.trimStart().length;
      cells.push({ text: raw.trim(), start: start + from + lead });
      from = i + 1;
    }
  }
  return cells;
}

/** Minimal markdown block parser that keeps raw offsets so quote spans survive formatting. */
export function parseBlocks(raw: string): MdBlock[] {
  const blocks: MdBlock[] = [];
  const lines: Line[] = [];
  let off = 0;
  for (const l of raw.split("\n")) {
    lines.push({ text: l.replace(/\s+$/, ""), start: off });
    off += l.length + 1;
  }
  let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    const t = ln.text.trim();
    if (t === "") {
      i++;
      continue;
    }
    const lead = ln.text.length - ln.text.trimStart().length;
    const at = (text: string, extra = 0): Line => ({ text, start: ln.start + lead + extra });
    const h = /^(#{1,6})\s+(.*)$/.exec(t);
    if (h) {
      blocks.push({ type: "h", level: h[1].length, line: at(h[2], h[1].length + 1) });
      i++;
      continue;
    }
    if (/^(-{3,}|\*{3,})$/.test(t)) {
      blocks.push({ type: "hr" });
      i++;
      continue;
    }
    if (t.startsWith("|")) {
      const rows: Line[][] = [];
      let header: Line[] | null = null;
      while (i < lines.length && lines[i].text.trim().startsWith("|")) {
        const row = lines[i].text.trim();
        const rowLead = lines[i].text.length - lines[i].text.trimStart().length;
        if (SEPARATOR_ROW.test(row)) {
          if (rows.length === 1 && !header) header = rows.pop() ?? null;
        } else {
          rows.push(splitRow(row, lines[i].start + rowLead));
        }
        i++;
      }
      blocks.push({ type: "table", header, rows });
      continue;
    }
    const li = /^([-*•]|\d+[.)])\s+/.exec(t);
    if (li) {
      const ordered = /\d/.test(li[1]);
      const items: Line[] = [];
      while (i < lines.length) {
        const cur = lines[i];
        const ct = cur.text.trim();
        const m = /^([-*•]|\d+[.)])\s+/.exec(ct);
        if (!m) break;
        const cl = cur.text.length - cur.text.trimStart().length;
        items.push({ text: ct.slice(m[0].length), start: cur.start + cl + m[0].length });
        i++;
      }
      blocks.push({ type: "list", ordered, items });
      continue;
    }
    if (t.startsWith(">")) {
      const q: Line[] = [];
      while (i < lines.length && lines[i].text.trim().startsWith(">")) {
        const cur = lines[i];
        const cl = cur.text.length - cur.text.trimStart().length;
        const body = cur.text.trim().replace(/^>\s?/, "");
        q.push({ text: body, start: cur.start + cl + (cur.text.trim().length - body.length) });
        i++;
      }
      blocks.push({ type: "quote", lines: q });
      continue;
    }
    const p: Line[] = [];
    while (i < lines.length) {
      const cur = lines[i];
      const ct = cur.text.trim();
      if (ct === "" || /^(#{1,6}\s|\||>|-{3,}$|([-*•]|\d+[.)])\s)/.test(ct)) break;
      const cl = cur.text.length - cur.text.trimStart().length;
      p.push({ text: ct, start: cur.start + cl });
      i++;
    }
    if (p.length === 0) {
      i++;
      continue;
    }
    blocks.push({ type: "p", lines: p });
  }
  return blocks;
}

/** True when `raw` has no visible content (whitespace, rules and blank form lines only). */
export function isBlankText(raw: string): boolean {
  return raw.replace(/[\s\-_*|:]/g, "") === "";
}

const INLINE = /\*\*(.+?)\*\*|(?<![*\w])\*(?!\s)(.+?)(?<!\s)\*(?![*\w])|_{3,}/g;

interface Piece {
  s: number;
  e: number;
  kind: "plain" | "bold" | "italic" | "blank";
}

function pieces(text: string, base: number): Piece[] {
  const out: Piece[] = [];
  let last = 0;
  INLINE.lastIndex = 0;
  let m: RegExpExecArray | null;
  while ((m = INLINE.exec(text))) {
    if (m.index > last) out.push({ s: base + last, e: base + m.index, kind: "plain" });
    if (m[1] !== undefined) out.push({ s: base + m.index + 2, e: base + m.index + 2 + m[1].length, kind: "bold" });
    else if (m[2] !== undefined) out.push({ s: base + m.index + 1, e: base + m.index + 1 + m[2].length, kind: "italic" });
    else out.push({ s: base + m.index, e: base + m.index + m[0].length, kind: "blank" });
    last = m.index + m[0].length;
  }
  if (last < text.length) out.push({ s: base + last, e: base + text.length, kind: "plain" });
  return out;
}

export function markClass(token: TokenKey): string {
  const tok = verdictToken(token);
  return cn(
    "rounded-[3px] border-b-2 px-0.5 text-inherit [box-decoration-break:clone]",
    tok.soft === "noise-hatch" || token === "optional_relaxed" ? "bg-surface-muted" : tok.soft,
    tok.border,
  );
}

/** Renders one line of inline markdown. `base` is the raw offset of `text[0]`; highlights are in raw offsets. */
export function Inline({ text, base = 0, highlights = [] }: { text: string; base?: number; highlights?: Highlight[] }) {
  const parts = pieces(text, base);
  return (
    <>
      {parts.map((p, idx) => {
        if (p.kind === "blank") {
          return <span key={idx} aria-hidden className="inline-block h-[1em] min-w-[9rem] translate-y-[2px] border-b border-ink-4" />;
        }
        const raw = text.slice(p.s - base, p.e - base);
        const cuts = new Set<number>([p.s, p.e]);
        for (const h of highlights) {
          for (const x of h.range) if (x > p.s && x < p.e) cuts.add(x);
        }
        const sorted = [...cuts].sort((a, b) => a - b);
        const segs = sorted.slice(0, -1).map((a, k) => {
          const b = sorted[k + 1];
          const h = highlights.find((hh) => hh.range[0] <= a && hh.range[1] >= b);
          const str = raw.slice(a - p.s, b - p.s);
          return h ? (
            <mark key={a} data-quote-highlight="" aria-describedby={h.describedBy} className={markClass(h.token)}>
              {str}
            </mark>
          ) : (
            <React.Fragment key={a}>{str}</React.Fragment>
          );
        });
        if (p.kind === "bold") return <strong key={idx} className="font-semibold">{segs}</strong>;
        if (p.kind === "italic") return <em key={idx}>{segs}</em>;
        return <React.Fragment key={idx}>{segs}</React.Fragment>;
      })}
    </>
  );
}

const HEADING_CLASS = [
  "",
  "font-serif text-[22px] leading-[30px] mt-2",
  "font-serif text-[19px] leading-[26px] mt-2",
  "text-[15px] font-semibold leading-6 mt-1",
  "text-[15px] font-semibold leading-6 mt-1",
  "text-[14px] font-semibold leading-6",
  "text-[14px] font-semibold leading-6",
];

/** Block-level markdown with quote highlighting by raw offset. `variant="form"` renders tables as form fields. */
export function MarkdownText({
  raw,
  highlights = [],
  variant = "prose",
  className,
}: {
  raw: string;
  highlights?: Highlight[];
  variant?: "prose" | "form";
  className?: string;
}) {
  const blocks = React.useMemo(() => parseBlocks(raw), [raw]);
  return (
    <div className={cn("space-y-3", className)}>
      {blocks.map((b, i) => {
        switch (b.type) {
          case "h":
            return (
              <p key={i} role="heading" aria-level={Math.min(6, b.level + 2)} className={cn("text-ink", HEADING_CLASS[b.level])}>
                <Inline text={b.line.text} base={b.line.start} highlights={highlights} />
              </p>
            );
          case "hr":
            return <hr key={i} className="border-border" />;
          case "list": {
            const L = b.ordered ? "ol" : "ul";
            return (
              <L key={i} className={cn("space-y-1 pl-5", b.ordered ? "list-decimal" : "list-disc")}>
                {b.items.map((it, k) => (
                  <li key={k}>
                    <Inline text={it.text} base={it.start} highlights={highlights} />
                  </li>
                ))}
              </L>
            );
          }
          case "quote":
            return (
              <blockquote key={i} className="border-l-2 border-border-strong pl-3 text-ink-2">
                {b.lines.map((l, k) => (
                  <p key={k}>
                    <Inline text={l.text} base={l.start} highlights={highlights} />
                  </p>
                ))}
              </blockquote>
            );
          case "table":
            return variant === "form" ? (
              <FormRows key={i} block={b} highlights={highlights} />
            ) : (
              <div key={i} className="overflow-x-auto">
                <table className="w-full border-collapse text-[14px] leading-5">
                  {b.header && (
                    <thead>
                      <tr>
                        {b.header.map((c, k) => (
                          <th key={k} className="border border-border bg-surface-muted px-2.5 py-1.5 text-left font-sans text-[12px] font-medium text-ink-3">
                            <Inline text={c.text} base={c.start} highlights={highlights} />
                          </th>
                        ))}
                      </tr>
                    </thead>
                  )}
                  <tbody>
                    {b.rows.map((r, k) => (
                      <tr key={k}>
                        {r.map((c, j) => (
                          <td key={j} className={cn("border border-border px-2.5 py-1.5 align-top", c.text.length <= 12 && "whitespace-nowrap")}>
                            <Inline text={c.text} base={c.start} highlights={highlights} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          default:
            return (
              <p key={i}>
                {b.lines.map((l, k) => (
                  <React.Fragment key={k}>
                    {k > 0 && <br />}
                    <Inline text={l.text} base={l.start} highlights={highlights} />
                  </React.Fragment>
                ))}
              </p>
            );
        }
      })}
    </div>
  );
}

/** A table whose rows are "label | value" pairs, drawn like fields of a printed form. */
function FormRows({ block, highlights }: { block: Extract<MdBlock, { type: "table" }>; highlights: Highlight[] }) {
  const rows = block.header && block.header.some((c) => c.text && !/^field$/i.test(c.text) && !/^value$/i.test(c.text)) ? [block.header, ...block.rows] : block.rows;
  return (
    <dl className="divide-y divide-border border-y border-border">
      {rows.map((r, k) => (
        <div key={k} className="grid grid-cols-[minmax(0,2fr)_minmax(0,3fr)] gap-4 py-2">
          <dt className="text-[14px] leading-5 text-ink-2">
            <Inline text={r[0]?.text ?? ""} base={r[0]?.start ?? 0} highlights={highlights} />
          </dt>
          <dd className="min-w-0 text-[15px] leading-6">
            {r.slice(1).map((c, j) => (
              <span key={j} className="mr-3">
                <Inline text={c.text} base={c.start} highlights={highlights} />
              </span>
            ))}
          </dd>
        </div>
      ))}
    </dl>
  );
}

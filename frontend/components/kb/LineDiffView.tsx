"use client";
import * as React from "react";
import { diffWords } from "diff";
import type { LineDiff } from "@/lib/api/schemas";
import { formatCount } from "@/lib/format";

export interface Seg {
  op: "equal" | "delete" | "insert";
  text: string;
}

/** Word-level diff of two lines. Used for paired delete/insert lines so single-paragraph sections stay readable. */
export function wordSegments(a: string, b: string): Seg[] {
  return diffWords(a, b).map((p) => ({ op: p.added ? "insert" : p.removed ? "delete" : "equal", text: p.value }));
}

export type Block =
  | { kind: "equal"; lines: string[] }
  | { kind: "change"; deletes: string[]; inserts: string[] }
  | { kind: "skip"; count: number };

/** Group a line diff into change blocks, collapsing unchanged runs longer than 2*context+1 lines. */
export function buildBlocks(diff: LineDiff, context = 2): Block[] {
  const raw: Block[] = [];
  let i = 0;
  while (i < diff.length) {
    if (diff[i].op === "equal") {
      const lines: string[] = [];
      while (i < diff.length && diff[i].op === "equal") lines.push(diff[i++].line);
      raw.push({ kind: "equal", lines });
    } else {
      const deletes: string[] = [];
      const inserts: string[] = [];
      while (i < diff.length && diff[i].op !== "equal") {
        (diff[i].op === "delete" ? deletes : inserts).push(diff[i].line);
        i++;
      }
      raw.push({ kind: "change", deletes, inserts });
    }
  }
  const out: Block[] = [];
  raw.forEach((b, idx) => {
    if (b.kind !== "equal") return void out.push(b);
    const first = idx === 0;
    const last = idx === raw.length - 1;
    const keepHead = first ? 0 : context;
    const keepTail = last ? 0 : context;
    if (b.lines.length <= keepHead + keepTail + 1) return void out.push(b);
    if (keepHead) out.push({ kind: "equal", lines: b.lines.slice(0, keepHead) });
    out.push({ kind: "skip", count: b.lines.length - keepHead - keepTail });
    if (keepTail) out.push({ kind: "equal", lines: b.lines.slice(b.lines.length - keepTail) });
  });
  return out;
}

const HEAD = 110;
const LONG = 300;

function Segments({ segs }: { segs: Seg[] }) {
  return (
    <>
      {segs.map((s, i) => {
        if (s.op === "equal") {
          if (s.text.length > LONG) {
            const hidden = s.text.length - 2 * HEAD;
            return (
              <React.Fragment key={i}>
                {s.text.slice(0, HEAD)}
                <span className="mx-1 rounded-[4px] bg-surface-muted px-1.5 font-sans text-[12px] text-ink-3">
                  … {formatCount(hidden)} unchanged characters …
                </span>
                {s.text.slice(-HEAD)}
              </React.Fragment>
            );
          }
          return <React.Fragment key={i}>{s.text}</React.Fragment>;
        }
        return s.op === "delete" ? (
          <del key={i} className="bg-red-soft text-red line-through decoration-1">
            {s.text}
          </del>
        ) : (
          <ins key={i} className="bg-green-soft text-green underline decoration-1 underline-offset-2">
            {s.text}
          </ins>
        );
      })}
    </>
  );
}

function ChangeBlock({ deletes, inserts }: { deletes: string[]; inserts: string[] }) {
  const n = Math.max(deletes.length, inserts.length);
  return (
    <div className="space-y-1.5 border-l-2 border-border-strong pl-3">
      {Array.from({ length: n }, (_, i) => {
        const a = deletes[i];
        const b = inserts[i];
        const segs: Seg[] =
          a !== undefined && b !== undefined
            ? wordSegments(a, b)
            : a !== undefined
              ? [{ op: "delete", text: a }]
              : [{ op: "insert", text: b ?? "" }];
        return (
          <p key={i} className="font-serif text-[15px] leading-6 text-ink">
            <Segments segs={segs} />
          </p>
        );
      })}
    </div>
  );
}

/**
 * Line diff of two snapshots, redline style: deletions struck through, insertions underlined (never
 * colour alone). Paired lines get word-level marks; long unchanged runs collapse.
 */
export function LineDiffView({ diff }: { diff: LineDiff }) {
  const blocks = React.useMemo(() => buildBlocks(diff), [diff]);
  return (
    <div className="space-y-3" data-testid="line-diff">
      {blocks.map((b, i) =>
        b.kind === "skip" ? (
          <div key={i} className="text-[12px] text-ink-3">
            … {formatCount(b.count)} unchanged {b.count === 1 ? "line" : "lines"} …
          </div>
        ) : b.kind === "equal" ? (
          <p key={i} className="line-clamp-3 font-serif text-[15px] leading-6 text-ink-3">
            {b.lines.join(" ")}
          </p>
        ) : (
          <ChangeBlock key={i} deletes={b.deletes} inserts={b.inserts} />
        ),
      )}
    </div>
  );
}

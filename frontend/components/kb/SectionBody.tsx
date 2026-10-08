"use client";
import * as React from "react";
import { Button } from "@/components/ui/button";
import { formatCount } from "@/lib/format";

const PREVIEW_CHARS = 6000;
const CHUNK = 1400;

/** Split text into readable paragraphs: on blank lines/newlines, then long runs at a sentence boundary. */
export function toParagraphs(text: string): string[] {
  const out: string[] = [];
  for (const block of text.split(/\n+/)) {
    let rest = block.trim();
    while (rest.length > CHUNK * 1.4) {
      const window = rest.slice(CHUNK * 0.6, CHUNK * 1.4);
      const m = /[.;:]\s+(?=\(?[A-Z0-9(])/.exec(window);
      const cut = m ? CHUNK * 0.6 + m.index + 1 : CHUNK;
      out.push(rest.slice(0, cut).trim());
      rest = rest.slice(cut).trim();
    }
    if (rest) out.push(rest);
  }
  return out;
}

/** Full section text in the document serif; bodies reach ~150k characters, so long ones start collapsed. */
export function SectionBody({ text }: { text: string }) {
  const [full, setFull] = React.useState(false);
  const long = text.length > PREVIEW_CHARS;
  const shown = full || !long ? text : text.slice(0, PREVIEW_CHARS);
  const paras = React.useMemo(() => toParagraphs(shown), [shown]);
  return (
    <div>
      <div className="max-w-[72ch] space-y-4 font-serif text-[16px] leading-[26px] text-ink">
        {paras.map((p, i) => (
          <p key={i}>{p}</p>
        ))}
        {long && !full && <p className="text-ink-3">…</p>}
      </div>
      {long && (
        <Button variant="secondary" size="sm" className="mt-4" onClick={() => setFull((f) => !f)}>
          {full ? "Collapse text" : `Show full text (${formatCount(text.length)} characters)`}
        </Button>
      )}
    </div>
  );
}

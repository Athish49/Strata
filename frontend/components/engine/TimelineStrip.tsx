import { Fragment } from "react";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface TimelinePoint {
  key: string;
  /** e.g. "S1 snapshot", "Published", "Document approved". */
  label: string;
  /** ISO date; null / undefined renders "Not recorded". */
  date: string | null | undefined;
  /** Small extra line, e.g. "DIN 20250205-IR-170" or the date basis. */
  detail?: string | null;
  /** Mono detail (ids). */
  mono?: boolean;
}

export interface TimelineStripProps {
  points: TimelinePoint[];
  /** Caption under the strip, e.g. "This document was approved on {date}, after the rule change was published on {date}." */
  caption?: string;
  className?: string;
}

/** Horizontal dated strip: 8px ink nodes joined by a hairline. Used for S1 → published → S2 and rule published → doc approved. */
export function TimelineStrip({ points, caption, className }: TimelineStripProps) {
  return (
    <figure className={cn("space-y-2", className)}>
      <ol className="flex items-start">
        {points.map((p, i) => (
          <Fragment key={p.key}>
            <li className="min-w-0 max-w-[220px] shrink-0">
              <div className="flex items-center">
                <span aria-hidden className="size-2 shrink-0 rounded-full bg-ink" />
              </div>
              <div className="mt-1.5 text-[12px] font-medium leading-4 text-ink-3">{p.label}</div>
              <div className="text-[13px] leading-[18px] text-ink">{p.date ? formatDate(p.date) : <span className="text-ink-3">Not recorded</span>}</div>
              {p.detail ? <div className={cn("truncate text-[12px] leading-4 text-ink-3", p.mono && "font-mono")}>{p.detail}</div> : null}
            </li>
            {i < points.length - 1 && <li aria-hidden className="mt-[3px] h-px min-w-6 flex-1 bg-border-strong" />}
          </Fragment>
        ))}
      </ol>
      {caption && <figcaption className="text-[13px] text-ink-2">{caption}</figcaption>}
    </figure>
  );
}

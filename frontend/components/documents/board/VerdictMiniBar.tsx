import { verdictLabel } from "@/lib/labels";
import { verdictToken } from "@/lib/verdict-tokens";
import { verdictSegments } from "./logic";
import { cn } from "@/lib/utils";

/** Counts per verdict as a hairline segmented bar plus text; renders nothing when there are no findings. */
export function VerdictMiniBar({ counts, className }: { counts?: Record<string, number>; className?: string }) {
  const segs = verdictSegments(counts);
  if (segs.length === 0) return null;
  const total = segs.reduce((n, s) => n + s.count, 0);
  return (
    <div className={cn("space-y-1.5", className)}>
      <div className="flex h-1.5 w-full gap-px overflow-hidden rounded-full bg-surface-muted" aria-hidden>
        {segs.map((s) => (
          <span key={s.verdict} className={verdictToken(s.verdict).tick} style={{ width: `${(s.count / total) * 100}%` }} />
        ))}
      </div>
      <ul className="flex flex-wrap gap-x-3 gap-y-0.5 text-[12px] leading-4 text-ink-3">
        {segs.map((s) => (
          <li key={s.verdict} className="inline-flex items-center gap-1.5">
            <span aria-hidden className={cn("size-1.5 rounded-full", verdictToken(s.verdict).dot)} />
            <span className="tabular-nums text-ink-2">{s.count}</span> {verdictLabel(s.verdict).toLowerCase()}
          </li>
        ))}
      </ul>
    </div>
  );
}

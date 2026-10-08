import { Check, X } from "lucide-react";
import { formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface ScoreFigureProps {
  /** e.g. "Precision". */
  label: string;
  /** Measured value (ratio 0..1). */
  value: number;
  /** Target value from `score.targets`. */
  target: number;
  /** "min": pass when value >= target (precision, recall, routing). "max": pass when value <= target (false-positive rate). */
  goal?: "min" | "max";
  /** "ratio" (0.86, default) or "percent" (86%). */
  format?: "ratio" | "percent";
  /** Hide the pass/fail mark (e.g. what-if runs). */
  hideStatus?: boolean;
  className?: string;
}

const fmt = (v: number, f: "ratio" | "percent") => (f === "percent" ? formatPercent(v, 0) : Number.isInteger(v) ? String(v) : v.toFixed(2));

/** Big serif figure with its target and a pass/fail mark (text + icon, never colour-only). */
export function ScoreFigure({ label, value, target, goal = "min", format = "ratio", hideStatus, className }: ScoreFigureProps) {
  const pass = goal === "min" ? value >= target : value <= target;
  return (
    <div className={cn("min-w-0", className)} data-pass={pass ? "true" : "false"}>
      <div className="text-[12px] font-medium leading-4 text-ink-3">{label}</div>
      <div className="mt-1 font-serif text-[48px] font-normal leading-[52px] tracking-[-0.01em] text-ink">{fmt(value, format)}</div>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 text-[13px] text-ink-3">
        <span>
          Target {goal === "min" ? "≥" : "≤"} {fmt(target, format)}
        </span>
        {!hideStatus && (
          <span className={cn("inline-flex items-center gap-1 font-medium", pass ? "text-green" : "text-red")}>
            {pass ? <Check aria-hidden className="size-3.5" strokeWidth={2} /> : <X aria-hidden className="size-3.5" strokeWidth={2} />}
            {pass ? "Meets target" : "Misses target"}
          </span>
        )}
      </div>
    </div>
  );
}

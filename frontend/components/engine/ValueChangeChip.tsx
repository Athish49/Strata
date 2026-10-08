import { ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";

export interface ValueChangeChipProps {
  /** Shape of `characterization.value_changes[]`. */
  change: { label?: string | null; old: string; new: string; unit?: string | null };
  /** "neutral" (default) or "diff" (old in red strikethrough, new in green). */
  tone?: "neutral" | "diff";
  /** Show the label ("Notice period") before the values. Default true. */
  showLabel?: boolean;
  className?: string;
}

/** `10 → 14 business days`, with the value label first when known. */
export function ValueChangeChip({ change, tone = "neutral", showLabel = true, className }: ValueChangeChipProps) {
  const diff = tone === "diff";
  return (
    <span
      className={cn("inline-flex min-h-[22px] max-w-full items-center gap-1.5 rounded-[6px] border border-border-strong bg-surface px-2 py-0.5 text-[12px] text-ink-2", className)}
    >
      {showLabel && change.label ? <span className="text-ink-3">{change.label}</span> : null}
      <span className={cn("font-mono text-[12px]", diff && "rounded-[3px] bg-red-soft px-1 text-red line-through")}>{change.old}</span>
      <ArrowRight aria-label="changed to" className="size-3 shrink-0 text-ink-3" strokeWidth={1.75} />
      <span className={cn("font-mono text-[12px] font-medium text-ink", diff && "rounded-[3px] bg-green-soft px-1 text-green underline")}>
        {change.new}
      </span>
      {change.unit ? <span className="text-ink-3">{change.unit}</span> : null}
    </span>
  );
}

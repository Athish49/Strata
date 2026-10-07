import { ArrowDownRight, ArrowUpRight } from "lucide-react";
import { cn } from "@/lib/utils";

/** Big serif figure (48/52) with an optional delta. `tone` colors only the figure (e.g. green for cleared). */
export function StatTile({
  figure,
  caption,
  delta,
  deltaTone = "neutral",
  tone = "ink",
  className,
}: {
  figure: React.ReactNode;
  caption?: React.ReactNode;
  /** e.g. "5%"; arrow direction comes from deltaDirection. */
  delta?: string;
  deltaTone?: "positive" | "negative" | "neutral";
  tone?: "ink" | "green" | "red";
  className?: string;
}) {
  const Arrow = deltaTone === "negative" ? ArrowDownRight : ArrowUpRight;
  return (
    <div className={cn("min-w-0", className)}>
      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            "font-serif text-[48px] font-normal leading-[52px] tracking-[-0.01em]",
            tone === "green" ? "text-green" : tone === "red" ? "text-red" : "text-ink",
          )}
        >
          {figure}
        </span>
        {delta && (
          <span
            className={cn(
              "inline-flex items-center gap-0.5 text-[13px] font-medium",
              deltaTone === "positive" ? "text-green" : deltaTone === "negative" ? "text-red" : "text-ink-3",
            )}
          >
            <Arrow className="size-3.5" strokeWidth={1.5} />
            {delta}
          </span>
        )}
      </div>
      {caption && <div className="mt-1 text-[14px] leading-5 text-ink-3">{caption}</div>}
    </div>
  );
}

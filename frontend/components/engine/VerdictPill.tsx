import type { VerdictOrCleared } from "@/lib/labels";
import { verdictLabel } from "@/lib/labels";
import { verdictToken } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";
import { NamedIcon } from "./icons";

export interface VerdictPillProps {
  /** A verdict, or "cleared" for a cleared candidate. */
  verdict: VerdictOrCleared;
  /** "md" = h-22 pill (default); "sm" = compact h-18 for dense rows. */
  size?: "md" | "sm";
  /** Hide the leading icon (the text always carries the meaning). */
  hideIcon?: boolean;
  className?: string;
}

/** One pill for every verdict (and "cleared"): label + the single verdict token. Never colour-only. */
export function VerdictPill({ verdict, size = "md", hideIcon, className }: VerdictPillProps) {
  const tok = verdictToken(verdict);
  return (
    <span
      data-verdict={verdict}
      className={cn(
        "inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-[6px] font-medium",
        size === "sm" ? "h-[18px] px-1.5 text-[11px]" : "h-[22px] px-2 text-[12px]",
        tok.soft,
        tok.text,
        tok.pill === "outline" && "border border-border-strong",
        className,
      )}
    >
      {!hideIcon && <NamedIcon name={tok.icon} aria-hidden className={size === "sm" ? "size-3" : "size-3.5"} strokeWidth={1.75} />}
      {verdictLabel(verdict)}
    </span>
  );
}

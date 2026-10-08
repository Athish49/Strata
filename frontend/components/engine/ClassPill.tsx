import type { ChangeClass } from "@/lib/api/schemas";
import { changeClassLabel, isNoiseClass } from "@/lib/labels";
import { verdictToken } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";

export interface ClassPillProps {
  /** The change class (real or noise). */
  changeClass: ChangeClass;
  className?: string;
}

/** Change class label. Noise classes render as a hatched tag (never a solid colour); real classes as a neutral pill. */
export function ClassPill({ changeClass, className }: ClassPillProps) {
  const noise = isNoiseClass(changeClass);
  const tok = verdictToken("noise");
  return (
    <span
      data-class={changeClass}
      data-noise={noise ? "true" : undefined}
      className={cn(
        "inline-flex shrink-0 items-center whitespace-nowrap font-medium",
        noise
          ? cn("h-[18px] rounded-[4px] border px-1.5 text-[11px] leading-none", tok.border, tok.text, "bg-surface")
          : "h-[22px] rounded-[6px] bg-surface-muted px-2 text-[12px] text-ink-2",
        className,
      )}
    >
      {noise && <span aria-hidden className={cn("mr-1 inline-block h-2.5 w-2.5 rounded-[2px] border border-border-strong", tok.soft)} />}
      {changeClassLabel(changeClass)}
    </span>
  );
}

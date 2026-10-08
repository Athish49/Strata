import type { Direction } from "@/lib/api/schemas";
import { directionLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { NamedIcon } from "./icons";

const ICONS: Record<Direction, string> = {
  tightened: "ArrowUp",
  relaxed: "ArrowDown",
  new_requirement: "Plus",
  removed: "Minus",
  clarified: "Info",
  style_only: "Type",
  mixed: "ArrowUpDown",
};

export interface DirectionChipProps {
  /** Null / undefined (uncharacterized change) renders nothing. */
  direction: Direction | null | undefined;
  className?: string;
}

/** Direction of a change (tightened, relaxed, new requirement, removed, clarified, style only, mixed). Neutral. */
export function DirectionChip({ direction, className }: DirectionChipProps) {
  if (!direction) return null;
  return (
    <span
      data-direction={direction}
      className={cn("inline-flex h-[22px] items-center gap-1 rounded-[6px] border border-border-strong bg-surface px-2 text-[12px] font-medium text-ink-2", className)}
    >
      <NamedIcon name={ICONS[direction]} aria-hidden className="size-3.5" strokeWidth={1.75} />
      {directionLabel(direction)}
    </span>
  );
}

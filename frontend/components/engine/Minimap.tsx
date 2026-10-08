import { verdictToken, type TokenKey } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";

export interface MinimapTick {
  id: string;
  /** Relative position 0..1 (ordinal / clause count). Clamped. */
  position: number;
  /** Verdict token colouring the tick. */
  token: TokenKey;
  /** Accessible / tooltip label, e.g. "§8.2 — Action required". */
  label?: string;
}

export interface MinimapProps {
  ticks: MinimapTick[];
  /** Click / Enter on a tick (scroll there). */
  onTickClick?: (id: string) => void;
  /** Highlights the current tick. */
  activeId?: string | null;
  /** Track height in px (default 240) or any CSS length. */
  height?: number | string;
  className?: string;
}

/** Slim 6px track with verdict-coloured ticks at relative positions. Ticks are keyboard-focusable buttons. */
export function Minimap({ ticks, onTickClick, activeId, height = 240, className }: MinimapProps) {
  return (
    <div role="group" aria-label="Findings minimap" className={cn("relative w-[10px] shrink-0", className)} style={{ height }}>
      <div aria-hidden className="absolute inset-y-0 left-[2px] w-[6px] rounded-[3px] bg-surface-muted" />
      {ticks.map((t) => {
        const pos = Math.min(1, Math.max(0, Number.isFinite(t.position) ? t.position : 0));
        const tok = verdictToken(t.token);
        const active = activeId === t.id;
        return (
          <button
            key={t.id}
            type="button"
            title={t.label}
            aria-label={t.label ?? "Finding"}
            aria-current={active ? "true" : undefined}
            data-tick={t.id}
            onClick={() => onTickClick?.(t.id)}
            style={{ top: `calc(${pos * 100}% - 6px)` }}
            className="group absolute left-0 grid h-3 w-[10px] place-items-center"
          >
            <span aria-hidden className={cn("block rounded-[1px]", tok.tick, active ? "h-[3px] w-[10px]" : "h-[2px] w-[8px] group-hover:h-[3px]")} />
          </button>
        );
      })}
    </div>
  );
}

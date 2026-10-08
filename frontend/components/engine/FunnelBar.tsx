import { AppLink } from "@/lib/app-link";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface FunnelBarProps {
  /** Stage label, e.g. "Substantive". */
  label: string;
  count: number;
  /** The count that fills the whole track (usually the first stage). */
  max: number;
  /** Bar texture: "ink" solid, "hairline" for large "your data" bars, "noise" hatched. Default "hairline". */
  texture?: "ink" | "hairline" | "noise";
  /** Text after the number, e.g. "substantive". Omit for none. */
  suffix?: string;
  /** Makes the whole row a link (AppLink keeps ?run=). */
  href?: string;
  className?: string;
}

/** One funnel stage: label left, proportional bar, value right. Counts come from run.stats, never hardcoded. */
export function FunnelBar({ label, count, max, texture = "hairline", suffix, href, className }: FunnelBarProps) {
  const pct = max > 0 && count > 0 ? Math.max(0.6, Math.min(100, (count / max) * 100)) : 0;
  const row = (
    <>
      <span className="w-[150px] shrink-0 truncate text-[13px] leading-[18px] text-ink-2">{label}</span>
      <span aria-hidden className="relative h-5 min-w-0 flex-1">
        <span
          data-testid="funnel-fill"
          className={cn(
            "absolute inset-y-0 left-0 block rounded-[2px] border border-ink/70",
            texture === "ink" && "bg-ink",
            texture === "hairline" && "mark-hairline",
            texture === "noise" && "mark-noise border-ink-4",
          )}
          style={{ width: `${pct}%` }}
        />
      </span>
      <span className="w-[120px] shrink-0 text-[12px] tabular-nums leading-4 text-ink-3">
        <span className="font-medium text-ink">{formatCount(count)}</span>
        {suffix ? ` ${suffix}` : ""}
      </span>
    </>
  );
  const cls = cn("flex items-center gap-3 rounded-[6px] py-1", href && "-mx-2 px-2 transition-colors hover:bg-surface-muted", className);
  return href ? (
    <AppLink href={href} className={cls}>
      {row}
    </AppLink>
  ) : (
    <div className={cls}>{row}</div>
  );
}

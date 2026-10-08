import type { Severity } from "@/lib/api/schemas";
import { severityLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

const LEVEL: Record<Severity, number> = { low: 1, medium: 2, high: 3 };

export interface SeverityMarkProps {
  severity: Severity;
  /** Prefix the label with "Severity" (default true): "Severity · High". */
  withPrefix?: boolean;
  className?: string;
}

/** Neutral three-bar severity mark with text. Severity is never a colour of its own. */
export function SeverityMark({ severity, withPrefix = true, className }: SeverityMarkProps) {
  const level = LEVEL[severity];
  return (
    <span data-severity={severity} className={cn("inline-flex items-center gap-1.5 text-[12px] font-medium text-ink-2", className)}>
      <span aria-hidden className="flex items-end gap-[2px]">
        {[1, 2, 3].map((i) => (
          <span key={i} className={cn("w-[3px] rounded-[1px]", i <= level ? "bg-ink-2" : "bg-border-strong")} style={{ height: 4 + i * 2 }} />
        ))}
      </span>
      {withPrefix ? `Severity · ${severityLabel(severity)}` : severityLabel(severity)}
    </span>
  );
}

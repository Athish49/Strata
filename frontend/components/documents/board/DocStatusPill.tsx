import type { BoardStatusKey } from "@/lib/labels";
import { DOC_STATUS_LABELS } from "@/lib/labels";
import { verdictToken, type TokenKey } from "@/lib/verdict-tokens";
import { NamedIcon } from "@/components/engine/icons";
import { cn } from "@/lib/utils";

const TOKEN: Record<BoardStatusKey, TokenKey> = {
  action_needed: "action_required",
  review: "review",
  cleared: "cleared",
  not_monitored: "noise",
  processing: "info",
  in_review: "optional_relaxed",
  ingest_failed: "action_required",
  retired: "noise",
};

/** Statuses drawn in the neutral muted style instead of their token's soft fill. */
const MUTED: ReadonlySet<BoardStatusKey> = new Set(["not_monitored", "retired"]);

/** Icon overrides where the token's verdict icon would read as a verdict. */
const ICON: Partial<Record<BoardStatusKey, string>> = {
  not_monitored: "CircleOff",
  processing: "LoaderCircle",
  in_review: "Hourglass",
  ingest_failed: "CircleX",
  retired: "Archive",
};

/**
 * Document status (§11.5): Action needed / Review / Cleared / Not monitored, plus the lifecycle
 * states Processing / In review / Ingest failed / Retired. Same tokens as verdicts.
 */
export function DocStatusPill({ status, className }: { status: BoardStatusKey; className?: string }) {
  const tok = verdictToken(TOKEN[status]);
  return (
    <span
      data-status={status}
      className={cn(
        "inline-flex h-[22px] shrink-0 items-center gap-1 whitespace-nowrap rounded-[6px] px-2 text-[12px] font-medium",
        MUTED.has(status) ? "bg-surface-muted text-ink-2" : [tok.soft, tok.text],
        tok.pill === "outline" && "border border-border-strong",
        className,
      )}
    >
      <NamedIcon name={ICON[status] ?? tok.icon} aria-hidden className="size-3.5" strokeWidth={1.75} />
      {DOC_STATUS_LABELS[status]}
    </span>
  );
}

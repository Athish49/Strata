import type { DocStatusKey } from "@/lib/labels";
import { DOC_STATUS_LABELS } from "@/lib/labels";
import { verdictToken, type TokenKey } from "@/lib/verdict-tokens";
import { NamedIcon } from "@/components/engine/icons";
import { cn } from "@/lib/utils";

const TOKEN: Record<DocStatusKey, TokenKey> = {
  action_needed: "action_required",
  review: "review",
  cleared: "cleared",
  not_monitored: "noise",
};

/** Document status (§11.5): Action needed / Review / Cleared / Not monitored. Same tokens as verdicts. */
export function DocStatusPill({ status, className }: { status: DocStatusKey; className?: string }) {
  const tok = verdictToken(TOKEN[status]);
  return (
    <span
      data-status={status}
      className={cn(
        "inline-flex h-[22px] shrink-0 items-center gap-1 whitespace-nowrap rounded-[6px] px-2 text-[12px] font-medium",
        status === "not_monitored" ? "bg-surface-muted text-ink-2" : [tok.soft, tok.text],
        tok.pill === "outline" && "border border-border-strong",
        className,
      )}
    >
      <NamedIcon name={status === "not_monitored" ? "CircleOff" : tok.icon} aria-hidden className="size-3.5" strokeWidth={1.75} />
      {DOC_STATUS_LABELS[status]}
    </span>
  );
}

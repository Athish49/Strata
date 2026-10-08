import { BadgeCheck, Cpu, ShieldAlert, TriangleAlert } from "lucide-react";
import { decidedByLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

/** AI decisions below this confidence are flagged amber. */
export const LOW_CONFIDENCE = 0.7;

export interface TrustBadgesProps {
  /** true => "Verified quote ✓"; false => "Evidence unverified — review"; undefined => hidden. */
  quotesVerified?: boolean;
  /** "Decided by rule" / "AI judgment · 82%". Hidden when undefined. */
  decidedBy?: "rule" | "ai";
  /** 0..1. May be null (live data): the AI badge then omits the percentage. */
  confidence?: number | null;
  className?: string;
}

const pill = "inline-flex h-[22px] items-center gap-1 whitespace-nowrap rounded-[6px] px-2 text-[12px] font-medium";

/** The first-class trust signals of a finding (spec §7.1). Amber only for unverified evidence / low confidence. */
export function TrustBadges({ quotesVerified, decidedBy, confidence, className }: TrustBadgesProps) {
  const lowConf = decidedBy === "ai" && typeof confidence === "number" && confidence < LOW_CONFIDENCE;
  return (
    <span className={cn("inline-flex flex-wrap items-center gap-1.5", className)}>
      {decidedBy && (
        <span data-badge="decided-by" className={cn(pill, lowConf ? "bg-amber-soft text-amber" : "bg-surface-muted text-ink-2")}>
          {lowConf ? <TriangleAlert aria-hidden className="size-3.5" strokeWidth={1.75} /> : <Cpu aria-hidden className="size-3.5" strokeWidth={1.75} />}
          {decidedByLabel(decidedBy, confidence)}
        </span>
      )}
      {quotesVerified === true && (
        <span data-badge="verified" className={cn(pill, "bg-green-soft text-green")}>
          <BadgeCheck aria-hidden className="size-3.5" strokeWidth={1.75} />
          Verified quote ✓
        </span>
      )}
      {quotesVerified === false && (
        <span data-badge="unverified" className={cn(pill, "bg-amber-soft text-amber")}>
          <ShieldAlert aria-hidden className="size-3.5" strokeWidth={1.75} />
          Evidence unverified — review
        </span>
      )}
    </span>
  );
}

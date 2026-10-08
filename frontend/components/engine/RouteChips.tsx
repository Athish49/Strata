import { ChevronRight } from "lucide-react";
import type { Person } from "@/lib/api/schemas";
import { PersonChip } from "@/components/common/PersonChip";
import { cn } from "@/lib/utils";

export interface RouteChipsProps {
  /** `finding.route` or a DocumentMeta (owner / reviewer / approver). */
  route: { owner: Person; reviewer: Person; approver?: Person | null };
  /** Documents signed by two people by design: shows "Two-signature document" when there is no approver. */
  twoSignature?: boolean;
  /** Vertical stack (narrow rails). */
  stacked?: boolean;
  className?: string;
}

function Step({ role, person }: { role: string; person: Person }) {
  return (
    <div className="min-w-0">
      <div className="text-[12px] font-medium leading-4 text-ink-3">{role}</div>
      <PersonChip name={person.name} />
      <div className="truncate pl-7 text-[12px] leading-4 text-ink-3" title={person.title}>
        {person.title}
      </div>
    </div>
  );
}

/** Owner → reviewer → approver with names and titles; "Two-signature document" instead of a missing approver. */
export function RouteChips({ route, twoSignature, stacked, className }: RouteChipsProps) {
  const steps: { role: string; person: Person }[] = [
    { role: "Owner", person: route.owner },
    { role: "Reviewer", person: route.reviewer },
  ];
  if (route.approver) steps.push({ role: "Approver", person: route.approver });
  return (
    <div className={cn("flex flex-wrap items-start gap-x-2 gap-y-3", stacked && "flex-col", className)}>
      {steps.map((s, i) => (
        <div key={s.role} className="flex items-start gap-2">
          <Step role={s.role} person={s.person} />
          {i < steps.length - 1 && !stacked && <ChevronRight aria-hidden className="mt-[22px] size-4 shrink-0 text-ink-4" strokeWidth={1.5} />}
        </div>
      ))}
      {!route.approver && twoSignature && (
        <span className="inline-flex h-[18px] items-center self-center rounded-[4px] border border-border-strong px-1.5 text-[11px] font-medium text-ink-3">
          Two-signature document
        </span>
      )}
    </div>
  );
}

import { AppLink } from "@/lib/app-link";
import { cn } from "@/lib/utils";

/** Sans 18/24 title, grey subtitle, optional 'View all' link on the right. */
export function SectionHeader({
  title,
  subtitle,
  viewAllHref,
  viewAllLabel = "View all",
  actions,
  className,
}: {
  title: string;
  subtitle?: string;
  viewAllHref?: string;
  viewAllLabel?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-end justify-between gap-4", className)}>
      <div className="min-w-0">
        <h2 className="text-[18px] font-medium leading-6 text-ink">{title}</h2>
        {subtitle && <p className="text-[14px] leading-5 text-ink-3">{subtitle}</p>}
      </div>
      <div className="flex shrink-0 items-center gap-3">
        {actions}
        {viewAllHref && (
          <AppLink href={viewAllHref} className="text-[14px] font-medium text-ink-2 hover:text-ink">
            {viewAllLabel}
          </AppLink>
        )}
      </div>
    </div>
  );
}

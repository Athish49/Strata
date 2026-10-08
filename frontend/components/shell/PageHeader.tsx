import { Breadcrumbs, type Crumb } from "./Breadcrumbs";
import { RunSelector } from "./RunSelector";
import { cn } from "@/lib/utils";

/**
 * Breadcrumbs, grey caption, serif title on the left; RunSelector then actions on the right.
 * Actions: secondary buttons first, then at most one primary button.
 */
export function PageHeader({
  title,
  caption,
  breadcrumbs,
  actions,
  showRunSelector = true,
  className,
}: {
  title: React.ReactNode;
  caption?: React.ReactNode;
  breadcrumbs?: Crumb[];
  actions?: React.ReactNode;
  showRunSelector?: boolean;
  className?: string;
}) {
  return (
    <header className={cn("mb-6", className)}>
      {breadcrumbs && breadcrumbs.length > 0 && <Breadcrumbs items={breadcrumbs} />}
      <div className="flex items-end justify-between gap-6">
        <div className="min-w-0">
          {caption && <div className="mb-1 text-[13px] leading-[18px] text-ink-3">{caption}</div>}
          <h1 className="font-serif text-[36px] font-normal leading-[44px] tracking-[-0.015em] text-ink">{title}</h1>
        </div>
        <div className="flex shrink-0 items-center gap-2 pb-1">
          {showRunSelector && <RunSelector />}
          {actions}
        </div>
      </div>
    </header>
  );
}

/** Standard page padding (40px horizontal, 32px top). `full` drops the 1440px max-width. */
export function PageContainer({
  children,
  full,
  className,
}: {
  children: React.ReactNode;
  full?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("mx-auto w-full px-10 pb-16 pt-8", !full && "max-w-[1440px]", className)}>{children}</div>
  );
}

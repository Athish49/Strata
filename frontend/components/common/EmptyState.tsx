import { cn } from "@/lib/utils";

/** Text only: serif 20 line, sans 14 ink-3 explanation, one action. No illustrations. */
export function EmptyState({
  title,
  description,
  action,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-start gap-2 px-6 py-10", className)}>
      <p className="font-serif text-[20px] leading-7 text-ink">{title}</p>
      {description && <p className="max-w-[56ch] text-[14px] leading-5 text-ink-3">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}

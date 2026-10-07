import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/** A plain sentence, a retry, and which data source failed (§7.2). */
export function ErrorState({
  message = "This could not be loaded.",
  source,
  onRetry,
  className,
}: {
  message?: string;
  /** Which data source failed, e.g. "Runs" or "Knowledge base". */
  source?: string;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div role="alert" className={cn("flex flex-col items-start gap-2 px-6 py-10", className)}>
      <p className="font-serif text-[20px] leading-7 text-ink">{message}</p>
      {source && <p className="text-[14px] leading-5 text-ink-3">Source: {source}</p>}
      {onRetry && (
        <Button variant="secondary" size="sm" className="mt-2" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

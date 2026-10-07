import { FileText } from "lucide-react";
import { AppLink } from "@/lib/app-link";
import { cn } from "@/lib/utils";

/** Mono doc id with a small file icon; links to the reader (keeps ?run=) when `href` is given. */
export function DocChip({
  docId,
  title,
  href,
  className,
}: {
  docId: string;
  title?: string;
  href?: string;
  className?: string;
}) {
  const inner = (
    <>
      <FileText className="size-3.5 shrink-0 text-ink-3" strokeWidth={1.5} />
      <span className="font-mono text-[12.5px] leading-[18px] text-ink">{docId}</span>
      {title && <span className="truncate text-[13px] text-ink-3">{title}</span>}
    </>
  );
  const cls = cn("inline-flex min-w-0 items-center gap-1.5", className);
  return href ? (
    <AppLink href={href} className={cn(cls, "hover:underline")}>
      {inner}
    </AppLink>
  ) : (
    <span className={cls}>{inner}</span>
  );
}

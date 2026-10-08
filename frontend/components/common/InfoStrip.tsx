import Link from "next/link";
import { cn } from "@/lib/utils";

/** Full-width white strip: small monogram + one sentence. Use at most once per page. */
export function InfoStrip({
  children,
  href,
  className,
}: {
  children: React.ReactNode;
  href?: string;
  className?: string;
}) {
  const body = (
    <>
      <span
        aria-hidden
        className="grid size-6 shrink-0 place-items-center rounded-[6px] bg-ink font-serif text-[14px] font-medium leading-none text-white"
      >
        S
      </span>
      <span className="min-w-0 flex-1 truncate text-[15px] leading-5 text-ink-2">{children}</span>
    </>
  );
  const cls = cn("flex h-14 items-center gap-3 rounded-[12px] border border-border bg-surface px-5", className);
  return href ? (
    <Link href={href} className={cn(cls, "transition-colors hover:bg-surface-muted")}>
      {body}
    </Link>
  ) : (
    <div className={cls}>{body}</div>
  );
}

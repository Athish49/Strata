import { ChevronRight } from "lucide-react";
import { AppLink } from "@/lib/app-link";

export interface Crumb {
  label: string;
  href?: string;
  mono?: boolean;
}

/** Parents in ink-3, `›` separators, current page in ink. */
export function Breadcrumbs({ items }: { items: Crumb[] }) {
  if (items.length === 0) return null;
  return (
    <nav aria-label="Breadcrumb" className="mb-3">
      <ol className="flex min-w-0 items-center gap-1.5 text-[13px] leading-[18px]">
        {items.map((c, i) => {
          const last = i === items.length - 1;
          const cls = c.mono ? "font-mono text-[12.5px]" : "";
          return (
            <li key={`${c.label}-${i}`} className="flex min-w-0 items-center gap-1.5">
              {c.href && !last ? (
                <AppLink href={c.href} className={`truncate text-ink-3 hover:text-ink ${cls}`}>
                  {c.label}
                </AppLink>
              ) : (
                <span aria-current={last ? "page" : undefined} className={`truncate ${last ? "text-ink" : "text-ink-3"} ${cls}`}>
                  {c.label}
                </span>
              )}
              {!last && <ChevronRight aria-hidden className="size-3.5 shrink-0 text-ink-4" strokeWidth={1.5} />}
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

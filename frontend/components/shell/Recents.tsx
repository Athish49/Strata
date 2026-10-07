"use client";
import * as React from "react";
import { usePathname } from "next/navigation";
import { AppLink } from "@/lib/app-link";
import { cn } from "@/lib/utils";

export interface RecentItem {
  href: string;
  label: string;
}

const KEY = "strata.recents";
const listeners = new Set<() => void>();

function read(): string {
  try {
    return sessionStorage.getItem(KEY) ?? "[]";
  } catch {
    return "[]";
  }
}
function subscribe(cb: () => void) {
  listeners.add(cb);
  return () => void listeners.delete(cb);
}

/** Push a visited item (most recent first, max 4). Safe to call anywhere on the client. */
export function pushRecent(item: RecentItem) {
  try {
    const cur: RecentItem[] = JSON.parse(read());
    const next = [item, ...cur.filter((r) => r.href !== item.href)].slice(0, 4);
    sessionStorage.setItem(KEY, JSON.stringify(next));
  } catch {}
  listeners.forEach((l) => l());
}

/** Pages call this with a document, change or finding they show: useRecordRecent({href, label}). */
export function useRecordRecent(item: RecentItem | null | undefined) {
  const href = item?.href;
  const label = item?.label;
  React.useEffect(() => {
    if (href && label) pushRecent({ href, label });
  }, [href, label]);
}

export function useRecents(): RecentItem[] {
  const raw = React.useSyncExternalStore(subscribe, read, () => "[]");
  return React.useMemo(() => {
    try {
      return JSON.parse(raw) as RecentItem[];
    } catch {
      return [];
    }
  }, [raw]);
}

export function Recents() {
  const items = useRecents();
  const pathname = usePathname();
  if (items.length === 0) return null;
  return (
    <div className="mt-7">
      <div className="px-7 pb-1.5 text-[13px] leading-4 text-sidebar-muted">Recents</div>
      <ul className="flex flex-col gap-0.5 px-4">
        {items.map((r) => (
          <li key={r.href}>
            <AppLink
              href={r.href}
              className={cn(
                "flex h-8 items-center gap-3 rounded-[8px] px-3 text-[15px] leading-5 text-sidebar-fg transition-colors duration-150 hover:bg-sidebar-active/60",
                pathname === r.href && "bg-sidebar-active",
              )}
            >
              <span aria-hidden className="mx-[6px] size-1 shrink-0 bg-sidebar-muted" />
              <span className="truncate">{r.label}</span>
            </AppLink>
          </li>
        ))}
      </ul>
    </div>
  );
}

"use client";
import { streamLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

/** Activity stream filter: "All" plus one chip per stream (Federal Register, Orders, Investigations, Rulemakings). */
export function StreamChips({
  streams,
  value,
  onChange,
  counts,
}: {
  streams: string[];
  value: string | null;
  onChange: (stream: string | null) => void;
  counts?: Record<string, number>;
}) {
  const items: { key: string | null; label: string }[] = [{ key: null, label: "All" }, ...streams.map((s) => ({ key: s, label: streamLabel(s) }))];
  return (
    <div role="group" aria-label="Activity streams" className="flex flex-wrap items-center gap-2">
      {items.map((it) => {
        const active = (value ?? null) === it.key;
        const n = it.key && counts ? counts[it.key] : undefined;
        return (
          <button
            key={it.key ?? "all"}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(it.key)}
            className={cn(
              "inline-flex h-7 items-center gap-1.5 rounded-full border px-3 text-[13px] transition-colors duration-150",
              active ? "border-ink bg-ink text-white" : "border-border-strong bg-surface text-ink-2 hover:bg-surface-muted",
            )}
          >
            {it.label}
            {n !== undefined && <span className={active ? "text-white/70" : "text-ink-3"}>{n}</span>}
          </button>
        );
      })}
    </div>
  );
}

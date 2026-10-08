import { cn } from "@/lib/utils";

function initials(name: string) {
  const p = name.split(/\s+/).filter(Boolean);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase();
}

/** Neutral monogram + name (+ optional role). */
export function PersonChip({ name, role, className }: { name: string; role?: string; className?: string }) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-2 text-[13px] text-ink", className)}>
      <span
        aria-hidden
        className="grid size-5 shrink-0 place-items-center rounded-[4px] bg-surface-muted text-[10px] font-medium text-ink-2"
      >
        {initials(name)}
      </span>
      <span className="truncate">{name}</span>
      {role && <span className="truncate text-ink-3">{role}</span>}
    </span>
  );
}

"use client";
import * as React from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import type { ChangeClass, ChangeRecord } from "@/lib/api/schemas";
import { ClassPill } from "@/components/engine";
import { FutureCue } from "@/components/common/FutureCue";
import { formatCount, formatDate } from "@/lib/format";
import { changeClassLabel, isNoiseClass } from "@/lib/labels";
import { cn } from "@/lib/utils";
import {
  applyFilters,
  buildTree,
  classCounts,
  defaultOpen,
  dispositionLabel,
  DEFAULT_FILTERS,
  pathToChange,
  type ChangeFilters,
  type TreeGroup,
} from "./logic";

const GROUP_PAGE = 40;
const ROW_PAGE = 40;

function Chip({ pressed, onClick, children, title }: { pressed: boolean; onClick: () => void; children: React.ReactNode; title?: string }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      title={title}
      onClick={onClick}
      className={cn(
        "inline-flex h-7 items-center gap-1.5 whitespace-nowrap rounded-full border px-3 text-[13px] transition-colors",
        pressed ? "border-ink bg-ink text-white" : "border-border-strong bg-surface text-ink-2 hover:text-ink",
      )}
    >
      {children}
    </button>
  );
}

export interface ChangeTreeProps {
  changes: readonly ChangeRecord[];
  filters: ChangeFilters;
  onFilters: (patch: Partial<ChangeFilters>) => void;
  selectedId: string | null;
  /** Href for a change row (keeps filters and run in the query string). */
  hrefFor: (changeId: string) => string;
  agencyName?: (agencyId: string) => string;
  className?: string;
}

type Flat =
  | { t: "group"; g: TreeGroup; depth: number; open: boolean }
  | { t: "row"; r: ChangeRecord; depth: number }
  | { t: "more"; key: string; depth: number; remaining: number; what: "rows" | "groups" };

/** Filtered, grouped change tree. Collapsed groups render nothing; long groups are paged, so thousands of changes stay cheap. */
export function ChangeTree({ changes, filters, onFilters, selectedId, hrefFor, agencyName, className }: ChangeTreeProps) {
  const [open, setOpen] = React.useState<Record<string, boolean>>({});
  const [shown, setShown] = React.useState<Record<string, number>>({});
  const [draft, setDraft] = React.useState<string | null>(null);
  const qDraft = draft ?? filters.q;
  React.useEffect(() => {
    if (draft === null) return;
    const id = setTimeout(() => {
      onFilters({ q: draft });
      setDraft(null);
    }, 250);
    return () => clearTimeout(id);
  }, [draft, onFilters]);

  const filtered = React.useMemo(() => applyFilters(changes, filters), [changes, filters]);
  const tree = React.useMemo(() => buildTree(filtered, agencyName), [filtered, agencyName]);
  const selectedPath = React.useMemo(() => pathToChange(tree, selectedId), [tree, selectedId]);
  const counts = React.useMemo(() => classCounts(changes, filters.rpl), [changes, filters.rpl]);
  const realCount = React.useMemo(() => counts.filter((c) => !isNoiseClass(c.cls)).reduce((a, c) => a + c.n, 0), [counts]);
  const dispositions = React.useMemo(() => [...new Set(changes.map((c) => c.disposition ?? "none"))].sort(), [changes]);

  const flat = React.useMemo(() => {
    const out: Flat[] = [];
    const isOpen = (g: TreeGroup, depth: number) => open[g.key] ?? (selectedPath.has(g.key) || defaultOpen(g, depth));
    const walk = (g: TreeGroup, depth: number) => {
      const o = isOpen(g, depth);
      out.push({ t: "group", g, depth, open: o });
      if (!o) return;
      const gl = shown[`${g.key}#g`] ?? GROUP_PAGE;
      g.groups.slice(0, gl).forEach((c) => walk(c, depth + 1));
      if (g.groups.length > gl) out.push({ t: "more", key: `${g.key}#g`, depth: depth + 1, remaining: g.groups.length - gl, what: "groups" });
      const rl = shown[`${g.key}#r`] ?? ROW_PAGE;
      g.rows.slice(0, rl).forEach((r) => out.push({ t: "row", r, depth: depth + 1 }));
      if (g.rows.length > rl) out.push({ t: "more", key: `${g.key}#r`, depth: depth + 1, remaining: g.rows.length - rl, what: "rows" });
    };
    tree.forEach((g) => walk(g, 0));
    return out;
  }, [tree, open, shown, selectedPath]);

  const selRef = React.useRef<HTMLAnchorElement | null>(null);
  React.useEffect(() => {
    const el = selRef.current;
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "nearest" });
  }, [selectedId, tree]);

  const toggleClass = (c: ChangeClass) => {
    const next = filters.cls.includes(c) ? filters.cls.filter((x) => x !== c) : [...filters.cls, c];
    onFilters({ cls: next });
  };

  return (
    <div className={cn("flex min-h-0 flex-col rounded-[12px] border border-border bg-surface", className)}>
      <div className="space-y-2.5 border-b border-border p-3">
        <label className="relative block">
          <span className="sr-only">Filter changes by citation or heading</span>
          <Search aria-hidden className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" strokeWidth={1.5} />
          <input
            type="search"
            value={qDraft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="Filter by citation or heading"
            className="h-9 w-full rounded-[8px] border border-border bg-surface pl-8 pr-2 text-[14px] text-ink placeholder:text-ink-4"
          />
        </label>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filters">
          <Chip pressed={filters.rpl} onClick={() => onFilters({ rpl: !filters.rpl })} title="Only changes to rules that Rockridge documents cite">
            Touches RPL
          </Chip>
          <Chip
            pressed={!filters.noise && filters.cls.length === 0}
            onClick={() => onFilters(!filters.noise && filters.cls.length === 0 ? { sub: false, noise: true, cls: [] } : { sub: true, noise: false, cls: [] })}
            title="Substantive, repealed, renumbered and new sections; no cosmetic noise"
          >
            Real changes only
            <span className={cn("tabular-nums", !filters.noise && filters.cls.length === 0 ? "text-white/70" : "text-ink-3")}>{formatCount(realCount)}</span>
          </Chip>
          <Chip pressed={filters.noise && filters.cls.length === 0} onClick={() => onFilters({ noise: !filters.noise, sub: false, cls: [] })}>
            Show noise
          </Chip>
          <FutureCue id="proposed-rules" />
        </div>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Change class">
          {counts.map(({ cls, n }) => (
            <Chip key={cls} pressed={filters.cls.includes(cls)} onClick={() => toggleClass(cls)}>
              {changeClassLabel(cls)}
              <span className={cn("tabular-nums", filters.cls.includes(cls) ? "text-white/70" : "text-ink-3")}>{formatCount(n)}</span>
            </Chip>
          ))}
        </div>
        {dispositions.length > 1 && (
          <label className="flex items-center gap-2 text-[13px] text-ink-3">
            Outcome
            <select
              value={filters.disp ?? ""}
              onChange={(e) => onFilters({ disp: e.target.value || null })}
              className="h-8 min-w-0 flex-1 rounded-[8px] border border-border bg-surface px-2 text-[13px] text-ink"
            >
              <option value="">Any</option>
              {dispositions.map((d) => (
                <option key={d} value={d}>
                  {dispositionLabel(d)}
                </option>
              ))}
            </select>
          </label>
        )}
        <div className="text-[12px] text-ink-3" aria-live="polite">
          {formatCount(filtered.length)} of {formatCount(changes.length)} changes
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto" role="tree" aria-label="Changes">
        {filtered.length === 0 ? (
          <div className="px-4 py-8">
            <p className="font-serif text-[18px] leading-6 text-ink">No changes match these filters</p>
            <p className="mt-1 text-[13px] text-ink-3">Try widening the filters, or turn on noise to see what was removed.</p>
              <button
                type="button"
                onClick={() => onFilters({ ...DEFAULT_FILTERS, rpl: false, sub: false, noise: true })}
                className="mt-3 inline-flex h-8 items-center rounded-[8px] border border-border-strong px-3 text-[13px] text-ink hover:bg-surface-muted"
              >
                Reset filters
              </button>
          </div>
        ) : (
          flat.map((f) => {
            const pad = { paddingLeft: 12 + f.depth * 14 };
            if (f.t === "group") {
              const Chev = f.open ? ChevronDown : ChevronRight;
              const label = f.g.kind === "noise-class" ? changeClassLabel(f.g.label as ChangeClass) : f.g.label;
              return (
                <button
                  key={f.g.key}
                  type="button"
                  role="treeitem"
                  aria-expanded={f.open}
                  aria-selected={false}
                  aria-level={f.depth + 1}
                  onClick={() => setOpen((o) => ({ ...o, [f.g.key]: !f.open }))}
                  style={pad}
                  className={cn(
                    "flex min-h-8 w-full items-center gap-1.5 border-b border-border pr-3 text-left hover:bg-surface-muted",
                    f.g.kind === "agency" || f.g.kind === "noise" ? "bg-surface-muted/60" : "",
                  )}
                >
                  <Chev aria-hidden className="size-4 shrink-0 text-ink-3" strokeWidth={1.5} />
                  <span className={cn("min-w-0 truncate text-[13px]", f.g.kind === "rule" ? "font-mono text-ink-2" : "font-medium text-ink")}>{label}</span>
                  {f.g.sub && <span className="shrink-0 text-[12px] text-ink-3">· {f.g.sub}</span>}
                  <span className="ml-auto shrink-0 rounded-full bg-surface-muted px-2 text-[12px] tabular-nums text-ink-3">{formatCount(f.g.count)}</span>
                </button>
              );
            }
            if (f.t === "more") {
              return (
                <button
                  key={f.key}
                  type="button"
                  style={pad}
                  onClick={() => setShown((s) => ({ ...s, [f.key]: (s[f.key] ?? (f.what === "rows" ? ROW_PAGE : GROUP_PAGE)) + (f.what === "rows" ? ROW_PAGE : GROUP_PAGE) }))}
                  className="h-8 w-full border-b border-border pr-3 text-left text-[13px] text-ink-3 hover:text-ink"
                >
                  Show more ({formatCount(f.remaining)} {f.what === "rows" ? "sections" : "groups"} remaining)
                </button>
              );
            }
            const r = f.r;
            const sel = r.change_id === selectedId;
            return (
              <Link
                key={r.change_id}
                ref={sel ? selRef : undefined}
                href={hrefFor(r.change_id)}
                role="treeitem"
                aria-level={f.depth + 1}
                aria-selected={sel}
                aria-current={sel ? "page" : undefined}
                style={pad}
                className={cn(
                  "block border-b border-border py-2 pr-3 transition-colors hover:bg-surface-muted",
                  sel && "bg-surface-muted shadow-[inset_2px_0_0_var(--ink)]",
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="min-w-0 truncate font-mono text-[12.5px] text-ink">{r.citation}</span>
                  <ClassPill changeClass={r.change_class} className="ml-auto" />
                </div>
                {r.heading && <div className="truncate text-[13px] text-ink-2">{r.heading}</div>}
                <div className="mt-0.5 flex items-center gap-1.5 text-[12px] text-ink-3">
                  <span>{r.published_date ? formatDate(r.published_date) : "Date not recorded"}</span>
                  <span aria-hidden>·</span>
                  <span>{r.cited_clause_count === 0 ? "Not cited" : `Cited by ${formatCount(r.cited_clause_count)} ${r.cited_clause_count === 1 ? "clause" : "clauses"}`}</span>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </div>
  );
}

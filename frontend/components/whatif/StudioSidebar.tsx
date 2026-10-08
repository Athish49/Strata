"use client";
import * as React from "react";
import { Search } from "lucide-react";
import { FutureCue } from "@/components/common/FutureCue";
import { ErrorState } from "@/components/common/ErrorState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { AppLink } from "@/lib/app-link";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { EditableSection, Scenario } from "@/lib/api/schemas";
import { EDIT_KIND_LABELS } from "./config";

export function sectionKey(s: { source_system: string; citation: string }): string {
  return `${s.source_system}|${s.citation}`;
}

/** Pure: filter by citation/heading text, most-cited first. Exported for tests. */
export function filterSections(sections: readonly EditableSection[], query: string): EditableSection[] {
  const q = query.trim().toLowerCase();
  return sections
    .filter((s) => !q || s.citation.toLowerCase().includes(q) || s.heading.toLowerCase().includes(q))
    .sort((a, b) => b.cited_clause_count - a.cited_clause_count || a.citation.localeCompare(b.citation));
}

const MAX_ROWS = 80;

export function PresetCard({
  scenario,
  active,
  busy,
  disabled,
  onRun,
}: {
  scenario: Scenario;
  active: boolean;
  busy: boolean;
  disabled: boolean;
  onRun: (s: Scenario) => void;
}) {
  return (
    <li className={cn("rounded-[12px] border bg-surface p-4", active ? "border-ink" : "border-border")} data-testid="preset-card">
      <div className="flex items-start justify-between gap-2">
        <AppLink href={`/app/what-if/${encodeURIComponent(scenario.scenario_id)}`} className="min-w-0 text-[14px] font-medium leading-5 text-ink hover:underline">
          {scenario.title}
        </AppLink>
        <Badge variant="tag" className="mt-0.5">
          Instant
        </Badge>
      </div>
      <p className="mt-1 text-[12px] leading-4 text-ink-3">
        <span className="font-mono text-[12px]">{scenario.citation}</span> · {EDIT_KIND_LABELS[scenario.edit_kind]}
      </p>
      <div className="mt-3 flex items-center gap-2">
        <Button size="sm" variant="secondary" disabled={disabled || busy} aria-label={`Run ${scenario.title}`} onClick={() => onRun(scenario)}>
          {busy ? "Opening…" : "Run"}
        </Button>
        <Button size="sm" variant="ghost" asChild>
          <AppLink href={`/app/what-if/${encodeURIComponent(scenario.scenario_id)}`}>View edit</AppLink>
        </Button>
      </div>
    </li>
  );
}

export function PresetList({
  presets,
  loading,
  error,
  onRetry,
  activeId,
  busyId,
  onRun,
  runDisabled,
}: {
  presets: Scenario[];
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  activeId: string | null;
  busyId: string | null;
  onRun: (s: Scenario) => void;
  runDisabled: (s: Scenario) => boolean;
}) {
  return (
    <section aria-labelledby="whatif-presets">
      <h2 id="whatif-presets" className="text-[18px] font-medium leading-6 text-ink">
        Presets
      </h2>
      <p className="mb-3 text-[14px] leading-5 text-ink-3">Already analysed, so they open instantly.</p>
      {error ? (
        <ErrorState className="px-0 py-4" message="Presets could not be loaded." source="What-if scenarios" onRetry={onRetry} />
      ) : loading ? (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-[104px] w-full rounded-[12px]" />
          ))}
        </div>
      ) : (
        <ul className="space-y-3">
          {presets.map((s) => (
            <PresetCard key={s.scenario_id} scenario={s} active={activeId === s.scenario_id} busy={busyId === s.scenario_id} disabled={runDisabled(s)} onRun={onRun} />
          ))}
          <li>
            <FutureCue id="from-proposed-rule" />
          </li>
        </ul>
      )}
    </section>
  );
}

export function YourScenarios({ scenarios, activeId }: { scenarios: Scenario[]; activeId: string | null }) {
  if (scenarios.length === 0) return null;
  return (
    <section aria-labelledby="whatif-yours">
      <h2 id="whatif-yours" className="text-[18px] font-medium leading-6 text-ink">
        Your scenarios
      </h2>
      <ul className="mt-2 divide-y divide-border rounded-[12px] border border-border bg-surface">
        {scenarios.map((s) => (
          <li key={s.scenario_id}>
            <AppLink
              href={`/app/what-if/${encodeURIComponent(s.scenario_id)}`}
              className={cn("block px-4 py-2.5 hover:bg-surface-muted", activeId === s.scenario_id && "bg-surface-muted")}
            >
              <span className="block truncate text-[14px] leading-5 text-ink">{s.title}</span>
              <span className="block text-[12px] leading-4 text-ink-3">
                <span className="font-mono">{s.citation}</span> · {EDIT_KIND_LABELS[s.edit_kind]}
              </span>
            </AppLink>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function SectionPicker({
  sections,
  loading,
  error,
  onRetry,
  selectedKey,
  onPick,
}: {
  sections: EditableSection[] | undefined;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  selectedKey: string | null;
  onPick: (s: EditableSection) => void;
}) {
  const [query, setQuery] = React.useState("");
  const rows = React.useMemo(() => filterSections(sections ?? [], query), [sections, query]);
  const shown = rows.slice(0, MAX_ROWS);
  return (
    <section aria-labelledby="whatif-sections">
      <h2 id="whatif-sections" className="text-[18px] font-medium leading-6 text-ink">
        Edit a section
      </h2>
      <p className="mb-3 text-[14px] leading-5 text-ink-3">Sections your documents cite, most cited first.</p>
      <div className="relative mb-2">
        <Search aria-hidden className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-3" strokeWidth={1.5} />
        <Input aria-label="Search sections" placeholder="Search by citation or heading" className="pl-9" value={query} onChange={(e) => setQuery(e.target.value)} />
      </div>
      {error ? (
        <ErrorState className="px-0 py-4" message="Sections could not be loaded." source="What-if sections" onRetry={onRetry} />
      ) : loading ? (
        <div className="space-y-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-11 w-full" />
          ))}
        </div>
      ) : rows.length === 0 ? (
        <p className="px-1 py-4 text-[14px] text-ink-3">{query ? "No cited section matches that search." : "No cited sections are available."}</p>
      ) : (
        <>
          <ul className="max-h-[420px] divide-y divide-border overflow-y-auto rounded-[12px] border border-border bg-surface" data-testid="section-list">
            {shown.map((s) => {
              const key = sectionKey(s);
              return (
                <li key={key}>
                  <button
                    type="button"
                    onClick={() => onPick(s)}
                    aria-pressed={selectedKey === key}
                    className={cn("flex w-full items-start gap-3 px-4 py-2.5 text-left hover:bg-surface-muted", selectedKey === key && "bg-surface-muted")}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-mono text-[12.5px] leading-[18px] text-ink">{s.citation}</span>
                      <span className="block truncate text-[12px] leading-4 text-ink-3">{s.heading}</span>
                    </span>
                    <span className="shrink-0 pt-0.5 text-[12px] tabular-nums text-ink-3">
                      {formatCount(s.cited_clause_count)} {s.cited_clause_count === 1 ? "clause" : "clauses"}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {rows.length > shown.length && (
            <p className="mt-2 px-1 text-[12px] text-ink-3">
              Showing {formatCount(shown.length)} of {formatCount(rows.length)}. Search to narrow the list.
            </p>
          )}
        </>
      )}
    </section>
  );
}

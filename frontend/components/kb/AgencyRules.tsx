"use client";
import * as React from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { useChanges } from "@/lib/api/queries";
import { useAllSections } from "@/lib/kb-hooks";
import { useRunContext } from "@/lib/run-context";
import type { Agency } from "@/lib/api/schemas";
import { formatCount } from "@/lib/format";
import { makeChangedMap, SectionTree } from "./SectionTree";
import { filterSections } from "./tree";
import { useDebounced } from "./AgencyActivity";

/** Rules-in-force tab: search, repealed toggle, and the Title > Part > Rule > Section tree. */
export function AgencyRules({ agency }: { agency: Agency }) {
  const [query, setQuery] = React.useState("");
  const [repealed, setRepealed] = React.useState(false);
  const q = useDebounced(query, 200);
  const sections = useAllSections(agency.agency_id ?? agency.slug);
  const { runId } = useRunContext();
  const changes = useChanges(runId);
  const changed = React.useMemo(() => makeChangedMap(changes.data), [changes.data]);
  const all = React.useMemo(() => sections.data ?? [], [sections.data]);
  const repealedCount = React.useMemo(() => all.filter((s) => s.status === "repealed").length, [all]);
  const visible = React.useMemo(() => filterSections(all, q, repealed).length, [all, q, repealed]);

  return (
    <div>
      <div className="flex flex-wrap items-center gap-4 border-b border-border px-4 py-3">
        <div className="relative w-[320px]">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" strokeWidth={1.5} />
          <Input
            aria-label="Search sections"
            placeholder="Search citation or heading"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-8 pl-8 text-[13px]"
          />
        </div>
        <label className="inline-flex items-center gap-2 text-[13px] text-ink-2">
          <input type="checkbox" checked={repealed} onChange={(e) => setRepealed(e.target.checked)} className="size-4 accent-ink" />
          Show repealed{repealedCount > 0 ? ` (${formatCount(repealedCount)})` : ""}
        </label>
        {sections.data && (
          <span className="ml-auto text-[13px] text-ink-3">
            {formatCount(visible)} of {formatCount(all.length)} sections
          </span>
        )}
      </div>
      {sections.isError ? (
        <ErrorState message="Sections could not be loaded." source="Knowledge base · sections" onRetry={() => void sections.refetch()} />
      ) : sections.isLoading ? (
        <div className="space-y-2 p-4">
          {Array.from({ length: 8 }, (_, i) => (
            <Skeleton key={i} className="h-9" />
          ))}
        </div>
      ) : (
        <SectionTree sections={all} query={q} includeRepealed={repealed} changed={changed} />
      )}
    </div>
  );
}

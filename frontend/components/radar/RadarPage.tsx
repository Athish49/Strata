"use client";
import * as React from "react";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { InfoStrip } from "@/components/common/InfoStrip";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAgencies, useRadar } from "@/lib/api/queries";
import { useRunContext } from "@/lib/run-context";
import { APPLICABLE_LABELS } from "@/lib/labels";
import { formatCount } from "@/lib/format";
import type { RadarItem } from "@/lib/api/schemas";
import { GROUP_ORDER, filterItems, groupItems, type RadarGroup } from "./logic";
import { RadarItemCard } from "./RadarItemCard";

const PAGE = 30;

const EMPTY_COPY: Record<RadarGroup, string> = {
  yes: "Nothing here matches. No uncited change looks applicable to the company profile.",
  unclear: "Nothing here matches. Every uncited change could be screened one way or the other.",
  no: "Nothing here matches.",
};

function Group({ group, items, names }: { group: RadarGroup; items: RadarItem[]; names: Map<string, string> }) {
  const [shown, setShown] = React.useState(PAGE);
  if (items.length === 0) return <EmptyState title={EMPTY_COPY[group]} />;
  return (
    <>
      <ul className="space-y-3">
        {items.slice(0, shown).map((i) => (
          <RadarItemCard key={i.radar_id} item={i} agencyName={names.get(i.agency_id) ?? i.agency_id.toUpperCase()} />
        ))}
      </ul>
      {items.length > shown && (
        <div className="mt-4 flex justify-center">
          <Button variant="secondary" onClick={() => setShown((n) => n + PAGE)}>
            Show more ({formatCount(items.length - shown)} left)
          </Button>
        </div>
      )}
    </>
  );
}

export function RadarPage() {
  const { runId, run } = useRunContext();
  const radar = useRadar(runId);
  const agencies = useAgencies();
  const [tab, setTab] = React.useState<RadarGroup>("yes");
  const [agency, setAgency] = React.useState<string | null>(null);
  const [query, setQuery] = React.useState("");

  const names = React.useMemo(() => {
    const m = new Map<string, string>();
    for (const a of agencies.data ?? []) {
      m.set(a.agency_id ?? a.slug, a.name);
      m.set(a.slug, a.name);
    }
    return m;
  }, [agencies.data]);

  const all = React.useMemo(() => radar.data ?? [], [radar.data]);
  const grouped = React.useMemo(() => {
    const filtered = filterItems(all, { agency, query });
    return groupItems(filtered);
  }, [all, agency, query]);
  const agencyIds = React.useMemo(() => [...new Set(all.map((i) => i.agency_id))].sort(), [all]);
  const filtering = agency !== null || query.trim() !== "";

  const loading = !runId || radar.isLoading;
  let body: React.ReactNode;
  if (radar.isError) {
    body = <ErrorState message="Radar could not be loaded." source="Engine" onRetry={() => void radar.refetch()} />;
  } else if (loading) {
    body = (
      <div className="space-y-3">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-[120px] rounded-[12px]" />
        ))}
      </div>
    );
  } else if (all.length === 0) {
    body = (
      <EmptyState
        title="Radar is only produced for real regulatory waves"
        description={
          run?.kind === "whatif" || run?.kind === "baseline"
            ? "This is a simulated or baseline run, so no uncited changes were screened. Switch back to the real wave to see the Radar."
            : "No uncited changes were screened for this run."
        }
      />
    );
  } else {
    body = (
      <Tabs value={tab} onValueChange={(v) => setTab(v as RadarGroup)}>
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <TabsList>
            {GROUP_ORDER.map((g) => (
              <TabsTrigger key={g} value={g}>
                {APPLICABLE_LABELS[g]} <span className="ml-1 tabular-nums text-ink-3">{formatCount(grouped[g].length)}</span>
              </TabsTrigger>
            ))}
          </TabsList>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="search"
              aria-label="Search radar items"
              placeholder="Search citation or activity"
              className="w-[260px]"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select
              aria-label="Filter by agency"
              className="h-9 rounded-[8px] border border-border-strong bg-surface px-3 text-[14px] text-ink"
              value={agency ?? ""}
              onChange={(e) => setAgency(e.target.value || null)}
            >
              <option value="">All agencies</option>
              {agencyIds.map((id) => (
                <option key={id} value={id}>
                  {names.get(id) ?? id.toUpperCase()}
                </option>
              ))}
            </select>
            {filtering && (
              <Button variant="ghost" onClick={() => { setAgency(null); setQuery(""); }}>
                Clear
              </Button>
            )}
          </div>
        </div>
        {GROUP_ORDER.map((g) => (
          <TabsContent key={g} value={g} className="outline-none">
            <Group key={`${agency ?? ""}|${query}`} group={g} items={grouped[g]} names={names} />
          </TabsContent>
        ))}
      </Tabs>
    );
  }

  return (
    <PageContainer>
      <PageHeader caption="Radar" title="Changes your documents don't cite" />
      <InfoStrip className="mb-6">
        <strong className="font-medium text-ink">Advisory.</strong> These are not tied to any clause.
      </InfoStrip>
      {body}
    </PageContainer>
  );
}

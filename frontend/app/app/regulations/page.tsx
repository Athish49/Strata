"use client";
import * as React from "react";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { SectionHeader } from "@/components/common/SectionHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { FutureCue } from "@/components/common/FutureCue";
import { Skeleton } from "@/components/ui/skeleton";
import { AddAgencyCard, AgencyCard, MoreSourcesRow } from "@/components/kb/AgencyCard";
import { useAgencies, useChanges } from "@/lib/api/queries";
import { useRunContext } from "@/lib/run-context";
import { formatCount } from "@/lib/format";
import { groupAgencies } from "@/components/kb/agencies";

export default function Page() {
  const agencies = useAgencies();
  const { runId } = useRunContext();
  const changes = useChanges(runId);
  const changedBy = React.useMemo(() => {
    const m = new Map<string, number>();
    for (const c of changes.data ?? []) m.set(c.agency_id, (m.get(c.agency_id) ?? 0) + 1);
    return m;
  }, [changes.data]);

  const { federal, state } = groupAgencies(agencies.data ?? []);
  const totalSections = (agencies.data ?? []).reduce((n, a) => n + a.section_count, 0);

  return (
    <PageContainer>
      <PageHeader
        caption="Knowledge base"
        title="Regulations"
        actions={<FutureCue id="add-jurisdiction" />}
      />
      <p className="-mt-2 mb-8 max-w-[68ch] text-[14px] leading-5 text-ink-3">
        The government sources Strata monitors for Rockridge Power &amp; Light: the rules in force and, where an agency
        publishes one, its stream of orders, investigations and rulemakings.
        {agencies.data && agencies.data.length > 0 && <> {formatCount(totalSections)} sections across {agencies.data.length} sources.</>}
      </p>

      {agencies.isError ? (
        <ErrorState message="Agencies could not be loaded." source="Knowledge base" onRetry={() => void agencies.refetch()} />
      ) : agencies.isLoading ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }, (_, i) => (
            <Skeleton key={i} className="h-[200px] rounded-[12px]" />
          ))}
        </div>
      ) : (agencies.data ?? []).length === 0 ? (
        <EmptyState title="No agencies are monitored yet" description="Agencies appear here once their codebooks are loaded into the knowledge base." />
      ) : (
        <div className="space-y-10">
          <section>
            <SectionHeader title="Federal" subtitle="Rules and actions published by federal agencies" className="mb-4" />
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {federal.map((a) => (
                <AgencyCard key={a.slug} agency={a} changedInRun={runId ? (changedBy.get(a.slug) ?? 0) : undefined} />
              ))}
              <AddAgencyCard cueId="add-agency-federal" subtitle="NERC, OSHA, DOE…" />
            </div>
          </section>
          <section>
            <SectionHeader title="State · Indiana" subtitle="Indiana Administrative Code and agency activity" className="mb-4" />
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {state.map((a) => (
                <AgencyCard key={a.slug} agency={a} changedInRun={runId ? (changedBy.get(a.slug) ?? 0) : undefined} />
              ))}
              <AddAgencyCard cueId="add-agency-state" subtitle="OUCC, Indiana DNR…" />
            </div>
          </section>
          <section>
            <SectionHeader title="More source types" subtitle="Other places rules and obligations come from" className="mb-4" />
            <MoreSourcesRow />
          </section>
        </div>
      )}
    </PageContainer>
  );
}

"use client";
import * as React from "react";
import { parseAsString, useQueryState } from "nuqs";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { FutureCue } from "@/components/common/FutureCue";
import { InfoStrip } from "@/components/common/InfoStrip";
import { Skeleton } from "@/components/ui/skeleton";
import { DOC_STATUS_LABELS } from "@/lib/labels";
import { PAGE_CUES } from "@/lib/future-features";
import { VERTICALS } from "@/lib/verticals";
import { VerticalSection } from "./VerticalSection";
import { useBoardRows } from "./useBoardRows";
import { FilterSelect } from "./FilterSelect";
import { filterRows, groupByVertical, needsAction, needsActionSentence, normalizeStatus, ownerOptions, STATUS_ORDER } from "./logic";

export function DocumentsBoard() {
  const { docs, rows, isLoading, isError, statusError, refetch } = useBoardRows();
  const [statusParam, setStatus] = useQueryState("status", parseAsString);
  const [vertical, setVertical] = useQueryState("vertical", parseAsString);
  const [owner, setOwner] = useQueryState("owner", parseAsString);
  const status = normalizeStatus(statusParam);
  const filtered = !!(status || vertical || owner);

  const groups = React.useMemo(() => {
    const g = groupByVertical(filterRows(rows, { status, vertical, owner }));
    // A filter hides verticals with no matches; unfiltered, all 14 always show (fixed order).
    return filtered ? g.filter((x) => x.rows.length > 0) : g;
  }, [rows, status, vertical, owner, filtered]);

  const attention = rows.filter((r) => !r.pending && needsAction(r)).length;
  const sentence = needsActionSentence(attention);
  const monitoredCount = docs.filter((d) => d.monitored).length;

  return (
    <PageContainer>
      <PageHeader
        caption="Company"
        title="Documents"
        actions={
          <>
            {PAGE_CUES.documents.map((id) => (
              <FutureCue key={id} id={id} />
            ))}
          </>
        }
      />

      {statusError && (
        <ErrorState className="px-0 py-4" message="Document statuses could not be loaded for this run." source="Run results" onRetry={refetch} />
      )}
      {sentence && !statusError && (
        <InfoStrip className="mb-6">
          {sentence}
        </InfoStrip>
      )}

      {isError ? (
        <ErrorState message="Documents could not be loaded." source="Company data" onRetry={refetch} />
      ) : isLoading ? (
        <div className="space-y-8" aria-busy="true">
          {Array.from({ length: 3 }, (_, i) => (
            <div key={i} className="space-y-3">
              <Skeleton className="h-6 w-56" />
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                <Skeleton className="h-[148px] rounded-[12px]" />
                <Skeleton className="h-[148px] rounded-[12px]" />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <>
          <div className="mb-8 flex flex-wrap items-center gap-3" role="group" aria-label="Filters">
            <FilterSelect
              label="Status"
              allLabel="All statuses"
              value={status}
              onChange={(v) => void setStatus(v)}
              options={STATUS_ORDER.map((k) => ({ value: k, label: DOC_STATUS_LABELS[k] }))}
            />
            <FilterSelect
              label="Vertical"
              allLabel="All verticals"
              value={vertical}
              onChange={(v) => void setVertical(v)}
              options={VERTICALS.map((v) => ({ value: v.slug, label: v.name }))}
            />
            <FilterSelect
              label="Owner"
              allLabel="All owners"
              value={owner}
              onChange={(v) => void setOwner(v)}
              options={ownerOptions(docs).map((o) => ({ value: o.id, label: o.name }))}
            />
            <span className="ml-auto text-[13px] text-ink-3">
              {monitoredCount} monitored of {docs.length} documents · sorted by needs action first
            </span>
          </div>
          {groups.length === 0 ? (
            <EmptyState
              title="No documents match these filters"
              description="Clear a filter to see every vertical again."
              action={
                <button
                  type="button"
                  className="text-[14px] font-medium text-ink-2 underline underline-offset-2 hover:text-ink"
                  onClick={() => {
                    void setStatus(null);
                    void setVertical(null);
                    void setOwner(null);
                  }}
                >
                  Clear filters
                </button>
              }
            />
          ) : (
            <div className="space-y-10">
              {groups.map((g) => (
                <VerticalSection key={g.vertical.slug} group={g} filtered={filtered} />
              ))}
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
}

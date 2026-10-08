"use client";
import * as React from "react";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { FutureCue } from "@/components/common/FutureCue";
import { PersonChip } from "@/components/common/PersonChip";
import { Skeleton } from "@/components/ui/skeleton";
import { AppLink } from "@/lib/app-link";
import { formatDate, pluralize } from "@/lib/format";
import { PAGE_CUES } from "@/lib/future-features";
import { getVertical } from "@/lib/verticals";
import { StatusCell } from "./StatusCell";
import { TwoSignatureTag } from "./TwoSignatureTag";
import { useBoardRows } from "./useBoardRows";
import { compareRows, docHref, needsAction, versionLabel, type DocRow } from "./logic";

const TH = "h-10 px-3 text-left text-[12px] font-medium text-ink-3";

function Row({ row }: { row: DocRow }) {
  const { meta } = row;
  const monitored = meta.monitored;
  return (
    <tr data-doc-id={meta.doc_id} className="h-10 border-t border-border hover:bg-surface-muted">
      <td className="px-3 font-mono text-[12.5px] text-ink-2">{meta.doc_id}</td>
      <td className="max-w-[340px] px-3 text-[14px]">
        {monitored ? (
          <AppLink href={docHref(meta.doc_id)} className="block truncate font-medium text-ink hover:underline" title={meta.title}>
            {meta.title}
          </AppLink>
        ) : (
          <span className="block truncate text-ink-2" title={meta.title}>
            {meta.title}
          </span>
        )}
        {meta.two_signature && <TwoSignatureTag />}
      </td>
      <td className="px-3 text-[13px] text-ink-2">{meta.doc_type}</td>
      <td className="px-3 text-[13px] tabular-nums text-ink-2">{versionLabel(meta.version)}</td>
      <td className="px-3">
        <PersonChip name={meta.owner.name} />
      </td>
      <td className="whitespace-nowrap px-3 text-[13px] text-ink-2">{formatDate(meta.next_review)}</td>
      <td className="px-3">
        <StatusCell row={row} />
      </td>
      <td className="px-3 text-right text-[13px] tabular-nums text-ink-2">
        {monitored && !row.pending ? row.findings : "—"}
      </td>
    </tr>
  );
}

/** `/app/documents/verticals/[vertical]` body. `slug` is already validated by the route. */
export function VerticalView({ slug }: { slug: string }) {
  const vertical = getVertical(slug);
  const { rows, isLoading, isError, refetch } = useBoardRows();
  const mine = React.useMemo(() => rows.filter((r) => r.meta.vertical === slug).sort(compareRows), [rows, slug]);
  if (!vertical) return null;
  const monitored = mine.filter((r) => r.meta.monitored).length;
  const attention = mine.filter((r) => !r.pending && needsAction(r)).length;

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={[{ label: "Documents", href: "/app/documents" }, { label: vertical.name }]}
        title={vertical.name}
        actions={
          <>
            {PAGE_CUES.vertical
              .filter((id) => id !== "start-monitoring")
              .map((id) => (
                <FutureCue key={id} id={id} />
              ))}
          </>
        }
      />
      <p className="-mt-2 mb-2 max-w-[68ch] text-[14px] leading-5 text-ink-3">{vertical.description}</p>
      {!isLoading && !isError && (
        <p className="mb-8 text-[13px] text-ink-3">
          {pluralize(mine.length, "document")} · {monitored} monitored
          {attention > 0 && ` · ${attention} ${attention === 1 ? "needs" : "need"} attention`}
        </p>
      )}

      {isError ? (
        <ErrorState message="Documents could not be loaded." source="Company data" onRetry={refetch} />
      ) : isLoading ? (
        <Skeleton className="h-48 rounded-[12px]" />
      ) : mine.length === 0 ? (
        <div className="rounded-[12px] border border-border bg-surface">
          <EmptyState
            title="No documents are filed here yet"
            description={`Documents in ${vertical.name} appear here with their status for the selected run. Once one is added and monitored, Strata checks it against every regulatory change.`}
            action={<FutureCue id="upload-document" variant="inline-add" label="Add a document" />}
          />
        </div>
      ) : (
        <>
          {monitored === 0 && (
            <p className="mb-4 max-w-[68ch] text-[14px] leading-5 text-ink-3">
              These documents are not yet monitored, so they have no findings. Start monitoring to check them against future changes.
            </p>
          )}
          <div className="overflow-x-auto rounded-[12px] border border-border bg-surface">
            <table className="w-full min-w-[960px] border-collapse text-left">
              <thead>
                <tr className="bg-surface">
                  <th className={TH}>Doc ID</th>
                  <th className={TH}>Title</th>
                  <th className={TH}>Type</th>
                  <th className={TH}>Version</th>
                  <th className={TH}>Owner</th>
                  <th className={TH}>Next review</th>
                  <th className={TH}>Status</th>
                  <th className={`${TH} text-right`}>Findings</th>
                </tr>
              </thead>
              <tbody>
                {mine.map((r) => (
                  <Row key={r.meta.doc_id} row={r} />
                ))}
              </tbody>
            </table>
          </div>
          {mine.some((r) => !r.meta.monitored) && (
            <div className="mt-4">
              <FutureCue id="start-monitoring" variant="inline-add" />
            </div>
          )}
        </>
      )}
    </PageContainer>
  );
}

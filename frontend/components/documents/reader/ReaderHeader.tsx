"use client";
import * as React from "react";
import type { DocRollup, DocumentMeta } from "@/lib/api/schemas";
import { Breadcrumbs } from "@/components/shell/Breadcrumbs";
import { RunSelector } from "@/components/shell/RunSelector";
import { FutureCue } from "@/components/common/FutureCue";
import { RouteChips } from "@/components/engine";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCount, formatDate, pluralize } from "@/lib/format";
import { verdictLabel } from "@/lib/labels";
import type { DocStatus } from "@/lib/status";
import { VERDICT_SEVERITY_ORDER } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";

const STATUS_CLASS: Record<DocStatus["key"], string> = {
  action_needed: "bg-[color:var(--red-soft)] text-[color:var(--red)]",
  review: "bg-[color:var(--amber-soft)] text-[color:var(--amber)]",
  cleared: "bg-[color:var(--green-soft)] text-[color:var(--green)]",
  not_monitored: "bg-surface-muted text-ink-2",
};

/** Document-level status pill (text + soft tint; never colour alone). */
export function ReaderStatusPill({ status }: { status: DocStatus }) {
  return (
    <span data-doc-status={status.key} className={cn("inline-flex h-[22px] items-center rounded-[6px] px-2 text-[12px] font-medium", STATUS_CLASS[status.key])}>
      {status.label}
    </span>
  );
}

/** "1 Action required, 2 Needs review across 31 changes" for flagged documents; the cleared line otherwise. */
export function rollupSentence(status: DocStatus | undefined, rollup: DocRollup | undefined): string | null {
  if (!status) return null;
  if (status.key === "cleared" || status.key === "not_monitored") return status.reason ?? null;
  if (!rollup) return null;
  const parts = VERDICT_SEVERITY_ORDER.filter((v) => (rollup.counts_by_verdict?.[v] ?? 0) > 0).map(
    (v) => `${formatCount(rollup.counts_by_verdict[v])} ${verdictLabel(v).toLowerCase()}`,
  );
  const considered = rollup.changes_considered > 0 ? ` from ${pluralize(rollup.changes_considered, "change")} considered` : "";
  const total = Object.values(rollup.counts_by_verdict ?? {}).reduce((n, k) => n + (k > 0 ? k : 0), 0);
  const reviewed = total > 0 ? ` ${rollup.reviewed ?? 0} of ${total} reviewed.` : "";
  return parts.length ? `${parts.join(", ")}${considered}.${reviewed}` : null;
}

export interface ReaderHeaderProps {
  doc: DocumentMeta | undefined;
  status?: DocStatus;
  sentence?: string | null;
  loading?: boolean;
}

/** Title, ids, version, dates, status + rollup sentence and the owner → reviewer → approver route. */
export function ReaderHeader({ doc, status, sentence, loading }: ReaderHeaderProps) {
  const crumbs = [{ label: "Documents", href: "/app/documents" }, { label: doc?.doc_id ?? "Document", mono: true }];
  const dates: [string, string | null | undefined][] = doc
    ? [
        ["Effective", doc.effective_date],
        ["Approved", doc.approved_date],
        ["Law as of", doc.law_as_of],
      ]
    : [];
  return (
    <header className="px-10 pt-8">
      <Breadcrumbs items={crumbs} />
      <div className="flex items-start justify-between gap-6">
        <div className="min-w-0">
          {doc ? (
            <>
              <div className="mb-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] leading-[18px] text-ink-3">
                <span className="font-mono text-[12.5px] text-ink-2">{doc.doc_id}</span>
                <span className="inline-flex items-center gap-1">
                  Version {doc.version}
                  <FutureCue id="version-history" side="bottom" />
                </span>
                {dates
                  .filter(([, d]) => !!d)
                  .map(([label, d]) => (
                    <span key={label}>
                      {label} {formatDate(d)}
                    </span>
                  ))}
              </div>
              <h1 className="font-serif text-[32px] font-normal leading-[40px] tracking-[-0.015em] text-ink">{doc.title}</h1>
            </>
          ) : (
            <div className="space-y-2" aria-busy={loading}>
              <Skeleton className="h-4 w-64" />
              <Skeleton className="h-10 w-[28rem]" />
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2 pt-1">
          <RunSelector />
        </div>
      </div>
      <div className="mt-4 flex flex-wrap items-start justify-between gap-x-10 gap-y-4">
        <div className="flex min-w-0 items-center gap-3">
          {status ? <ReaderStatusPill status={status} /> : <Skeleton className="h-[22px] w-24" />}
          {sentence && <p className="min-w-0 text-[14px] leading-5 text-ink-2">{sentence}</p>}
        </div>
        {doc && <RouteChips route={doc} twoSignature={doc.two_signature} />}
      </div>
    </header>
  );
}

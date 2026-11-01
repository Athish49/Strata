import { CalendarClock } from "lucide-react";
import { AppLink } from "@/lib/app-link";
import { PersonChip } from "@/components/common/PersonChip";
import { formatDate } from "@/lib/format";
import { VerdictMiniBar } from "./VerdictMiniBar";
import { StatusCell } from "./StatusCell";
import { TwoSignatureTag } from "./TwoSignatureTag";
import { docHref, docVersionText, isLifecycleStatus, NO_OWNER_LABEL, ownerName, type DocRow } from "./logic";

/**
 * A monitored document, or one moving through ingest/approval: title (links to the document), id +
 * version, owner, status, verdict bar, reason. Blank backend fields show placeholders, never empty cells.
 */
export function DocCard({ row }: { row: DocRow }) {
  const { meta, status } = row;
  // A run rollup describes the current version; a document without one shows no findings.
  const rollup = isLifecycleStatus(status.key) ? undefined : row.rollup;
  const owner = ownerName(meta);
  return (
    <article
      data-doc-id={meta.doc_id}
      className="flex flex-col gap-3 rounded-[12px] border border-border bg-surface p-4 transition-colors hover:border-border-strong"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <AppLink href={docHref(meta.doc_id)} className="line-clamp-2 text-[15px] font-medium leading-5 text-ink hover:underline">
            {meta.title}
          </AppLink>
          <p className="mt-1 text-[12.5px] leading-[18px] text-ink-3">
            <span className="font-mono">{meta.doc_id}</span> · {docVersionText(meta, status.key)}
          </p>
        </div>
        <StatusCell row={row} />
      </div>

      {!row.pending && status.key !== "action_needed" && status.key !== "review" && status.reason && (
        <p className="text-[13px] leading-5 text-ink-3">{status.reason}</p>
      )}
      {!row.pending && rollup && row.findings > 0 && <VerdictMiniBar counts={rollup.counts_by_verdict} />}
      {!row.pending && rollup && row.findings > 0 && (
        <p data-reviewed className="text-[12.5px] text-ink-3">
          {rollup.reviewed ?? 0} of {row.findings} reviewed
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center justify-between gap-x-3 gap-y-1.5 border-t border-border pt-3">
        {owner ? <PersonChip name={owner} /> : <span className="text-[13px] text-ink-3">{NO_OWNER_LABEL}</span>}
        <div className="flex items-center gap-2">
          {meta.two_signature && <TwoSignatureTag />}
          {meta.next_review && (
            <span className="inline-flex items-center gap-1 text-[12px] text-ink-3" title="Next review">
              <CalendarClock aria-hidden className="size-3.5" strokeWidth={1.5} />
              {formatDate(meta.next_review)}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}

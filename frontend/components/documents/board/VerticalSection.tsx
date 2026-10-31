import { ChevronRight } from "lucide-react";
import { AppLink } from "@/lib/app-link";
import { UploadDocumentDialog } from "@/components/documents/upload";
import { pluralize } from "@/lib/format";
import { DocCard } from "./DocCard";
import { SampleDocRow } from "./SampleDocRow";
import { isUnclassified, verticalHref, type VerticalGroup } from "./logic";

/** Shown for a vertical (or filter result) with no documents. Never a blank panel. */
export function EmptyVertical({ name, slug, filtered }: { name: string; slug: string; filtered?: boolean }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-dashed border-border-strong px-4 py-4">
      <p className="max-w-[60ch] text-[14px] leading-5 text-ink-3">
        {filtered
          ? `No ${name} documents match these filters.`
          : `No documents are filed under ${name} yet. When one is added, Strata checks it against every regulatory change.`}
      </p>
      {/* Renders nothing for a vertical that cannot take uploads (or "unclassified"). */}
      {!filtered && <UploadDocumentDialog vertical={slug} variant="inline" />}
    </div>
  );
}

/**
 * One vertical: linked header (name, count, needs-action count), document cards, then not-monitored
 * rows. The "Unclassified" group has no vertical page, so its header is not a link.
 */
export function VerticalSection({ group, filtered }: { group: VerticalGroup; filtered?: boolean }) {
  const { vertical, rows, cards, samples, needsAction } = group;
  const title = (
    <>
      <h2 id={`v-${vertical.slug}`} className="truncate text-[18px] font-medium leading-6 text-ink group-hover:underline">
        {vertical.name}
      </h2>
      <span className="shrink-0 text-[14px] text-ink-3">
        · {pluralize(rows.length, "document")}
      </span>
    </>
  );
  return (
    <section aria-labelledby={`v-${vertical.slug}`} data-vertical={vertical.slug}>
      <header className="mb-3 flex items-center justify-between gap-4">
        {isUnclassified(vertical.slug) ? (
          <div className="inline-flex min-w-0 items-baseline gap-2">{title}</div>
        ) : (
          <AppLink href={verticalHref(vertical.slug)} className="group inline-flex min-w-0 items-baseline gap-2">
            {title}
            <ChevronRight aria-hidden className="size-4 shrink-0 self-center text-ink-4" strokeWidth={1.5} />
          </AppLink>
        )}
        {needsAction > 0 && (
          <span className="shrink-0 text-[13px] font-medium text-[color:var(--verdict-action-required)]">
            {needsAction} {needsAction === 1 ? "needs" : "need"} attention
          </span>
        )}
      </header>
      {rows.length === 0 ? (
        <EmptyVertical name={vertical.name} slug={vertical.slug} filtered={filtered} />
      ) : (
        <div className="space-y-3">
          {cards.length > 0 && (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {cards.map((r) => (
                <DocCard key={r.meta.doc_id} row={r} />
              ))}
            </div>
          )}
          {samples.length > 0 && (
            <ul className="overflow-hidden rounded-[12px] border border-border bg-surface">
              {samples.map((r) => (
                <SampleDocRow key={r.meta.doc_id} row={r} />
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

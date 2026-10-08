import { FileText } from "lucide-react";
import { FutureCue } from "@/components/common/FutureCue";
import { PersonChip } from "@/components/common/PersonChip";
import { DocStatusPill } from "./DocStatusPill";
import type { DocRow } from "./logic";

/** Compact row for a document that is not monitored: no reader link, disabled "Start monitoring". */
export function SampleDocRow({ row }: { row: DocRow }) {
  const { meta } = row;
  return (
    <li
      data-doc-id={meta.doc_id}
      className="flex min-h-10 flex-wrap items-center gap-x-4 gap-y-1 border-t border-border px-4 py-2 first:border-t-0"
    >
      <FileText aria-hidden className="size-4 shrink-0 text-ink-4" strokeWidth={1.5} />
      <span className="min-w-0 flex-1 truncate text-[14px] text-ink-2" title={meta.title}>
        {meta.title}
      </span>
      <span className="hidden font-mono text-[12.5px] text-ink-3 md:inline">{meta.doc_id}</span>
      <PersonChip name={meta.owner.name} className="hidden w-48 lg:inline-flex" />
      <DocStatusPill status="not_monitored" />
      <FutureCue id="start-monitoring" variant="inline-add" />
    </li>
  );
}

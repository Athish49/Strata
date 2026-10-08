"use client";
import * as React from "react";
import { Check } from "lucide-react";
import type { ChangeRecord, DocumentMeta, MatrixCell } from "@/lib/api/schemas";
import { AppLink } from "@/lib/app-link";
import { pluralize } from "@/lib/format";
import { verdictLabel } from "@/lib/labels";
import { compareVerticals, verticalName } from "@/lib/verticals";
import { verdictToken } from "@/lib/verdict-tokens";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { ClassPill } from "./ClassPill";

export interface MatrixCellInfo {
  doc: DocumentMeta;
  change: ChangeRecord;
  cell: MatrixCell;
}

export interface MatrixGridProps {
  /** Rows: the monitored documents (grouped by `vertical`). */
  docs: DocumentMeta[];
  /** Columns: changed sections. */
  changes: ChangeRecord[];
  /** Sparse cells; a missing (doc, change) pair renders empty = the document does not cite the section. */
  cells: MatrixCell[];
  /** Emitted when a populated cell is activated (click / Enter / Space). Pages use it to load the cell's findings. */
  onCellClick?: (info: MatrixCellInfo) => void;
  /** Content of the cell popover (findings + cleared candidates with links). Default: a count summary. */
  renderCellPopover?: (info: MatrixCellInfo) => React.ReactNode;
  /** Row header link; omit for plain text. */
  docHref?: (doc: DocumentMeta) => string | undefined;
  className?: string;
}

function CellFace({ cell }: { cell: MatrixCell }) {
  if (cell.worst_verdict === "cleared") {
    return <Check aria-hidden className={cn("size-4", verdictToken("cleared").text)} strokeWidth={2} />;
  }
  const tok = verdictToken(cell.worst_verdict);
  return (
    <span className="inline-flex items-center gap-1">
      <span aria-hidden className={cn("size-2.5 rounded-full", tok.dot)} />
      <span className="text-[12px] tabular-nums text-ink-2">{cell.n_findings}</span>
    </span>
  );
}

function cellLabel(doc: DocumentMeta, change: ChangeRecord, cell: MatrixCell) {
  const outcome =
    cell.worst_verdict === "cleared"
      ? `${pluralize(cell.n_cleared, "clause")} checked and cleared`
      : `${pluralize(cell.n_findings, "finding")}, worst: ${verdictLabel(cell.worst_verdict)}${cell.n_cleared ? `, ${cell.n_cleared} cleared` : ""}`;
  return `${doc.title}, ${change.citation}: ${outcome}`;
}

/** Docs × changes grid. Presentational: popover content is supplied by the page, clicks are emitted. */
export function MatrixGrid({ docs, changes, cells, onCellClick, renderCellPopover, docHref, className }: MatrixGridProps) {
  const [open, setOpen] = React.useState<string | null>(null);
  const byKey = React.useMemo(() => {
    const m = new Map<string, MatrixCell>();
    for (const c of cells) m.set(`${c.doc_id}|${c.change_id}`, c);
    return m;
  }, [cells]);

  const groups = React.useMemo(() => {
    const g = new Map<string, DocumentMeta[]>();
    for (const d of docs) g.set(d.vertical, [...(g.get(d.vertical) ?? []), d]);
    return [...g.entries()].sort((a, b) => compareVerticals(a[0], b[0]));
  }, [docs]);

  if (docs.length === 0 || changes.length === 0) {
    return (
      <p className="rounded-[12px] border border-dashed border-border-strong px-4 py-8 text-center text-[14px] text-ink-3">
        {changes.length === 0 ? "No changed sections to show." : "No documents to show."}
      </p>
    );
  }

  return (
    <div className={cn("overflow-auto rounded-[12px] border border-border bg-surface", className)}>
      <table className="border-collapse text-[13px]">
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 z-20 min-w-[260px] border-b border-r border-border bg-surface px-3 py-2 text-left align-bottom text-[12px] font-medium text-ink-3">
              Document
            </th>
            {changes.map((c) => (
              <th key={c.change_id} scope="col" aria-label={`${c.citation}, ${c.heading}`} className="h-[132px] w-11 min-w-11 border-b border-r border-border p-0 align-bottom last:border-r-0">
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button type="button" className="mx-auto flex h-[124px] w-full items-end justify-center pb-2 text-ink-2 hover:text-ink">
                      <span className="max-h-[116px] overflow-hidden whitespace-nowrap font-mono text-[12px] [text-orientation:mixed] [writing-mode:vertical-rl] rotate-180">{c.citation}</span>
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="bottom">
                    <div className="font-mono">{c.citation}</div>
                    <div className="mt-0.5">{c.heading}</div>
                    <div className="mt-1 text-ink-4">{pluralize(c.cited_clause_count, "clause")} cite it</div>
                  </TooltipContent>
                </Tooltip>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map(([vertical, rows]) => (
            <React.Fragment key={vertical}>
              <tr>
                <th scope="colgroup" colSpan={changes.length + 1} className="sticky left-0 border-b border-border bg-surface-muted px-3 py-1.5 text-left text-[13px] font-medium text-ink">
                  {verticalName(vertical)} <span className="font-normal text-ink-3">· {pluralize(rows.length, "document")}</span>
                </th>
              </tr>
              {rows.map((d) => {
                const href = docHref?.(d);
                return (
                  <tr key={d.doc_id} className="group h-8">
                    <th scope="row" className="sticky left-0 z-10 max-w-[300px] border-b border-r border-border bg-surface px-3 text-left font-normal group-hover:bg-surface-muted">
                      {href ? (
                        <AppLink href={href} className="block truncate hover:underline" title={d.title}>
                          <span className="font-mono text-[12.5px] text-ink">{d.doc_id}</span> <span className="text-ink-3">{d.title}</span>
                        </AppLink>
                      ) : (
                        <span className="block truncate" title={d.title}>
                          <span className="font-mono text-[12.5px] text-ink">{d.doc_id}</span> <span className="text-ink-3">{d.title}</span>
                        </span>
                      )}
                    </th>
                    {changes.map((c) => {
                      const cell = byKey.get(`${d.doc_id}|${c.change_id}`);
                      const key = `${d.doc_id}|${c.change_id}`;
                      const td = "h-8 w-11 min-w-11 border-b border-r border-border p-0 text-center last:border-r-0 group-hover:bg-surface-muted";
                      if (!cell) {
                        return <td key={c.change_id} className={td} data-empty="true" />;
                      }
                      const info = { doc: d, change: c, cell };
                      return (
                        <td key={c.change_id} className={td}>
                          <Popover open={open === key} onOpenChange={(o) => setOpen(o ? key : null)}>
                            <PopoverTrigger asChild>
                              <button
                                type="button"
                                aria-label={cellLabel(d, c, cell)}
                                data-cell={key}
                                data-verdict={cell.worst_verdict}
                                onClick={() => onCellClick?.(info)}
                                className="grid h-8 w-full place-items-center hover:bg-surface-muted"
                              >
                                <CellFace cell={cell} />
                              </button>
                            </PopoverTrigger>
                            <PopoverContent className="w-80">
                              <div className="mb-2 space-y-0.5">
                                <div className="font-mono text-[12.5px]">{c.citation}</div>
                                <div className="text-[13px] text-ink-2">{d.title}</div>
                                <ClassPill changeClass={c.change_class} className="mt-1" />
                              </div>
                              {renderCellPopover ? (
                                renderCellPopover(info)
                              ) : (
                                <p className="text-[13px] text-ink-2">
                                  {cell.n_findings > 0 ? `${pluralize(cell.n_findings, "finding")} (worst: ${verdictLabel(cell.worst_verdict)}). ` : ""}
                                  {cell.n_cleared > 0 ? `${pluralize(cell.n_cleared, "clause")} checked and cleared.` : ""}
                                </p>
                              )}
                            </PopoverContent>
                          </Popover>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </React.Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

"use client";
import * as React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { MatchPath } from "@/lib/api/schemas";
import { AppLink } from "@/lib/app-link";
import { DocChip } from "@/components/common/DocChip";
import { formatCount, pluralize } from "@/lib/format";
import { verdictLabel, type VerdictOrCleared } from "@/lib/labels";
import { VERDICT_SEVERITY_ORDER } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";
import { MatchPathIcon } from "./MatchPathIcon";
import { VerdictPill } from "./VerdictPill";

export interface LedgerRow {
  /** Stable key (finding_id or candidate_id). Never displayed. */
  id: string;
  /** Clause id as shown (mono), e.g. "RPL-CS-PRO-004:8.2". */
  clauseId: string;
  /** Short clause label, e.g. "§8.2" (optional). */
  clauseLabel?: string;
  docId: string;
  docTitle?: string;
  matchPath: MatchPath;
  /** One-line reason or finding sentence. */
  reason: React.ReactNode;
  /** Findings: their verdict. Cleared rows ignore it. */
  verdict?: VerdictOrCleared;
  /** Row navigates here (cleared rows -> the reader). */
  href?: string;
}

export interface LedgerListProps {
  /** Affected candidates. Grouped by verdict, worst first. */
  findings: LedgerRow[];
  /** Cleared candidates (collapsed by default). */
  cleared: LedgerRow[];
  /** Called when a finding row is activated (opens the evidence drawer). */
  onOpenFinding?: (row: LedgerRow) => void;
  /** Start with "Cleared (n)" expanded. */
  defaultClearedOpen?: boolean;
  /** Rows shown before "Show more" in a long group (default 50). */
  pageSize?: number;
  className?: string;
}

function Row({ row, onOpen }: { row: LedgerRow; onOpen?: (row: LedgerRow) => void }) {
  const inner = (
    <>
      <MatchPathIcon path={row.matchPath} />
      <span className="w-[210px] shrink-0 truncate font-mono text-[12.5px] text-ink" title={row.clauseId}>
        {row.clauseLabel ? <span className="mr-1.5 font-sans text-ink-2">{row.clauseLabel}</span> : null}
        {row.clauseId}
      </span>
      <DocChip docId={row.docId} className="w-[170px] shrink-0" />
      <span className="min-w-0 flex-1 truncate text-[13px] text-ink-2">{row.reason}</span>
    </>
  );
  const cls = "flex h-8 w-full items-center gap-3 px-3 text-left transition-colors hover:bg-surface-muted";
  if (row.href && !onOpen) {
    return (
      <AppLink href={row.href} className={cls}>
        {inner}
      </AppLink>
    );
  }
  return (
    <button type="button" onClick={() => onOpen?.(row)} className={cls}>
      {inner}
    </button>
  );
}

function Rows({ rows, onOpen, pageSize }: { rows: LedgerRow[]; onOpen?: (row: LedgerRow) => void; pageSize: number }) {
  const [shown, setShown] = React.useState(pageSize);
  const visible = rows.slice(0, shown);
  return (
    <div className="divide-y divide-border">
      {visible.map((r) => (
        <Row key={r.id} row={r} onOpen={onOpen} />
      ))}
      {rows.length > shown && (
        <button type="button" onClick={() => setShown((s) => s + pageSize)} className="h-8 w-full px-3 text-left text-[13px] text-ink-3 hover:text-ink">
          Show {formatCount(Math.min(pageSize, rows.length - shown))} more of {formatCount(rows.length - shown)} remaining
        </button>
      )}
    </div>
  );
}

/** Impacted-clauses ledger for a change or document: findings by verdict first, then a collapsed "Cleared (n)" group with reasons. */
export function LedgerList({ findings, cleared, onOpenFinding, defaultClearedOpen = false, pageSize = 50, className }: LedgerListProps) {
  const [open, setOpen] = React.useState(defaultClearedOpen);
  const grouped = React.useMemo(() => {
    const by = new Map<string, LedgerRow[]>();
    for (const f of findings) {
      const v = f.verdict && f.verdict !== "cleared" ? f.verdict : "info";
      by.set(v, [...(by.get(v) ?? []), f]);
    }
    return VERDICT_SEVERITY_ORDER.filter((v) => by.has(v)).map((v) => ({ verdict: v, rows: by.get(v) ?? [] }));
  }, [findings]);

  if (findings.length === 0 && cleared.length === 0) {
    return <p className="rounded-[8px] border border-dashed border-border-strong px-4 py-6 text-center text-[13px] text-ink-3">No clause was checked against this change.</p>;
  }

  return (
    <div className={cn("overflow-hidden rounded-[12px] border border-border bg-surface", className)}>
      {grouped.map((g) => (
        <section key={g.verdict} aria-label={verdictLabel(g.verdict)} className="border-b border-border last:border-b-0">
          <h4 className="flex items-center gap-2 bg-surface-muted px-3 py-1.5 text-[13px] font-medium text-ink">
            <VerdictPill verdict={g.verdict} size="sm" />
            <span className="font-normal text-ink-3">· {pluralize(g.rows.length, "clause")}</span>
          </h4>
          <Rows rows={g.rows} onOpen={onOpenFinding} pageSize={pageSize} />
        </section>
      ))}
      {cleared.length > 0 && (
        <section aria-label="Cleared" className="border-border">
          <h4 className="m-0">
            <button
              type="button"
              aria-expanded={open}
              onClick={() => setOpen((o) => !o)}
              className="flex w-full items-center gap-2 bg-surface-muted px-3 py-1.5 text-left text-[13px] font-medium text-ink"
            >
              {open ? <ChevronDown aria-hidden className="size-4 text-ink-3" strokeWidth={1.5} /> : <ChevronRight aria-hidden className="size-4 text-ink-3" strokeWidth={1.5} />}
              Cleared ({formatCount(cleared.length)})
              <span className="font-normal text-ink-3">· checked, no impact</span>
            </button>
          </h4>
          {open && <Rows rows={cleared} pageSize={pageSize} />}
        </section>
      )}
    </div>
  );
}

"use client";
import * as React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { VerdictPill } from "@/components/engine";
import { formatCount, pluralize } from "@/lib/format";
import { clauseLabel, localClauseId } from "@/lib/sentences";
import { cn } from "@/lib/utils";
import type { ClearedClause, RailFinding } from "./model";

export interface FindingsRailProps {
  findings: RailFinding[];
  /** finding key -> plain-English sentence (falls back to the finding's rationale). */
  sentences: ReadonlyMap<string, string>;
  activeId: string | null;
  /** Click or Enter on a finding: scroll to its clause, pulse it and open the evidence drawer. */
  onSelect: (finding: RailFinding) => void;
  cleared: ClearedClause[];
  /** Click on a cleared clause: scroll there and show its reasons. */
  onSelectCleared?: (clauseId: string) => void;
  /** Shown instead of the empty message while the run's results load. */
  loading?: boolean;
  className?: string;
}

/** Right rail: findings in document order, then a collapsed "Cleared (n)" group. */
export function FindingsRail({ findings, sentences, activeId, onSelect, cleared, onSelectCleared, loading, className }: FindingsRailProps) {
  const [open, setOpen] = React.useState(false);
  const [shown, setShown] = React.useState(30);
  const activeRef = React.useRef<HTMLButtonElement | null>(null);
  React.useEffect(() => {
    activeRef.current?.scrollIntoView?.({ block: "nearest" });
  }, [activeId]);

  return (
    <aside aria-label="Findings" className={cn("flex min-h-0 flex-col rounded-[12px] border border-border bg-surface", className)}>
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <h2 className="text-[14px] font-medium text-ink">Findings</h2>
        <span className="text-[13px] tabular-nums text-ink-3">{formatCount(findings.length)}</span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {findings.length === 0 ? (
          <p className="px-4 py-5 text-[13px] leading-5 text-ink-3">
            {loading ? "Loading findings…" : "No clause in this document is out of line with the changes in this run."}
          </p>
        ) : (
          <ol className="divide-y divide-border">
            {findings.map((f) => {
              const active = f.id === activeId;
              return (
                <li key={f.id}>
                  <button
                    type="button"
                    ref={active ? activeRef : undefined}
                    data-finding-id={f.id}
                    aria-current={active ? "true" : undefined}
                    onClick={() => onSelect(f)}
                    className={cn(
                      "flex w-full flex-col items-start gap-1.5 px-4 py-3 text-left transition-colors duration-150 hover:bg-surface-muted",
                      active && "bg-surface-muted shadow-[inset_2px_0_0_var(--ink)]",
                    )}
                  >
                    <span className="flex w-full items-center gap-2">
                      <VerdictPill verdict={f.verdict} size="sm" />
                      <span className="min-w-0 truncate font-mono text-[12px] text-ink" title={f.clause.clause_id}>
                        {localClauseId(f.clause)}
                      </span>
                    </span>
                    <span className="line-clamp-3 text-[13px] leading-[18px] text-ink">{sentences.get(f.id) ?? f.reason}</span>
                    {f.citation && <span className="font-mono text-[12px] text-ink-3">{f.citation}</span>}
                  </button>
                </li>
              );
            })}
          </ol>
        )}
        {cleared.length > 0 && (
          <section aria-label="Cleared" className="border-t border-border">
            <h3 className="m-0">
              <button
                type="button"
                aria-expanded={open}
                onClick={() => setOpen((o) => !o)}
                className="flex w-full items-center gap-2 bg-surface-muted px-4 py-2 text-left text-[13px] font-medium text-ink"
              >
                {open ? <ChevronDown aria-hidden className="size-4 text-ink-3" strokeWidth={1.5} /> : <ChevronRight aria-hidden className="size-4 text-ink-3" strokeWidth={1.5} />}
                Cleared ({formatCount(cleared.length)})
                <span className="font-normal text-ink-3">· checked, no impact</span>
              </button>
            </h3>
            {open && (
              <ul className="divide-y divide-border">
                {cleared.slice(0, shown).map((c) => (
                  <li key={c.clause.clause_id}>
                    <button
                      type="button"
                      onClick={() => onSelectCleared?.(c.clause.clause_id)}
                      className="flex w-full items-baseline justify-between gap-3 px-4 py-2 text-left text-[13px] hover:bg-surface-muted"
                    >
                      <span className="min-w-0 truncate">
                        <span className="text-ink-2">{clauseLabel(c.clause)}</span>
                      </span>
                      <span className="shrink-0 text-[12px] text-ink-3">{pluralize(c.reasons.length, "change")}</span>
                    </button>
                  </li>
                ))}
                {cleared.length > shown && (
                  <li>
                    <button type="button" onClick={() => setShown((s) => s + 40)} className="w-full px-4 py-2 text-left text-[13px] text-ink-3 hover:text-ink">
                      Show {formatCount(Math.min(40, cleared.length - shown))} more of {formatCount(cleared.length - shown)} remaining
                    </button>
                  </li>
                )}
              </ul>
            )}
          </section>
        )}
      </div>
    </aside>
  );
}

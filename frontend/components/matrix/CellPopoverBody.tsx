"use client";
import * as React from "react";
import { parseAsString, useQueryState } from "nuqs";
import { AppLink } from "@/lib/app-link";
import { useCandidates, useFindings } from "@/lib/api/queries";
import { findingSentence } from "@/lib/sentences";
import { pluralize } from "@/lib/format";
import { Skeleton } from "@/components/ui/skeleton";
import { VerdictPill, type MatrixCellInfo } from "@/components/engine";

/** "RPL-CS-PRO-004:8.2" -> "§8.2" (never shows the raw doc prefix twice). */
export function shortClause(clauseId: string): string {
  const local = clauseId.includes(":") ? clauseId.slice(clauseId.indexOf(":") + 1) : clauseId;
  return /^\d/.test(local) ? `§${local}` : local;
}

/** Content of a matrix cell popover: findings (open the evidence drawer), cleared candidates, deep links. */
export function CellPopoverBody({ info, runId }: { info: MatrixCellInfo; runId: string | null }) {
  const { doc, change } = info;
  const q = { doc_id: doc.doc_id, change_id: change.change_id };
  const findings = useFindings(runId, q);
  const candidates = useCandidates(runId, q);
  const [, setFinding] = useQueryState("finding", parseAsString);

  const cleared = (candidates.data ?? []).filter((c) => c.outcome === "cleared");
  const loading = findings.isLoading || candidates.isLoading;
  const failed = findings.isError || candidates.isError;

  return (
    <div className="space-y-3">
      {loading && (
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      )}
      {failed && <p className="text-[13px] text-ink-3">The clause details could not be loaded.</p>}
      {!loading && !failed && (findings.data ?? []).length > 0 && (
        <ul className="space-y-2">
          {(findings.data ?? []).map((f) => (
            <li key={f.finding_id}>
              <button
                type="button"
                onClick={() => void setFinding(f.finding_id)}
                className="block w-full rounded-[8px] border border-border p-2 text-left hover:bg-surface-muted"
              >
                <span className="mb-1 flex items-center gap-2">
                  <VerdictPill verdict={f.verdict} size="sm" />
                  <span className="font-mono text-[12px] text-ink-2">{shortClause(f.clause_id)}</span>
                </span>
                <span className="line-clamp-3 text-[13px] leading-[18px] text-ink-2">
                  {findingSentence(f, shortClause(f.clause_id), change)}
                </span>
                <span className="mt-1 block text-[12px] text-ink-3 underline">Open evidence</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!loading && !failed && cleared.length > 0 && (
        <div>
          <p className="mb-1 text-[12px] font-medium text-ink-3">
            Checked and cleared · {pluralize(cleared.length, "clause")}
          </p>
          <ul className="max-h-40 space-y-1 overflow-auto">
            {cleared.map((c) => (
              <li key={c.candidate_id} className="text-[12.5px] leading-[17px] text-ink-2">
                <span className="font-mono text-ink">{shortClause(c.clause_id)}</span>
                {(c.skip_reason || c.rationale) && <span className="text-ink-3"> · {c.skip_reason || c.rationale}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex items-center gap-3 border-t border-border pt-2 text-[13px]">
        <AppLink href={`/app/documents/${doc.doc_id}`} className="text-ink underline underline-offset-2">
          Open document
        </AppLink>
        <AppLink href={`/app/changes/${change.change_id}`} className="text-ink underline underline-offset-2">
          Open change
        </AppLink>
      </div>
    </div>
  );
}

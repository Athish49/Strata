"use client";
import * as React from "react";
import { parseAsBoolean, useQueryState } from "nuqs";
import { Check } from "lucide-react";
import { useMatrix } from "@/lib/api/queries";
import { useRunContext } from "@/lib/run-context";
import { pluralize } from "@/lib/format";
import { verdictToken } from "@/lib/verdict-tokens";
import { verdictLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { FutureCue } from "@/components/common/FutureCue";
import { Toolbar } from "@/components/common/Toolbar";
import { EvidenceDrawer, MatrixGrid } from "@/components/engine";
import { CellPopoverBody } from "./CellPopoverBody";

const LEGEND_VERDICTS = ["action_required", "review", "update_citation", "optional_relaxed", "info"] as const;

function Legend() {
  return (
    <ul aria-label="Legend" className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] text-ink-3">
      {LEGEND_VERDICTS.map((v) => (
        <li key={v} className="inline-flex items-center gap-1.5">
          <span aria-hidden className={cn("size-2.5 rounded-full", verdictToken(v).dot)} />
          {verdictLabel(v)}
        </li>
      ))}
      <li className="inline-flex items-center gap-1.5">
        <Check aria-hidden className={cn("size-3.5", verdictToken("cleared").text)} />
        Checked, all cleared
      </li>
      <li className="inline-flex items-center gap-1.5">
        <span aria-hidden className="inline-block h-3 w-4 rounded-[3px] border border-border bg-surface" />
        Document does not cite the section
      </li>
      <li>Number = findings in that cell; worst verdict colours the dot.</li>
    </ul>
  );
}

function NoiseToggle({ on, onChange }: { on: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="inline-flex h-8 cursor-pointer items-center gap-2 rounded-[8px] px-3 text-[14px] text-ink-2 hover:bg-surface-muted">
      <button
        type="button"
        role="switch"
        aria-checked={on}
        onClick={() => onChange(!on)}
        className={cn("relative h-[18px] w-8 rounded-full border border-border-strong transition-colors", on ? "bg-ink" : "bg-surface-muted")}
      >
        <span className={cn("absolute top-[2px] size-3 rounded-full bg-white shadow transition-all", on ? "left-[16px]" : "left-[2px] bg-ink-3")} />
        <span className="sr-only">Show noise columns</span>
      </button>
      Show noise columns
    </label>
  );
}

export function MatrixView() {
  const { runId, run, isLoading: runLoading } = useRunContext();
  const [noiseParam, setNoise] = useQueryState("noise", parseAsBoolean);
  const noise = !!noiseParam;
  const matrix = useMatrix(runId, { include_noise: noise });
  const data = matrix.data;

  const stats = React.useMemo(() => {
    if (!data) return null;
    const cells = data.cells;
    return {
      cleared: cells.filter((c) => c.worst_verdict === "cleared").length,
      flagged: cells.filter((c) => c.worst_verdict !== "cleared").length,
    };
  }, [data]);

  let body: React.ReactNode;
  if (!runId || runLoading || matrix.isLoading) {
    body = (
      <div className="space-y-2" aria-busy>
        <Skeleton className="h-[132px] w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
        <Skeleton className="h-8 w-full" />
      </div>
    );
  } else if (matrix.isError) {
    body = <ErrorState message="The impact matrix could not be loaded." source="Engine results" onRetry={() => void matrix.refetch()} />;
  } else if (run?.status === "running") {
    body = <EmptyState title="Results will appear when the run finishes" description="This matrix is built from the run's findings." />;
  } else if (!data || data.docs.length === 0 || data.changes.length === 0) {
    body = (
      <EmptyState
        title="Nothing to cross-check yet"
        description={
          data && data.docs.length > 0
            ? "No changed sections in this run touch the monitored documents."
            : "This run has no matrix to show. It may still be running, or no documents are monitored."
        }
      />
    );
  } else {
    body = (
      <MatrixGrid
        docs={data.docs}
        changes={data.changes}
        cells={data.cells}
        docHref={(d) => `/app/documents/${d.doc_id}`}
        renderCellPopover={(info) => <CellPopoverBody info={info} runId={runId} />}
        className="max-h-[calc(100vh-300px)]"
      />
    );
  }

  return (
    <div className="space-y-4">
      <Toolbar className="rounded-[12px] border border-border bg-surface">
        <NoiseToggle on={noise} onChange={(v) => void setNoise(v ? true : null)} />
        <FutureCue id="ai-column" />
        <FutureCue id="export-matrix" />
      </Toolbar>
      {stats && data && data.docs.length > 0 && (
        <p className="text-[14px] text-ink-2">
          {pluralize(data.docs.length, "document")} by {pluralize(data.changes.length, "changed section")}.{" "}
          {pluralize(stats.flagged, "cell")} with findings, {pluralize(stats.cleared, "cell")} checked and cleared.
        </p>
      )}
      {body}
      <Legend />
      <EvidenceDrawer />
    </div>
  );
}

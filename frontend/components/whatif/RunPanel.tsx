"use client";
import * as React from "react";
import { ArrowRight } from "lucide-react";
import { StageStepper } from "@/components/engine";
import { Button } from "@/components/ui/button";
import { AppLink } from "@/lib/app-link";
import { formatCount, pluralize } from "@/lib/format";
import type { Run, Stage } from "@/lib/api/schemas";

function sum(rec: Record<string, number> | undefined): number {
  return Object.values(rec ?? {}).reduce((a, b) => a + b, 0);
}

/** Per-stage result text shown once a run has finished (from `run.stats`). */
export function stageCountsFor(run: Run | null | undefined): Partial<Record<Stage, string>> | undefined {
  if (!run || run.status !== "succeeded") return undefined;
  const s = run.stats;
  return {
    delta: pluralize(s.changes_raw, "change"),
    characterize: `${formatCount(s.substantive)} real ${s.substantive === 1 ? "change" : "changes"}`,
    candidates: pluralize(sum(s.candidates_by_path), "candidate clause"),
    judge: pluralize(sum(s.findings_by_verdict), "finding"),
    ledger: pluralize(s.docs_flagged + s.docs_cleared, "document"),
  };
}

/** One plain sentence summarising a finished what-if run. */
export function runSummary(run: Run): string {
  const s = run.stats;
  const findings = sum(s.findings_by_verdict);
  if (findings === 0) return "No clause in your documents would be affected by this change.";
  return `${pluralize(findings, "finding")} across ${pluralize(s.docs_flagged, "document")}; ${pluralize(s.clauses_cleared, "clause")} checked and cleared.`;
}

/**
 * Stage progress for a what-if run (or the "starting" moment before the run exists), then the
 * results links. The run id only ever appears in link URLs.
 */
export function RunPanel({ run, starting }: { run: Run | null | undefined; starting?: boolean }) {
  const status = run?.status ?? "running";
  const counts = stageCountsFor(run);
  const ref = React.useRef<HTMLElement>(null);
  React.useEffect(() => {
    ref.current?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, []);
  const href = run ? `/app?run=${encodeURIComponent(run.run_id)}` : "/app";
  const q = run ? `?run=${encodeURIComponent(run.run_id)}` : "";
  return (
    <section ref={ref} aria-label="Run progress" className="rounded-[12px] border border-border bg-surface p-6">
      <div className="mb-4">
        <h2 className="text-[18px] font-medium leading-6 text-ink">
          {status === "succeeded" ? "Impact analysis finished" : status === "failed" ? "Impact analysis stopped" : "Running impact analysis"}
        </h2>
        <p className="text-[14px] leading-5 text-ink-3">
          {status === "succeeded" && run
            ? runSummary(run)
            : starting && !run
              ? "Starting the run…"
              : "Results will appear when the run finishes."}
        </p>
      </div>
      <StageStepper status={status} progress={run?.progress} stageCounts={counts} error={run?.error} />
      {status === "succeeded" && run && (
        <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-border pt-4">
          <Button variant="primary" asChild>
            <AppLink href={href}>
              Open results
              <ArrowRight />
            </AppLink>
          </Button>
          <Button variant="ghost" asChild>
            <AppLink href={`/app/documents${q}`}>Documents</AppLink>
          </Button>
          <Button variant="ghost" asChild>
            <AppLink href={`/app/changes${q}`}>Changes</AppLink>
          </Button>
        </div>
      )}
    </section>
  );
}

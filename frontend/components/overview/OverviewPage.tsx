"use client";
import { AppLink } from "@/lib/app-link";
import { EvidenceDrawer, StageStepper } from "@/components/engine";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { InfoStrip } from "@/components/common/InfoStrip";
import { ErrorState } from "@/components/common/ErrorState";
import { FutureCue } from "@/components/common/FutureCue";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useRollups, useScore, useRuns } from "@/lib/api/queries";
import { runKindLabel } from "@/lib/labels";
import { formatCount, pluralize } from "@/lib/format";
import { useRunContext } from "@/lib/run-context";
import { Attention } from "./Attention";
import { Funnel, OVERVIEW_LINKS } from "./Funnel";
import { Tiles } from "./Tiles";
import { isRunning, totalFindings } from "./logic";

function OverviewSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading overview" className="space-y-6">
      <Skeleton className="h-14 w-full rounded-[12px]" />
      <Skeleton className="h-[320px] rounded-[12px]" />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-[148px] rounded-[12px]" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-[12px]" />
    </div>
  );
}

export function OverviewPage() {
  const { run, runId, isLoading } = useRunContext();
  const runs = useRuns();
  const score = useScore(runId);
  const rollups = useRollups(runId);
  const running = isRunning(run);
  const done = run?.status === "succeeded";
  const stats = run?.stats;
  const findings = stats ? totalFindings(stats) : 0;
  const flaggedDocs = (rollups.data ?? []).filter((r) => r.status === "flagged").length || stats?.docs_flagged || 0;

  const header = (
    <PageHeader
      caption={run ? (run.kind === "whatif" ? "What-if scenario" : runKindLabel(run)) : "Overview"}
      title="The wave at a glance"
      actions={
        <>
          <FutureCue id="schedule-briefing" />
          <FutureCue id="export-report" />
        </>
      }
    />
  );

  let body: React.ReactNode;
  if (!runId && !isLoading && !runs.isLoading && (runs.data?.length ?? 0) === 0) {
    body = <ErrorState message={runs.isError ? "Runs could not be loaded." : "There are no runs yet."} source="Runs" onRetry={runs.isError ? () => void runs.refetch() : undefined} />;
  } else if (!run || !stats) {
    body = <OverviewSkeleton />;
  } else if (run.status === "failed") {
    body = <ErrorState message="This run failed." source={run.error ? `Run · ${run.error}` : "Run"} />;
  } else if (running) {
    body = (
      <div className="space-y-6">
        <section className="rounded-[12px] border border-border bg-surface p-6">
          <h2 className="mb-1 text-[18px] font-medium leading-6 text-ink">This run is in progress</h2>
          <p className="mb-4 text-[14px] text-ink-3">Results will appear when the run finishes.</p>
          <StageStepper status={run.status} progress={run.progress} error={run.error} />
        </section>
        <Attention runId={runId} running />
      </div>
    );
  } else {
    body = (
      <div className="space-y-6">
        {findings > 0 ? (
          <InfoStrip href="/app/documents?status=action_needed">
            {pluralize(findings, "clause")} {findings === 1 ? "needs" : "need"} action across {pluralize(flaggedDocs, "document")}.
          </InfoStrip>
        ) : null}
        {findings === 0 && done ? (
          <section aria-label="No clause needs action" className="rounded-[12px] border border-border bg-surface p-8">
            <h2 className="font-serif text-[32px] font-normal leading-10 tracking-[-0.01em] text-ink">No clause needs action.</h2>
            <p className="mt-2 text-[15px] text-ink-2">
              <AppLink href={OVERVIEW_LINKS.cleared} className="underline decoration-border-strong underline-offset-4 hover:decoration-ink">
                {formatCount(stats.clauses_cleared)} clauses checked across {pluralize(stats.docs_flagged + stats.docs_cleared, "document")} — see why.
              </AppLink>
            </p>
            <Button asChild variant="secondary" className="mt-5">
              <AppLink href="/app/what-if">Try a what-if change</AppLink>
            </Button>
          </section>
        ) : null}
        <Funnel stats={stats} />
        <Tiles stats={stats} score={score.data} />
        {findings > 0 && <Attention runId={runId} />}
      </div>
    );
  }

  return (
    <PageContainer>
      {header}
      {body}
      <EvidenceDrawer />
    </PageContainer>
  );
}

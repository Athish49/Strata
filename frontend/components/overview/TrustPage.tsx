"use client";
import Link from "next/link";
import { Check } from "lucide-react";
import { AppLink } from "@/lib/app-link";
import { ScoreFigure } from "@/components/engine";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { FutureCue } from "@/components/common/FutureCue";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { useRuns, useScore } from "@/lib/api/queries";
import type { Run, ScoreReport } from "@/lib/api/schemas";
import { runKindLabel } from "@/lib/labels";
import { formatCount, pluralize } from "@/lib/format";
import { useRunContext } from "@/lib/run-context";

const METHOD = [
  "Only changes are evaluated.",
  "Noise classes never reach AI.",
  "Every finding carries verified quotes.",
  "Every change has a recorded outcome.",
];

export function newestBaseline(runs: readonly Run[] | undefined): Run | null {
  const b = (runs ?? []).filter((r) => r.kind === "baseline");
  b.sort((a, c) => (c.started_at ?? "").localeCompare(a.started_at ?? ""));
  return b[0] ?? null;
}

function Scorecard({ score }: { score: ScoreReport }) {
  const t = score.targets;
  return (
    <section aria-label="Accuracy" className="rounded-[12px] border border-border bg-surface p-6">
      <div className="grid gap-8 sm:grid-cols-2 xl:grid-cols-4 xl:divide-x xl:divide-border">
        <ScoreFigure label="Precision" value={score.precision} target={t.precision} className="xl:pr-6" />
        <ScoreFigure label="Recall" value={score.recall} target={t.recall} className="xl:px-6" />
        <ScoreFigure label="False-positive rate on the must-not-flag set" value={score.fp_rate_must_not_flag} target={t.fp_rate} goal="max" className="xl:px-6" />
        <ScoreFigure label="Routing accuracy" value={score.routing_accuracy} target={t.routing} className="xl:pl-6" />
      </div>
    </section>
  );
}

/** Document-level agreement: shown after the four honest clause-level metrics; never recolours them. */
function DocAgreement({ score }: { score: ScoreReport }) {
  const a = score.doc_agreement;
  if (!a || a.total <= 0) return null;
  return (
    <div className="mt-4 rounded-[12px] border border-border bg-surface px-6 py-4">
      <p className="font-serif text-[20px] leading-7 text-ink">
        <strong className="font-semibold">
          {formatCount(a.agree)} of {formatCount(a.total)} documents correctly flagged or cleared
        </strong>
        {a.agree === a.total && <Check aria-hidden className="ml-1.5 inline size-4 text-green" strokeWidth={2} />}
      </p>
      <p className="mt-1 text-[13px] leading-5 text-ink-3">
        Document-level agreement asks whether each document ends up flagged or cleared as expected. The clause-level metrics above ask whether each
        individual finding matches an expected clause, which is stricter.
      </p>
    </div>
  );
}

function Baseline({ score, baseline }: { score: ScoreReport; baseline: Run | null }) {
  const n = score.baseline_findings;
  const link = baseline ? `/app?run=${encodeURIComponent(baseline.run_id)}` : null;
  const text =
    n === null ? (
      "No baseline run has been recorded yet."
    ) : n === 0 ? (
      <>
        <strong className="font-semibold">Baseline: S1 vs S1 → 0 findings</strong>
        <Check aria-hidden className="ml-1.5 inline size-4 text-green" strokeWidth={2} />
        <span className="sr-only">Passed</span>
      </>
    ) : (
      <strong className="font-semibold">
        Baseline: S1 vs S1 → {pluralize(n, "finding")} (expected 0)
      </strong>
    );
  return (
    <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-border bg-surface px-6 py-4">
      <p className="font-serif text-[20px] leading-7 text-ink">{text}</p>
      <span className="flex items-center gap-4 text-[13px] text-ink-3">
        <span>Comparing a snapshot with itself must find nothing.</span>
        {link && (
          <Link href={link} className="font-medium text-ink-2 hover:text-ink">
            View baseline run
          </Link>
        )}
      </span>
    </div>
  );
}

export function TrustPage() {
  const { run, runId, isLoading } = useRunContext();
  const runs = useRuns();
  const q = useScore(runId);
  const score = q.data ?? null;
  const baseline = newestBaseline(runs.data);
  const decided = score?.decided_by ?? run?.stats.decided_by;
  const calls = score?.llm_calls ?? run?.stats.llm_calls;

  let body: React.ReactNode;
  if (q.isError) {
    body = <ErrorState message="The scorecard could not be loaded." source="Scores" onRetry={() => void q.refetch()} />;
  } else if (!runId || isLoading || q.isLoading) {
    body = (
      <div aria-busy="true" aria-label="Loading scorecard" className="space-y-4">
        <Skeleton className="h-[190px] rounded-[12px]" />
        <Skeleton className="h-16 rounded-[12px]" />
      </div>
    );
  } else if (!score) {
    body = (
      <section className="rounded-[12px] border border-border bg-surface">
        <EmptyState
          title="This run is not scored"
          description="Accuracy is measured on the real wave against a held-out answer set. What-if scenarios and baseline runs have no accuracy report."
          action={
            <Link href="/app/trust" className="text-[14px] font-medium text-ink-2 underline underline-offset-4 hover:text-ink">
              Show the real wave scorecard
            </Link>
          }
        />
      </section>
    );
  } else {
    body = (
      <>
        <Scorecard score={score} />
        <DocAgreement score={score} />
        <Baseline score={score} baseline={baseline} />
      </>
    );
  }

  return (
    <PageContainer>
      <PageHeader caption={run ? (run.kind === "whatif" ? "What-if scenario" : runKindLabel(run)) : "Trust"} title="Trust scorecard" actions={<FutureCue id="evidence-pack" />} />
      {body}
      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <section aria-label="Method" className="rounded-[12px] border border-border bg-surface p-6">
          <SectionHeader title="Method" subtitle="How every result is produced." className="mb-4" />
          <ul className="space-y-2.5">
            {METHOD.map((m) => (
              <li key={m} className="flex items-start gap-2.5 text-[14px] leading-5 text-ink">
                <span aria-hidden className="mt-2 size-1 shrink-0 rounded-full bg-ink" />
                {m}
              </li>
            ))}
          </ul>
          <div className="mt-5 border-t border-border pt-4">
            <FutureCue id="review-sampling" />
          </div>
        </section>
        <section aria-label="Decisions" className="rounded-[12px] border border-border bg-surface p-6">
          <SectionHeader title="Decisions" subtitle="Who made each call in this run." className="mb-4" />
          {decided ? (
            <dl className="grid grid-cols-3 gap-4">
              <div>
                <dt className="text-[12px] font-medium text-ink-3">Decided by rule</dt>
                <dd className="mt-1 font-serif text-[36px] leading-10 text-ink">{formatCount(decided.rule)}</dd>
              </div>
              <div>
                <dt className="text-[12px] font-medium text-ink-3">Decided by AI</dt>
                <dd className="mt-1 font-serif text-[36px] leading-10 text-ink">{formatCount(decided.ai)}</dd>
              </div>
              <div>
                <dt className="text-[12px] font-medium text-ink-3">LLM calls</dt>
                <dd className="mt-1 font-serif text-[36px] leading-10 text-ink">{calls === undefined ? "—" : formatCount(calls)}</dd>
              </div>
            </dl>
          ) : (
            <Skeleton className="h-16" />
          )}
          <p className="mt-4 text-[13px] text-ink-3">
            Each decision is traceable on its{" "}
            <AppLink href="/app/documents?status=action_needed" className="text-ink-2 underline underline-offset-4 hover:text-ink">
              evidence card
            </AppLink>
            .
          </p>
        </section>
      </div>
    </PageContainer>
  );
}

import { ArrowRight } from "lucide-react";
import { AppLink } from "@/lib/app-link";
import type { Run, ScoreReport } from "@/lib/api/schemas";
import { VerdictPill } from "@/components/engine";
import { formatCount, formatPercent } from "@/lib/format";
import { cn } from "@/lib/utils";
import { verdictCounts, totalFindings } from "./logic";

function Tile({ title, href, children, className }: { title: string; href: string; children: React.ReactNode; className?: string }) {
  return (
    <AppLink
      href={href}
      className={cn("group flex min-h-[148px] flex-col rounded-[12px] border border-border bg-surface p-5 transition-colors hover:bg-surface-muted", className)}
    >
      <div className="flex items-center justify-between text-[12px] font-medium leading-4 text-ink-3">
        <span>{title}</span>
        <ArrowRight aria-hidden className="size-3.5 opacity-0 transition-opacity group-hover:opacity-100" strokeWidth={1.5} />
      </div>
      {children}
    </AppLink>
  );
}

const fig = "mt-2 font-serif text-[40px] font-normal leading-[44px] tracking-[-0.01em] text-ink";

export function Tiles({ stats, score }: { stats: Run["stats"]; score: ScoreReport | null | undefined }) {
  const verdicts = verdictCounts(stats.findings_by_verdict);
  const findings = totalFindings(stats);
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <Tile title="Documents" href="/app/documents">
        <div className={fig}>
          {formatCount(stats.docs_flagged)} <span className="text-[18px] text-ink-3">flagged</span>
        </div>
        <p className="mt-auto pt-3 text-[13px] text-ink-3">
          <span className="font-medium text-green">{formatCount(stats.docs_cleared)} cleared</span> · {formatCount(stats.docs_flagged + stats.docs_cleared)} monitored
        </p>
      </Tile>
      <Tile title="Findings by verdict" href="/app/matrix">
        <div className={fig}>{formatCount(findings)}</div>
        <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
          {verdicts.length === 0 ? (
            <span className="text-[13px] text-ink-3">No findings in this run.</span>
          ) : (
            verdicts.map((v) => (
              <span key={v.verdict} className="inline-flex items-center gap-1 text-[12px] tabular-nums text-ink-2">
                <VerdictPill verdict={v.verdict} size="sm" />
                {formatCount(v.count)}
              </span>
            ))
          )}
        </div>
      </Tile>
      <Tile title="Radar" href="/app/radar">
        <div className={fig}>
          {formatCount(stats.radar.applicable)} <span className="text-[18px] text-ink-3">possibly applicable</span>
        </div>
        <p className="mt-auto pt-3 text-[13px] text-ink-3">
          Changes your documents don&apos;t cite · {formatCount(stats.radar.unclear)} unclear
        </p>
      </Tile>
      <Tile title="Trust" href="/app/trust">
        {score ? (
          <>
            <div className={fig}>
              {formatPercent(score.precision, 0)} <span className="text-[18px] text-ink-3">precision</span>
            </div>
            <p className="mt-auto pt-3 text-[13px] leading-5 text-ink-3">
              Recall {formatPercent(score.recall, 0)} · False positives {formatPercent(score.fp_rate_must_not_flag, 0)}
              {score.baseline_findings === 0 && <span className="font-medium text-green"> · Baseline ✓</span>}
            </p>
            {score.doc_agreement && score.doc_agreement.total > 0 && (
              <p className="mt-1 text-[13px] font-medium leading-5 text-ink-2">
                {formatCount(score.doc_agreement.agree)} of {formatCount(score.doc_agreement.total)} documents correct
              </p>
            )}
          </>
        ) : (
          <>
            <div className={cn(fig, "text-[28px] leading-[44px] text-ink-2")}>Not scored</div>
            <p className="mt-auto pt-3 text-[13px] leading-5 text-ink-3">This run has no accuracy report.</p>
          </>
        )}
      </Tile>
    </div>
  );
}

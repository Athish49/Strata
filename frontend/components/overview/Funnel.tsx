import { AppLink } from "@/lib/app-link";
import type { Run } from "@/lib/api/schemas";
import { FunnelBar } from "@/components/engine";
import { SectionHeader } from "@/components/common/SectionHeader";
import { formatCount, pluralize } from "@/lib/format";
import { noiseSplit, totalFindings } from "./logic";

// Query keys are the real nuqs filters of /app/changes (rpl, sub, noise, cls, disp) and /app/documents (status).
const NOISE_CLS = "cls=cosmetic,metadata_only,punctuation_only,cross_ref_only";
export const OVERVIEW_LINKS = {
  /** All real (non-noise) classes, whole law (run.stats.substantive = substantive + repealed + renumbered + new_section). */
  real: "/app/changes?rpl=false&sub=false",
  noise: `/app/changes?rpl=false&${NOISE_CLS}`,
  /** Real changes inside the footprint (run.stats.in_footprint_real). */
  footprint: "/app/changes?sub=false",
  /** Noise changes that also touched the footprint (run.stats.in_footprint - in_footprint_real). */
  footprintNoise: `/app/changes?${NOISE_CLS}`,
  /** Real changes inside the footprint whose obligation changed (run.stats.obligation_changed). */
  obligation: "/app/changes?sub=false",
  findings: "/app/documents?status=action_needed",
  cleared: "/app/documents?status=cleared",
} as const;

/** Hero card: the funnel from raw changes to findings, with the noise split and the cleared figure. Numbers are run.stats. */
export function Funnel({ stats }: { stats: Run["stats"] }) {
  const max = stats.changes_raw;
  const findings = totalFindings(stats);
  const noise = noiseSplit(stats.by_class);
  const realInFootprint = stats.in_footprint_real ?? null;
  const noiseInFootprint = realInFootprint === null ? 0 : Math.max(0, stats.in_footprint - realInFootprint);
  return (
    <section aria-label="From changes to clauses" className="rounded-[12px] border border-border bg-surface p-6">
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_240px]">
        <div className="min-w-0">
          <SectionHeader title="From changes to clauses" subtitle="Everything that changed in the law, narrowed to what touches your documents." className="mb-5" />
          <div className="space-y-1">
            <FunnelBar label="Changes in the law" count={stats.changes_raw} max={max} texture="hairline" suffix="changes" />
            <FunnelBar label="Real changes" count={stats.substantive} max={max} texture="hairline" suffix="real" href={OVERVIEW_LINKS.real} />
            <FunnelBar label="Noise removed" count={stats.noise} max={max} texture="noise" suffix="noise" href={OVERVIEW_LINKS.noise} />
            {noise.length > 0 && (
              <ul aria-label="Noise by class" className="!mb-2 ml-[162px] flex flex-wrap gap-x-4 gap-y-1 pb-1 text-[12px] text-ink-3">
                {noise.map((n) => (
                  <li key={n.key} className="inline-flex items-center gap-1.5">
                    <span aria-hidden className="mark-noise inline-block h-2.5 w-3.5 rounded-[2px] border border-ink-4" />
                    {n.label} <span className="tabular-nums text-ink-2">{formatCount(n.count)}</span>
                  </li>
                ))}
              </ul>
            )}
            <FunnelBar
              label="Real changes in your documents' rules"
              count={realInFootprint ?? stats.in_footprint}
              max={max}
              texture="hairline"
              suffix="real"
              href={realInFootprint === null ? "/app/changes?sub=false&noise=true" : OVERVIEW_LINKS.footprint}
            />
            {noiseInFootprint > 0 && (
              <p className="!mb-2 ml-[162px] pb-1 text-[12px] text-ink-3">
                <AppLink href={OVERVIEW_LINKS.footprintNoise} className="hover:underline">
                  + <span className="tabular-nums text-ink-2">{formatCount(noiseInFootprint)}</span> noise {noiseInFootprint === 1 ? "change" : "changes"} also touched your documents — cleared
                </AppLink>
              </p>
            )}
            <FunnelBar label="Obligation changed" count={stats.obligation_changed} max={max} texture="ink" suffix="changed" href={OVERVIEW_LINKS.obligation} />
            <FunnelBar label="Findings" count={findings} max={max} texture="ink" suffix={`${findings === 1 ? "finding" : "findings"} in ${pluralize(stats.docs_flagged, "document")}`} href={OVERVIEW_LINKS.findings} />
          </div>
        </div>
        <AppLink
          href={OVERVIEW_LINKS.cleared}
          className="group flex flex-col justify-center border-t border-border pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0"
        >
          <span className="font-serif text-[48px] font-normal leading-[52px] tracking-[-0.01em] text-green">{formatCount(stats.clauses_cleared)}</span>
          <span className="mt-1 text-[14px] leading-5 text-ink-2 group-hover:underline">
            {stats.clauses_cleared === 1 ? "clause" : "clauses"} checked and cleared
          </span>
          <span className="mt-1 text-[12px] leading-4 text-ink-3">
            Each with a recorded reason. Across {pluralize(stats.docs_flagged + stats.docs_cleared, "document")}.
          </span>
        </AppLink>
      </div>
    </section>
  );
}

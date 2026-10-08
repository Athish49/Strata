// Pure helpers for the Overview and Trust pages (no React).
import type { Finding, Run, RunStats, Verdict } from "@/lib/api/schemas";
import { NOISE_CLASSES, changeClassLabel } from "@/lib/labels";

export const VERDICT_ORDER: readonly Verdict[] = ["action_required", "review", "update_citation", "optional_relaxed", "info"];
const SEVERITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

/** Top findings: by severity (high first), then verdict order. Stable. At most `limit`. */
export function topFindings(findings: readonly Finding[], limit = 7): Finding[] {
  return findings
    .map((f, i) => ({ f, i }))
    .sort((a, b) => {
      const s = (SEVERITY_RANK[a.f.severity] ?? 9) - (SEVERITY_RANK[b.f.severity] ?? 9);
      if (s) return s;
      const v = VERDICT_ORDER.indexOf(a.f.verdict) - VERDICT_ORDER.indexOf(b.f.verdict);
      return v || a.i - b.i;
    })
    .slice(0, limit)
    .map((x) => x.f);
}

/** Total findings = sum of findings_by_verdict. */
export function totalFindings(stats: Pick<RunStats, "findings_by_verdict">): number {
  return Object.values(stats.findings_by_verdict ?? {}).reduce((n, k) => n + (k ?? 0), 0);
}

/** Noise classes with a non-zero count, largest first, with display labels. */
export function noiseSplit(byClass: Record<string, number>): { key: string; label: string; count: number }[] {
  return NOISE_CLASSES.map((key) => ({ key, label: changeClassLabel(key), count: byClass[key] ?? 0 }))
    .filter((x) => x.count > 0)
    .sort((a, b) => b.count - a.count);
}

/** Verdict counts in display order, non-zero only. */
export function verdictCounts(byVerdict: Record<string, number>): { verdict: Verdict; count: number }[] {
  return VERDICT_ORDER.map((verdict) => ({ verdict, count: byVerdict[verdict] ?? 0 })).filter((x) => x.count > 0);
}

export function isRunning(run: Pick<Run, "status"> | null | undefined): boolean {
  return run?.status === "running" || run?.status === "queued";
}

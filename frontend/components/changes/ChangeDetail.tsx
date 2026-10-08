"use client";
import * as React from "react";
import { ArrowUpRight } from "lucide-react";
import { parseAsString, useQueryState } from "nuqs";
import type { Candidate, ChangeRecord, Finding } from "@/lib/api/schemas";
import { useAgencies, useCandidates, useChange, useCompare, useFindings } from "@/lib/api/queries";
import { AppLink } from "@/lib/app-link";
import { useRunContext } from "@/lib/run-context";
import { ClassPill, DiffView, DirectionChip, LedgerList, TimelineStrip, ValueChangeChip, type LedgerRow } from "@/components/engine";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { FutureCue } from "@/components/common/FutureCue";
import { SectionHeader } from "@/components/common/SectionHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { sectionHref } from "@/components/kb/links";
import { formatCount, pluralize } from "@/lib/format";
import { changeClassLabel, isNoiseClass } from "@/lib/labels";
import { clearedReason, findingSentence, localClauseId } from "@/lib/sentences";
import { dateBasisLabel, dispositionLabel, noiseBanner, refineRawDiff } from "./logic";

function DetailSkeleton() {
  return (
    <div aria-label="Loading change" className="space-y-4">
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-9 w-2/3" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

/** Pure: candidates + findings -> ledger rows (findings by verdict, cleared with reasons). */
export function buildLedger(
  change: Pick<ChangeRecord, "change_class" | "citation" | "characterization">,
  candidates: readonly Candidate[],
  findings: readonly Finding[],
): { findings: LedgerRow[]; cleared: LedgerRow[] } {
  const byId = new Map(findings.map((f) => [f.finding_id, f]));
  const out = { findings: [] as LedgerRow[], cleared: [] as LedgerRow[] };
  for (const c of candidates) {
    const base = {
      clauseId: c.clause_id,
      clauseLabel: undefined,
      docId: c.doc_id,
      matchPath: c.match_path,
    };
    const f = c.finding_id ? byId.get(c.finding_id) : undefined;
    if (c.outcome === "affected" && f) {
      const hasChange = f.required_change.from_text && f.required_change.to_text;
      out.findings.push({
        ...base,
        id: f.finding_id,
        verdict: f.verdict,
        reason: hasChange ? findingSentence(f, `§${localClauseId({ clause_id: c.clause_id, doc_id: c.doc_id })}`, change) : f.rationale || findingSentence(f, "This clause", change),
      });
    } else if (c.outcome === "affected") {
      out.findings.push({ ...base, id: c.candidate_id, verdict: "review", reason: c.rationale || "Flagged for review." });
    } else {
      out.cleared.push({
        ...base,
        id: c.candidate_id,
        reason: clearedReason(c, change),
        href: `/app/documents/${encodeURIComponent(c.doc_id)}?clause=${encodeURIComponent(c.clause_id)}`,
      });
    }
  }
  return out;
}

function Ledger({ runId, change }: { runId: string; change: ChangeRecord }) {
  const cands = useCandidates(runId, { change_id: change.change_id });
  const finds = useFindings(runId, { change_id: change.change_id });
  const [, setFinding] = useQueryState("finding", parseAsString);
  const rows = React.useMemo(() => buildLedger(change, cands.data ?? [], finds.data ?? []), [change, cands.data, finds.data]);

  if (cands.isLoading || finds.isLoading) return <Skeleton className="h-32 w-full" aria-label="Loading impacted clauses" />;
  if (cands.isError || finds.isError)
    return <ErrorState message="The impacted clauses could not be loaded." source="Analysis results" onRetry={() => { void cands.refetch(); void finds.refetch(); }} />;

  const total = rows.findings.length + rows.cleared.length;
  const noise = isNoiseClass(change.change_class);
  return (
    <div className="space-y-3">
      {total > 0 && (
        <p data-testid="ledger-proof" className="text-[14px] leading-5 text-ink-2">
          {formatCount(total)} {total === 1 ? "clause" : "clauses"} checked
          {rows.findings.length > 0 ? <> · <strong className="font-medium text-ink">{formatCount(rows.findings.length)} flagged</strong></> : <> · none flagged</>}
          {rows.cleared.length > 0 && (
            <>
              {" · "}
              {noise ? `${changeClassLabel(change.change_class).toLowerCase()} change: ` : ""}
              {formatCount(rows.cleared.length)} cleared
            </>
          )}
        </p>
      )}
      <LedgerList
        findings={rows.findings}
        cleared={rows.cleared}
        onOpenFinding={(r) => void setFinding(r.id)}
      />
    </div>
  );
}

function RawDiffLoader({ change, children }: { change: ChangeRecord; children: (raw: React.ComponentProps<typeof DiffView>["rawDiff"]) => React.ReactNode }) {
  const [on, setOn] = React.useState(false);
  const q = useCompare(on ? change.source_system : null, on ? change.citation : null, change.s1_snapshot, change.s2_snapshot);
  const lines = React.useMemo(() => refineRawDiff(q.data), [q.data]);
  return <>{children({ lines, loading: on && q.isLoading, error: on && q.isError, onToggle: setOn })}</>;
}

/** Full change detail: header, characterization, timeline, diff, impacted clauses. */
export function ChangeDetail({ changeId }: { changeId: string }) {
  const { runId } = useRunContext();
  const q = useChange(runId, changeId);
  const agencies = useAgencies();

  if (!runId || q.isLoading) return <DetailSkeleton />;
  if (q.isError) return <ErrorState message="This change could not be loaded." source="Analysis results" onRetry={() => void q.refetch()} />;
  const c = q.data;
  if (!c)
    return (
      <EmptyState
        title="This change is not part of the selected run"
        description="It may belong to a different run. Pick another change from the list."
        action={<AppLink href="/app/changes" className="text-[14px] text-ink underline">Back to all changes</AppLink>}
      />
    );

  const agency = agencies.data?.find((a) => a.agency_id === c.agency_id)?.name ?? c.agency_id.toUpperCase();
  const ch = c.characterization;
  const noise = isNoiseClass(c.change_class);
  const banner = noiseBanner(c.change_class);
  const basis = dateBasisLabel(c.date_basis);
  const caption = [c.din ? `DIN ${c.din}` : null, c.published_date ? (basis ? `Publication date from the ${basis}` : null) : "Publication date not recorded for this change"].filter(Boolean).join(" · ") || undefined;

  return (
    <article className="space-y-6" data-testid="change-detail">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-ink-3">
          <span className="font-mono text-[13px] text-ink">{c.citation}</span>
          <ClassPill changeClass={c.change_class} />
          <span>{agency}</span>
          {c.in_footprint ? <span>Cited by {pluralize(c.cited_clause_count, "clause")}</span> : <span>Not cited by Rockridge documents</span>}
        </div>
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <h2 className="min-w-0 font-serif text-[28px] font-normal leading-9 tracking-[-0.01em] text-ink">{c.heading || c.citation}</h2>
          <div className="flex shrink-0 items-center gap-1">
            <FutureCue id="watch" />
            <FutureCue id="impact-memo" />
          </div>
        </div>
        {ch ? (
          <div className="space-y-2">
            {ch.summary && <p className="max-w-[72ch] text-[15px] leading-6 text-ink-2">{ch.summary}</p>}
            <div className="flex flex-wrap items-center gap-2">
              <DirectionChip direction={ch.direction} />
              {ch.value_changes.map((v, i) => (
                <ValueChangeChip key={i} change={v} />
              ))}
            </div>
          </div>
        ) : (
          <p className="max-w-[72ch] text-[14px] leading-5 text-ink-3">
            {noise ? "No plain-English summary: this change was screened out as noise before characterization." : "Not characterized yet. The exact wording change is shown below."}
          </p>
        )}
        {(c.disposition || c.disposition_reason) && (
          <p className="text-[13px] text-ink-3">
            <span className="font-medium text-ink-2">{dispositionLabel(c.disposition)}</span>
            {c.disposition_reason ? <> · {c.disposition_reason.replace(/\b1 (\w+)\(s\)/g, "1 $1").replace(/\(s\)/g, "s")}</> : null}
          </p>
        )}
      </header>

      <TimelineStrip
        points={[
          { key: "s1", label: "S1 snapshot", date: c.s1_snapshot },
          { key: "pub", label: "Published", date: c.published_date },
          { key: "s2", label: "S2 snapshot", date: c.s2_snapshot },
        ]}
        caption={caption}
      />

      <section aria-label="What changed" className="space-y-2">
        <SectionHeader title="What changed" subtitle="Old rule against new rule, word by word." />
        <RawDiffLoader change={c}>
          {(raw) => <DiffView key={c.change_id} segments={c.diff_segments} banner={banner} rawDiff={raw} hotkeys />}
        </RawDiffLoader>
      </section>

      <section aria-label="Impacted clauses" className="space-y-2">
        <SectionHeader title="Impacted clauses" subtitle="Every clause checked against this change, and what was decided." />
        <Ledger runId={runId} change={c} />
      </section>

      <div>
        <AppLink
          href={sectionHref(c.source_system, c.citation)}
          className="inline-flex items-center gap-1 text-[14px] text-ink underline decoration-border-strong underline-offset-4 hover:decoration-ink"
        >
          Open full regulation
          <ArrowUpRight aria-hidden className="size-4" strokeWidth={1.5} />
        </AppLink>
      </div>
    </article>
  );
}

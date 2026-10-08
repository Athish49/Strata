"use client";
import * as React from "react";
import { parseAsString, useQueryState } from "nuqs";
import type { Finding, UnitKind } from "@/lib/api/schemas";
import { findingHeadline, VerdictPill } from "@/components/engine";
import { DocChip } from "@/components/common/DocChip";
import { SectionHeader } from "@/components/common/SectionHeader";
import { ErrorState } from "@/components/common/ErrorState";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocuments, useFindings } from "@/lib/api/queries";
import { clauseLabel, localClauseId, type Segment } from "@/lib/sentences";
import { pluralize } from "@/lib/format";
import { topFindings } from "./logic";

const NODE_UNIT: Record<string, UnitKind> = { form_field: "form_field", register_row: "register_row", tariff_rule: "tariff_subrule" };

/** One-line sentence for a finding (§11.4); see findingHeadline. */
export function findingLine(f: Finding): Segment[] {
  const kind = f.path_detail[f.path_detail.length - 1]?.kind ?? "clause";
  const local = localClauseId({ clause_id: f.clause_id, doc_id: f.doc_id });
  const unit: UnitKind = NODE_UNIT[kind] ?? (/^[A-Za-z]/.test(local) ? "register_row" : "section");
  return findingHeadline(f, clauseLabel({ clause_id: f.clause_id, doc_id: f.doc_id, unit_kind: unit }));
}

/** "Needs your attention": up to 7 findings; a click opens the evidence drawer (?finding=). */
export function Attention({ runId, running }: { runId: string | null; running?: boolean }) {
  const q = useFindings(runId);
  const docs = useDocuments();
  const [, setFinding] = useQueryState("finding", parseAsString);
  const titles = React.useMemo(() => new Map((docs.data ?? []).map((d) => [d.doc_id, d.title])), [docs.data]);
  const all = q.data ?? [];
  const top = topFindings(all, 7);

  return (
    <section aria-label="Needs your attention" className="rounded-[12px] border border-border bg-surface">
      <div className="p-6 pb-4">
        <SectionHeader
          title="Needs your attention"
          subtitle={all.length > top.length ? `The ${top.length} most severe of ${pluralize(all.length, "finding")}.` : "Clauses that are out of line with the new rules."}
          viewAllHref={all.length > 0 ? "/app/documents?status=action_needed" : undefined}
          viewAllLabel="View documents"
        />
      </div>
      {q.isError ? (
        <ErrorState message="Findings could not be loaded." source="Findings" onRetry={() => void q.refetch()} />
      ) : q.isLoading || !runId ? (
        <div className="space-y-3 px-6 pb-6">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : top.length === 0 ? (
        <p className="border-t border-border px-6 py-6 text-[14px] text-ink-3">
          {running ? "Results will appear when the run finishes." : "No findings in this run."}
        </p>
      ) : (
        <ul className="border-t border-border">
          {top.map((f) => (
            <li key={f.finding_id} className="border-b border-border last:border-b-0">
              <button
                type="button"
                onClick={() => void setFinding(f.finding_id)}
                className="flex w-full items-center gap-4 px-6 py-3 text-left transition-colors hover:bg-surface-muted"
              >
                <span className="line-clamp-2 min-w-0 flex-1 text-[15px] leading-6 text-ink">
                  {findingLine(f).map((s, i) =>
                    s.strong ? (
                      <strong key={i} className="font-semibold">
                        {s.text}
                      </strong>
                    ) : (
                      <React.Fragment key={i}>{s.text}</React.Fragment>
                    ),
                  )}
                </span>
                <DocChip docId={f.doc_id} title={titles.get(f.doc_id)} className="hidden max-w-[260px] shrink-0 md:inline-flex [&>span:nth-child(2)]:whitespace-nowrap [&>span:nth-child(3)]:hidden xl:[&>span:nth-child(3)]:inline" />
                <VerdictPill verdict={f.verdict} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

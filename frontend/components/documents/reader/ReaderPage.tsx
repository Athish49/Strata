"use client";
import * as React from "react";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { useRecordRecent } from "@/components/shell/Recents";
import { useAutoCollapseSidebar } from "@/components/shell/ShellContext";
import { Skeleton } from "@/components/ui/skeleton";
import { useClauses, useDocument, useFindings, useReader, useRollups } from "@/lib/api/queries";
import { AppLink } from "@/lib/app-link";
import { pluralize } from "@/lib/format";
import { useRunContext } from "@/lib/run-context";
import { clauseLabel, findingSentence } from "@/lib/sentences";
import { documentStatus } from "@/lib/status";
import { DocumentReader } from "./DocumentReader";
import { ReaderHeader, rollupSentence } from "./ReaderHeader";

function ReaderSkeleton() {
  return (
    <div className="px-10 pt-5" aria-busy="true" aria-label="Loading document">
      <Skeleton className="mb-4 h-11 w-full rounded-[10px]" />
      {Array.from({ length: 7 }).map((_, i) => (
        <div key={i} className="mb-5 pl-14">
          <Skeleton className="mb-2 h-4 w-3/4" />
          <Skeleton className="mb-2 h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      ))}
    </div>
  );
}

/** "/app/documents/[docId]": header, document, findings rail, minimap and evidence drawer. */
export function ReaderPage({ docId }: { docId: string }) {
  useAutoCollapseSidebar();
  const { runId, run, isLoading: runLoading } = useRunContext();
  const reader = useReader(docId, runId);
  const docQ = useDocument(docId);
  const clausesQ = useClauses(docId);
  const rollups = useRollups(runId);
  const findingsQ = useFindings(runId, { doc_id: docId });

  const doc = reader.data?.doc ?? docQ.data ?? undefined;
  const clauses = React.useMemo(() => reader.data?.clauses ?? clausesQ.data ?? [], [reader.data, clausesQ.data]);
  const annotations = React.useMemo(() => reader.data?.annotations ?? [], [reader.data]);
  useRecordRecent(doc ? { href: `/app/documents/${doc.doc_id}`, label: doc.title } : null);

  const rollup = rollups.data?.find((r) => r.doc_id === docId);
  const status = doc ? documentStatus(doc, rollup) : undefined;
  const rollupsReady = !!runId && rollups.isSuccess;
  const sentence = rollupsReady || !runId ? rollupSentence(status, rollup) : null;

  const sentences = React.useMemo(() => {
    const m = new Map<string, string>();
    const byId = new Map(clauses.map((c) => [c.clause_id, c]));
    for (const f of findingsQ.data ?? []) {
      const c = byId.get(f.clause_id);
      m.set(f.finding_id, findingSentence(f, c ? clauseLabel(c) : f.clause_id).replace(/\.{2,}$/, "."));
    }
    return m;
  }, [findingsQ.data, clauses]);

  const loading = (!doc && (docQ.isLoading || reader.isLoading)) || (clauses.length === 0 && (clausesQ.isLoading || reader.isLoading));
  const failed = !doc && (docQ.isError || reader.isError);
  const missing = !loading && !failed && !doc;

  let notice: React.ReactNode = null;
  if (doc && rollupsReady && !rollup && annotations.length === 0) {
    const cites = doc.cited_citations ?? [];
    notice = (
      <section aria-label="Run coverage" className="mb-4 rounded-[12px] border border-border bg-surface px-5 py-4">
        <p className="font-serif text-[18px] leading-7 text-ink">No change in this run touched this document</p>
        {cites.length > 0 && (
          <>
            <p className="mt-1 text-[13px] text-ink-3">It cites {pluralize(cites.length, "rule")}:</p>
            <ul className="mt-2 flex flex-wrap gap-1.5">
              {cites.map((c) => (
                <li key={c} className="rounded-[4px] border border-border bg-surface-muted px-1.5 py-0.5 font-mono text-[12px] text-ink-2">
                  {c}
                </li>
              ))}
            </ul>
          </>
        )}
      </section>
    );
  } else if (doc && !runId && !runLoading) {
    notice = (
      <section aria-label="Run coverage" className="mb-4 rounded-[12px] border border-border bg-surface px-5 py-4">
        <p className="font-serif text-[18px] leading-7 text-ink">No analysis run to show yet</p>
        <p className="mt-1 text-[13px] text-ink-3">The document is shown without findings. Choose a run to see what changed.</p>
      </section>
    );
  } else if (run && run.status === "running") {
    notice = (
      <section aria-label="Run coverage" className="mb-4 rounded-[12px] border border-border bg-surface px-5 py-4 text-[14px] text-ink-2">
        Results will appear when the run finishes.
      </section>
    );
  }

  return (
    <div data-reader-page="">
      <ReaderHeader doc={doc} status={status} sentence={sentence} loading={loading} />
      {failed ? (
        <ErrorState
          message="This document could not be loaded."
          source="Company documents"
          onRetry={() => {
            void docQ.refetch();
            void reader.refetch();
          }}
        />
      ) : missing ? (
        <EmptyState
          title="We could not find this document"
          description="It may have been removed, or the link may be mistyped."
          action={
            <AppLink href="/app/documents" className="text-[14px] text-ink underline underline-offset-2">
              Back to documents
            </AppLink>
          }
        />
      ) : loading ? (
        <ReaderSkeleton />
      ) : (
        <DocumentReader
          docId={docId}
          clauses={clauses}
          annotations={annotations}
          sentences={sentences}
          notice={notice}
          loadingFindings={!!runId && (reader.isLoading || findingsQ.isLoading)}
        />
      )}
    </div>
  );
}

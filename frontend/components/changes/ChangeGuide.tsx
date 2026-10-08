"use client";
import Link from "next/link";
import { useChanges } from "@/lib/api/queries";
import { useRunContext } from "@/lib/run-context";
import { ClassPill } from "@/components/engine";
import { Skeleton } from "@/components/ui/skeleton";
import { formatCount } from "@/lib/format";
import { topCited } from "./logic";
import { useChangeHref } from "./useChangeHref";

/** Empty detail pane: a short guide and the 3 most-cited changes. */
export function ChangeGuide() {
  const { runId, run } = useRunContext();
  const q = useChanges(runId);
  const href = useChangeHref();
  const top = topCited(q.data ?? []);
  const running = run && (run.status === "running" || run.status === "queued");
  return (
    <div className="space-y-6">
      <div>
        <h2 className="font-serif text-[24px] leading-8 text-ink">Pick a change to see what moved</h2>
        <p className="mt-1 max-w-[60ch] text-[14px] leading-5 text-ink-3">
          Each change shows the old and new wording, what it means in plain English, and every company clause it touches. Cosmetic edits are
          filtered out by default; turn on Show noise to see what was removed and why.
        </p>
      </div>
      {running ? (
        <p className="text-[14px] text-ink-3">Results will appear when the run finishes.</p>
      ) : q.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : top.length > 0 ? (
        <section aria-label="Most cited changes">
          <h3 className="mb-2 text-[13px] font-medium text-ink-3">Most cited by your documents</h3>
          <ul className="divide-y divide-border overflow-hidden rounded-[12px] border border-border bg-surface">
            {top.map((c) => (
              <li key={c.change_id}>
                <Link href={href(c.change_id)} className="flex items-center gap-3 px-4 py-3 hover:bg-surface-muted">
                  <span className="w-[150px] shrink-0 font-mono text-[12.5px] text-ink">{c.citation}</span>
                  <span className="min-w-0 flex-1 truncate text-[14px] text-ink-2">{c.heading}</span>
                  <ClassPill changeClass={c.change_class} />
                  <span className="w-[110px] shrink-0 text-right text-[13px] text-ink-3">{formatCount(c.cited_clause_count)} clauses</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

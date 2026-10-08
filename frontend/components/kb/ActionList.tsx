"use client";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/common/EmptyState";
import { AppLink } from "@/lib/app-link";
import type { RegulatoryAction } from "@/lib/api/schemas";
import { formatDate } from "@/lib/format";
import { actionDisplayTitle, actionTypeLabel, StatusPill, streamLabel } from "./bits";
import { actionHref } from "./links";

/** Activity feed rows: title, type, status, stream chip, publication date (or "Date not published"). */
export function ActionList({
  actions,
  showStream = true,
  emptyTitle = "No actions match these filters",
  emptyDescription = "Try clearing a filter or choosing another stream.",
}: {
  actions: RegulatoryAction[];
  showStream?: boolean;
  emptyTitle?: string;
  emptyDescription?: string;
}) {
  if (actions.length === 0) return <EmptyState title={emptyTitle} description={emptyDescription} />;
  return (
    <ul className="divide-y divide-border">
      {actions.map((a) => (
        <li key={`${a.source_system}|${a.source_id}`}>
          <AppLink
            href={actionHref(a.source_system, a.source_id)}
            className="flex items-start gap-4 px-4 py-3 transition-colors duration-150 hover:bg-surface-muted"
          >
            <div className="min-w-0 flex-1">
              <div className="line-clamp-2 text-[14px] leading-5 text-ink">{actionDisplayTitle(a)}</div>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[12px] text-ink-3">
                <span className="font-mono text-[12px]">{a.source_id}</span>
                <span>{a.date_published ? formatDate(a.date_published) : "Date not published"}</span>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
              {showStream && <Badge variant="tag">{streamLabel(a.stream || a.source_system)}</Badge>}
              <Badge variant="neutral">{actionTypeLabel(a.action_type)}</Badge>
              <StatusPill status={a.status} />
            </div>
          </AppLink>
        </li>
      ))}
    </ul>
  );
}

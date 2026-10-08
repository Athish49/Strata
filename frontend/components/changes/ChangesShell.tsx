"use client";
import * as React from "react";
import { useSelectedLayoutSegment } from "next/navigation";
import { parseAsArrayOf, parseAsBoolean, parseAsString, useQueryStates } from "nuqs";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { EvidenceDrawer } from "@/components/engine";
import { ErrorState } from "@/components/common/ErrorState";
import { EmptyState } from "@/components/common/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import { useAgencies, useChanges } from "@/lib/api/queries";
import { useRunContext } from "@/lib/run-context";
import { ChangeTree } from "./ChangeTree";
import type { ChangeFilters } from "./logic";
import { useChangeHref } from "./useChangeHref";

const filterParsers = {
  rpl: parseAsBoolean.withDefault(true),
  sub: parseAsBoolean.withDefault(true),
  noise: parseAsBoolean.withDefault(false),
  cls: parseAsArrayOf(parseAsString).withDefault([]),
  disp: parseAsString,
  q: parseAsString.withDefault(""),
};

const MIN_W = 320;
const MAX_W = 640;

/** Layout of /app/changes: header, filterable change tree (persists while selecting), and the detail pane (children). */
export function ChangesShell({ children }: { children: React.ReactNode }) {
  const segment = useSelectedLayoutSegment();
  const selectedId = segment ? decodeURIComponent(segment) : null;
  const { runId, run, isLoading: runLoading } = useRunContext();
  const changes = useChanges(runId);
  const agencies = useAgencies();
  const hrefFor = useChangeHref();
  const [filters, setFilters] = useQueryStates(filterParsers, { clearOnDefault: true });
  const onFilters = React.useCallback((patch: Partial<ChangeFilters>) => void setFilters(patch), [setFilters]);

  const names = React.useMemo(() => new Map((agencies.data ?? []).filter((a) => a.agency_id).map((a) => [a.agency_id as string, a.name])), [agencies.data]);
  const agencyName = React.useCallback((id: string) => names.get(id) ?? id.toUpperCase(), [names]);

  const [width, setWidth] = React.useState(400);
  const drag = React.useRef<{ x: number; w: number } | null>(null);
  const running = run && (run.status === "running" || run.status === "queued");

  let tree: React.ReactNode;
  if (!runId || runLoading || changes.isLoading) {
    tree = (
      <div className="space-y-2 rounded-[12px] border border-border bg-surface p-3" aria-label="Loading changes">
        <Skeleton className="h-9 w-full" />
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  } else if (changes.isError) {
    tree = <ErrorState message="The changes could not be loaded." source="Analysis results" onRetry={() => void changes.refetch()} />;
  } else if (running) {
    tree = <EmptyState title="Analysis in progress" description="Results will appear when the run finishes." />;
  } else if ((changes.data ?? []).length === 0) {
    tree = <EmptyState title="No changes in this run" description="This run found no changed sections between the two snapshots." />;
  } else {
    tree = (
      <ChangeTree
        changes={changes.data ?? []}
        filters={filters}
        onFilters={onFilters}
        selectedId={selectedId}
        hrefFor={hrefFor}
        agencyName={agencyName}
        className="h-full"
      />
    );
  }

  return (
    <PageContainer full>
      <PageHeader caption="Changes" title="What changed in the law" />
      <div className="flex items-start gap-0 max-lg:flex-col">
        <aside style={{ "--tree-w": `${width}px` } as React.CSSProperties} className="sticky top-0 h-[calc(100vh-190px)] min-h-[420px] w-[min(var(--tree-w),max(320px,36%))] shrink-0 max-lg:static max-lg:mb-6 max-lg:h-[420px] max-lg:w-full" aria-label="Change list">
          {tree}
        </aside>
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize change list"
          aria-valuemin={MIN_W}
          aria-valuemax={MAX_W}
          aria-valuenow={width}
          tabIndex={0}
          onPointerDown={(e) => {
            drag.current = { x: e.clientX, w: width };
            e.currentTarget.setPointerCapture(e.pointerId);
          }}
          onPointerMove={(e) => {
            if (drag.current) setWidth(Math.min(MAX_W, Math.max(MIN_W, drag.current.w + e.clientX - drag.current.x)));
          }}
          onPointerUp={() => (drag.current = null)}
          onKeyDown={(e) => {
            if (e.key === "ArrowLeft") setWidth((w) => Math.max(MIN_W, w - 24));
            if (e.key === "ArrowRight") setWidth((w) => Math.min(MAX_W, w + 24));
          }}
          className="group mx-1.5 w-2 shrink-0 cursor-col-resize self-stretch max-lg:hidden"
        >
          <div className="mx-auto h-full w-px bg-border group-hover:bg-border-strong group-focus-visible:bg-ink" />
        </div>
        <section className="min-w-0 flex-1 pl-2 max-lg:pl-0" aria-label="Change detail">
          {children}
        </section>
      </div>
      <EvidenceDrawer />
    </PageContainer>
  );
}

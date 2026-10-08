"use client";
import * as React from "react";
import { Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { FutureCue } from "@/components/common/FutureCue";
import { Toolbar } from "@/components/common/Toolbar";
import { useActions } from "@/lib/api/queries";
import type { Agency } from "@/lib/api/schemas";
import { ActionList } from "./ActionList";
import { ACTION_STATUSES, ACTION_TYPES, actionStatusLabel, actionTypeLabel, Pager, SelectControl, useKeyedPage } from "./bits";
import { StreamChips } from "./StreamChips";

export const ACTIVITY_PAGE_SIZE = 25;

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = React.useState(value);
  React.useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Activity tab: stream chips, filters (type, status, dates, text) and a paginated ActionList. */
export function AgencyActivity({ agency }: { agency: Agency }) {
  const [stream, setStream] = React.useState<string | null>(null);
  const [type, setType] = React.useState("");
  const [status, setStatus] = React.useState("");
  const [from, setFrom] = React.useState("");
  const [to, setTo] = React.useState("");
  const [text, setText] = React.useState("");
  const search = useDebounced(text.trim());
  const [page, setPage] = useKeyedPage([stream, type, status, from, to, search].join("|"));

  const q = {
    agency: agency.agency_id ?? agency.slug,
    stream: stream ?? undefined,
    action_type: type || undefined,
    status: status || undefined,
    date_from: from || undefined,
    date_to: to || undefined,
    search: search || undefined,
    page,
    limit: ACTIVITY_PAGE_SIZE,
  };
  const actions = useActions(q);
  const filtered = !!(stream || type || status || from || to || search);

  return (
    <div>
      <Toolbar>
        <FutureCue id="track-docket" />
      </Toolbar>
      <div className="space-y-3 border-b border-border px-4 py-3">
        <StreamChips streams={agency.streams} value={stream} onChange={setStream} />
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-[260px]">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3" strokeWidth={1.5} />
            <Input
              aria-label="Search activity"
              placeholder="Search title or id"
              value={text}
              onChange={(e) => setText(e.target.value)}
              className="h-8 pl-8 text-[13px]"
            />
          </div>
          <SelectControl
            label="Type"
            value={type}
            onChange={setType}
            options={[{ value: "", label: "All types" }, ...ACTION_TYPES.map((t) => ({ value: t, label: actionTypeLabel(t) }))]}
          />
          <SelectControl
            label="Status"
            value={status}
            onChange={setStatus}
            options={[{ value: "", label: "Any status" }, ...ACTION_STATUSES.map((s) => ({ value: s, label: actionStatusLabel(s) }))]}
          />
          <label className="inline-flex items-center gap-2 text-[13px] text-ink-3">
            From
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="h-8 rounded-[8px] border border-border-strong bg-surface px-2 text-[13px] text-ink" />
          </label>
          <label className="inline-flex items-center gap-2 text-[13px] text-ink-3">
            To
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="h-8 rounded-[8px] border border-border-strong bg-surface px-2 text-[13px] text-ink" />
          </label>
          {filtered && (
            <button
              type="button"
              className="text-[13px] text-ink-2 underline-offset-2 hover:underline"
              onClick={() => {
                setStream(null);
                setType("");
                setStatus("");
                setFrom("");
                setTo("");
                setText("");
              }}
            >
              Clear filters
            </button>
          )}
        </div>
      </div>
      {actions.isError ? (
        <ErrorState message="The activity feed could not be loaded." source="Knowledge base · actions" onRetry={() => void actions.refetch()} />
      ) : actions.isLoading ? (
        <div className="space-y-3 p-4">
          {Array.from({ length: 6 }, (_, i) => (
            <Skeleton key={i} className="h-12" />
          ))}
        </div>
      ) : (
        <>
          <ActionList
            actions={actions.data?.items ?? []}
            emptyTitle={filtered ? "No actions match these filters" : "No actions recorded yet"}
            emptyDescription={filtered ? "Try clearing a filter or choosing another stream." : "This agency has no activity in the knowledge base yet."}
          />
          <Pager
            page={actions.data?.page ?? page}
            pages={Math.max(1, Math.ceil((actions.data?.total ?? 0) / ACTIVITY_PAGE_SIZE))}
            total={actions.data?.total ?? 0}
            size={ACTIVITY_PAGE_SIZE}
            onPage={setPage}
            noun="actions"
          />
        </>
      )}
    </div>
  );
}

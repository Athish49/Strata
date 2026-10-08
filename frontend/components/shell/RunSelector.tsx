"use client";
import { Check, ChevronDown } from "lucide-react";
import { useRunContext } from "@/lib/run-context";
import { useRuns } from "@/lib/api/queries";
import { runKindLabel } from "@/lib/labels";
import type { Run } from "@/lib/api/schemas";
import { FutureCue } from "@/components/common/FutureCue";
import { Badge } from "@/components/ui/badge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";

const ORDER = { kb: 0, baseline: 1, whatif: 2 } as const;
const STATUS: Record<Run["status"], string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "",
  failed: "Failed",
};

/** Select-style control listing runs; writes ?run= via setRunId. Shown at the right of every page header. */
export function RunSelector({ className }: { className?: string }) {
  const { run, runId, isSimulated, setRunId } = useRunContext();
  const { data } = useRuns();
  const runs = [...((data as Run[] | undefined) ?? [])].sort((a, b) => ORDER[a.kind] - ORDER[b.kind]);
  const currentId = runId ?? run?.run_id ?? null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          aria-label="Choose run"
          className={cn(
            "inline-flex h-8 items-center gap-2 rounded-[8px] border border-border-strong bg-surface px-3 text-[14px] font-medium text-ink transition-colors duration-150 hover:bg-surface-muted",
            className,
          )}
        >
          <span className="max-w-[260px] truncate">{run ? runKindLabel(run) : "Loading runs"}</span>
          {isSimulated && <Badge variant="tag">Simulated</Badge>}
          <ChevronDown className="size-3.5 text-ink-2" strokeWidth={1.5} />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-[320px]">
        <DropdownMenuLabel>Run</DropdownMenuLabel>
        {runs.map((r) => (
          <DropdownMenuItem key={r.run_id} onSelect={() => setRunId(r.run_id)} className="items-start">
            <Check
              className={cn("mt-0.5 size-4 shrink-0", r.run_id === currentId ? "text-ink" : "invisible")}
              strokeWidth={1.5}
            />
            <span className="min-w-0 flex-1">
              <span className="block truncate">{runKindLabel(r)}</span>
              {STATUS[r.status] && <span className="block text-[12px] text-ink-3">{STATUS[r.status]}</span>}
            </span>
            {r.kind === "whatif" && <Badge variant="tag">Simulated</Badge>}
          </DropdownMenuItem>
        ))}
        {runs.length === 0 && <div className="px-2.5 py-2 text-[13px] text-ink-3">No runs yet.</div>}
        <DropdownMenuSeparator />
        <DropdownMenuLabel>Coming soon</DropdownMenuLabel>
        <FutureCue id="continuous-monitoring" variant="menu-item" side="left" />
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

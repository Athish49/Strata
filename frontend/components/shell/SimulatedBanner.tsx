"use client";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useRunContext } from "@/lib/run-context";

/** Pinned to the top of the main area whenever the current run is a what-if. */
export function SimulatedBanner() {
  const { run, isSimulated, setRunId } = useRunContext();
  if (!isSimulated) return null;
  return (
    <div role="status" className="flex h-11 shrink-0 items-stretch border-b border-ink bg-surface">
      <div aria-hidden className="mark-simulated w-14 shrink-0 border-r border-ink" />
      <div className="flex min-w-0 flex-1 items-center gap-3 px-5">
        <Badge variant="tag" className="border-ink text-ink">
          Simulated
        </Badge>
        <p className="min-w-0 truncate text-[14px] text-ink">
          {run ? `What-if: ${run.title}. ` : ""}These results are not real regulatory changes.
        </p>
      </div>
      <div className="flex items-center pr-4">
        <Button variant="secondary" size="sm" onClick={() => setRunId(null)}>
          Back to real wave
        </Button>
      </div>
    </div>
  );
}

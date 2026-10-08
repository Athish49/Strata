import { Check, X } from "lucide-react";
import type { Run, Stage } from "@/lib/api/schemas";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";

export const STAGES: readonly { key: Stage; label: string }[] = [
  { key: "delta", label: "Delta" },
  { key: "characterize", label: "Characterize" },
  { key: "candidates", label: "Candidates" },
  { key: "judge", label: "Judge" },
  { key: "ledger", label: "Ledger" },
];

export interface StageStepperProps {
  /** `run.status`. */
  status: Run["status"];
  /** `run.progress`. null/undefined or total === 0 => the running stage is indeterminate (no count, no percentage). */
  progress?: Run["progress"];
  /** Optional per-stage result text shown once a stage is done, e.g. { delta: "1,114 changes" }. */
  stageCounts?: Partial<Record<Stage, string | number>>;
  /** `run.error`, shown when failed. */
  error?: string | null;
  className?: string;
}

type StageState = "done" | "running" | "pending" | "failed";

/** Pure: state of each stage for a run status + progress. Exported for tests. */
export function stageStates(status: Run["status"], progress?: Run["progress"]): StageState[] {
  if (status === "succeeded") return STAGES.map(() => "done");
  const cur = progress ? STAGES.findIndex((s) => s.key === progress.stage) : -1;
  if (status === "queued") return STAGES.map(() => "pending");
  if (status === "failed") return STAGES.map((_, i) => (cur < 0 ? "pending" : i < cur ? "done" : i === cur ? "failed" : "pending"));
  // running
  if (cur < 0) return STAGES.map((_, i) => (i === 0 ? "running" : "pending"));
  return STAGES.map((_, i) => (i < cur ? "done" : i === cur ? "running" : "pending"));
}

/** Vertical stage list (Delta → Characterize → Candidates → Judge → Ledger): ✓ done, spinner running, hollow ring pending. */
export function StageStepper({ status, progress, stageCounts, error, className }: StageStepperProps) {
  const states = stageStates(status, progress);
  const indeterminate = status === "running" && (!progress || progress.total === 0);
  return (
    <div className={cn("space-y-2", className)}>
      <ol aria-label="Run progress" className="space-y-0">
        {STAGES.map((s, i) => {
          const st = states[i];
          const isCur = progress?.stage === s.key;
          const known = !!progress && progress.total > 0 && isCur;
          const count = stageCounts?.[s.key];
          return (
            <li key={s.key} data-stage={s.key} data-state={st} aria-current={st === "running" ? "step" : undefined} className="relative flex gap-3 pb-4 last:pb-0">
              {i < STAGES.length - 1 && <span aria-hidden className="absolute left-[9px] top-5 h-[calc(100%-12px)] w-px bg-border-strong" />}
              <span className="relative z-10 grid size-5 shrink-0 place-items-center bg-surface">
                {st === "done" ? (
                  <Check aria-hidden className="size-4 text-ink" strokeWidth={2} />
                ) : st === "failed" ? (
                  <X aria-hidden className="size-4 text-red" strokeWidth={2} />
                ) : st === "running" ? (
                  <span aria-hidden className="size-4 rounded-full border-2 border-border-strong border-t-ink motion-safe:animate-spin" />
                ) : (
                  <span aria-hidden className="size-4 rounded-full border border-ink-4" />
                )}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-baseline gap-x-2">
                  <span className={cn("text-[14px] leading-5", st === "pending" ? "text-ink-3" : "font-medium text-ink")}>{s.label}</span>
                  <span className="sr-only">
                    {st === "done" ? " (done)" : st === "running" ? " (in progress)" : st === "failed" ? " (failed)" : " (waiting)"}
                  </span>
                  {st === "done" && count !== undefined && <span className="text-[12px] text-ink-3">{typeof count === "number" ? formatCount(count) : count}</span>}
                  {st === "running" && known && (
                    <span className="text-[12px] tabular-nums text-ink-3">
                      {formatCount(progress.done)} of {formatCount(progress.total)}
                    </span>
                  )}
                </div>
                {st === "running" && progress?.message && isCur && <div className="truncate text-[12px] text-ink-3">{progress.message}</div>}
              </div>
            </li>
          );
        })}
      </ol>
      {indeterminate && (
        <div role="status" className="text-[12px] text-ink-3">
          <span className="block h-px w-full overflow-hidden bg-border">
            <span className="block h-px w-1/3 bg-ink motion-safe:animate-pulse" />
          </span>
          <span className="mt-1.5 block">{progress ? "Working…" : "Starting…"}</span>
        </div>
      )}
      {status === "failed" && <p className="text-[13px] text-red">{error || "The run did not finish."}</p>}
    </div>
  );
}

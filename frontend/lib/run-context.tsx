"use client";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { parseAsString, useQueryState } from "nuqs";
import type { Run } from "@/lib/api/schemas";
import { useRunById, useRuns } from "@/lib/api/queries";

export interface RunContextValue {
  /** Current run, or null while loading. */
  run: Run | null;
  runId: string | null;
  isSimulated: boolean;
  isLoading: boolean;
  /** `?run=` names a run that does not exist; the latest real wave is used instead. */
  invalidRun: boolean;
  /** Writes ?run= (null => clears it, falling back to the latest kb run). */
  setRunId: (id: string | null) => void;
}

/** Mock-mode id of the real wave run. Live mode resolves the default from the runs list instead. */
export const DEFAULT_RUN_ID = "run_kb_real";

/** Newest succeeded kb run (the default when ?run= is absent), or null. */
export function latestKbRunId(runs: readonly Run[] | undefined): string | null {
  const kb = (runs ?? []).filter((r) => r.kind === "kb" && r.status === "succeeded");
  kb.sort((a, b) => b.started_at.localeCompare(a.started_at));
  return kb[0]?.run_id ?? null;
}

const NO_PROVIDER: RunContextValue = {
  run: null,
  runId: null,
  isSimulated: false,
  isLoading: true,
  invalidRun: false,
  setRunId: () => {},
};

const RunContext = createContext<RunContextValue | null>(null);

export function RunProvider({ children }: { children: ReactNode }) {
  const [param, setParam] = useQueryState("run", parseAsString);
  const { data: runs, isLoading: runsLoading } = useRuns();
  // A ?run= that is not in the runs list is probed once (a just-started run may be cached but not listed yet);
  // when it does not exist the latest real wave is shown instead and `invalidRun` is set.
  const knownInList = !!param && !!runs?.some((r) => r.run_id === param);
  const probe = useRunById(param && runs && !knownInList ? param : null);
  const latest = latestKbRunId(runs);
  let runId: string | null;
  let invalidRun = false;
  if (!param) runId = latest;
  else if (!runs) runId = runsLoading ? null : param;
  else if (knownInList || probe.data) runId = param;
  else if (probe.isLoading) runId = null;
  else {
    runId = latest;
    invalidRun = true;
  }
  const { data, isLoading: runLoading } = useRunById(runId);
  const isLoading = runsLoading || probe.isLoading || (!!runId && runLoading);
  const setRunId = useCallback(
    (id: string | null) => {
      void setParam(id && id !== "" ? id : null);
    },
    [setParam],
  );
  const value = useMemo<RunContextValue>(
    () => ({
      run: data ?? null,
      runId,
      isSimulated: data?.kind === "whatif",
      isLoading,
      invalidRun,
      setRunId,
    }),
    [data, runId, isLoading, invalidRun, setRunId],
  );
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRunContext(): RunContextValue {
  // Outside a provider (e.g. isolated component tests) behave like "still loading".
  return useContext(RunContext) ?? NO_PROVIDER;
}

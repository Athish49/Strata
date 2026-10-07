"use client";
import { createContext, useCallback, useContext, useMemo, type ReactNode } from "react";
import { parseAsString, useQueryState } from "nuqs";
import type { Run } from "@/lib/api/schemas";
import { useRunById } from "@/lib/api/queries";

export interface RunContextValue {
  /** Current run, or null while loading. */
  run: Run | null;
  runId: string | null;
  isSimulated: boolean;
  isLoading: boolean;
  /** Writes ?run= (null => clears it, falling back to the latest kb run). */
  setRunId: (id: string | null) => void;
}

/** The latest real (kb) run; used whenever ?run= is absent. */
export const DEFAULT_RUN_ID = "run_kb_real";

const NO_PROVIDER: RunContextValue = {
  run: null,
  runId: null,
  isSimulated: false,
  isLoading: true,
  setRunId: () => {},
};

const RunContext = createContext<RunContextValue | null>(null);

export function RunProvider({ children }: { children: ReactNode }) {
  const [param, setParam] = useQueryState("run", parseAsString);
  const runId = param || DEFAULT_RUN_ID;
  const { data, isLoading } = useRunById(runId);
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
      setRunId,
    }),
    [data, runId, isLoading, setRunId],
  );
  return <RunContext.Provider value={value}>{children}</RunContext.Provider>;
}

export function useRunContext(): RunContextValue {
  // Outside a provider (e.g. isolated component tests) behave like "still loading".
  return useContext(RunContext) ?? NO_PROVIDER;
}

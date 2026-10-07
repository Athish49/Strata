"use client";
// STUB — implemented by the mock-layer agent. Signatures below are the contract used by the shell.
import type { Run } from "@/lib/api/schemas";

export interface RunContextValue {
  /** Current run, or null while loading. */
  run: Run | null;
  runId: string | null;
  isSimulated: boolean;
  isLoading: boolean;
  /** Writes ?run= (omit/undefined => latest kb run). */
  setRunId: (id: string | null) => void;
}

export function useRunContext(): RunContextValue {
  return { run: null, runId: null, isSimulated: false, isLoading: true, setRunId: () => {} };
}

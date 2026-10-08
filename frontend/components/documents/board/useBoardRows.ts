"use client";
import * as React from "react";
import { useDocuments, useRollups } from "@/lib/api/queries";
import { useRunContext } from "@/lib/run-context";
import { buildRows, type DocRow } from "./logic";
import type { DocumentMeta } from "@/lib/api/schemas";

export interface BoardData {
  docs: DocumentMeta[];
  rows: DocRow[];
  isLoading: boolean;
  isError: boolean;
  /** Rollups failed: statuses are not shown rather than guessed. */
  statusError: boolean;
  refetch: () => void;
}

/** Documents joined with the current run's rollups. Statuses stay pending until the run's rollups arrive. */
export function useBoardRows(): BoardData {
  const { runId, isLoading: runLoading } = useRunContext();
  const documents = useDocuments();
  const rollups = useRollups(runId);
  const docs = React.useMemo(() => documents.data ?? [], [documents.data]);
  const statusError = rollups.isError;
  const pending = runLoading || rollups.isLoading || statusError;
  const rows = React.useMemo(() => buildRows(docs, rollups.data, pending), [docs, rollups.data, pending]);
  return {
    docs,
    rows,
    isLoading: documents.isLoading,
    isError: documents.isError,
    statusError,
    refetch: () => {
      void documents.refetch();
      void rollups.refetch();
    },
  };
}

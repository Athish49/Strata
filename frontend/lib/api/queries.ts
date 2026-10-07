"use client";
// TanStack Query hooks over StrataApi. Every engine query key includes run_id.
import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { Finding, Run } from "./schemas";

type Nullable<T> = T | null | undefined;

export const qk = {
  runs: () => ["engine", "runs"] as const,
  run: (runId: string) => ["engine", runId, "run"] as const,
  changes: (runId: string) => ["engine", runId, "changes"] as const,
  change: (runId: string, changeId: string) => ["engine", runId, "change", changeId] as const,
  candidates: (runId: string, q?: object) => ["engine", runId, "candidates", q ?? {}] as const,
  findings: (runId: string, q?: object) => ["engine", runId, "findings", q ?? {}] as const,
  finding: (findingId: string) => ["engine", "finding", findingId] as const,
  rollups: (runId: string) => ["engine", runId, "rollups"] as const,
  reader: (runId: string, docId: string) => ["engine", runId, "reader", docId] as const,
  matrix: (runId: string, includeNoise: boolean) => ["engine", runId, "matrix", includeNoise] as const,
  radar: (runId: string) => ["engine", runId, "radar"] as const,
  scenarios: () => ["engine", "scenarios"] as const,
  score: () => ["engine", "score"] as const,
  documents: () => ["company", "documents"] as const,
  document: (docId: string) => ["company", "document", docId] as const,
  clauses: (docId: string) => ["company", "clauses", docId] as const,
  people: () => ["company", "people"] as const,
  profile: () => ["company", "profile"] as const,
  agencies: () => ["kb", "agencies"] as const,
  agency: (slug: string) => ["kb", "agency", slug] as const,
  sections: (q: object) => ["kb", "sections", q] as const,
  section: (ss: string, citation: string) => ["kb", "section", ss, citation] as const,
  actions: (q: object) => ["kb", "actions", q] as const,
  action: (ss: string, id: string) => ["kb", "action", ss, id] as const,
  versions: (ss: string, citation: string) => ["kb", "versions", ss, citation] as const,
  compare: (ss: string, citation: string, a?: string, b?: string) => ["kb", "compare", ss, citation, a ?? "", b ?? ""] as const,
};

/** Invalidate every result-bearing query of one run (not the run record itself). */
export function invalidateRunQueries(qc: QueryClient, runId: string) {
  return qc.invalidateQueries({
    predicate: (q) => q.queryKey[0] === "engine" && q.queryKey[1] === runId && q.queryKey[2] !== "run",
  });
}

// ---------- runs ----------

export function useRuns() {
  return useQuery({ queryKey: qk.runs(), queryFn: () => api.engine.listRuns() });
}

/** Polls every 2 s while the run is `running`; invalidates the run's queries when it finishes. */
export function useRunById(runId: Nullable<string>) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: qk.run(runId ?? ""),
    queryFn: () => api.engine.getRun(runId as string),
    enabled: !!runId,
    refetchInterval: (q) => (q.state.data?.status === "running" ? 2000 : false),
  });
  const status = query.data?.status;
  const prev = useRef<Run["status"] | undefined>(undefined);
  useEffect(() => {
    if (runId && prev.current === "running" && status && status !== "running") {
      void invalidateRunQueries(qc, runId);
      void qc.invalidateQueries({ queryKey: qk.runs() });
    }
    prev.current = status;
  }, [status, runId, qc]);
  return query;
}

// ---------- engine (run-scoped) ----------

export function useChanges(runId: Nullable<string>) {
  return useQuery({ queryKey: qk.changes(runId ?? ""), queryFn: () => api.engine.listChanges(runId as string), enabled: !!runId });
}

export function useChange(runId: Nullable<string>, changeId: Nullable<string>) {
  return useQuery({
    queryKey: qk.change(runId ?? "", changeId ?? ""),
    queryFn: () => api.engine.getChange(runId as string, changeId as string),
    enabled: !!runId && !!changeId,
  });
}

export function useCandidates(runId: Nullable<string>, q?: { change_id?: string; doc_id?: string }) {
  return useQuery({ queryKey: qk.candidates(runId ?? "", q), queryFn: () => api.engine.listCandidates(runId as string, q), enabled: !!runId });
}

export function useFindings(runId: Nullable<string>, q?: { doc_id?: string; change_id?: string }) {
  return useQuery({ queryKey: qk.findings(runId ?? "", q), queryFn: () => api.engine.listFindings(runId as string, q), enabled: !!runId });
}

export function useFinding(findingId: Nullable<string>) {
  return useQuery({ queryKey: qk.finding(findingId ?? ""), queryFn: () => api.engine.getFinding(findingId as string), enabled: !!findingId });
}

export function useRollups(runId: Nullable<string>) {
  return useQuery({ queryKey: qk.rollups(runId ?? ""), queryFn: () => api.engine.listRollups(runId as string), enabled: !!runId });
}

export function useReader(docId: Nullable<string>, runId: Nullable<string>) {
  return useQuery({
    queryKey: qk.reader(runId ?? "", docId ?? ""),
    queryFn: () => api.engine.getReader(docId as string, runId as string),
    enabled: !!runId && !!docId,
  });
}

export function useMatrix(runId: Nullable<string>, opts?: { include_noise?: boolean }) {
  const noise = !!opts?.include_noise;
  return useQuery({
    queryKey: qk.matrix(runId ?? "", noise),
    queryFn: () => api.engine.getMatrix(runId as string, { include_noise: noise }),
    enabled: !!runId,
  });
}

export function useRadar(runId: Nullable<string>) {
  return useQuery({ queryKey: qk.radar(runId ?? ""), queryFn: () => api.engine.listRadar(runId as string), enabled: !!runId });
}

export function useScenarios() {
  return useQuery({ queryKey: qk.scenarios(), queryFn: () => api.engine.listScenarios() });
}

export function useScore() {
  return useQuery({ queryKey: qk.score(), queryFn: () => api.engine.getScore() });
}

// ---------- company ----------

export function useDocuments() {
  return useQuery({ queryKey: qk.documents(), queryFn: () => api.company.listDocuments() });
}

export function useDocument(docId: Nullable<string>) {
  return useQuery({ queryKey: qk.document(docId ?? ""), queryFn: () => api.company.getDocument(docId as string), enabled: !!docId });
}

export function useClauses(docId: Nullable<string>) {
  return useQuery({ queryKey: qk.clauses(docId ?? ""), queryFn: () => api.company.listClauses(docId as string), enabled: !!docId });
}

export function usePeople() {
  return useQuery({ queryKey: qk.people(), queryFn: () => api.company.listPeople() });
}

export function useProfile() {
  return useQuery({ queryKey: qk.profile(), queryFn: () => api.company.getProfile() });
}

// ---------- KB ----------

type SectionQuery = Parameters<typeof api.kb.listSections>[0];
type ActionQuery = Parameters<typeof api.kb.listActions>[0];

export function useAgencies() {
  return useQuery({ queryKey: qk.agencies(), queryFn: () => api.kb.listAgencies() });
}

export function useAgency(slug: Nullable<string>) {
  return useQuery({ queryKey: qk.agency(slug ?? ""), queryFn: () => api.kb.getAgency(slug as string), enabled: !!slug });
}

export function useSections(q: SectionQuery) {
  return useQuery({ queryKey: qk.sections(q), queryFn: () => api.kb.listSections(q) });
}

export function useSection(sourceSystem: Nullable<string>, citation: Nullable<string>) {
  return useQuery({
    queryKey: qk.section(sourceSystem ?? "", citation ?? ""),
    queryFn: () => api.kb.getSection(sourceSystem as string, citation as string),
    enabled: !!sourceSystem && !!citation,
  });
}

export function useActions(q: ActionQuery) {
  return useQuery({ queryKey: qk.actions(q), queryFn: () => api.kb.listActions(q) });
}

export function useAction(sourceSystem: Nullable<string>, sourceId: Nullable<string>) {
  return useQuery({
    queryKey: qk.action(sourceSystem ?? "", sourceId ?? ""),
    queryFn: () => api.kb.getAction(sourceSystem as string, sourceId as string),
    enabled: !!sourceSystem && !!sourceId,
  });
}

export function useVersionHistory(sourceSystem: Nullable<string>, citation: Nullable<string>) {
  return useQuery({
    queryKey: qk.versions(sourceSystem ?? "", citation ?? ""),
    queryFn: () => api.kb.getVersionHistory(sourceSystem as string, citation as string),
    enabled: !!sourceSystem && !!citation,
  });
}

export function useCompare(sourceSystem: Nullable<string>, citation: Nullable<string>, dateA?: string, dateB?: string) {
  return useQuery({
    queryKey: qk.compare(sourceSystem ?? "", citation ?? "", dateA, dateB),
    queryFn: () => api.kb.compare(sourceSystem as string, citation as string, dateA, dateB),
    enabled: !!sourceSystem && !!citation,
  });
}

// ---------- mutations ----------

export function useSubmitReview() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { findingId: string; decision: "accept" | "reject"; note?: string }) =>
      api.engine.submitReview(v.findingId, v.decision, v.note),
    onSuccess: (f: Finding) => {
      qc.setQueryData(qk.finding(f.finding_id), f);
      void qc.invalidateQueries({ queryKey: ["engine", f.run_id, "findings"] });
    },
  });
}

export function useSaveScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (s: Parameters<typeof api.engine.saveScenario>[0]) => api.engine.saveScenario(s),
    onSuccess: () => void qc.invalidateQueries({ queryKey: qk.scenarios() }),
  });
}

/** Resolves to the Run (already succeeded for presets; `running` for custom scenarios). */
export function useStartWhatIf() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scenarioId: string) => api.engine.startWhatIf(scenarioId),
    onSuccess: (run: Run) => {
      qc.setQueryData(qk.run(run.run_id), run);
      void qc.invalidateQueries({ queryKey: qk.runs() });
      void qc.invalidateQueries({ queryKey: qk.scenarios() });
    },
  });
}


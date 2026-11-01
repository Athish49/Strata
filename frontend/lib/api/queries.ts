"use client";
// TanStack Query hooks over StrataApi. Every engine query key includes run_id.
import { useEffect, useRef } from "react";
import { useMutation, useQuery, useQueryClient, type QueryClient } from "@tanstack/react-query";
import { api, type UploadDocumentMeta, type UploadResult, type UploadVersionMeta } from "./client";
import type { ApprovalRequest, DocumentRole, Finding, IngestJob, IngestJobState, Run } from "./schemas";
import { isTerminalJobState } from "./schemas";

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
  score: (runId: string) => ["engine", runId, "score"] as const,
  editableSections: () => ["engine", "editable-sections"] as const,
  sectionS1Text: (ss: string, citation: string) => ["engine", "section-s1-text", ss, citation] as const,
  verticals: () => ["company", "verticals"] as const,
  documents: () => ["company", "documents"] as const,
  document: (docId: string) => ["company", "document", docId] as const,
  clauses: (docId: string) => ["company", "clauses", docId] as const,
  people: () => ["company", "people"] as const,
  profile: () => ["company", "profile"] as const,
  orgPeople: (includeInactive: boolean) => ["company", "org-people", includeInactive] as const,
  /** Company document version history (distinct from the KB `versions` key). */
  docVersions: (docId: string) => ["company", "doc-versions", docId] as const,
  ingestJob: (jobId: string) => ["company", "ingest-job", jobId] as const,
  approvalRequest: (requestId: string) => ["company", "approval-request", requestId] as const,
  documentRoles: (docId: string) => ["company", "roles", docId] as const,
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

export function useScore(runId: Nullable<string>) {
  return useQuery({ queryKey: qk.score(runId ?? ""), queryFn: () => api.engine.getScore(runId as string), enabled: !!runId });
}

export function useEditableSections() {
  return useQuery({ queryKey: qk.editableSections(), queryFn: () => api.engine.listEditableSections() });
}

export function useSectionS1Text(sourceSystem: Nullable<string>, citation: Nullable<string>) {
  return useQuery({
    queryKey: qk.sectionS1Text(sourceSystem ?? "", citation ?? ""),
    queryFn: () => api.engine.getSectionS1Text(sourceSystem as string, citation as string),
    enabled: !!sourceSystem && !!citation,
  });
}

// ---------- company ----------

/** The 14 verticals, ordered by sort_order. Reference data: rarely changes, so
 * never refetched automatically once loaded (staleTime: Infinity). */
export function useVerticals() {
  return useQuery({ queryKey: qk.verticals(), queryFn: () => api.company.listVerticals(), staleTime: Infinity });
}

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

export function useOrgPeople(q?: { include_inactive?: boolean }) {
  const inc = q?.include_inactive ?? true;
  return useQuery({ queryKey: qk.orgPeople(inc), queryFn: () => api.company.listOrgPeople({ include_inactive: inc }) });
}

/** Version history of one document, newest first (null when the document is unknown). */
export function useDocumentVersions(docId: Nullable<string>) {
  return useQuery({ queryKey: qk.docVersions(docId ?? ""), queryFn: () => api.company.listVersions(docId as string), enabled: !!docId });
}

export function useApprovalRequest(requestId: Nullable<string>) {
  return useQuery({
    queryKey: qk.approvalRequest(requestId ?? ""),
    queryFn: () => api.company.getApprovalRequest(requestId as string),
    enabled: !!requestId,
  });
}

export function useDocumentRoles(docId: Nullable<string>) {
  return useQuery({ queryKey: qk.documentRoles(docId ?? ""), queryFn: () => api.company.listDocumentRoles(docId as string), enabled: !!docId });
}

export const INGEST_POLL_MS = 2000;

/** Poll interval for an ingest job: every 2 s while queued/running (or not yet loaded), off once terminal or 404. */
export function ingestJobRefetchInterval(job: IngestJob | null | undefined): number | false {
  if (job === null) return false; // 404: unknown job, nothing to wait for
  if (job === undefined) return INGEST_POLL_MS;
  return isTerminalJobState(job.job.state) ? false : INGEST_POLL_MS;
}

/** Invalidate what a finished ingest job changes: the document list/record and its versions (+ clauses on success). */
export function invalidateAfterIngest(qc: QueryClient, docId: string, state: IngestJobState) {
  const keys: (readonly unknown[])[] = [qk.documents(), qk.document(docId), qk.docVersions(docId)];
  if (state === "succeeded") keys.push(qk.clauses(docId));
  return Promise.all(keys.map((queryKey) => qc.invalidateQueries({ queryKey })));
}

/**
 * Polls GET /company/ingest-jobs/{id} every 2 s until the job is `succeeded` or `failed`, then stops.
 * The first time a terminal state is seen for a job id, the documents and versions queries are invalidated
 * (covers queued -> succeeded without an observed `running`, and a job already finished on first load).
 */
export function useIngestJob(jobId: Nullable<string>) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: qk.ingestJob(jobId ?? ""),
    queryFn: () => api.company.getIngestJob(jobId as string),
    enabled: !!jobId,
    refetchInterval: (q) => ingestJobRefetchInterval(q.state.data),
  });
  const state = query.data?.job.state;
  const docId = query.data?.job.doc_id;
  const handled = useRef<string | null>(null);
  useEffect(() => {
    if (!jobId || !docId || !state) return;
    // A retry reuses the SAME job id (failed -> queued -> running -> succeeded). Leaving a
    // terminal state clears the marker so the next terminal state refreshes the lists again;
    // otherwise the documents/versions would stay stale after a successful retry.
    if (!isTerminalJobState(state)) {
      handled.current = null;
      return;
    }
    if (handled.current === jobId) return;
    handled.current = jobId;
    void invalidateAfterIngest(qc, docId, state);
  }, [jobId, docId, state, qc]);
  return query;
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
    mutationFn: (v: { findingId: string; decision: "accept" | "reject"; note?: string; personId?: string }) =>
      api.engine.submitReview(v.findingId, v.decision, v.note, v.personId),
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

// ---------- company writes ----------

/** Seed a `queued` job so the poller starts immediately after an upload or retry. */
function seedQueuedJob(qc: QueryClient, job_id: string, doc_id: string, version_id: string) {
  const seeded: IngestJob = {
    job: { job_id, doc_id, version_id, state: "queued", error: null, created_at: null, started_at: null, finished_at: null },
    stats: {},
  };
  qc.setQueryData(qk.ingestJob(job_id), seeded);
}

/** Resolves to an UploadResult (branch on `kind`); HTTP errors reject with ApiError, no actor with MissingActorError. */
export function useUploadDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { vertical: string; file: Blob; meta?: UploadDocumentMeta }) => api.company.uploadDocument(v.vertical, v.file, v.meta),
    onSuccess: (r: UploadResult) => {
      if (r.kind !== "created") return;
      seedQueuedJob(qc, r.job_id, r.doc_id, r.version_id);
      void qc.invalidateQueries({ queryKey: qk.documents() });
    },
  });
}

export function useUploadVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { docId: string; file: Blob; meta?: UploadVersionMeta }) => api.company.uploadVersion(v.docId, v.file, v.meta),
    onSuccess: (r: UploadResult, v) => {
      if (r.kind !== "created") return;
      seedQueuedJob(qc, r.job_id, r.doc_id, r.version_id);
      void qc.invalidateQueries({ queryKey: qk.docVersions(v.docId) });
      void qc.invalidateQueries({ queryKey: qk.document(v.docId) });
      void qc.invalidateQueries({ queryKey: qk.documents() });
    },
  });
}

export function useRetryIngestJob() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (jobId: string) => api.company.retryIngestJob(jobId),
    onSuccess: (r) => {
      if (r.doc_id && r.version_id) {
        seedQueuedJob(qc, r.job_id, r.doc_id, r.version_id);
        void qc.invalidateQueries({ queryKey: qk.docVersions(r.doc_id) });
      } else {
        void qc.invalidateQueries({ queryKey: qk.ingestJob(r.job_id) });
      }
      void qc.invalidateQueries({ queryKey: qk.documents() });
    },
  });
}

function afterApprovalChange(qc: QueryClient, req: ApprovalRequest) {
  qc.setQueryData(qk.approvalRequest(req.request_id), req);
  if (!req.doc_id) return;
  // A final approval promotes the version (current version, clauses and document status all change).
  void qc.invalidateQueries({ queryKey: qk.docVersions(req.doc_id) });
  void qc.invalidateQueries({ queryKey: qk.document(req.doc_id) });
  void qc.invalidateQueries({ queryKey: qk.documents() });
  if (req.state === "approved") void qc.invalidateQueries({ queryKey: qk.clauses(req.doc_id) });
}

export function useDecideApprovalStep() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { requestId: string; stepNo: number; decision: "approved" | "rejected"; note?: string; actingPersonId?: string }) =>
      api.company.decideApprovalStep(v.requestId, v.stepNo, v.decision, { note: v.note, acting_person_id: v.actingPersonId }),
    onSuccess: (r) => afterApprovalChange(qc, r),
  });
}

export function useCancelApprovalRequest() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { requestId: string; actingPersonId?: string }) =>
      api.company.cancelApprovalRequest(v.requestId, { acting_person_id: v.actingPersonId }),
    onSuccess: (r) => afterApprovalChange(qc, r),
  });
}

export function useAssignDocumentRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (v: { docId: string; personId: string; role: DocumentRole; actingPersonId?: string }) =>
      api.company.assignDocumentRole(v.docId, v.personId, v.role, { acting_person_id: v.actingPersonId }),
    onSuccess: (_r, v) => {
      void qc.invalidateQueries({ queryKey: qk.documentRoles(v.docId) });
      void qc.invalidateQueries({ queryKey: qk.document(v.docId) });
      void qc.invalidateQueries({ queryKey: qk.documents() });
      // Steps with no assignee are signed by role holders, so the version's approval summary may change.
      void qc.invalidateQueries({ queryKey: qk.docVersions(v.docId) });
    },
  });
}


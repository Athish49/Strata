import { httpApi } from "./http";
import type {
  Agency,
  ApprovalDecisionResult,
  ApprovalRequest,
  ApprovalState,
  DocumentRole,
  IngestJob,
  OrgPerson,
  RetryJobResult,
  RoleAssigned,
  RoleAssignment,
  VersionList,
  Candidate,
  ChangeRecord,
  Clause,
  CodeSection,
  CompanyProfile,
  DocRollup,
  DocumentMeta,
  EditableSection,
  Finding,
  LineDiff,
  MatrixCell,
  Annotation,
  Person,
  RadarItem,
  RegulatoryAction,
  Run,
  Scenario,
  ScoreReport,
  SectionS1Text,
  VersionEntry,
} from "./schemas";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

export interface Reader {
  doc: DocumentMeta;
  clauses: Clause[];
  annotations: Annotation[];
}

export interface Matrix {
  docs: DocumentMeta[];
  changes: ChangeRecord[];
  cells: MatrixCell[];
}

export interface KbApi {
  listAgencies(): Promise<Agency[]>;
  getAgency(slug: string): Promise<Agency | null>;
  listSections(q: {
    agency?: string;
    source_system?: string;
    status?: "approved" | "repealed";
    search?: string;
    page?: number;
    limit?: number;
  }): Promise<Page<CodeSection>>;
  getSection(source_system: string, citation: string): Promise<CodeSection | null>;
  listActions(q: {
    agency?: string;
    source_system?: string;
    status?: string;
    action_type?: string;
    stream?: string;
    date_from?: string;
    date_to?: string;
    search?: string;
    page?: number;
    limit?: number;
  }): Promise<Page<RegulatoryAction>>;
  getAction(source_system: string, source_id: string): Promise<RegulatoryAction | null>;
  /** Modeled on GET /diff/{source_system}/{citation} (version history). */
  getVersionHistory(source_system: string, citation: string): Promise<VersionEntry[]>;
  /** Modeled on GET /diff/{source_system}/{citation}/compare. */
  compare(source_system: string, citation: string, date_a?: string, date_b?: string): Promise<LineDiff>;
}

export interface EngineApi {
  listRuns(): Promise<Run[]>;
  /** Polled every 2s by the UI while status === "running". */
  getRun(run_id: string): Promise<Run | null>;
  listChanges(run_id: string): Promise<ChangeRecord[]>;
  getChange(run_id: string, change_id: string): Promise<ChangeRecord | null>;
  listCandidates(run_id: string, q?: { change_id?: string; doc_id?: string }): Promise<Candidate[]>;
  listFindings(run_id: string, q?: { doc_id?: string; change_id?: string }): Promise<Finding[]>;
  getFinding(finding_id: string): Promise<Finding | null>;
  listRollups(run_id: string): Promise<DocRollup[]>;
  getReader(doc_id: string, run_id: string): Promise<Reader | null>;
  getMatrix(run_id: string, opts?: { include_noise?: boolean }): Promise<Matrix>;
  listRadar(run_id: string): Promise<RadarItem[]>;
  listScenarios(): Promise<Scenario[]>;
  saveScenario(s: Omit<Scenario, "scenario_id" | "is_preset" | "last_run_id"> & { scenario_id?: string }): Promise<Scenario>;
  /** Presets finish instantly; custom scenarios advance through the five stages (~8–10 s). */
  startWhatIf(scenario_id: string): Promise<Run>;
/** null when the run has no score report (what-if runs are never scored). */
  getScore(run_id: string): Promise<ScoreReport | null>;
  /** person_id defaults to the finding's routed reviewer when omitted. */
  submitReview(finding_id: string, decision: "accept" | "reject", note?: string, person_id?: string): Promise<Finding>;
  /** Sections cited by at least one company clause: the what-if section picker. */
  listEditableSections(): Promise<EditableSection[]>;
  /** The S1 (baseline) text of a section, the starting point of a what-if edit. */
  getSectionS1Text(source_system: string, citation: string): Promise<SectionS1Text | null>;
}

/** Optional fields of POST /company/documents (multipart). `vertical` and `file` are positional. */
export interface UploadDocumentMeta {
  /** Defaults server-side to the filename stem. */
  title?: string;
  doc_number?: string;
  doc_class?: string;
  /** Register CSV spec: a JSON string or an object (stringified). Required for .csv uploads. */
  register_spec?: string | Record<string, unknown>;
  /** ISO date YYYY-MM-DD. */
  law_as_of?: string;
  change_reason?: string;
  /** Overrides the "acting as" store (lib/actor.ts) for this call. */
  acting_person_id?: string;
  /** Filename to send when `file` is a Blob rather than a File. */
  filename?: string;
}

/** Optional fields of POST /company/documents/{doc_id}/versions (multipart). */
export interface UploadVersionMeta {
  change_reason?: string;
  /** Registers inherit their spec from the latest job when omitted. */
  register_spec?: string | Record<string, unknown>;
  law_as_of?: string;
  acting_person_id?: string;
  filename?: string;
}

/**
 * Every non-error outcome of an upload. HTTP errors the user must act on (413 too large,
 * 415 not .docx, 422 unreadable/empty/bad spec/unknown vertical/format mismatch, 404 unknown
 * document or actor, 503 storage failure) are thrown as ApiError with the server message in
 * `.detail`; a missing actor throws MissingActorError before any request is sent.
 */
export type UploadResult =
  /** 202: stored; poll `job_id`. `version_no` is 1 for a new document. */
  | {
      kind: "created";
      doc_id: string;
      version_id: string;
      job_id: string;
      version_no: number;
      approval_request_id: string | null;
      approval_state: ApprovalState | null;
      /** New-version uploads only: stale in-review versions this upload retired. */
      retired_version_ids: string[];
    }
  /** 200 (new version only): content matches the current/pending version; nothing written. */
  | { kind: "unchanged"; message: string }
  /** 409: the content already belongs to `doc_id` (null only on a rare race); nothing written. */
  | { kind: "duplicate"; message: string; doc_id: string | null }
  /** 409 (new version only): identical bytes to a failed version; offer Retry on `job_id`. */
  | { kind: "retry_available"; message: string; doc_id: string; version_id: string; job_id: string };

export interface ActingOpts {
  /** Overrides the "acting as" store (lib/actor.ts) for this call. */
  acting_person_id?: string;
}

export interface CompanyApi {
  /** Every document; a vertical outside the 14 is normalised to "unclassified" (never dropped). */
  listDocuments(): Promise<DocumentMeta[]>;
  getDocument(doc_id: string): Promise<DocumentMeta | null>;
  listClauses(doc_id: string): Promise<Clause[]>;
  /** Legacy GET /company/people (no is_active). */
  listPeople(): Promise<Person[]>;
  /** GET /company/org/people: adds department_id, email, is_active. Inactive people included by default. */
  listOrgPeople(q?: { include_inactive?: boolean }): Promise<OrgPerson[]>;
  getProfile(): Promise<CompanyProfile>;

  // ---- writes (each attaches acting_person_id from lib/actor.ts unless overridden) ----
  /** POST /company/documents. `vertical` is a frontend slug (only canUploadToVertical() slugs are accepted). */
  uploadDocument(vertical: string, file: Blob, meta?: UploadDocumentMeta): Promise<UploadResult>;
  /** POST /company/documents/{doc_id}/versions. */
  uploadVersion(doc_id: string, file: Blob, meta?: UploadVersionMeta): Promise<UploadResult>;
  /** GET /company/documents/{doc_id}/versions (newest first); null on 404. */
  listVersions(doc_id: string): Promise<VersionList | null>;
  /** GET /company/ingest-jobs/{job_id}; null on 404. */
  getIngestJob(job_id: string): Promise<IngestJob | null>;
  /** POST /company/ingest-jobs/{job_id}/retry (no body, no actor). 409/422 throw ApiError. */
  retryIngestJob(job_id: string): Promise<RetryJobResult>;
  /** GET /company/approval-requests/{request_id}; null on 404. */
  getApprovalRequest(request_id: string): Promise<ApprovalRequest | null>;
  /** 403 (not the assignee / lacks the role) and 409 (not open, out of order, ingest not succeeded) throw ApiError. */
  decideApprovalStep(
    request_id: string,
    step_no: number,
    decision: "approved" | "rejected",
    opts?: ActingOpts & { note?: string },
  ): Promise<ApprovalDecisionResult>;
  /** Cancels an open request and retires its version. 409 when not open. */
  cancelApprovalRequest(request_id: string, opts?: ActingOpts): Promise<ApprovalRequest>;
  /** GET /company/documents/{doc_id}/roles. */
  listDocumentRoles(doc_id: string): Promise<RoleAssignment[]>;
  /** POST /company/documents/{doc_id}/roles (idempotent). */
  assignDocumentRole(doc_id: string, person_id: string, role: DocumentRole, opts?: ActingOpts): Promise<RoleAssigned>;
}

export interface StrataApi {
  kb: KbApi;
  engine: EngineApi;
  company: CompanyApi;
}

/** The app always talks to the live backend. */
export const api: StrataApi = httpApi;

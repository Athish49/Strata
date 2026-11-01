import { z } from "zod";
import { isoDate, personSchema, unitKindSchema } from "./common";

/** GET /company/verticals row: one of the 14 verticals, DB-ordered by sort_order. */
export const verticalSchema = z.object({
  name: z.string(),
  slug: z.string(),
  description: z.string(),
  sort_order: z.number(),
});
export type CompanyVertical = z.infer<typeof verticalSchema>;

export const documentMetaSchema = z.object({
  doc_id: z.string(),
  title: z.string(),
  version: z.string(),
  status: z.string(),
  effective_date: isoDate.nullable(),
  approved_date: isoDate.nullable(),
  law_as_of: isoDate.nullable(),
  next_review: isoDate.nullable(),
  review_cycle: z.string().nullable(),
  /** One of the 14 vertical slugs (lib/verticals.ts). */
  vertical: z.string(),
  owner: personSchema,
  reviewer: personSchema,
  approver: personSchema.nullable(),
  two_signature: z.boolean(),
  monitored: z.boolean(),
  /** Free-text document type shown in vertical tables, e.g. "Procedure", "Register". */
  doc_type: z.string(),
  /** Citations this document cites (from regulatory_basis + in-text). Empty for samples. */
  cited_citations: z.array(z.string()).default([]),
  /** Company document number, e.g. "OPS-014". Absent on older payloads. */
  doc_number: z.string().nullable().optional(),
  /** Stored backend vertical name ("Compliance & Legal"); null when unclassified. */
  vertical_name: z.string().nullable().optional(),
  /**
   * Ingest status of the current version ("pending" | "ingested" | "failed").
   * NOTE: GET /company/documents does not send this yet (backend gap); treat absent as unknown.
   */
  ingest_status: z.string().nullable().optional(),
  /**
   * Document lifecycle (see LIFECYCLE_STATES). A string, not an enum, because the column has no
   * CHECK constraint. Absent on older payloads.
   */
  lifecycle_state: z.string().nullable().optional(),
  /** False when the document has no current (approved) version yet. Absent on older payloads: treat as true. */
  has_current_version: z.boolean().nullable().optional(),
  /** The newest non-retired version: number, version status and ingest status. */
  latest_version_no: z.number().int().nullable().optional(),
  latest_version_status: z.string().nullable().optional(),
  latest_ingest_status: z.string().nullable().optional(),
});
export type DocumentMeta = z.infer<typeof documentMetaSchema>;

export const clauseSchema = z.object({
  clause_id: z.string(),
  doc_id: z.string(),
  ordinal: z.number().int(),
  heading_path: z.array(z.string()),
  unit_kind: unitKindSchema,
  text_raw: z.string(),
  row_cells: z.record(z.string(), z.string()).nullable().optional(),
  parent_clause_id: z.string().nullable().optional(),
});
export type Clause = z.infer<typeof clauseSchema>;

export const companyAttributeSchema = z.object({
  key: z.string(),
  value: z.union([z.string(), z.number(), z.boolean()]),
  source: z.string(),
});
export type CompanyAttribute = z.infer<typeof companyAttributeSchema>;

export const companyProfileSchema = z.object({
  name: z.string(),
  type: z.string(),
  state: z.string(),
  customers: z.number(),
  regulator: z.string(),
  attributes: z.array(companyAttributeSchema),
});
export type CompanyProfile = z.infer<typeof companyProfileSchema>;

// ---------------------------------------------------------------- write-side contracts
// Shapes from implementation_plan.md "Wave 5 outcome" and backend/app/api/company/{upload,versions,org}.py.
// Plain z.object strips unknown keys (never .strict()), so extra backend fields are tolerated.

/** company_documents.lifecycle_state values the backend writes (no DB CHECK constraint). */
export const LIFECYCLE_STATES = ["active", "pending", "failed", "retired"] as const;
export type LifecycleState = (typeof LIFECYCLE_STATES)[number];

/** document_versions.status, matching the DB CHECK (the contract names only the last four, plus draft/approved). */
export const versionStatusSchema = z.enum(["draft", "in_review", "approved", "effective", "superseded", "retired"]);
export type VersionStatus = z.infer<typeof versionStatusSchema>;

export const ingestJobStateSchema = z.enum(["queued", "running", "succeeded", "failed"]);
export type IngestJobState = z.infer<typeof ingestJobStateSchema>;
export const TERMINAL_JOB_STATES: readonly IngestJobState[] = ["succeeded", "failed"];
export const isTerminalJobState = (s: IngestJobState | null | undefined): boolean => !!s && TERMINAL_JOB_STATES.includes(s);

export const approvalStateSchema = z.enum(["open", "approved", "rejected", "cancelled"]);
export type ApprovalState = z.infer<typeof approvalStateSchema>;

export const documentRoleSchema = z.enum(["owner", "reviewer", "approver"]);
export type DocumentRole = z.infer<typeof documentRoleSchema>;

/** 202 from POST /company/documents and POST /company/documents/{id}/versions. */
export const uploadAcceptedSchema = z.object({
  doc_id: z.string(),
  version_id: z.string(),
  job_id: z.string(),
  status: z.string(), // "processing"
  /** Only on new-version uploads. */
  version_no: z.number().int().nullable().optional(),
  approval_request_id: z.string().nullable().optional(),
  approval_state: approvalStateSchema.nullable().optional(),
  /** Only on new-version uploads: stale in-review versions retired by this upload. */
  retired_version_ids: z.array(z.string()).optional(),
});
export type UploadAccepted = z.infer<typeof uploadAcceptedSchema>;

/** 409 duplicate (content already belongs to a document). doc_id is null on the concurrent-insert race path. */
export const uploadDuplicateSchema = z.object({
  status: z.literal("duplicate"),
  message: z.string(),
  doc_id: z.string().nullable().optional(),
});

/** 200 from POST /company/documents/{id}/versions when nothing changed. Nothing written. */
export const uploadUnchangedSchema = z.object({
  status: z.literal("unchanged"),
  message: z.string(),
});

/** 409 when the bytes match a failed version of this document: offer Retry on job_id. */
export const uploadRetryAvailableSchema = z.object({
  status: z.literal("retry_available"),
  message: z.string(),
  doc_id: z.string(),
  version_id: z.string(),
  job_id: z.string(),
});

export const versionIngestJobRefSchema = z.object({
  job_id: z.string(),
  state: ingestJobStateSchema,
});

export const versionApprovalSummarySchema = z.object({
  request_id: z.string(),
  state: approvalStateSchema,
  created_at: isoDate.nullable().optional(),
  completed_at: isoDate.nullable().optional(),
  steps_total: z.number().int(),
  steps_decided: z.number().int(),
  steps_approved: z.number().int(),
  next_step_no: z.number().int().nullable().optional(),
  next_required_role: z.string().nullable().optional(),
  next_assignee_person_id: z.string().nullable().optional(),
});
export type VersionApprovalSummary = z.infer<typeof versionApprovalSummarySchema>;

export const documentVersionSchema = z.object({
  version_id: z.string(),
  version_no: z.number().int().nullable(),
  /** Free-text version label, e.g. "3.2". */
  version: z.string().nullable().optional(),
  status: versionStatusSchema,
  is_current: z.boolean(),
  effective_date: isoDate.nullable().optional(),
  approved_date: isoDate.nullable().optional(),
  created_at: isoDate.nullable().optional(),
  created_by_person_id: z.string().nullable().optional(),
  change_reason: z.string().nullable().optional(),
  supersedes_version_id: z.string().nullable().optional(),
  superseded_by: z.string().nullable().optional(),
  ingest_status: z.string().nullable().optional(),
  /** Latest ingest job of this version. */
  ingest_job: versionIngestJobRefSchema.nullable().optional(),
  /** Latest approval request of this version. */
  approval: versionApprovalSummarySchema.nullable().optional(),
});
export type DocumentVersion = z.infer<typeof documentVersionSchema>;

/**
 * Whether "approve" may be enabled for this version: its latest ingest job has succeeded, or it
 * has no job row at all (mirrors the server guard in org.py, which 409s otherwise). Rejecting is never blocked.
 */
export function canApproveVersion(v: Pick<DocumentVersion, "ingest_job">): boolean {
  return !v.ingest_job || v.ingest_job.state === "succeeded";
}

/** GET /company/documents/{doc_id}/versions, newest first. */
export const versionListSchema = z.object({
  doc_id: z.string(),
  current_version_id: z.string().nullable(),
  versions: z.array(documentVersionSchema),
});
export type VersionList = z.infer<typeof versionListSchema>;

/** GET /company/ingest-jobs/{job_id}. */
export const ingestJobSchema = z.object({
  job: z.object({
    job_id: z.string(),
    doc_id: z.string(),
    version_id: z.string(),
    state: ingestJobStateSchema,
    error: z.string().nullable().optional(),
    created_at: isoDate.nullable().optional(),
    started_at: isoDate.nullable().optional(),
    finished_at: isoDate.nullable().optional(),
  }),
  stats: z.record(z.string(), z.unknown()).default({}),
});
export type IngestJob = z.infer<typeof ingestJobSchema>;

/** 202 from POST /company/ingest-jobs/{job_id}/retry. */
export const retryJobSchema = z.object({
  job_id: z.string(),
  doc_id: z.string().nullable(),
  version_id: z.string().nullable(),
  state: ingestJobStateSchema,
});
export type RetryJobResult = z.infer<typeof retryJobSchema>;

export const approvalStepSchema = z.object({
  step_no: z.number().int(),
  required_role: z.string(),
  assignee_person_id: z.string().nullable(),
  decision: z.enum(["approved", "rejected"]).nullable(),
  decided_at: isoDate.nullable(),
  note: z.string().nullable(),
});
export type ApprovalStep = z.infer<typeof approvalStepSchema>;

/** GET /company/approval-requests/{id} and the cancel response. */
export const approvalRequestSchema = z.object({
  request_id: z.string(),
  version_id: z.string(),
  doc_id: z.string().nullable(),
  version_no: z.number().int().nullable(),
  version_status: z.string().nullable(),
  policy_id: z.string().nullable(),
  state: approvalStateSchema,
  created_at: isoDate.nullable(),
  completed_at: isoDate.nullable(),
  steps: z.array(approvalStepSchema),
});
export type ApprovalRequest = z.infer<typeof approvalRequestSchema>;

/** POST /company/approval-requests/{id}/steps/{n}/decision: the request plus the decision echo. */
export const approvalDecisionResultSchema = approvalRequestSchema.extend({
  decided_step: z.number().int(),
  decided_by: z.string(),
  request_state: approvalStateSchema,
});
export type ApprovalDecisionResult = z.infer<typeof approvalDecisionResultSchema>;

/** GET /company/org/people. Unlike /company/people, nullable fields are NOT coalesced to "". */
export const orgPersonSchema = z.object({
  person_id: z.string(),
  name: z.string(),
  title: z.string().nullable(),
  department: z.string().nullable(),
  department_id: z.string().nullable().optional(),
  reports_to_id: z.string().nullable(),
  email: z.string().nullable().optional(),
  is_active: z.boolean(),
});
export type OrgPerson = z.infer<typeof orgPersonSchema>;

/** GET /company/documents/{doc_id}/roles item. */
export const roleAssignmentSchema = z.object({
  doc_id: z.string(),
  person_id: z.string(),
  role: documentRoleSchema,
  assigned_at: isoDate.nullable(),
  name: z.string(),
  title: z.string(),
});
export type RoleAssignment = z.infer<typeof roleAssignmentSchema>;

/** 201 from POST /company/documents/{doc_id}/roles. */
export const roleAssignedSchema = z.object({
  doc_id: z.string(),
  person_id: z.string(),
  role: documentRoleSchema,
  legacy_column: z.string().optional(),
  legacy_value: z.string().nullable().optional(),
});
export type RoleAssigned = z.infer<typeof roleAssignedSchema>;

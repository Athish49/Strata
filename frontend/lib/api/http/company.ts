// CompanyApi over HTTP. See development_docs/ui_wiring_contract.md section 5 and the
// "Wave 5 outcome" contract in implementation_plan.md. No fixtures.
import { z } from "zod";
import type { CompanyApi, UploadDocumentMeta, UploadResult, UploadVersionMeta } from "../client";
import {
  approvalDecisionResultSchema,
  approvalRequestSchema,
  clauseSchema,
  companyProfileSchema,
  documentMetaSchema,
  ingestJobSchema,
  orgPersonSchema,
  retryJobSchema,
  roleAssignedSchema,
  roleAssignmentSchema,
  uploadAcceptedSchema,
  uploadDuplicateSchema,
  uploadRetryAvailableSchema,
  uploadUnchangedSchema,
  versionListSchema,
} from "../schemas/company";
import type { DocumentMeta } from "../schemas/company";
import { personSchema } from "../schemas/common";
import { isVerticalSlug, UNCLASSIFIED_SLUG } from "../../verticals";
import { requireActingPersonId } from "../actor-store";
import { getJson, postJson, postRaw, qs, rawError, seg, type RawResponse } from "./shared";

/** Never drop a document: a vertical outside the 14 (incl. the backend's "unclassified") becomes "unclassified". */
export function normalizeDocument(doc: DocumentMeta): DocumentMeta {
  if (isVerticalSlug(doc.vertical)) return doc;
  if (doc.vertical !== UNCLASSIFIED_SLUG) {
    console.warn(`Document ${doc.doc_id}: unknown vertical "${doc.vertical}", shown as unclassified`);
  }
  return { ...doc, vertical: UNCLASSIFIED_SLUG };
}

function specString(spec: string | Record<string, unknown> | undefined): string | undefined {
  if (spec === undefined) return undefined;
  return typeof spec === "string" ? spec : JSON.stringify(spec);
}

function buildForm(file: Blob, filename: string | undefined, fields: Record<string, string | undefined>): FormData {
  const form = new FormData();
  const name = filename ?? (typeof File !== "undefined" && file instanceof File ? file.name : "upload.docx");
  form.append("file", file, name);
  for (const [k, v] of Object.entries(fields)) {
    if (v !== undefined && v !== "") form.append(k, v);
  }
  return form;
}

/** Map an upload response to UploadResult; anything unmapped throws ApiError with the server message. */
export function uploadResultFrom(r: RawResponse): UploadResult {
  const status = (r.body as { status?: unknown } | null)?.status;
  if (r.status === 202) {
    const b = uploadAcceptedSchema.parse(r.body);
    return {
      kind: "created",
      doc_id: b.doc_id,
      version_id: b.version_id,
      job_id: b.job_id,
      version_no: b.version_no ?? 1,
      approval_request_id: b.approval_request_id ?? null,
      approval_state: b.approval_state ?? null,
      retired_version_ids: b.retired_version_ids ?? [],
    };
  }
  if (r.status === 200 && status === "unchanged") {
    const b = uploadUnchangedSchema.parse(r.body);
    return { kind: "unchanged", message: b.message };
  }
  if (r.status === 409 && status === "duplicate") {
    const b = uploadDuplicateSchema.parse(r.body);
    return { kind: "duplicate", message: b.message, doc_id: b.doc_id ?? null };
  }
  if (r.status === 409 && status === "retry_available") {
    const b = uploadRetryAvailableSchema.parse(r.body);
    return { kind: "retry_available", message: b.message, doc_id: b.doc_id, version_id: b.version_id, job_id: b.job_id };
  }
  throw rawError(r);
}

export const companyHttp: CompanyApi = {
  async listDocuments() {
    return (await getJson("/company/documents", z.array(documentMetaSchema))).map(normalizeDocument);
  },

  async getDocument(doc_id) {
    const doc = await getJson(`/company/documents/${seg(doc_id)}`, documentMetaSchema.nullable(), { on404: null });
    return doc ? normalizeDocument(doc) : null;
  },

  listClauses: (doc_id) => getJson(`/company/documents/${seg(doc_id)}/clauses`, z.array(clauseSchema), { on404: [] }),

  listPeople: () => getJson("/company/people", z.array(personSchema)),

  listOrgPeople: (q) =>
    getJson(`/company/org/people${qs({ include_inactive: q?.include_inactive })}`, z.array(orgPersonSchema)),

  getProfile: () => getJson("/company/profile", companyProfileSchema),

  // ---------------------------------------------------------------- writes

  async uploadDocument(vertical, file, meta: UploadDocumentMeta = {}) {
    const acting = requireActingPersonId(meta.acting_person_id);
    const form = buildForm(file, meta.filename, {
      vertical,
      acting_person_id: acting,
      title: meta.title,
      doc_number: meta.doc_number,
      doc_class: meta.doc_class,
      register_spec: specString(meta.register_spec),
      law_as_of: meta.law_as_of,
      change_reason: meta.change_reason,
    });
    return uploadResultFrom(await postRaw("/company/documents", form));
  },

  async uploadVersion(doc_id, file, meta: UploadVersionMeta = {}) {
    const acting = requireActingPersonId(meta.acting_person_id);
    const form = buildForm(file, meta.filename, {
      acting_person_id: acting,
      change_reason: meta.change_reason,
      register_spec: specString(meta.register_spec),
      law_as_of: meta.law_as_of,
    });
    return uploadResultFrom(await postRaw(`/company/documents/${seg(doc_id)}/versions`, form));
  },

  listVersions: (doc_id) =>
    getJson(`/company/documents/${seg(doc_id)}/versions`, versionListSchema.nullable(), { on404: null }),

  getIngestJob: (job_id) => getJson(`/company/ingest-jobs/${seg(job_id)}`, ingestJobSchema.nullable(), { on404: null }),

  retryIngestJob: (job_id) => postJson(`/company/ingest-jobs/${seg(job_id)}/retry`, {}, retryJobSchema),

  getApprovalRequest: (request_id) =>
    getJson(`/company/approval-requests/${seg(request_id)}`, approvalRequestSchema.nullable(), { on404: null }),

  async decideApprovalStep(request_id, step_no, decision, opts) {
    const acting = requireActingPersonId(opts?.acting_person_id);
    const body: Record<string, string> = { acting_person_id: acting, decision };
    if (opts?.note && opts.note.trim()) body.note = opts.note;
    return postJson(
      `/company/approval-requests/${seg(request_id)}/steps/${seg(step_no)}/decision`,
      body,
      approvalDecisionResultSchema,
    );
  },

  async cancelApprovalRequest(request_id, opts) {
    const acting = requireActingPersonId(opts?.acting_person_id);
    return postJson(`/company/approval-requests/${seg(request_id)}/cancel`, { acting_person_id: acting }, approvalRequestSchema);
  },

  listDocumentRoles: (doc_id) => getJson(`/company/documents/${seg(doc_id)}/roles`, z.array(roleAssignmentSchema)),

  async assignDocumentRole(doc_id, person_id, role, opts) {
    const acting = requireActingPersonId(opts?.acting_person_id);
    return postJson(`/company/documents/${seg(doc_id)}/roles`, { acting_person_id: acting, person_id, role }, roleAssignedSchema);
  },
};

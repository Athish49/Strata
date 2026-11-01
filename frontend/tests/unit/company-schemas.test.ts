// The zod schemas must accept the real backend shapes (implementation_plan.md "Wave 5 outcome",
// backend/app/api/company/{upload,versions,org}.py), including extra keys.
import { describe, expect, it } from "vitest";
import {
  approvalDecisionResultSchema,
  approvalRequestSchema,
  canApproveVersion,
  ingestJobSchema,
  isTerminalJobState,
  orgPersonSchema,
  retryJobSchema,
  roleAssignmentSchema,
  uploadAcceptedSchema,
  uploadDuplicateSchema,
  uploadRetryAvailableSchema,
  uploadUnchangedSchema,
  versionListSchema,
} from "@/lib/api/schemas";

const VERSION_LIST = {
  doc_id: "DOC-000007",
  current_version_id: "11111111-1111-1111-1111-111111111111",
  versions: [
    {
      version_id: "22222222-2222-2222-2222-222222222222",
      version_no: 2,
      version: null,
      status: "in_review",
      is_current: false,
      effective_date: null,
      approved_date: null,
      created_at: "2026-10-01T12:00:00.123456+00:00",
      created_by_person_id: "P05",
      change_reason: "Annual refresh",
      supersedes_version_id: "11111111-1111-1111-1111-111111111111",
      superseded_by: null,
      ingest_status: "ingested",
      ingest_job: { job_id: "33333333-3333-3333-3333-333333333333", state: "succeeded" },
      approval: {
        request_id: "44444444-4444-4444-4444-444444444444",
        state: "open",
        created_at: "2026-10-01T12:00:00+00:00",
        completed_at: null,
        steps_total: 2,
        steps_decided: 1,
        steps_approved: 1,
        next_step_no: 2,
        next_required_role: "approver",
        next_assignee_person_id: null,
      },
    },
    {
      version_id: "11111111-1111-1111-1111-111111111111",
      version_no: 1,
      version: "1.0",
      status: "effective",
      is_current: true,
      effective_date: "2025-01-23",
      approved_date: "2025-01-23",
      created_at: "2025-01-20T09:00:00+00:00",
      created_by_person_id: null,
      change_reason: null,
      supersedes_version_id: null,
      superseded_by: null,
      ingest_status: "ingested",
      ingest_job: null,
      approval: null,
    },
  ],
};

const REQUEST = {
  request_id: "44444444-4444-4444-4444-444444444444",
  version_id: "22222222-2222-2222-2222-222222222222",
  doc_id: "DOC-000007",
  version_no: 2,
  version_status: "in_review",
  policy_id: null,
  state: "open",
  created_at: "2026-10-01T12:00:00+00:00",
  completed_at: null,
  steps: [
    { step_no: 1, required_role: "reviewer", assignee_person_id: "P05", decision: "approved", decided_at: "2026-10-02T08:00:00+00:00", note: null },
    { step_no: 2, required_role: "approver", assignee_person_id: null, decision: null, decided_at: null, note: null },
  ],
};

describe("company write-side schemas accept real backend shapes", () => {
  it("POST /company/documents 202 (new document)", () => {
    const b = uploadAcceptedSchema.parse({
      doc_id: "DOC-000041",
      version_id: "55555555-5555-5555-5555-555555555555",
      job_id: "66666666-6666-6666-6666-666666666666",
      status: "processing",
      approval_request_id: "77777777-7777-7777-7777-777777777777",
      approval_state: "open",
    });
    expect(b.version_no).toBeUndefined();
  });

  it("POST /company/documents/{id}/versions 202, with no-policy approval", () => {
    expect(
      uploadAcceptedSchema.parse({
        doc_id: "DOC-000041", version_id: "v", version_no: 2, job_id: "j", status: "processing",
        approval_request_id: "r", approval_state: "approved", retired_version_ids: [],
      }).version_no,
    ).toBe(2);
  });

  it("409 duplicate, 200 unchanged, 409 retry_available", () => {
    expect(uploadDuplicateSchema.parse({ status: "duplicate", message: "This document is already in the system as 'X'.", doc_id: "DOC-000001" }).doc_id).toBe("DOC-000001");
    expect(uploadDuplicateSchema.parse({ status: "duplicate", message: "m", doc_id: null }).doc_id).toBeNull();
    expect(uploadUnchangedSchema.parse({ status: "unchanged", message: "No changes compared to the current version." }).status).toBe("unchanged");
    expect(
      uploadRetryAvailableSchema.parse({ status: "retry_available", message: "m", doc_id: "D", version_id: "v", job_id: "j" }).job_id,
    ).toBe("j");
  });

  it("GET /company/documents/{id}/versions, tolerating extra keys", () => {
    const parsed = versionListSchema.parse({ ...VERSION_LIST, extra: true, versions: VERSION_LIST.versions.map((v) => ({ ...v, new_col: 1 })) });
    expect(parsed.versions.map((v) => v.version_no)).toEqual([2, 1]);
    expect(parsed.versions.filter((v) => v.is_current)).toHaveLength(1);
    expect(parsed.versions[0].approval?.next_required_role).toBe("approver");
    expect("new_col" in parsed.versions[0]).toBe(false);
  });

  it("accepts the DB's draft/approved version statuses too", () => {
    for (const status of ["draft", "approved", "superseded", "retired"]) {
      expect(() => versionListSchema.parse({ ...VERSION_LIST, versions: [{ ...VERSION_LIST.versions[1], status }] })).not.toThrow();
    }
  });

  it("GET /company/ingest-jobs/{id} for each state", () => {
    for (const state of ["queued", "running", "succeeded", "failed"]) {
      const j = ingestJobSchema.parse({
        job: {
          job_id: "j", doc_id: "D", version_id: "v", state,
          error: state === "failed" ? "IngestError('boom')" : null,
          created_at: "2026-10-01T12:00:00+00:00", started_at: null, finished_at: null,
        },
        stats: state === "succeeded" ? { clause_count: 12, citations: { resolved: 3 } } : {},
      });
      expect(j.job.state).toBe(state);
    }
    expect(isTerminalJobState("succeeded")).toBe(true);
    expect(isTerminalJobState("failed")).toBe(true);
    expect(isTerminalJobState("running")).toBe(false);
    expect(isTerminalJobState(undefined)).toBe(false);
  });

  it("POST retry 202", () => {
    expect(retryJobSchema.parse({ job_id: "j", doc_id: "D", version_id: "v", state: "queued" }).state).toBe("queued");
    expect(retryJobSchema.parse({ job_id: "j", doc_id: null, version_id: null, state: "queued" }).doc_id).toBeNull();
  });

  it("approval request + decision response", () => {
    expect(approvalRequestSchema.parse(REQUEST).steps).toHaveLength(2);
    const d = approvalDecisionResultSchema.parse({ ...REQUEST, decided_step: 1, decided_by: "P05", request_state: "open" });
    expect(d.decided_by).toBe("P05");
    // list endpoint returns steps: [] and a missing version yields nulls
    expect(approvalRequestSchema.parse({ ...REQUEST, doc_id: null, version_no: null, version_status: null, steps: [] }).doc_id).toBeNull();
  });

  it("org people (null fields not coalesced) and role assignments", () => {
    expect(
      orgPersonSchema.parse({ person_id: "P01", name: "W", title: null, department: "Exec", department_id: null, reports_to_id: null, email: null, is_active: true }).is_active,
    ).toBe(true);
    expect(roleAssignmentSchema.parse({ doc_id: "D", person_id: "P05", role: "owner", assigned_at: "2026-10-01T12:00:00+00:00", name: "", title: "" }).role).toBe("owner");
  });

  it("canApproveVersion: blocked until the latest job succeeded; no job row is not blocked", () => {
    const [v2, v1] = versionListSchema.parse(VERSION_LIST).versions;
    expect(canApproveVersion(v2)).toBe(true);
    expect(canApproveVersion(v1)).toBe(true);
    expect(canApproveVersion({ ingest_job: { job_id: "j", state: "running" } })).toBe(false);
    expect(canApproveVersion({ ingest_job: { job_id: "j", state: "failed" } })).toBe(false);
  });
});

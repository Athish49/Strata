import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { companyHttp } from "@/lib/api/http/company";
import { ApiError, postJson } from "@/lib/api/http/shared";
import { MissingActorError, resetActorStoreForTests, setActingPersonId } from "@/lib/actor";
import { z } from "zod";

interface Call {
  url: string;
  init: RequestInit;
}

function stub(handler: (url: string, init: RequestInit) => { status?: number; body?: unknown }) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      const { status = 200, body = null } = handler(url, init);
      return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
    }),
  );
  return calls;
}

const docx = () => new File(["hello"], "Outage Plan.docx", { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });
const headerNames = (init: RequestInit) => Object.keys((init.headers ?? {}) as Record<string, string>).map((k) => k.toLowerCase());
const form = (c: Call) => c.init.body as FormData;

beforeEach(() => {
  resetActorStoreForTests();
  localStorage.clear();
  setActingPersonId("P05");
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("FormData transport", () => {
  it("uploadDocument sends multipart FormData with NO Content-Type header and the actor attached", async () => {
    const calls = stub(() => ({
      status: 202,
      body: { doc_id: "DOC-000041", version_id: "v1", job_id: "j1", status: "processing", approval_request_id: "r1", approval_state: "open" },
    }));
    const r = await companyHttp.uploadDocument("operations-quality", docx(), { title: "Outage", doc_number: "OPS-9", register_spec: { a: 1 } });
    expect(r).toEqual({
      kind: "created",
      doc_id: "DOC-000041",
      version_id: "v1",
      job_id: "j1",
      version_no: 1,
      approval_request_id: "r1",
      approval_state: "open",
      retired_version_ids: [],
    });
    const c = calls[0];
    expect(c.url).toMatch(/\/company\/documents$/);
    expect(c.init.method).toBe("POST");
    expect(c.init.body).toBeInstanceOf(FormData);
    expect(headerNames(c.init)).not.toContain("content-type");
    const f = form(c);
    expect(f.get("vertical")).toBe("operations-quality");
    expect(f.get("acting_person_id")).toBe("P05");
    expect(f.get("title")).toBe("Outage");
    expect(f.get("doc_number")).toBe("OPS-9");
    expect(f.get("register_spec")).toBe('{"a":1}');
    expect(f.has("law_as_of")).toBe(false);
    expect((f.get("file") as File).name).toBe("Outage Plan.docx");
  });

  it("postJson with a FormData body also omits Content-Type, JSON keeps it", async () => {
    const calls = stub(() => ({ body: { ok: true } }));
    const fd = new FormData();
    fd.append("a", "b");
    await postJson("/x", fd, z.object({ ok: z.boolean() }));
    await postJson("/y", { a: 1 }, z.object({ ok: z.boolean() }));
    expect(headerNames(calls[0].init)).not.toContain("content-type");
    expect(calls[0].init.body).toBe(fd);
    expect((calls[1].init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(calls[1].init.body).toBe('{"a":1}');
  });

  it("explicit acting_person_id overrides the store; no actor rejects before any request", async () => {
    const calls = stub(() => ({ status: 202, body: { doc_id: "D", version_id: "v", job_id: "j", status: "processing" } }));
    await companyHttp.uploadVersion("D", docx(), { acting_person_id: "P09", change_reason: "typo" });
    expect(form(calls[0]).get("acting_person_id")).toBe("P09");
    expect(form(calls[0]).get("change_reason")).toBe("typo");
    setActingPersonId(null);
    await expect(companyHttp.uploadDocument("compliance-ethics", docx())).rejects.toBeInstanceOf(MissingActorError);
    await expect(companyHttp.decideApprovalStep("r", 1, "approved")).rejects.toBeInstanceOf(MissingActorError);
    expect(calls).toHaveLength(1);
  });
});

describe("upload results (bodies of 200/409 are surfaced, not thrown)", () => {
  it("409 duplicate -> kind duplicate with message and doc_id", async () => {
    stub(() => ({ status: 409, body: { status: "duplicate", message: "This document is already in the system as 'Outage Plan'.", doc_id: "DOC-000003" } }));
    expect(await companyHttp.uploadDocument("compliance-ethics", docx())).toEqual({
      kind: "duplicate",
      message: "This document is already in the system as 'Outage Plan'.",
      doc_id: "DOC-000003",
    });
  });

  it("409 duplicate on the race path carries doc_id null", async () => {
    stub(() => ({ status: 409, body: { status: "duplicate", message: "This document is already in the system as 'another document'.", doc_id: null } }));
    expect(await companyHttp.uploadDocument("compliance-ethics", docx())).toMatchObject({ kind: "duplicate", doc_id: null });
  });

  it("200 unchanged -> kind unchanged", async () => {
    const calls = stub(() => ({ status: 200, body: { status: "unchanged", message: "No changes compared to the current version." } }));
    expect(await companyHttp.uploadVersion("DOC 1", docx())).toEqual({ kind: "unchanged", message: "No changes compared to the current version." });
    expect(calls[0].url).toMatch(/\/company\/documents\/DOC%201\/versions$/);
  });

  it("409 retry_available -> kind retry_available with job_id", async () => {
    stub(() => ({
      status: 409,
      body: {
        status: "retry_available",
        message: "This exact file is already stored as version 2, whose ingest failed. Retry that ingest instead of uploading it again.",
        doc_id: "DOC-000001",
        version_id: "v2",
        job_id: "j2",
      },
    }));
    expect(await companyHttp.uploadVersion("DOC-000001", docx())).toMatchObject({ kind: "retry_available", job_id: "j2", version_id: "v2", doc_id: "DOC-000001" });
  });

  it("202 new version carries version_no and retired_version_ids", async () => {
    stub(() => ({
      status: 202,
      body: { doc_id: "D", version_id: "v3", version_no: 3, job_id: "j3", status: "processing", approval_request_id: null, approval_state: "approved", retired_version_ids: ["v2"] },
    }));
    expect(await companyHttp.uploadVersion("D", docx())).toMatchObject({ kind: "created", version_no: 3, approval_state: "approved", retired_version_ids: ["v2"] });
  });

  it.each([
    [415, { detail: "Only .docx documents are supported. PDF is not yet available." }, "Only .docx documents are supported. PDF is not yet available."],
    [422, { detail: "No extractable text found in this document." }, "No extractable text found in this document."],
    [413, { detail: "too large" }, "too large"],
    [409, { detail: "approval request is open" }, "approval request is open"],
    [422, { detail: [{ loc: ["body", "vertical"], msg: "Field required" }] }, "Field required"],
  ])("HTTP %i without a mapped body throws ApiError with the server message", async (status, body, msg) => {
    stub(() => ({ status, body }));
    const err = await companyHttp.uploadDocument("compliance-ethics", docx()).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status, detail: msg });
  });
});

describe("versions, jobs, approvals, roles", () => {
  it("listVersions / getIngestJob / getApprovalRequest return null on 404", async () => {
    stub(() => ({ status: 404, body: { detail: "not found" } }));
    expect(await companyHttp.listVersions("D")).toBeNull();
    expect(await companyHttp.getIngestJob("j")).toBeNull();
    expect(await companyHttp.getApprovalRequest("r")).toBeNull();
  });

  it("retryIngestJob posts to the retry path; a 409 throws", async () => {
    let n = 0;
    const calls = stub(() =>
      n++ === 0
        ? { status: 202, body: { job_id: "j", doc_id: "D", version_id: "v", state: "queued" } }
        : { status: 409, body: { detail: "job is running, not failed" } },
    );
    expect(await companyHttp.retryIngestJob("j")).toEqual({ job_id: "j", doc_id: "D", version_id: "v", state: "queued" });
    expect(calls[0].url).toMatch(/\/company\/ingest-jobs\/j\/retry$/);
    await expect(companyHttp.retryIngestJob("j")).rejects.toMatchObject({ status: 409 });
  });

  it("decideApprovalStep sends acting_person_id, decision and note as JSON; 403 surfaces the detail", async () => {
    const req = {
      request_id: "r1",
      version_id: "v1",
      doc_id: "D",
      version_no: 1,
      version_status: "in_review",
      policy_id: null,
      state: "open",
      created_at: "2026-01-01T00:00:00+00:00",
      completed_at: null,
      steps: [{ step_no: 1, required_role: "reviewer", assignee_person_id: "P05", decision: "approved", decided_at: "2026-01-01T00:00:01+00:00", note: "ok" }],
    };
    let n = 0;
    const calls = stub(() =>
      n++ === 0
        ? { body: { ...req, decided_step: 1, decided_by: "P05", request_state: "open" } }
        : { status: 403, body: { detail: "P05 does not hold role 'approver' on D" } },
    );
    const r = await companyHttp.decideApprovalStep("r1", 1, "approved", { note: "ok" });
    expect(r.request_state).toBe("open");
    expect(calls[0].url).toMatch(/\/company\/approval-requests\/r1\/steps\/1\/decision$/);
    expect(JSON.parse(calls[0].init.body as string)).toEqual({ acting_person_id: "P05", decision: "approved", note: "ok" });
    await expect(companyHttp.decideApprovalStep("r1", 2, "approved")).rejects.toMatchObject({
      status: 403,
      detail: "P05 does not hold role 'approver' on D",
    });
  });

  it("cancelApprovalRequest and assignDocumentRole attach the actor", async () => {
    const calls = stub((url) =>
      url.endsWith("/cancel")
        ? {
            body: {
              request_id: "r1", version_id: "v1", doc_id: "D", version_no: 1, version_status: "retired", policy_id: null,
              state: "cancelled", created_at: null, completed_at: null, steps: [],
            },
          }
        : { status: 201, body: { doc_id: "D", person_id: "P07", role: "reviewer", legacy_column: "reviewer_id", legacy_value: "P07" } },
    );
    expect((await companyHttp.cancelApprovalRequest("r1")).state).toBe("cancelled");
    expect(JSON.parse(calls[0].init.body as string)).toEqual({ acting_person_id: "P05" });
    expect((await companyHttp.assignDocumentRole("D", "P07", "reviewer")).role).toBe("reviewer");
    expect(calls[1].url).toMatch(/\/company\/documents\/D\/roles$/);
    expect(JSON.parse(calls[1].init.body as string)).toEqual({ acting_person_id: "P05", person_id: "P07", role: "reviewer" });
  });

  it("listOrgPeople passes include_inactive and parses null fields", async () => {
    const calls = stub(() => ({
      body: [{ person_id: "P01", name: "W", title: null, department: null, department_id: null, reports_to_id: null, email: null, is_active: false }],
    }));
    const [p] = await companyHttp.listOrgPeople({ include_inactive: false });
    expect(p.is_active).toBe(false);
    expect(calls[0].url).toMatch(/\/company\/org\/people\?include_inactive=false$/);
  });
});

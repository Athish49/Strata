import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { mockApi, setMockLatency } from "@/tests/support/mock-api";
import { MOCK_DUPLICATE_DOC_ID, addMockDocument, resetCompanyMock } from "@/tests/support/mock-api/company";
import { fixtures } from "@/tests/support/mock-api/fixtures";
import {
  INGEST_POLL_MS,
  ingestJobRefetchInterval,
  qk,
  useDocuments,
  useDocumentVersions,
  useIngestJob,
  useRetryIngestJob,
  useUploadDocument,
} from "@/lib/api/queries";
import { ApiError } from "@/lib/api/http/shared";
import { MissingActorError, resetActorStoreForTests, setActingPersonId } from "@/lib/actor";
import { VERTICAL_GROUPS } from "@/lib/verticals";
import type { IngestJob } from "@/lib/api/schemas";

const file = (name: string) => new File(["x"], name);

function setup() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  return { qc, wrapper };
}

const job = (state: IngestJob["job"]["state"]): IngestJob => ({
  job: { job_id: "j", doc_id: "D", version_id: "v", state, error: null, created_at: null, started_at: null, finished_at: null },
  stats: {},
});

beforeEach(() => {
  setMockLatency(false);
  resetCompanyMock();
  localStorage.clear();
  resetActorStoreForTests();
  setActingPersonId("P05");
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  setMockLatency(true);
});

describe("ingest job poller", () => {
  it("refetchInterval polls while queued/running/unloaded and stops on terminal states or 404", () => {
    expect(ingestJobRefetchInterval(undefined)).toBe(INGEST_POLL_MS);
    expect(ingestJobRefetchInterval(job("queued"))).toBe(2000);
    expect(ingestJobRefetchInterval(job("running"))).toBe(2000);
    expect(ingestJobRefetchInterval(job("succeeded"))).toBe(false);
    expect(ingestJobRefetchInterval(job("failed"))).toBe(false);
    expect(ingestJobRefetchInterval(null)).toBe(false);
  });

  it("polls until succeeded, then stops and invalidates documents + versions + clauses", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const up = await mockApi.company.uploadDocument("operations-quality", file("Outage.docx"));
    if (up.kind !== "created") throw new Error("expected created");
    const spy = vi.spyOn(mockApi.company, "getIngestJob");
    const { qc, wrapper } = setup();
    const inval = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useIngestJob(up.job_id), { wrapper });

    await waitFor(() => expect(result.current.data?.job.state).toBe("running"));
    await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS + 50));
    await waitFor(() => expect(result.current.data?.job.state).toBe("succeeded"));
    const calls = spy.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS * 3));
    expect(spy.mock.calls.length).toBe(calls); // stopped

    const keys = inval.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toContain(JSON.stringify(qk.documents()));
    expect(keys).toContain(JSON.stringify(qk.docVersions(up.doc_id)));
    expect(keys).toContain(JSON.stringify(qk.clauses(up.doc_id)));
    expect(keys.filter((k) => k === JSON.stringify(qk.docVersions(up.doc_id)))).toHaveLength(1); // once per job
  });

  it("stops on failed and still invalidates documents + versions (lifecycle flips)", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const up = await mockApi.company.uploadDocument("compliance-ethics", file("will-fail.docx"));
    if (up.kind !== "created") throw new Error("expected created");
    const { qc, wrapper } = setup();
    const inval = vi.spyOn(qc, "invalidateQueries");
    const { result } = renderHook(() => useIngestJob(up.job_id), { wrapper });
    await waitFor(() => expect(result.current.data?.job.state).toBe("running"));
    await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS + 50));
    await waitFor(() => expect(result.current.data?.job.state).toBe("failed"));
    expect(result.current.data?.job.error).toBeTruthy();
    const keys = inval.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toContain(JSON.stringify(qk.documents()));
    expect(keys).toContain(JSON.stringify(qk.docVersions(up.doc_id)));
    expect(keys).not.toContain(JSON.stringify(qk.clauses(up.doc_id)));
    expect((await mockApi.company.getDocument(up.doc_id))?.lifecycle_state).toBe("failed");
  });

  it("a retry reuses the same job id, so a second terminal state must refresh the lists again", async () => {
    // Regression: the hook used to mark a job id as handled forever, so after failed -> retry ->
    // succeeded the documents and versions stayed stale (still "Ingest failed" in the UI).
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const up = await mockApi.company.uploadDocument("compliance-ethics", file("will-fail.docx"));
    if (up.kind !== "created") throw new Error("expected created");
    const { qc, wrapper } = setup();
    const inval = vi.spyOn(qc, "invalidateQueries");
    const job = renderHook(() => useIngestJob(up.job_id), { wrapper });
    await waitFor(() => expect(job.result.current.data?.job.state).toBe("running"));
    await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS + 50));
    await waitFor(() => expect(job.result.current.data?.job.state).toBe("failed"));
    // Count the CLAUSES key: only the post-ingest-success path invalidates it. (The versions and
    // documents keys are also invalidated by useRetryIngestJob's own onSuccess, so they would
    // go up on a retry even with the bug present and make this test vacuous.)
    const clausesKey = JSON.stringify(qk.clauses(up.doc_id));
    const count = () => inval.mock.calls.filter((c) => JSON.stringify(c[0]?.queryKey) === clausesKey).length;
    expect(count()).toBe(0); // a failed ingest wrote no clauses

    const retry = renderHook(() => useRetryIngestJob(), { wrapper });
    await act(async () => { await retry.result.current.mutateAsync(up.job_id); });
    await waitFor(() => expect(job.result.current.data?.job.state).not.toBe("failed"));
    for (let i = 0; i < 4 && job.result.current.data?.job.state !== "succeeded"; i++) {
      await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS + 50));
    }
    await waitFor(() => expect(job.result.current.data?.job.state).toBe("succeeded"));
    await waitFor(() => expect(count()).toBe(1)); // refreshed once the retry succeeded
  });
});

describe("documents hook keeps unclassified documents", () => {
  it("a document with vertical 'unclassified' is returned and has a group", async () => {
    const base = fixtures().documents[0];
    addMockDocument({ ...base, doc_id: "DOC-UNCLASS", vertical: "unclassified" });
    addMockDocument({ ...base, doc_id: "DOC-WEIRD", vertical: "something-new" });
    vi.spyOn(console, "warn").mockImplementation(() => {});
    const { wrapper } = setup();
    const { result } = renderHook(() => useDocuments(), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    const mine = result.current.data!.filter((d) => d.doc_id.startsWith("DOC-"));
    expect(mine.map((d) => [d.doc_id, d.vertical])).toEqual([
      ["DOC-UNCLASS", "unclassified"],
      ["DOC-WEIRD", "unclassified"],
    ]);
    expect(VERTICAL_GROUPS.map((g) => g.slug)).toContain("unclassified");
  });
});

describe("upload mutation + mock states", () => {
  it("created: seeds a queued job and the new document appears", async () => {
    const { qc, wrapper } = setup();
    const { result } = renderHook(() => useUploadDocument(), { wrapper });
    let r: Awaited<ReturnType<typeof result.current.mutateAsync>> | undefined;
    await act(async () => {
      r = await result.current.mutateAsync({ vertical: "workforce-employment", file: file("Safety Manual.docx"), meta: { doc_number: "HR-7" } });
    });
    if (r?.kind !== "created") throw new Error("expected created");
    expect(qc.getQueryData<IngestJob>(qk.ingestJob(r.job_id))?.job.state).toBe("queued");
    const doc = await mockApi.company.getDocument(r.doc_id);
    expect(doc).toMatchObject({ title: "Safety Manual", vertical: "workforce-employment", doc_number: "HR-7", lifecycle_state: "pending" });
  });

  it("duplicate / unchanged / retry_available / errors are deterministic", async () => {
    expect(await mockApi.company.uploadDocument("compliance-ethics", file("duplicate.docx"))).toMatchObject({ kind: "duplicate", doc_id: MOCK_DUPLICATE_DOC_ID });
    expect(await mockApi.company.uploadVersion(MOCK_DUPLICATE_DOC_ID, file("unchanged.docx"))).toMatchObject({ kind: "unchanged" });
    const retry = await mockApi.company.uploadVersion(MOCK_DUPLICATE_DOC_ID, file("retry.docx"));
    if (retry.kind !== "retry_available") throw new Error("expected retry_available");
    expect((await mockApi.company.retryIngestJob(retry.job_id)).state).toBe("queued");
    await expect(mockApi.company.uploadDocument("compliance-ethics", file("scan.pdf"))).rejects.toMatchObject({ status: 415 });
    await expect(mockApi.company.uploadDocument("compliance-ethics", file("empty.docx"))).rejects.toMatchObject({ status: 422 });
    // `unclassified` is a fallback group, never an upload target (the backend 422s it).
    await expect(mockApi.company.uploadDocument("unclassified", file("ok.docx"))).rejects.toBeInstanceOf(ApiError);
    setActingPersonId(null);
    await expect(mockApi.company.uploadDocument("compliance-ethics", file("ok.docx"))).rejects.toBeInstanceOf(MissingActorError);
  });

  it("approval on a new document: 403 until roles are assigned", async () => {
    const up = await mockApi.company.uploadDocument("compliance-ethics", file("New Policy.docx"));
    if (up.kind !== "created" || !up.approval_request_id) throw new Error("expected created with a request");
    await mockApi.company.getIngestJob(up.job_id);
    await mockApi.company.getIngestJob(up.job_id); // succeeded
    await expect(mockApi.company.decideApprovalStep(up.approval_request_id, 1, "approved")).rejects.toMatchObject({
      status: 403,
      detail: `P05 does not hold role 'reviewer' on ${up.doc_id}`,
    });
    await mockApi.company.assignDocumentRole(up.doc_id, "P05", "reviewer");
    expect((await mockApi.company.decideApprovalStep(up.approval_request_id, 1, "approved")).request_state).toBe("open");
    expect(await mockApi.company.listDocumentRoles(up.doc_id)).toMatchObject([{ person_id: "P05", role: "reviewer" }]);
  });

  it("approval: refused until ingest succeeds, final approval promotes the new version", async () => {
    // RPL-CMP-REG-001 fixture: reviewer P05, approver P04 (legacy role columns).
    const up = await mockApi.company.uploadVersion(MOCK_DUPLICATE_DOC_ID, file("v2.docx"), { change_reason: "refresh" });
    if (up.kind !== "created" || !up.approval_request_id) throw new Error("expected created with a request");
    await expect(mockApi.company.decideApprovalStep(up.approval_request_id, 1, "approved")).rejects.toMatchObject({ status: 409 });
    await mockApi.company.getIngestJob(up.job_id); // running
    await mockApi.company.getIngestJob(up.job_id); // succeeded
    await expect(mockApi.company.decideApprovalStep(up.approval_request_id, 2, "approved")).rejects.toMatchObject({ status: 409 }); // out of order
    expect((await mockApi.company.decideApprovalStep(up.approval_request_id, 1, "approved")).request_state).toBe("open");
    await expect(mockApi.company.decideApprovalStep(up.approval_request_id, 2, "approved")).rejects.toMatchObject({ status: 403 }); // P05 is not the approver
    expect((await mockApi.company.decideApprovalStep(up.approval_request_id, 2, "approved", { acting_person_id: "P04" })).request_state).toBe("approved");
    const list = await mockApi.company.listVersions(MOCK_DUPLICATE_DOC_ID);
    expect(list?.versions.map((v) => [v.version_no, v.status, v.is_current])).toEqual([
      [2, "effective", true],
      [1, "superseded", false],
    ]);
    expect(list?.current_version_id).toBe(up.version_id);
  });

  it("useDocumentVersions returns a single-version history for a fixture document", async () => {
    const { wrapper } = setup();
    const { result } = renderHook(() => useDocumentVersions(MOCK_DUPLICATE_DOC_ID), { wrapper });
    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(result.current.data?.versions).toHaveLength(1);
    expect(result.current.data?.versions[0]).toMatchObject({ is_current: true, status: "effective", approval: null, ingest_job: null });
  });
});

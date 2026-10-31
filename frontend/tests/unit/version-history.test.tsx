import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { VersionHistoryButton, VersionHistoryPanel } from "@/components/documents/versions";
import { errorMessage } from "@/components/documents/versions/logic";
import { mockApi, setMockLatency } from "@/tests/support/mock-api";
import { MOCK_DUPLICATE_DOC_ID, resetCompanyMock } from "@/tests/support/mock-api/company";
import { INGEST_POLL_MS, qk } from "@/lib/api/queries";
import { ApiError } from "@/lib/api/http/shared";
import { MissingActorError, resetActorStoreForTests, setActingPersonId } from "@/lib/actor";
import { isTerminalJobState } from "@/lib/api/schemas";

// Fixture document: legacy owner P06, reviewer P05 (David Okafor), approver P04 (Margaret Ellison).
const FIXTURE_DOC = MOCK_DUPLICATE_DOC_ID;
const file = (name: string) => new File(["x"], name);

function renderPanel(docId: string, qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })) {
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
  const utils = render(<VersionHistoryPanel docId={docId} />, { wrapper });
  return { qc, ...utils };
}

/** Drive the mock job to a terminal state (each GET advances it one step), then refetch the panel. */
async function finishJob(qc: QueryClient, jobId: string) {
  for (let i = 0; i < 4; i++) {
    const j = await mockApi.company.getIngestJob(jobId);
    if (!j || isTerminalJobState(j.job.state)) break;
  }
  await act(() => qc.invalidateQueries({ queryKey: ["company"] }));
}

const cards = () => Array.from(document.querySelectorAll<HTMLElement>("[data-version]"));
const card = (no: number) => {
  const el = document.querySelector<HTMLElement>(`[data-version-no="${no}"]`);
  if (!el) throw new Error(`no card for v${no}`);
  return el;
};
const live = () => document.querySelector("[data-live]")?.textContent ?? "";

async function twoVersionDoc() {
  const up = await mockApi.company.uploadVersion(FIXTURE_DOC, file("v2.docx"), { change_reason: "Annual refresh" });
  if (up.kind !== "created") throw new Error("expected created");
  return up;
}

beforeEach(() => {
  setMockLatency(false);
  resetCompanyMock();
  localStorage.clear();
  resetActorStoreForTests();
  setActingPersonId("P05");
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  setMockLatency(true);
});

describe("VersionHistoryPanel", () => {
  it("lists two versions newest-first with exactly one Current marker", async () => {
    await twoVersionDoc();
    renderPanel(FIXTURE_DOC);
    await waitFor(() => expect(cards()).toHaveLength(2));
    expect(cards().map((c) => c.dataset.versionNo)).toEqual(["2", "1"]);
    const markers = document.querySelectorAll("[data-current-marker]");
    expect(markers).toHaveLength(1);
    expect(card(1)).toContainElement(markers[0] as HTMLElement);
    expect(card(1)).toHaveAttribute("aria-current", "true");
    expect(within(card(2)).getByText("In review")).toBeInTheDocument();
    expect(card(1).querySelector("[data-status]")?.textContent).toBe("Effective");
    expect(within(card(2)).getByText("“Annual refresh”")).toBeInTheDocument();
    expect(within(card(2)).getByText("David Okafor")).toBeInTheDocument(); // author
    expect(within(card(2)).getByText("Supersedes")).toBeInTheDocument();
    expect(within(card(2)).getByText("v1")).toBeInTheDocument();
  });

  it("renders a single-version document without an approval block or glitch", async () => {
    renderPanel(FIXTURE_DOC);
    await waitFor(() => expect(cards()).toHaveLength(1));
    expect(card(1).querySelector("[data-approval]")).toBeNull();
    expect(document.querySelectorAll("[data-current-marker]")).toHaveLength(1);
    expect(document.body.textContent).not.toMatch(/null|undefined|NaN/);
  });

  it("shows approval progress for the in-review version", async () => {
    await twoVersionDoc();
    renderPanel(FIXTURE_DOC);
    const section = await waitFor(() => {
      const s = card(2).querySelector<HTMLElement>("[data-approval]");
      if (!s) throw new Error("no approval yet");
      return s;
    });
    expect(within(section).getByText("Approval · Open")).toBeInTheDocument();
    expect(within(section).getByText("0 of 2 steps approved")).toBeInTheDocument();
    const steps = within(section).getAllByRole("listitem");
    expect(steps).toHaveLength(2);
    expect(within(steps[0]).getByText("Reviewer")).toBeInTheDocument();
    expect(within(steps[0]).getByText("Any reviewer")).toBeInTheDocument();
    expect(within(steps[1]).getByText("Approver")).toBeInTheDocument();
    expect(within(section).getAllByText("Pending")).toHaveLength(2);
  });

  it("keeps Approve disabled until the version's ingest job succeeded", async () => {
    const up = await twoVersionDoc();
    const { qc } = renderPanel(FIXTURE_DOC);
    const approve = await screen.findByRole("button", { name: "Approve step 1" });
    expect(approve).toBeDisabled();
    expect(screen.getByText("Approval opens once this version's ingest has succeeded.")).toBeInTheDocument();
    await finishJob(qc, up.job_id);
    await waitFor(() => expect(screen.getByRole("button", { name: "Approve step 1" })).toBeEnabled());
    expect(within(card(2)).getByText("Ingested")).toBeInTheDocument();
  });

  it("requires a note to reject a step", async () => {
    await twoVersionDoc();
    renderPanel(FIXTURE_DOC);
    fireEvent.click(await screen.findByRole("button", { name: "Reject…" }));
    const submit = screen.getByRole("button", { name: "Reject step 1" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for rejecting (required)"), { target: { value: "   " } });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Reason for rejecting (required)"), { target: { value: "Section 4 is out of date" } });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await waitFor(() => expect(screen.getByText("Approval · Rejected")).toBeInTheDocument());
    expect(screen.getByText("“Section 4 is out of date”")).toBeInTheDocument();
    expect(live()).toBe("Step 1 rejected for v2.");
  });

  it("final approval promotes the version, moves the Current marker and invalidates the engine reader cache", async () => {
    const up = await twoVersionDoc();
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    const readerKey = qk.reader("run_1", FIXTURE_DOC);
    const otherKey = qk.reader("run_1", "SOME-OTHER-DOC");
    qc.setQueryData(readerKey, { doc: null, clauses: [], annotations: [] });
    qc.setQueryData(otherKey, { doc: null, clauses: [], annotations: [] });
    renderPanel(FIXTURE_DOC, qc);
    await screen.findByRole("button", { name: "Approve step 1" });
    await finishJob(qc, up.job_id);

    // Step 1: P05 is the document's reviewer.
    fireEvent.click(await waitFor(() => {
      const b = screen.getByRole("button", { name: "Approve step 1" });
      expect(b).toBeEnabled();
      return b;
    }));
    await waitFor(() => expect(live()).toBe("Step 1 approved for v2."));
    expect(qc.getQueryState(readerKey)?.isInvalidated).toBe(false);

    // Step 2: P04 is the approver.
    act(() => setActingPersonId("P04"));
    fireEvent.click(await screen.findByRole("button", { name: "Approve step 2" }));
    await waitFor(() => expect(live()).toBe("v2 approved. It is now the current version."));
    await waitFor(() => expect(card(2)).toHaveAttribute("aria-current", "true"));
    expect(document.querySelectorAll("[data-current-marker]")).toHaveLength(1);
    expect(card(2)).toContainElement(document.querySelector("[data-current-marker]") as HTMLElement);
    expect(within(card(1)).getByText("Superseded")).toBeInTheDocument();
    expect(within(card(1)).getByText("Superseded by")).toBeInTheDocument();
    expect(qc.getQueryState(readerKey)?.isInvalidated).toBe(true);
    expect(qc.getQueryState(otherKey)?.isInvalidated).toBe(false);
  });

  it("explains a 403 on a brand-new document with no roles, with an actionable message", async () => {
    const up = await mockApi.company.uploadDocument("operations-quality", file("Outage.docx"));
    if (up.kind !== "created") throw new Error("expected created");
    const { qc } = renderPanel(up.doc_id);
    await waitFor(() => expect(document.querySelector("[data-no-roles]")).not.toBeNull());
    await waitFor(() => expect(document.querySelector("[data-no-role]")?.textContent).toContain("Nobody holds the reviewer role"));
    await finishJob(qc, up.job_id);
    const approve = await waitFor(() => {
      const b = screen.getByRole("button", { name: "Approve step 1" });
      expect(b).toBeEnabled();
      return b;
    });
    fireEvent.click(approve);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("does not hold role 'reviewer'");
    expect(alert.textContent).toContain("Assign the role below");
  });

  it("assigns a role (inactive people hidden) and then lets the holder sign", async () => {
    const up = await mockApi.company.uploadDocument("operations-quality", file("Outage.docx"));
    if (up.kind !== "created") throw new Error("expected created");
    const real = mockApi.company.listOrgPeople;
    vi.spyOn(mockApi.company, "listOrgPeople").mockImplementation(async (q) => {
      const people = await real(q);
      return people.map((p) => (p.person_id === "P08" ? { ...p, is_active: false } : p));
    });
    const { qc } = renderPanel(up.doc_id);
    await finishJob(qc, up.job_id);
    fireEvent.click(await screen.findByRole("button", { name: "Assign a reviewer" }));
    const roleSel = screen.getByLabelText("Role") as HTMLSelectElement;
    await waitFor(() => expect(roleSel.value).toBe("reviewer"));
    const personSel = screen.getByLabelText("Person") as HTMLSelectElement;
    await waitFor(() => expect(within(personSel).getByText(/David Okafor/)).toBeInTheDocument());
    expect(within(personSel).queryByText(/Elena Vasquez/)).toBeNull(); // inactive
    expect(screen.getByRole("button", { name: "Assign role" })).toBeDisabled();
    fireEvent.change(personSel, { target: { value: "P05" } });
    fireEvent.click(screen.getByRole("button", { name: "Assign role" }));
    await waitFor(() => expect(live()).toBe("David Okafor assigned as reviewer."));
    await waitFor(() => expect(document.querySelector('[data-role-holders="reviewer"]')?.textContent).toBe("David Okafor"));
    await waitFor(() => expect(document.querySelector("[data-no-role]")).toBeNull());

    fireEvent.click(screen.getByRole("button", { name: "Approve step 1" }));
    await waitFor(() => expect(live()).toBe("Step 1 approved for v1."));
    // Step 2 now needs an approver nobody holds yet.
    await waitFor(() => expect(document.querySelector("[data-no-role]")?.textContent).toContain("approver role"));
  });

  it("retries a failed ingest job, and the retried attempt refreshes the document when it finishes", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const up = await mockApi.company.uploadDocument("operations-quality", file("fail-report.docx"));
    if (up.kind !== "created") throw new Error("expected created");
    const spy = vi.spyOn(mockApi.company, "retryIngestJob");
    const { qc } = renderPanel(up.doc_id);
    // The panel's own poller watches the first attempt fail.
    for (let i = 0; i < 4 && !within(document.body).queryByText("Ingest failed"); i++) {
      await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS + 50));
    }
    await waitFor(() => expect(within(card(1)).getByText("Ingest failed")).toBeInTheDocument());
    expect(await screen.findByRole("button", { name: "Approve step 1" })).toBeDisabled();

    const inval = vi.spyOn(qc, "invalidateQueries");
    fireEvent.click(screen.getByRole("button", { name: "Retry ingest" }));
    await waitFor(() => expect(live()).toBe("Ingest retry queued for v1."));
    expect(spy).toHaveBeenCalledWith(up.job_id);
    await waitFor(() => expect(within(card(1)).queryByText("Ingest failed")).toBeNull());
    for (let i = 0; i < 4 && !within(document.body).queryByText("Ingested"); i++) {
      await act(() => vi.advanceTimersByTimeAsync(INGEST_POLL_MS + 50));
    }
    await waitFor(() => expect(within(card(1)).getByText("Ingested")).toBeInTheDocument());
    await waitFor(() => expect(screen.getByRole("button", { name: "Approve step 1" })).toBeEnabled());
    const keys = inval.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey));
    expect(keys).toContain(JSON.stringify(qk.clauses(up.doc_id)));
    expect(keys).toContain(JSON.stringify(qk.document(up.doc_id)));
  });

  it("cancelling the request retires the version", async () => {
    const up = await twoVersionDoc();
    const spy = vi.spyOn(mockApi.company, "cancelApprovalRequest");
    renderPanel(FIXTURE_DOC);
    fireEvent.click(await screen.findByRole("button", { name: "Cancel request" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, cancel request" }));
    await waitFor(() => expect(within(card(2)).getByText("Retired")).toBeInTheDocument());
    expect(screen.getByText("Approval · Cancelled")).toBeInTheDocument();
    expect(spy).toHaveBeenCalledWith(up.approval_request_id, { acting_person_id: "P05" });
    expect(live()).toBe("Approval request cancelled. v2 is retired.");
    expect(screen.queryByRole("button", { name: /Approve step/ })).toBeNull();
    expect(card(1)).toHaveAttribute("aria-current", "true");
  });

  it("prompts for an acting person when none is chosen and disables signing", async () => {
    act(() => setActingPersonId(null));
    await mockApi.company.uploadVersion(FIXTURE_DOC, file("v2.docx"), { acting_person_id: "P05" });
    renderPanel(FIXTURE_DOC);
    const prompt = await waitFor(() => {
      const p = document.querySelector<HTMLElement>("[data-actor-prompt]");
      if (!p) throw new Error("no prompt");
      return p;
    });
    expect(within(prompt).getByText("Choose who you are acting as")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Approve step 1" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Reject…" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Cancel request" })).toBeDisabled();
    const sel = within(prompt).getByLabelText("Act as");
    await waitFor(() => expect(within(sel).getByText(/David Okafor/)).toBeInTheDocument());
    fireEvent.change(sel, { target: { value: "P05" } });
    await waitFor(() => expect(document.querySelector("[data-actor-prompt]")).toBeNull());
    expect(screen.getByRole("button", { name: "Reject…" })).toBeEnabled();
  });

  it("shows a not-found state when the document is unknown", async () => {
    renderPanel("NOPE-404");
    expect(await screen.findByText("We could not find this document's versions.")).toBeInTheDocument();
  });
});

describe("VersionHistoryButton", () => {
  it("opens the drawer from the reader header icon", async () => {
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const spy = vi.spyOn(mockApi.company, "listVersions");
    render(
      <QueryClientProvider client={qc}>
        <TooltipProvider>
          <VersionHistoryButton docId={FIXTURE_DOC} />
        </TooltipProvider>
      </QueryClientProvider>,
    );
    expect(spy).not.toHaveBeenCalled(); // nothing fetched until opened
    fireEvent.click(screen.getByRole("button", { name: "Version history" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Version history")).toBeInTheDocument();
    await waitFor(() => expect(dialog.querySelectorAll("[data-version]")).toHaveLength(1));
  });
});

describe("errorMessage", () => {
  it("maps 403/409/404 to the server detail with guidance", () => {
    expect(errorMessage(new ApiError(403, "P01 does not hold role 'approver' on D"), "approve", "approver")).toMatch(
      /P01 does not hold role 'approver' on D.*approver role/,
    );
    expect(errorMessage(new ApiError(409, "cannot approve: the version's ingest job has not succeeded"), "approve")).toContain(
      "ingest job has not succeeded",
    );
    expect(errorMessage(new ApiError(409, "approval request is cancelled, not open"), "cancel")).toContain("not open");
    expect(errorMessage(new ApiError(404, "approval request not found"), "approve")).toBe("Not found: approval request not found.");
    expect(errorMessage(new MissingActorError(), "assign")).toMatch(/acting as/);
  });
});

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockApi, setMockLatency } from "@/tests/support/mock-api";
import { MOCK_DUPLICATE_DOC_ID, MOCK_MESSAGES, resetCompanyMock } from "@/tests/support/mock-api/company";
import { fixtures } from "@/tests/support/mock-api/fixtures";
import { UploadDocumentDialog, UploadVersionDialog } from "@/components/documents/upload";
import {
  MAX_UPLOAD_BYTES,
  UPLOAD_MESSAGES,
  buildRegisterSpec,
  columnOptions,
  duplicateTitle,
  fileProblem,
  isUploadTarget,
  parseCsvHeader,
  titleFromFilename,
  uploadableVerticals,
} from "@/components/documents/upload/logic";
import { ApiError } from "@/lib/api/http/shared";
import { resetActorStoreForTests, setActingPersonId } from "@/lib/actor";
import { UNCLASSIFIED_SLUG } from "@/lib/verticals";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(""),
  usePathname: () => "/app/documents",
}));

const VERTICAL = "operations-processes";
const DOC = "RPL-CMP-REG-001";
const docx = (name: string) => new File(["x"], name, { type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" });

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

// applyAccept: false simulates the OS picker's "All files" option, which ignores `accept`.
const user = () => userEvent.setup({ applyAccept: false });

async function openDialog(u: ReturnType<typeof user>, name: RegExp) {
  await u.click(screen.getByRole("button", { name }));
  return screen.findByRole("dialog");
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
  vi.restoreAllMocks();
  setMockLatency(true);
});

describe("upload logic", () => {
  it("blocks PDFs and non-docx, routes CSVs to the register mode, enforces 25 MB", () => {
    expect(fileProblem({ name: "Policy.pdf", size: 10 }, "docx")).toBe("Only .docx documents are supported. PDF is not yet available.");
    expect(fileProblem({ name: "Policy.PDF", size: 10 }, "register")).toBe(UPLOAD_MESSAGES.pdf);
    expect(fileProblem({ name: "notes.txt", size: 10 }, "docx")).toBe(UPLOAD_MESSAGES.notDocx);
    expect(fileProblem({ name: "reg.csv", size: 10 }, "docx")).toBe(UPLOAD_MESSAGES.csvInDocxMode);
    expect(fileProblem({ name: "reg.docx", size: 10 }, "register")).toBe(UPLOAD_MESSAGES.notCsv);
    expect(fileProblem({ name: "a.docx", size: MAX_UPLOAD_BYTES + 1 }, "docx")).toBe(UPLOAD_MESSAGES.tooLarge);
    expect(fileProblem({ name: "a.docx", size: MAX_UPLOAD_BYTES }, "docx")).toBeNull();
    expect(fileProblem({ name: "a.csv", size: 5 }, "register")).toBeNull();
  });

  it("parses the CSV header (BOM, quotes, embedded commas) and builds the spec", () => {
    expect(parseCsvHeader('﻿obligation_id,"Text, full","say ""hi"""\r\nA,b,c')).toEqual(["obligation_id", "Text, full", 'say "hi"']);
    expect(() => parseCsvHeader("")).toThrow(/empty/);
    expect(() => parseCsvHeader(",,\nA,B,C")).toThrow(/header row/);
    expect(columnOptions(["a", "", "a", "b"])).toEqual(["a", "b"]);
    expect(buildRegisterSpec("", "id")).toBeNull();
    expect(buildRegisterSpec("obligation", "")).toBeNull();
    expect(buildRegisterSpec("obligation", "obligation_id")).toEqual({ register_type: "obligation", id_column: "obligation_id" });
  });

  it("titles default to the file stem; duplicate messages yield the holder's title", () => {
    expect(titleFromFilename("Outage Response.v2.docx")).toBe("Outage Response.v2");
    expect(duplicateTitle("This document is already in the system as 'Ethics Register'.")).toBe("Ethics Register");
    expect(duplicateTitle("something else")).toBeNull();
  });

  it("never targets unclassified, but every one of the 14 verticals is a target", () => {
    expect(isUploadTarget(UNCLASSIFIED_SLUG)).toBe(false);
    expect(isUploadTarget("financial-reporting")).toBe(true);
    expect(isUploadTarget("not-a-vertical")).toBe(false);
    expect(isUploadTarget(VERTICAL)).toBe(true);
    expect(uploadableVerticals().map((v) => v.slug)).not.toContain(UNCLASSIFIED_SLUG);
  });
});

describe("UploadDocumentDialog", () => {
  it("renders nothing for unclassified or an unknown vertical", () => {
    const { container } = wrap(
      <>
        <UploadDocumentDialog vertical={UNCLASSIFIED_SLUG} />
        <UploadDocumentDialog vertical="not-a-vertical" variant="inline" />
      </>,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("board entry point asks for a vertical and never offers unclassified", async () => {
    const u = user();
    wrap(<UploadDocumentDialog />);
    const dialog = await openDialog(u, /^upload$/i);
    const select = within(dialog).getByLabelText("Vertical") as HTMLSelectElement;
    const values = [...select.options].map((o) => o.value);
    expect(values).not.toContain(UNCLASSIFIED_SLUG);
    expect(values).toContain("financial-reporting");
    // the empty "Choose a vertical" placeholder plus exactly the 14 real verticals
    expect(values.filter((v) => v !== "")).toHaveLength(14);
    expect(values).toContain(VERTICAL);
    // Submitting without a vertical is refused client-side.
    const spy = vi.spyOn(mockApi.company, "uploadDocument");
    await u.upload(within(dialog).getByLabelText("File"), docx("Outage.docx"));
    await u.click(within(dialog).getByRole("button", { name: "Upload" }));
    expect(within(dialog).getByText("Choose the vertical this document belongs to.")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("created: uploads, shows queued → running → succeeded progress, then links the new document", async () => {
    const u = user();
    const spy = vi.spyOn(mockApi.company, "uploadDocument");
    wrap(<UploadDocumentDialog vertical={VERTICAL} />);
    const dialog = await openDialog(u, /^upload$/i);
    expect(within(dialog).getByText(/Filed under/)).toHaveTextContent("Operations & Processes");
    await u.upload(within(dialog).getByLabelText("File"), docx("Outage Response.docx"));
    expect(within(dialog).getByLabelText("Title")).toHaveValue("Outage Response"); // defaults to the filename
    await u.type(within(dialog).getByLabelText(/Document number/), "OPS-099");
    await u.click(within(dialog).getByRole("button", { name: "Upload" }));

    await waitFor(() => expect(dialog.querySelector("[data-job-state]")).not.toBeNull());
    expect(spy).toHaveBeenCalledTimes(1);
    const [vertical, file, meta] = spy.mock.calls[0];
    expect(vertical).toBe(VERTICAL);
    expect((file as File).name).toBe("Outage Response.docx");
    expect(meta).toMatchObject({ title: "Outage Response", doc_number: "OPS-099", acting_person_id: "P05" });
    expect(meta?.register_spec).toBeUndefined();

    await waitFor(() => expect(dialog.querySelector("[data-job-state]")?.getAttribute("data-job-state")).toBe("running"));
    await waitFor(() => expect(dialog.querySelector("[data-job-state]")?.getAttribute("data-job-state")).toBe("succeeded"), { timeout: 5000 });
    const status = within(dialog).getAllByRole("status").find((n) => n.textContent?.includes("Processed"));
    expect(status).toBeTruthy();
    const link = within(dialog).getByRole("link", { name: "Open Outage Response" });
    const docs = await mockApi.company.listDocuments();
    const created = docs.find((d) => d.title === "Outage Response");
    expect(created?.doc_number).toBe("OPS-099");
    expect(link.getAttribute("href")).toBe(`/app/documents/${created?.doc_id}`);
  });

  it("duplicate: says where it already lives, links it, and creates nothing", async () => {
    const u = user();
    const before = (await mockApi.company.listDocuments()).length;
    wrap(<UploadDocumentDialog vertical={VERTICAL} />);
    const dialog = await openDialog(u, /^upload$/i);
    await u.upload(within(dialog).getByLabelText("File"), docx("copy-duplicate.docx"));
    await u.click(within(dialog).getByRole("button", { name: "Upload" }));
    const holder = fixtures().documents.find((d) => d.doc_id === MOCK_DUPLICATE_DOC_ID)!;
    const result = await within(dialog).findByText(/Already in the system as/);
    expect(result).toHaveTextContent(`Already in the system as ${holder.title}.`);
    expect(within(dialog).getByRole("link", { name: `Open ${holder.title}` })).toHaveAttribute("href", `/app/documents/${MOCK_DUPLICATE_DOC_ID}`);
    expect(dialog.querySelector("[data-job-state]")).toBeNull();
    expect((await mockApi.company.listDocuments()).length).toBe(before);
  });

  it("duplicate with a null doc_id shows the message without a link", async () => {
    const u = user();
    vi.spyOn(mockApi.company, "uploadDocument").mockResolvedValue({
      kind: "duplicate",
      message: "This document is already in the system as 'Old Policy'.",
      doc_id: null,
    });
    wrap(<UploadDocumentDialog vertical={VERTICAL} />);
    const dialog = await openDialog(u, /^upload$/i);
    await u.upload(within(dialog).getByLabelText("File"), docx("x-duplicate.docx"));
    await u.click(within(dialog).getByRole("button", { name: "Upload" }));
    await within(dialog).findByText(/Already in the system as/);
    expect(within(dialog).queryByRole("link")).toBeNull();
  });

  it("blocks a PDF client-side with a clear message and sends nothing", async () => {
    const u = user();
    const spy = vi.spyOn(mockApi.company, "uploadDocument");
    wrap(<UploadDocumentDialog vertical={VERTICAL} />);
    const dialog = await openDialog(u, /^upload$/i);
    const input = within(dialog).getByLabelText("File") as HTMLInputElement;
    expect(input.accept).toContain(".docx");
    expect(input.accept).not.toContain(".pdf");
    await u.upload(input, new File(["%PDF"], "Policy.pdf", { type: "application/pdf" }));
    expect(within(dialog).getByText("Only .docx documents are supported. PDF is not yet available.")).toBeInTheDocument();
    expect(input).toHaveAttribute("aria-invalid", "true");
    await u.click(within(dialog).getByRole("button", { name: "Upload" }));
    expect(within(dialog).getByText("Choose a file to upload.")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
  });

  it("handles a forced 415 from the server by showing its message", async () => {
    const u = user();
    vi.spyOn(mockApi.company, "uploadDocument").mockRejectedValue(new ApiError(415, MOCK_MESSAGES.unsupported));
    wrap(<UploadDocumentDialog vertical={VERTICAL} />);
    const dialog = await openDialog(u, /^upload$/i);
    await u.upload(within(dialog).getByLabelText("File"), docx("renamed-pdf.docx"));
    await u.click(within(dialog).getByRole("button", { name: "Upload" }));
    const alert = await within(dialog).findByText(MOCK_MESSAGES.unsupported);
    expect(alert.closest("[role=alert]")).not.toBeNull();
    // The form stays open so the user can pick another file.
    expect(within(dialog).getByLabelText("File")).toBeInTheDocument();
  });

  it("empty document: shows the server's 422 message", async () => {
    const u = user();
    wrap(<UploadDocumentDialog vertical={VERTICAL} />);
    const dialog = await openDialog(u, /^upload$/i);
    await u.upload(within(dialog).getByLabelText("File"), docx("empty.docx"));
    await u.click(within(dialog).getByRole("button", { name: "Upload" }));
    expect(await within(dialog).findByText("No extractable text found in this document.")).toBeInTheDocument();
  });

  it("no acting person: prompts to choose one and cannot submit", async () => {
    setActingPersonId(null);
    const u = user();
    const spy = vi.spyOn(mockApi.company, "uploadDocument");
    wrap(<UploadDocumentDialog vertical={VERTICAL} />);
    const dialog = await openDialog(u, /^upload$/i);
    const prompt = within(dialog).getByTestId("actor-prompt");
    expect(prompt).toHaveTextContent("Choose who you are acting as before uploading.");
    expect(within(prompt).getByRole("link", { name: "Acting as" })).toHaveAttribute("href", "#acting-as");
    await u.upload(within(dialog).getByLabelText("File"), docx("Outage.docx"));
    expect(within(dialog).getByRole("button", { name: "Upload" })).toBeDisabled();
    expect(spy).not.toHaveBeenCalled();
  });

  it("register CSV: requires a register type and an id column read from the header", async () => {
    const u = user();
    const spy = vi.spyOn(mockApi.company, "uploadDocument");
    wrap(<UploadDocumentDialog vertical={VERTICAL} />);
    const dialog = await openDialog(u, /^upload$/i);
    // A CSV is refused in document mode.
    await u.upload(within(dialog).getByLabelText("File"), new File(["a,b\n1,2"], "reg.csv", { type: "text/csv" }));
    expect(within(dialog).getByText(UPLOAD_MESSAGES.csvInDocxMode)).toBeInTheDocument();

    await u.click(within(dialog).getByRole("radio", { name: "Register (CSV)" }));
    const input = within(dialog).getByLabelText("File") as HTMLInputElement;
    expect(input.accept).toContain(".csv");
    await u.upload(input, new File(['obligation_id,"Obligation, text",citation\nOB-1,Do it,170 IAC 1'], "Obligations.csv", { type: "text/csv" }));
    const idSelect = within(dialog).getByLabelText("ID column") as HTMLSelectElement;
    await waitFor(() => expect(idSelect).not.toBeDisabled());
    expect([...idSelect.options].map((o) => o.value)).toEqual(["", "obligation_id", "Obligation, text", "citation"]);

    await u.click(within(dialog).getByRole("button", { name: "Upload" }));
    expect(within(dialog).getByText("Choose what the rows of this register are.")).toBeInTheDocument();
    expect(within(dialog).getByText("Choose the column holding each row’s stable ID.")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();

    await u.selectOptions(within(dialog).getByLabelText("Register type"), "obligation");
    await u.selectOptions(idSelect, "obligation_id");
    await u.click(within(dialog).getByRole("button", { name: "Upload" }));
    await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
    expect(spy.mock.calls[0][2]?.register_spec).toEqual({ register_type: "obligation", id_column: "obligation_id" });
    expect(spy.mock.calls[0][2]?.title).toBe("Obligations");
    await waitFor(() => expect(dialog.querySelector("[data-job-state]")).not.toBeNull());
  });

  it("is keyboard operable: labelled controls, Escape closes and returns focus", async () => {
    const u = user();
    wrap(<UploadDocumentDialog vertical={VERTICAL} variant="inline" />);
    const trigger = screen.getByRole("button", { name: "Add a document" });
    trigger.focus();
    await u.keyboard("{Enter}");
    const dialog = await screen.findByRole("dialog", { name: "Upload a document" });
    expect(dialog.contains(document.activeElement)).toBe(true); // focus moved into the dialog (trapped)
    for (const label of ["File", "Title", /Document number/]) expect(within(dialog).getByLabelText(label)).toBeInTheDocument();
    await u.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(document.activeElement).toBe(trigger);
  });
});

describe("UploadVersionDialog", () => {
  it("created: sends change_reason and shows job progress", async () => {
    const u = user();
    const spy = vi.spyOn(mockApi.company, "uploadVersion");
    wrap(<UploadVersionDialog docId={DOC} docTitle="Compliance Register" />);
    const dialog = await openDialog(u, /upload new version/i);
    await u.upload(within(dialog).getByLabelText("File"), docx("Register v2.docx"));
    await u.type(within(dialog).getByLabelText(/Reason for change/), "Annual refresh");
    await u.click(within(dialog).getByRole("button", { name: "Upload version" }));
    await waitFor(() => expect(dialog.querySelector("[data-job-state]")).not.toBeNull());
    expect(spy.mock.calls[0][0]).toBe(DOC);
    expect(spy.mock.calls[0][2]).toMatchObject({ change_reason: "Annual refresh", acting_person_id: "P05" });
  });

  it("unchanged: says nothing changed and writes nothing", async () => {
    const u = user();
    wrap(<UploadVersionDialog docId={DOC} />);
    const dialog = await openDialog(u, /upload new version/i);
    await u.upload(within(dialog).getByLabelText("File"), docx("same-unchanged.docx"));
    await u.click(within(dialog).getByRole("button", { name: "Upload version" }));
    expect(await within(dialog).findByText("No changes compared to the current version.")).toBeInTheDocument();
    expect(dialog.querySelector("[data-job-state]")).toBeNull();
    const versions = await mockApi.company.listVersions(DOC);
    expect(versions?.versions).toHaveLength(1);
  });

  it("retry_available: offers Retry, which restarts the failed job and shows progress to success", async () => {
    const u = user();
    const retry = vi.spyOn(mockApi.company, "retryIngestJob");
    wrap(<UploadVersionDialog docId={DOC} />);
    const dialog = await openDialog(u, /upload new version/i);
    await u.upload(within(dialog).getByLabelText("File"), docx("again-retry.docx"));
    await u.click(within(dialog).getByRole("button", { name: "Upload version" }));
    expect(await within(dialog).findByText(/whose ingest failed/)).toBeInTheDocument();
    await u.click(within(dialog).getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(dialog.querySelector("[data-job-state]")?.getAttribute("data-job-state")).toBe("succeeded"), { timeout: 6000 });
  });

  it("thrown ApiError (404 unknown document) shows its detail", async () => {
    const u = user();
    wrap(<UploadVersionDialog docId="NOPE-1" />);
    const dialog = await openDialog(u, /upload new version/i);
    await u.upload(within(dialog).getByLabelText("File"), docx("v2.docx"));
    await u.click(within(dialog).getByRole("button", { name: "Upload version" }));
    expect(await within(dialog).findByText("document not found")).toBeInTheDocument();
  });

  it("blocks a PDF client-side and requires an actor", async () => {
    setActingPersonId(null);
    const u = user();
    const spy = vi.spyOn(mockApi.company, "uploadVersion");
    wrap(<UploadVersionDialog docId={DOC} />);
    const dialog = await openDialog(u, /upload new version/i);
    expect(within(dialog).getByTestId("actor-prompt")).toBeInTheDocument();
    await u.upload(within(dialog).getByLabelText("File"), new File(["%PDF"], "v2.pdf", { type: "application/pdf" }));
    expect(within(dialog).getByText(UPLOAD_MESSAGES.pdf)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Upload version" })).toBeDisabled();
    expect(spy).not.toHaveBeenCalled();
  });
});

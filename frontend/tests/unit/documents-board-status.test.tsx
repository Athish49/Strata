// Task 8.2: lifecycle board statuses (processing / in review / ingest failed / retired), unclassified grouping.
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, within } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  boardStatus,
  buildRows,
  compareRows,
  docVersionText,
  filterRows,
  groupByVertical,
  normalizeStatus,
  ownerOptions,
  STATUS_ORDER,
} from "@/components/documents/board/logic";
import { VerticalSection } from "@/components/documents/board/VerticalSection";
import { DocCard } from "@/components/documents/board/DocCard";
import { DocStatusPill } from "@/components/documents/board/DocStatusPill";
import type { DocRollup, DocumentMeta } from "@/lib/api/schemas";
import { documentMetaSchema } from "@/lib/api/schemas/company";
import { normalizeDocument } from "@/lib/api/http/company";
import { DOC_STATUS_LABELS, type BoardStatusKey } from "@/lib/labels";
import { documentStatus } from "@/lib/status";
import { VERTICALS } from "@/lib/verticals";
import { resetActorStoreForTests, setActingPersonId } from "@/lib/actor";
import { resetCompanyMock } from "@/tests/support/mock-api/company";
import { mockApi } from "@/tests/support/mock-api";

afterEach(cleanup);
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("run=run_x"),
  usePathname: () => "/app/documents",
}));

const person = { person_id: "P01", name: "Dana Reyes", title: "Director", department: "Legal", reports_to_id: null };
const blankPerson = { person_id: "", name: "", title: "", department: "", reports_to_id: null };
const doc = (over: Partial<DocumentMeta>): DocumentMeta => ({
  doc_id: "RPL-CS-PRO-004",
  title: "Disconnection Procedure",
  version: "3.0",
  status: "approved",
  effective_date: null,
  approved_date: null,
  law_as_of: null,
  next_review: null,
  review_cycle: null,
  vertical: "compliance-ethics",
  owner: person,
  reviewer: person,
  approver: null,
  two_signature: false,
  monitored: true,
  doc_type: "Procedure",
  cited_citations: [],
  ...over,
});
/** A document as GET /company/documents returns it when it has no current version yet. */
const fresh = (over: Partial<DocumentMeta>): DocumentMeta =>
  doc({
    version: "",
    status: "",
    monitored: false,
    owner: blankPerson,
    reviewer: blankPerson,
    // the backend sends approver_id IS NULL, i.e. true, for a document with no roles yet
    two_signature: true,
    has_current_version: false,
    lifecycle_state: "pending",
    latest_version_no: 1,
    latest_version_status: "in_review",
    latest_ingest_status: "pending",
    ...over,
  });
const rollup = (over: Partial<DocRollup>): DocRollup => ({
  run_id: "r",
  doc_id: "RPL-CS-PRO-004",
  status: "flagged",
  counts_by_verdict: { action_required: 2, review: 1 },
  changes_considered: 4,
  considered_by_class: {},
  cleared_reason: null,
  ...over,
});

describe("boardStatus derivation", () => {
  it("parses the real GET /company/documents shape for a new upload and keeps the lifecycle fields", () => {
    const raw = {
      doc_id: "DOC-000042",
      title: "New Upload",
      version: "",
      status: "",
      effective_date: null,
      approved_date: null,
      law_as_of: null,
      next_review: null,
      review_cycle: null,
      vertical: "unclassified",
      vertical_name: null,
      owner: blankPerson,
      reviewer: blankPerson,
      approver: null,
      two_signature: true,
      monitored: false,
      lifecycle_state: "pending",
      has_current_version: false,
      latest_version_no: 1,
      latest_version_status: "in_review",
      latest_ingest_status: "ingested",
      doc_type: "Document",
      doc_number: null,
      cited_citations: [],
    };
    const meta = normalizeDocument(documentMetaSchema.parse(raw));
    expect(meta).toMatchObject({
      lifecycle_state: "pending",
      has_current_version: false,
      latest_version_no: 1,
      latest_version_status: "in_review",
      latest_ingest_status: "ingested",
      vertical: "unclassified",
    });
    expect(boardStatus(meta).key).toBe("in_review");
    expect(boardStatus(normalizeDocument(documentMetaSchema.parse({ ...raw, latest_ingest_status: "pending" }))).key).toBe("processing");
  });

  it.each<[string, Partial<DocumentMeta>, BoardStatusKey]>([
    ["no current version, ingest pending", { latest_ingest_status: "pending" }, "processing"],
    ["no current version, ingest unknown", { latest_ingest_status: null, latest_version_status: null }, "processing"],
    ["no current version, in_review + ingested", { latest_ingest_status: "ingested" }, "in_review"],
    ["no current version, latest ingest failed", { latest_ingest_status: "failed", lifecycle_state: "failed" }, "ingest_failed"],
    [
      "lifecycle failed with no latest version",
      { lifecycle_state: "failed", latest_version_no: null, latest_version_status: null, latest_ingest_status: null },
      "ingest_failed",
    ],
    ["sticky failed lifecycle but healthy v2 in review", { lifecycle_state: "failed", latest_ingest_status: "ingested" }, "in_review"],
    ["sticky failed lifecycle, v2 still processing", { lifecycle_state: "failed", latest_ingest_status: "pending" }, "processing"],
    ["retired (no current version)", { lifecycle_state: "retired" }, "retired"],
  ])("%s", (_, over, key) => {
    const s = boardStatus(fresh(over));
    expect(s.key).toBe(key);
    expect(s.label).toBe(DOC_STATUS_LABELS[key]);
    expect(s.reason).toBeTruthy();
  });

  it("retired wins even when a current version exists", () => {
    expect(boardStatus(doc({ lifecycle_state: "retired", has_current_version: true }), rollup({})).key).toBe("retired");
  });

  it("documents with a current version get exactly the existing four statuses", () => {
    const cases: [Partial<DocumentMeta>, DocRollup | undefined][] = [
      [{}, rollup({})],
      [{}, rollup({ counts_by_verdict: { review: 2 } })],
      [{}, rollup({ status: "cleared", counts_by_verdict: {}, changes_considered: 0 })],
      [{}, undefined],
      [{ monitored: false }, undefined],
      // the new fields, when present with a current version, change nothing (lifecycle failed included)
      [{ has_current_version: true, lifecycle_state: "active", latest_ingest_status: "pending" }, rollup({})],
      [{ has_current_version: true, lifecycle_state: "failed", latest_ingest_status: "failed" }, undefined],
      [{ has_current_version: null }, rollup({})],
    ];
    for (const [over, r] of cases) {
      const meta = doc(over);
      expect(boardStatus(meta, r)).toEqual(documentStatus(meta, r));
    }
    expect(boardStatus(doc({}), rollup({})).key).toBe("action_needed");
    expect(boardStatus(doc({}), rollup({ counts_by_verdict: { review: 2 } })).key).toBe("review");
    expect(boardStatus(doc({}), undefined).key).toBe("cleared");
    expect(boardStatus(doc({ monitored: false }), undefined).key).toBe("not_monitored");
  });

  it("every status has a label and a place in the order", () => {
    expect(STATUS_ORDER).toEqual([
      "action_needed",
      "review",
      "ingest_failed",
      "in_review",
      "processing",
      "cleared",
      "not_monitored",
      "retired",
    ]);
    for (const k of STATUS_ORDER) expect(DOC_STATUS_LABELS[k]).toBeTruthy();
    expect(Object.keys(DOC_STATUS_LABELS).sort()).toEqual([...STATUS_ORDER].sort());
  });

  it("normalises status URL values including aliases for the new states", () => {
    expect(normalizeStatus("in_review")).toBe("in_review");
    expect(normalizeStatus("in-review")).toBe("in_review");
    expect(normalizeStatus("failed")).toBe("ingest_failed");
    expect(normalizeStatus("retired")).toBe("retired");
    expect(normalizeStatus("review")).toBe("review");
  });
});

describe("ordering, grouping and filtering", () => {
  const rows = buildRows(
    [
      doc({ doc_id: "C", title: "Cleared" }),
      doc({ doc_id: "A", title: "Flagged" }),
      fresh({ doc_id: "P", title: "Processing doc" }),
      fresh({ doc_id: "I", title: "In review doc", latest_ingest_status: "ingested" }),
      fresh({ doc_id: "F", title: "Failed doc", lifecycle_state: "failed", latest_ingest_status: "failed" }),
      fresh({ doc_id: "R", title: "Retired doc", lifecycle_state: "retired" }),
      doc({ doc_id: "S", title: "Sample", monitored: false }),
      fresh({ doc_id: "U", title: "Unclassified upload", vertical: "unclassified", latest_ingest_status: "ingested" }),
    ],
    [rollup({ doc_id: "A" }), rollup({ doc_id: "C", status: "cleared", counts_by_verdict: {}, changes_considered: 0 })],
  );

  it("sorts needs-action first, then failed, in review, processing, cleared, not monitored, retired", () => {
    const sorted = [...rows].filter((r) => r.meta.vertical === "compliance-ethics").sort(compareRows);
    expect(sorted.map((r) => r.meta.doc_id)).toEqual(["A", "F", "I", "P", "C", "S", "R"]);
  });

  it("lifecycle rows are never pending on rollups and become cards, not sample rows", () => {
    const pendingRows = buildRows([fresh({ doc_id: "P" }), doc({ doc_id: "M" })], undefined, true);
    expect(pendingRows.find((r) => r.meta.doc_id === "P")?.pending).toBe(false);
    expect(pendingRows.find((r) => r.meta.doc_id === "M")?.pending).toBe(true);

    const g = groupByVertical(filterRows(rows, {})).find((group) => group.vertical.slug === "compliance-ethics")!;
    expect(g.cards.map((r) => r.meta.doc_id)).toEqual(["A", "F", "I", "P", "C"]);
    expect(g.samples.map((r) => r.meta.doc_id)).toEqual(["S"]);
  });

  it("groups an unclassified document into a trailing Unclassified group", () => {
    const g = groupByVertical(rows);
    expect(g).toHaveLength(15);
    expect(g.slice(0, 14).map((x) => x.vertical.slug)).toEqual(VERTICALS.map((v) => v.slug));
    expect(g[14].vertical.slug).toBe("unclassified");
    expect(g[14].vertical.name).toBe("Unclassified");
    expect(g[14].rows.map((r) => r.meta.doc_id)).toEqual(["U"]);
    // without unclassified documents the board keeps its 14 groups
    expect(groupByVertical(rows.filter((r) => r.meta.vertical !== "unclassified"))).toHaveLength(14);
  });

  it("filters to the unclassified group by vertical", () => {
    expect(filterRows(rows, { vertical: "unclassified" }).map((r) => r.meta.doc_id)).toEqual(["U"]);
  });

  it("hides retired documents unless the status filter asks for them", () => {
    expect(filterRows(rows, {}).some((r) => r.meta.doc_id === "R")).toBe(false);
    expect(filterRows(rows, { status: "retired" }).map((r) => r.meta.doc_id)).toEqual(["R"]);
    expect(filterRows(rows, { status: "processing" }).map((r) => r.meta.doc_id)).toEqual(["P"]);
  });

  it("drops blank owners from the owner filter", () => {
    expect(ownerOptions(rows.map((r) => r.meta))).toEqual([{ id: "P01", name: "Dana Reyes" }]);
  });

  it("degrades the version text when there is no current version", () => {
    expect(docVersionText(doc({}), "cleared")).toBe("v3.0");
    expect(docVersionText(fresh({}), "processing")).toBe("v1 · Awaiting approval");
    expect(docVersionText(fresh({ latest_version_no: null }), "in_review")).toBe("Awaiting approval");
    expect(docVersionText(fresh({}), "ingest_failed")).toBe("v1");
    expect(docVersionText(fresh({ latest_version_no: null }), "retired")).toBe("—");
  });
});

describe("lifecycle cards and pills", () => {
  it.each<[BoardStatusKey, Partial<DocumentMeta>]>([
    ["processing", {}],
    ["in_review", { latest_ingest_status: "ingested" }],
    ["ingest_failed", { lifecycle_state: "failed", latest_ingest_status: "failed" }],
    ["retired", { lifecycle_state: "retired" }],
  ])("renders a %s card with a pill, a link and no blank cells", (key, over) => {
    const [row] = buildRows([fresh({ doc_id: "DOC-000042", title: "New Upload", ...over })], undefined);
    expect(row.status.key).toBe(key);
    const { container } = render(
      <TooltipProvider>
        <DocCard row={row} />
      </TooltipProvider>,
    );
    const card = container.querySelector("article")!;
    const pill = card.querySelector(`[data-status="${key}"]`);
    expect(pill?.textContent).toBe(DOC_STATUS_LABELS[key]);
    expect(pill?.querySelector("svg")).toBeTruthy();
    expect(within(card).getByRole("link", { name: "New Upload" }).getAttribute("href")).toContain("/app/documents/DOC-000042");
    expect(within(card).getByText("Unassigned")).toBeTruthy();
    expect(within(card).getByText(row.status.reason!)).toBeTruthy();
    const idLine = within(card).getByText("DOC-000042").parentElement!;
    expect(idLine.textContent).not.toMatch(/·\s*$/);
    expect(idLine.textContent).toContain("v1");
    // no empty text-bearing elements
    for (const el of card.querySelectorAll("p, span")) {
      if (el.querySelector("svg") || el.getAttribute("aria-hidden")) continue;
      expect(el.textContent?.trim(), el.outerHTML).not.toBe("");
    }
  });

  it("keeps the in-review pill visibly distinct from review and cleared", () => {
    render(
      <>
        <DocStatusPill status="in_review" />
        <DocStatusPill status="review" />
        <DocStatusPill status="cleared" />
      </>,
    );
    const cls = (t: string) => screen.getByText(t).className;
    expect(cls("In review")).not.toBe(cls("Review"));
    expect(cls("In review")).not.toBe(cls("Cleared"));
  });

  it("renders the existing four pills exactly as before", () => {
    const { container } = render(
      <>
        <DocStatusPill status="action_needed" />
        <DocStatusPill status="review" />
        <DocStatusPill status="cleared" />
        <DocStatusPill status="not_monitored" />
      </>,
    );
    const pills = [...container.querySelectorAll("[data-status]")];
    expect(pills.map((p) => p.textContent)).toEqual(["Action needed", "Review", "Cleared", "Not monitored"]);
    expect(pills[0].className).toContain("--red-soft");
    expect(pills[1].className).toContain("--amber-soft");
    expect(pills[2].className).toContain("--green-soft");
    expect(pills[3].className).toContain("bg-surface-muted");
  });

  it("renders an Unclassified section with its documents and an unlinked header", () => {
    const rows = buildRows([fresh({ doc_id: "DOC-000007", title: "Loose Doc", vertical: "unclassified" })], undefined);
    const group = groupByVertical(rows).find((g) => g.vertical.slug === "unclassified")!;
    render(
      <TooltipProvider>
        <VerticalSection group={group} />
      </TooltipProvider>,
    );
    const heading = screen.getByRole("heading", { name: "Unclassified" });
    expect(heading.closest("a")).toBeNull();
    expect(screen.getByRole("link", { name: "Loose Doc" })).toBeTruthy();
    expect(screen.getByText("Processing")).toBeTruthy();
    expect(screen.queryByText("Not monitored")).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// Mock-driven lifecycle: the board states a real upload passes through
// ---------------------------------------------------------------------------
describe("board status follows a mock upload through its lifecycle", () => {
  async function advanceJob(jobId: string, until: "succeeded" | "failed") {
    // each poll moves the mock job one state forward: queued -> running -> final
    for (let i = 0; i < 4; i++) {
      const j = await mockApi.company.getIngestJob(jobId);
      if (j?.job.state === until) return;
    }
    throw new Error(`job never reached ${until}`);
  }

  it("Processing -> In review once ingested (not Cleared / Not monitored)", async () => {
    resetCompanyMock();
    setActingPersonId("P01");
    const up = await mockApi.company.uploadDocument("operations-quality", new File(["x"], "Outage.docx"));
    if (up.kind !== "created") throw new Error("expected created");

    expect(boardStatus((await mockApi.company.getDocument(up.doc_id))!).key).toBe("processing");
    await advanceJob(up.job_id, "succeeded");
    const doc = (await mockApi.company.getDocument(up.doc_id))!;
    expect(boardStatus(doc).key).toBe("in_review");
    // `monitored` describes the CURRENT version; nothing is current until approval promotes it.
    expect(doc.monitored).toBe(false);
    expect(doc.has_current_version).toBe(false);
  });

  it("a failed first ingest shows Ingest failed", async () => {
    resetCompanyMock();
    setActingPersonId("P01");
    const up = await mockApi.company.uploadDocument("operations-quality", new File(["x"], "will-fail.docx"));
    if (up.kind !== "created") throw new Error("expected created");
    await advanceJob(up.job_id, "failed");
    expect(boardStatus((await mockApi.company.getDocument(up.doc_id))!).key).toBe("ingest_failed");
  });
});

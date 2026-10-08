import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { buildRows, filterRows, groupByVertical, verdictSegments } from "@/components/documents/board/logic";
import { VerticalSection } from "@/components/documents/board/VerticalSection";
import { VerdictMiniBar } from "@/components/documents/board/VerdictMiniBar";
import { DocStatusPill } from "@/components/documents/board/DocStatusPill";
import type { DocRollup, DocumentMeta } from "@/lib/api/schemas";
import { VERTICALS } from "@/lib/verticals";

afterEach(cleanup);
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("run=run_x"),
  usePathname: () => "/app/documents",
}));

const person = { person_id: "P01", name: "Dana Reyes", title: "Director", department: "Legal", reports_to_id: null };
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
  vertical: "compliance-legal",
  owner: person,
  reviewer: person,
  approver: null,
  two_signature: false,
  monitored: true,
  doc_type: "Procedure",
  cited_citations: [],
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

describe("board logic", () => {
  const docs = [
    doc({ doc_id: "B", title: "Cleared doc" }),
    doc({ doc_id: "A", title: "Flagged doc" }),
    doc({ doc_id: "S", title: "Sample", vertical: "financial-reporting", monitored: false }),
  ];
  const rows = buildRows(docs, [rollup({ doc_id: "A" }), rollup({ doc_id: "B", status: "cleared", counts_by_verdict: {}, changes_considered: 0 })]);

  it("derives statuses per §11.5 and sorts needs-action first", () => {
    const g = groupByVertical(rows);
    expect(g).toHaveLength(14);
    expect(g.map((x) => x.vertical.slug)).toEqual(VERTICALS.map((v) => v.slug));
    const cl = g[0];
    expect(cl.rows.map((r) => r.meta.doc_id)).toEqual(["A", "B"]);
    expect(cl.rows[0].status.key).toBe("action_needed");
    expect(cl.rows[1].status.reason).toBe("No cited section changed");
    expect(cl.needsAction).toBe(1);
    expect(g[2].samples).toHaveLength(1);
    expect(g[2].rows[0].status.key).toBe("not_monitored");
    expect(g[3].rows).toHaveLength(0);
  });

  it("treats a run without rollups as cleared with the no-candidates reason", () => {
    const r = buildRows([doc({})], []);
    expect(r[0].status.key).toBe("cleared");
    expect(r[0].status.reason).toBe("No cited section changed");
  });

  it("filters by status, vertical and owner", () => {
    expect(filterRows(rows, { status: "action_needed" })).toHaveLength(1);
    expect(filterRows(rows, { vertical: "financial-reporting" })).toHaveLength(1);
    expect(filterRows(rows, { owner: "P99" })).toHaveLength(0);
  });

  it("orders verdict segments worst first and drops zeros", () => {
    expect(verdictSegments({ review: 1, action_required: 2, info: 0 }).map((s) => s.verdict)).toEqual(["action_required", "review"]);
  });
});

describe("board components", () => {
  it("renders a section with a card linking to the reader and sample rows without a link", () => {
    const rows = buildRows(
      [doc({ doc_id: "RPL-CS-PRO-004" }), doc({ doc_id: "S-1", title: "Sample SOP", monitored: false })],
      [rollup({})],
    );
    const group = groupByVertical(rows)[0];
    render(
      <TooltipProvider>
        <VerticalSection group={group} />
      </TooltipProvider>,
    );
    expect(screen.getByRole("link", { name: "Disconnection Procedure" }).getAttribute("href")).toContain("/app/documents/RPL-CS-PRO-004");
    expect(screen.queryByRole("link", { name: "Sample SOP" })).toBeNull();
    expect(screen.getByText("Not monitored")).toBeTruthy();
    expect(screen.getByText("Action needed")).toBeTruthy();
    expect(screen.getByText(/1 needs attention/)).toBeTruthy();
  });

  it("renders an empty vertical with a disabled add cue", () => {
    render(
      <TooltipProvider>
        <VerticalSection group={groupByVertical([])[3]} />
      </TooltipProvider>,
    );
    expect(screen.getByText(/No documents are filed under Revenue & Pricing yet/)).toBeTruthy();
    expect(screen.getByText(/Add a document/).closest("button")?.getAttribute("aria-disabled")).toBe("true");
  });

  it("mini bar and pill render text, nothing for no findings", () => {
    const { container } = render(<VerdictMiniBar counts={{}} />);
    expect(container.innerHTML).toBe("");
    render(<VerdictMiniBar counts={{ action_required: 2 }} />);
    expect(screen.getByText(/action required/i)).toBeTruthy();
    render(<DocStatusPill status="cleared" />);
    expect(screen.getByText("Cleared")).toBeTruthy();
  });
});

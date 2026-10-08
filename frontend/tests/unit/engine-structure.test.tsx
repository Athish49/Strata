import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  FunnelBar,
  LedgerList,
  MatrixGrid,
  Minimap,
  StageStepper,
  TimelineStrip,
  TraceChain,
  defaultTraceHref,
  stageStates,
  type LedgerRow,
} from "@/components/engine";
import type { ChangeRecord, DocumentMeta, MatrixCell } from "@/lib/api/schemas";

afterEach(cleanup);

const wrap = (ui: ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);

describe("TraceChain", () => {
  const nodes = [
    { kind: "section" as const, ref: "170 IAC 4-1-16", label: "170 IAC 4-1-16(e)" },
    { kind: "register_row" as const, ref: "RPL-CMP-REG-001:OBL-2024-0036", label: "OBL-2024-0036" },
    { kind: "form_field" as const, ref: "RPL-CS-PRO-004:App-A.F6", label: "Notice letter field App-A.F6" },
    { kind: "rule" as const, ref: "170 IAC 4-1", label: "170 IAC 4-1" },
  ];
  it("renders one linked node per path_detail entry, except where no route exists", () => {
    render(<TraceChain nodes={nodes} />);
    expect(screen.getAllByRole("listitem")).toHaveLength(4);
    expect(screen.getByRole("link", { name: /170 IAC 4-1-16\(e\)/ })).toHaveAttribute("href", expect.stringContaining("/app/regulations/sections/iac/"));
    expect(screen.getByRole("link", { name: /App-A.F6/ })).toHaveAttribute("href", expect.stringContaining("/app/documents/RPL-CS-PRO-004?clause="));
    expect(screen.getAllByRole("link")).toHaveLength(3);
    expect(screen.getByText("Fix once, fix everywhere.")).toBeInTheDocument();
  });
  it("shows the propagated-from link", () => {
    const onOpen = vi.fn();
    render(<TraceChain nodes={nodes} propagatedFrom={{ label: "row OBL-1", onOpen }} />);
    fireEvent.click(screen.getByRole("button", { name: "row OBL-1" }));
    expect(onOpen).toHaveBeenCalled();
  });
  it("routes CFR sections and ignores bare refs", () => {
    expect(defaultTraceHref({ kind: "section", ref: "18 CFR 35.28", label: "x" })).toContain("/cfr/");
    expect(defaultTraceHref({ kind: "clause", ref: "nocolon", label: "x" })).toBeNull();
  });
  it("renders with no nodes", () => {
    render(<TraceChain nodes={[]} />);
    expect(screen.queryByRole("list")).toBeNull();
  });
});

describe("Minimap", () => {
  it("positions ticks, clamps, and emits clicks", () => {
    const onTickClick = vi.fn();
    render(
      <Minimap
        ticks={[
          { id: "a", position: 0.5, token: "action_required", label: "§1 — Action required" },
          { id: "b", position: 4, token: "review", label: "§2 — Needs review" },
        ]}
        onTickClick={onTickClick}
        activeId="a"
      />,
    );
    const a = screen.getByRole("button", { name: "§1 — Action required" });
    expect(a).toHaveStyle({ top: "calc(50% - 6px)" });
    expect(screen.getByRole("button", { name: "§2 — Needs review" })).toHaveStyle({ top: "calc(100% - 6px)" });
    fireEvent.click(a);
    expect(onTickClick).toHaveBeenCalledWith("a");
  });
});

describe("FunnelBar", () => {
  it("fills proportionally and shows the count", () => {
    render(<FunnelBar label="Substantive" count={491} max={1114} suffix="substantive" />);
    expect(screen.getByText("491")).toBeInTheDocument();
    expect(parseFloat(screen.getByTestId("funnel-fill").style.width)).toBeCloseTo((491 / 1114) * 100, 1);
  });
  it("handles zero and a zero max", () => {
    const { rerender } = render(<FunnelBar label="Findings" count={0} max={1114} />);
    expect(screen.getByTestId("funnel-fill").style.width).toBe("0%");
    rerender(<FunnelBar label="Findings" count={5} max={0} />);
    expect(screen.getByTestId("funnel-fill").style.width).toBe("0%");
  });
  it("is a link when href is given", () => {
    render(<FunnelBar label="In footprint" count={8} max={100} href="/app/changes?touches=1" />);
    expect(screen.getByRole("link")).toHaveAttribute("href", expect.stringContaining("/app/changes"));
  });
});

describe("StageStepper", () => {
  it("derives stage states", () => {
    expect(stageStates("queued")).toEqual(["pending", "pending", "pending", "pending", "pending"]);
    expect(stageStates("succeeded")).toEqual(["done", "done", "done", "done", "done"]);
    expect(stageStates("running", { stage: "candidates", done: 3, total: 10, message: "" })).toEqual(["done", "done", "running", "pending", "pending"]);
    expect(stageStates("failed", { stage: "judge", done: 1, total: 4, message: "" })[3]).toBe("failed");
  });
  it("shows counts for a known total", () => {
    render(<StageStepper status="running" progress={{ stage: "judge", done: 3, total: 12, message: "Judging clause pairs" }} stageCounts={{ delta: 1114 }} />);
    expect(screen.getByText("3 of 12")).toBeInTheDocument();
    expect(screen.getByText("1,114")).toBeInTheDocument();
    expect(screen.getByText("Judging clause pairs")).toBeInTheDocument();
    expect(screen.queryByRole("status")).toBeNull();
  });
  it("is indeterminate when progress is null or total is 0", () => {
    const { rerender } = render(<StageStepper status="running" progress={null} />);
    expect(screen.getByRole("status")).toHaveTextContent("Starting");
    rerender(<StageStepper status="running" progress={{ stage: "delta", done: 0, total: 0, message: "" }} />);
    expect(screen.getByRole("status")).toHaveTextContent("Working");
    expect(screen.queryByText(/ of /)).toBeNull();
  });
  it("shows the error when failed", () => {
    render(<StageStepper status="failed" progress={{ stage: "judge", done: 1, total: 4, message: "" }} error="Model unavailable" />);
    expect(screen.getByText("Model unavailable")).toBeInTheDocument();
  });
});

describe("TimelineStrip", () => {
  it("formats dates and tolerates nulls", () => {
    render(
      <TimelineStrip
        points={[
          { key: "a", label: "Rule published", date: "2025-02-20" },
          { key: "b", label: "Document approved", date: null },
        ]}
        caption="This document was approved on 14 Mar 2025, after the rule change was published on 19 Feb 2025."
      />,
    );
    expect(screen.getByText("Feb 20, 2025")).toBeInTheDocument();
    expect(screen.getByText("Not recorded")).toBeInTheDocument();
    expect(screen.getByText(/after the rule change was published/)).toBeInTheDocument();
  });
});

describe("LedgerList", () => {
  const row = (id: string, verdict: LedgerRow["verdict"], extra: Partial<LedgerRow> = {}): LedgerRow => ({
    id,
    clauseId: `RPL-CS-PRO-004:${id}`,
    docId: "RPL-CS-PRO-004",
    matchPath: "direct_section",
    reason: `reason ${id}`,
    verdict,
    ...extra,
  });
  it("groups findings worst first and collapses cleared", () => {
    const onOpen = vi.fn();
    wrap(
      <LedgerList
        findings={[row("1", "info"), row("2", "action_required"), row("3", "action_required")]}
        cleared={[row("c1", "cleared", { href: "/app/documents/RPL-CS-PRO-004?clause=c1" })]}
        onOpenFinding={onOpen}
      />,
    );
    const headings = screen.getAllByRole("heading", { level: 4 }).map((h) => h.textContent);
    expect(headings[0]).toContain("Action required");
    expect(headings[0]).toContain("2 clauses");
    expect(headings[1]).toContain("Info");
    expect(screen.queryByText("reason c1")).toBeNull();
    fireEvent.click(screen.getByText("reason 2"));
    expect(onOpen).toHaveBeenCalledWith(expect.objectContaining({ id: "2" }));
    fireEvent.click(screen.getByRole("button", { name: /Cleared \(1\)/ }));
    expect(screen.getByText("reason c1").closest("a")).toHaveAttribute("href", expect.stringContaining("clause=c1"));
  });
  it("paginates long cleared groups and handles empty", () => {
    const many = Array.from({ length: 94 }, (_, i) => row(`c${i}`, "cleared"));
    const { unmount } = wrap(<LedgerList findings={[]} cleared={many} defaultClearedOpen pageSize={50} />);
    expect(screen.getByRole("button", { name: /Cleared \(94\)/ })).toBeInTheDocument();
    expect(screen.getAllByText(/^reason c/)).toHaveLength(50);
    fireEvent.click(screen.getByRole("button", { name: /Show 44 more/ }));
    expect(screen.getAllByText(/^reason c/)).toHaveLength(94);
    unmount();
    wrap(<LedgerList findings={[]} cleared={[]} />);
    expect(screen.getByText(/No clause was checked/)).toBeInTheDocument();
  });
});

describe("MatrixGrid", () => {
  const person = { person_id: "P", name: "N", title: "T", department: "D", reports_to_id: null };
  const doc = (id: string, vertical: string): DocumentMeta =>
    ({ doc_id: id, title: `Title ${id}`, vertical, owner: person, reviewer: person, approver: null, two_signature: false, monitored: true }) as unknown as DocumentMeta;
  const change = (id: string, citation: string): ChangeRecord =>
    ({ change_id: id, citation, heading: `Heading ${id}`, change_class: "cosmetic", cited_clause_count: 3 }) as unknown as ChangeRecord;
  const docs = [doc("D1", "compliance-legal"), doc("D2", "policy-governance")];
  const changes = [change("c1", "170 IAC 4-1-16"), change("c2", "170 IAC 4-1-17")];
  const cells: MatrixCell[] = [
    { doc_id: "D1", change_id: "c1", worst_verdict: "action_required", n_findings: 2, n_cleared: 1 },
    { doc_id: "D2", change_id: "c1", worst_verdict: "cleared", n_findings: 0, n_cleared: 4 },
  ];
  it("renders groups, dots, checks and empty cells with headers and labels", () => {
    const { container } = wrap(<MatrixGrid docs={docs} changes={changes} cells={cells} />);
    expect(screen.getByText("Compliance & Legal")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "170 IAC 4-1-16, Heading c1" })).toBeInTheDocument();
    expect(container.querySelectorAll("[data-cell]")).toHaveLength(2);
    expect(container.querySelectorAll('td[data-empty="true"]')).toHaveLength(2);
    expect(screen.getByRole("button", { name: /Title D2, 170 IAC 4-1-16: 4 clauses checked and cleared/ })).toBeInTheDocument();
  });
  it("emits onCellClick and opens the popover", () => {
    const onCellClick = vi.fn();
    wrap(<MatrixGrid docs={docs} changes={changes} cells={cells} onCellClick={onCellClick} renderCellPopover={(i) => <div>detail for {i.doc.doc_id}</div>} />);
    fireEvent.click(screen.getByRole("button", { name: /Title D1, 170 IAC 4-1-16: 2 findings/ }));
    expect(onCellClick).toHaveBeenCalledWith(expect.objectContaining({ cell: cells[0] }));
    expect(screen.getByText("detail for D1")).toBeInTheDocument();
  });
  it("shows an empty message with no columns", () => {
    wrap(<MatrixGrid docs={docs} changes={[]} cells={[]} />);
    expect(screen.getByText("No changed sections to show.")).toBeInTheDocument();
  });
});

import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import type { ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { Annotation, Clause } from "@/lib/api/schemas";
import { ClauseRenderer } from "@/components/documents/reader/ClauseRenderer";
import { DocumentReader } from "@/components/documents/reader/DocumentReader";
import { FindingsRail } from "@/components/documents/reader/FindingsRail";
import { ReaderHeader, rollupSentence } from "@/components/documents/reader/ReaderHeader";
import { buildReaderModel, notesByClause, notesFor, railFindings, clearedClauses } from "@/components/documents/reader/model";
import { documentStatus } from "@/lib/status";
import { setMockLatency } from "@/tests/support/mock-api";

afterEach(cleanup);
beforeAll(() => setMockLatency(false));

const clause = (id: string, ordinal: number, over: Partial<Clause> = {}): Clause => ({
  clause_id: `D:${id}`,
  doc_id: "D",
  ordinal,
  heading_path: ["1. Purpose"],
  unit_kind: "section",
  text_raw: `**${id}** Notices must be sent within 10 business days.`,
  row_cells: null,
  parent_clause_id: null,
  ...over,
});
const ann = (clause_id: string, over: Partial<Annotation> = {}): Annotation => ({
  clause_id,
  kind: "cleared",
  verdict: null,
  finding_id: null,
  change_id: "ch1",
  citation: "170 IAC 1-1",
  quote_span: null,
  reason: "Checked: no impact — cosmetic change to 170 IAC 1-1.",
  ...over,
});

function wrap(ui: ReactNode, searchParams = "") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter searchParams={searchParams}>
        <TooltipProvider>{ui}</TooltipProvider>
      </NuqsTestingAdapter>
    </QueryClientProvider>,
  );
}

function renderItems(clauses: Clause[], annotations: Annotation[], extra: Partial<React.ComponentProps<typeof ClauseRenderer>> = {}) {
  const notes = notesByClause(annotations);
  const model = buildReaderModel(clauses, notes, "D");
  return render(
    <TooltipProvider>
      {model.items.map((item) => {
        const id = item.kind === "clause" || item.kind === "table-row" ? item.clause.clause_id : "";
        return <ClauseRenderer key={item.key} item={item} notes={notesFor(notes, id)} sentences={new Map()} {...extra} />;
      })}
    </TooltipProvider>,
  );
}

describe("ClauseRenderer", () => {
  it("highlights the exact quote span in the verdict token and marks the clause", () => {
    const c = clause("8.2", 1);
    const span: [number, number] = [c.text_raw.indexOf("10 business days"), c.text_raw.indexOf("10 business days") + 16];
    renderItems([c], [ann(c.clause_id, { kind: "finding", verdict: "action_required", finding_id: "f1", quote_span: span, reason: "R" })]);
    const mark = document.querySelector("mark[data-quote-highlight]");
    expect(mark?.textContent).toBe("10 business days");
    expect(mark?.className).toContain("verdict-action-required");
    expect(mark?.getAttribute("aria-describedby")).toBeTruthy();
    expect(document.getElementById(mark?.getAttribute("aria-describedby") ?? "")).not.toBeNull();
    expect(document.querySelector('[data-clause-state="finding"]')).not.toBeNull();
    // markdown bold markers never leak into the text
    expect(document.body.textContent).not.toContain("**");
  });

  it("marks a finding with a null span without highlighting anything", () => {
    const c = clause("8.2", 1);
    renderItems([c], [ann(c.clause_id, { kind: "finding", verdict: "review", finding_id: "f1", quote_span: null })]);
    expect(document.querySelector("mark")).toBeNull();
    expect(document.querySelector('[data-clause-state="finding"]')).not.toBeNull();
    expect(screen.getByText("Needs review")).toBeInTheDocument();
  });

  it("aggregates many cleared annotations into one marker with expandable reasons", () => {
    const c = clause("3.1", 1);
    const anns = Array.from({ length: 6 }, (_, i) => ann(c.clause_id, { change_id: `ch${i}`, reason: `Reason number ${i}` }));
    const onToggle = vi.fn();
    const { rerender } = renderItems([c], anns, { onToggleCleared: onToggle });
    const markers = document.querySelectorAll("[data-cleared-marker]");
    expect(markers).toHaveLength(1);
    expect(markers[0].getAttribute("aria-label")).toBe("Checked against 6 changes, no impact");
    expect(screen.queryByText("Reason number 0")).toBeNull();
    fireEvent.click(markers[0]);
    expect(onToggle).toHaveBeenCalledWith(c.clause_id);
    // open state: panel lists reasons, 4 first
    const notes = notesByClause(anns);
    const model = buildReaderModel([c], notes, "D");
    rerender(
      <TooltipProvider>
        <ClauseRenderer item={model.items[model.items.length - 1]} notes={notesFor(notes, c.clause_id)} sentences={new Map()} clearedOpen />
      </TooltipProvider>,
    );
    expect(screen.getByText("Checked against 6 changes, no impact", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("Reason number 0")).toBeInTheDocument();
    expect(screen.queryByText("Reason number 5")).toBeNull();
    fireEvent.click(screen.getByText("Show all 6"));
    expect(screen.getByText("Reason number 5")).toBeInTheDocument();
  });

  it("uses the single reason as the marker tooltip when cleared against one change", () => {
    const c = clause("3.1", 1);
    renderItems([c], [ann(c.clause_id)]);
    expect(document.querySelector("[data-cleared-marker]")?.getAttribute("title")).toBe("Checked: no impact — cosmetic change to 170 IAC 1-1.");
  });

  it("renders register rows as a table with a header and expandable fields, highlighting inside the cell", () => {
    const cells = { id: "R1", citation: "170 IAC 1-1", title: "T", description: "Use 30-day procedures", a: "1", b: "2", c: "3", frequency: "continuous" };
    const text = Object.entries(cells).map(([k, v]) => `${k}: ${v}`).join("\n");
    const c = clause("R1", 1, { unit_kind: "register_row", heading_path: ["Reg"], row_cells: cells, text_raw: text });
    const start = text.indexOf("30-day");
    renderItems([c], [ann(c.clause_id, { kind: "finding", verdict: "action_required", finding_id: "f", quote_span: [start, start + 6] })], { rowExpanded: true });
    expect(screen.getByRole("columnheader", { name: "Citation" })).toBeInTheDocument();
    expect(document.querySelector("mark")?.textContent).toBe("30-day");
    // expanded: hidden columns appear in the details list
    expect(screen.getByText("Frequency")).toBeInTheDocument();
  });

  it("renders form fields as a labelled form block and tariff sub-rules with a rule label", () => {
    const form = clause("App-A.F1", 1, {
      unit_kind: "form_field",
      heading_path: ["Appendices", "App-A — Notice"],
      text_raw: "**PART A**\n\n| Field | |\n|---|---|\n| **A.F1 — Account Number** | _________ |\n",
    });
    const tariff = clause("R01.D01", 2, { unit_kind: "tariff_subrule", heading_path: ["Sheets 5–11 — Rule 1"], text_raw: "**1.2 — Applicant.** Any person." });
    renderItems([form, tariff], []);
    expect(document.querySelector("[data-form-block]")).not.toBeNull();
    expect(screen.getByText("Appendix / Form")).toBeInTheDocument();
    expect(screen.getByText("A.F1 — Account Number")).toBeInTheDocument();
    expect(screen.getByText("Rule R01.D01")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "App-A — Notice" })).toBeInTheDocument();
  });

  it("renders empty clauses as headings, never blank rows", () => {
    renderItems([clause("1", 1, { heading_path: ["Table of Contents"], text_raw: "" })], []);
    expect(screen.getByRole("heading", { name: "Table of Contents" })).toBeInTheDocument();
    expect(document.querySelector("[data-clause]")).toBeNull();
  });
});

describe("FindingsRail", () => {
  const clauses = [clause("1", 1), clause("2", 2), clause("3", 3)];
  const annotations = [
    ann("D:1", { kind: "finding", verdict: "action_required", finding_id: "f1", reason: "First finding" }),
    ann("D:2", { kind: "finding", verdict: "review", finding_id: "f2", reason: "Second finding" }),
    ann("D:3"),
    ann("D:3", { change_id: "x" }),
  ];
  const notes = notesByClause(annotations);

  it("lists findings in order with verdict, clause id and citation, and a collapsed Cleared group", () => {
    const onSelect = vi.fn();
    render(
      <FindingsRail
        findings={railFindings(clauses, annotations)}
        sentences={new Map([["f1", "§1 states 10 days; 170 IAC 1-1 now requires 14 days."]])}
        activeId="f2"
        onSelect={onSelect}
        cleared={clearedClauses(clauses, notes)}
      />,
    );
    const items = screen.getAllByRole("button", { name: /RPL|1|2/ }).filter((b) => b.hasAttribute("data-finding-id"));
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Action required");
    expect(items[0]).toHaveTextContent("§1 states 10 days");
    expect(items[1]).toHaveAttribute("aria-current", "true");
    expect(items[1]).toHaveTextContent("Second finding");
    fireEvent.click(items[0]);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ findingId: "f1" }));
    const toggle = screen.getByRole("button", { name: /Cleared \(1\)/ });
    expect(toggle).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(toggle);
    expect(screen.getByText("2 changes")).toBeInTheDocument();
  });

  it("explains an empty rail", () => {
    render(<FindingsRail findings={[]} sentences={new Map()} activeId={null} onSelect={() => {}} cleared={[]} />);
    expect(screen.getByText(/No clause in this document is out of line/)).toBeInTheDocument();
  });
});

function makeScroller(height = 800) {
  const el = document.createElement("div");
  Object.defineProperty(el, "offsetHeight", { value: height });
  Object.defineProperty(el, "offsetWidth", { value: 1000 });
  Object.defineProperty(el, "clientHeight", { value: height });
  document.body.appendChild(el);
  return el;
}

describe("DocumentReader", () => {
  beforeAll(() => {
    // jsdom has no layout: give virtual rows a fixed measured height.
    Object.defineProperty(HTMLElement.prototype, "offsetHeight", {
      configurable: true,
      get(this: HTMLElement) {
        return this.hasAttribute("data-index") ? 80 : 0;
      },
    });
  });
  const clauses = Array.from({ length: 12 }, (_, i) => clause(`${i + 1}`, i + 1, { heading_path: [i < 6 ? "1. Purpose" : "2. Scope"] }));
  const annotations = [
    ann("D:2", { kind: "finding", verdict: "action_required", finding_id: "f2", reason: "Finding two" }),
    ann("D:9", { kind: "finding", verdict: "review", finding_id: "f9", reason: "Finding nine" }),
    ann("D:4"),
  ];

  it("renders the document, a minimap tick per finding and a keyboard-navigable rail", async () => {
    const scroller = makeScroller();
    wrap(<DocumentReader docId="D" clauses={clauses} annotations={annotations} scrollElement={scroller} overscan={100} />);
    expect(await screen.findByRole("heading", { name: "2. Scope" })).toBeInTheDocument();
    const ticks = within(screen.getByRole("group", { name: "Findings minimap" })).getAllByRole("button");
    expect(ticks).toHaveLength(2);
    // j / k move the selection through findings
    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() => expect(document.querySelector('[data-finding-id="f2"]')).toHaveAttribute("aria-current", "true"));
    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() => expect(document.querySelector('[data-finding-id="f9"]')).toHaveAttribute("aria-current", "true"));
    fireEvent.keyDown(window, { key: "k" });
    await waitFor(() => expect(document.querySelector('[data-finding-id="f2"]')).toHaveAttribute("aria-current", "true"));
    // Esc clears the selection
    fireEvent.keyDown(window, { key: "Escape" });
    await waitFor(() => expect(document.querySelector('[data-finding-id="f2"]')).not.toHaveAttribute("aria-current"));
    scroller.remove();
  });

  it("opens the evidence drawer for the selected finding on Enter and ignores keys while typing", async () => {
    const scroller = makeScroller();
    wrap(<DocumentReader docId="D" clauses={clauses} annotations={annotations} scrollElement={scroller} overscan={100} />);
    await screen.findByRole("heading", { name: "2. Scope" });
    const input = document.createElement("input");
    document.body.appendChild(input);
    fireEvent.keyDown(input, { key: "j" });
    expect(document.querySelector("[aria-current='true'][data-finding-id]")).toBeNull();
    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() => expect(document.querySelector('[data-finding-id="f2"]')).toHaveAttribute("aria-current", "true"));
    fireEvent.keyDown(window, { key: "Enter" });
    await waitFor(() => expect(screen.getByRole("dialog")).toBeInTheDocument());
    input.remove();
    scroller.remove();
  });

  it("windows long documents instead of rendering every clause", () => {
    const many = Array.from({ length: 400 }, (_, i) => clause(`${i + 1}`, i + 1));
    const scroller = makeScroller();
    wrap(<DocumentReader docId="D" clauses={many} annotations={[]} scrollElement={scroller} />);
    expect(document.querySelectorAll("[data-clause]").length).toBeLessThan(60);
    scroller.remove();
  });
});

describe("ReaderHeader", () => {
  it("builds the rollup sentence for flagged and cleared documents", () => {
    const flagged = {
      run_id: "r",
      doc_id: "D",
      status: "flagged" as const,
      counts_by_verdict: { action_required: 3, review: 3, optional_relaxed: 0, update_citation: 0, info: 0 },
      changes_considered: 31,
      considered_by_class: {},
      reviewed: 0,
    };
    const meta = { monitored: true } as never;
    const st = documentStatus(meta, flagged);
    expect(st.label).toBe("Action needed");
    expect(rollupSentence(st, flagged)).toBe("3 action required, 3 needs review from 31 changes considered. 0 of 6 reviewed.");
    const clearedRollup = { ...flagged, status: "cleared" as const, counts_by_verdict: {}, changes_considered: 12, considered_by_class: { cosmetic: 5 } };
    const st2 = documentStatus(meta, clearedRollup);
    expect(rollupSentence(st2, clearedRollup)).toContain("12 changes considered");
  });

  it("shows a skeleton while loading and no raw ids or 'null'", () => {
    wrap(<ReaderHeader doc={undefined} loading />);
    expect(document.body.textContent).not.toMatch(/null|undefined/);
  });
});

describe("DocumentReader with mock fixtures (what-if preset A on RPL-CS-PRO-004)", () => {
  it("shows findings in the rail and one finding on a form field rendered as a letter", async () => {
    const { mockApi } = await import("@/tests/support/mock-api");
    const reader = await mockApi.engine.getReader("RPL-CS-PRO-004", "run_whatif_preset_a");
    expect(reader).not.toBeNull();
    const findings = railFindings(reader!.clauses, reader!.annotations);
    expect(findings.length).toBeGreaterThan(0);
    const formFinding = findings.find((f) => f.clause.unit_kind === "form_field");
    expect(formFinding).toBeDefined();
    const scroller = makeScroller(100000);
    wrap(<DocumentReader docId="RPL-CS-PRO-004" clauses={reader!.clauses} annotations={reader!.annotations} scrollElement={scroller} overscan={1000} />);
    await waitFor(() => expect(document.querySelector("[data-form-block]")).not.toBeNull());
    expect(document.querySelectorAll("[data-finding-id]").length).toBe(findings.length);
    expect(within(screen.getByRole("group", { name: "Findings minimap" })).getAllByRole("button")).toHaveLength(findings.length);
    expect(document.body.textContent).not.toMatch(/\bnull\b|\bundefined\b|\*\*/);
    scroller.remove();
  });
});

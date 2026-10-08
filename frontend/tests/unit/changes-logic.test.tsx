import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { ChangeRecord } from "@/lib/api/schemas";
import { ChangeTree } from "@/components/changes/ChangeTree";
import { buildLedger } from "@/components/changes/ChangeDetail";
import { applyFilters, buildTree, DEFAULT_FILTERS, dispositionLabel, noiseBanner, pathToChange, topCited } from "@/components/changes/logic";

afterEach(cleanup);

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("run=r1"),
  usePathname: () => "/app/changes",
}));

const mk = (i: number, over: Partial<ChangeRecord> = {}): ChangeRecord => ({
  change_id: `c${i}`,
  citation: `170 IAC 4-1-${i}`,
  heading: `Heading ${i}`,
  source_system: "iac",
  rule_key: "170 IAC 4-1",
  agency_id: "iurc",
  title_number: "170",
  change_class: "substantive",
  diff_segments: [],
  s1_text: "",
  s2_text: "",
  published_date: "2025-02-19",
  date_basis: "din_publication",
  s1_snapshot: "2024-12-31",
  s2_snapshot: "2025-12-31",
  in_footprint: true,
  cited_clause_count: i,
  characterization: null,
  disposition: null,
  disposition_reason: null,
  ...over,
});

describe("change filters and tree", () => {
  const data = [
    mk(1),
    mk(2, { change_class: "cosmetic" }),
    mk(3, { in_footprint: false }),
    mk(4, { change_class: "new_section", agency_id: "ferc", title_number: "18", rule_key: "18 CFR 35" }),
  ];
  it("defaults to in-footprint real changes only; noise and class chips widen", () => {
    expect(applyFilters(data, DEFAULT_FILTERS).map((c) => c.change_id)).toEqual(["c1", "c4"]);
    expect(applyFilters(data, { ...DEFAULT_FILTERS, sub: false }).map((c) => c.change_id)).toEqual(["c1", "c4"]);
    expect(applyFilters(data, { ...DEFAULT_FILTERS, sub: false, noise: true }).length).toBe(3);
    expect(applyFilters(data, { ...DEFAULT_FILTERS, rpl: false, cls: ["cosmetic"] }).map((c) => c.change_id)).toEqual(["c2"]);
    expect(applyFilters(data, { ...DEFAULT_FILTERS, q: "heading 1" }).map((c) => c.change_id)).toEqual(["c1"]);
  });
  it("groups agency > rule and puts noise classes in a separate collapsed block", () => {
    const tree = buildTree(applyFilters(data, { ...DEFAULT_FILTERS, sub: false, noise: true }), (a) => a.toUpperCase());
    expect(tree.map((g) => g.label)).toEqual(["FERC", "IURC", "Noise removed"]);
    expect(tree[1].groups[0].label).toBe("170 IAC 4-1");
    expect(tree[2].groups[0].kind).toBe("noise-class");
    expect([...pathToChange(tree, "c2")]).toContain("noise");
  });
  it("lists the most cited non-noise changes and labels dispositions", () => {
    expect(topCited(data, 2).map((c) => c.change_id)).toEqual(["c4", "c3"]);
    expect(dispositionLabel(null)).toBe("No disposition recorded");
    expect(dispositionLabel("findings_emitted")).toBe("Findings emitted");
    expect(noiseBanner("cosmetic")).toMatch(/readoption stamp/);
    expect(noiseBanner("substantive")).toBeNull();
  });
});

describe("ChangeTree rendering", () => {
  it("renders only paged rows for a huge noise set and a reset on empty results", () => {
    const many = Array.from({ length: 1500 }, (_, i) => mk(i + 1, { change_class: "cosmetic", rule_key: "170 IAC 4-1" }));
    const onFilters = vi.fn();
    render(
      <TooltipProvider>
        <ChangeTree
          changes={many}
          filters={{ ...DEFAULT_FILTERS, sub: false, noise: true }}
          onFilters={onFilters}
          selectedId={null}
          hrefFor={(id) => `/app/changes/${id}?run=r1`}
        />
      </TooltipProvider>,
    );
    // Noise block is collapsed by default: nothing but the group header.
    expect(screen.queryAllByRole("treeitem").length).toBe(1);
    fireEvent.click(screen.getByText("Noise removed"));
    fireEvent.click(screen.getByText("Cosmetic", { selector: "span" }));
    fireEvent.click(screen.getByText("170 IAC 4-1", { selector: "span" }));
    const rows = screen.getAllByRole("treeitem").filter((e) => e.tagName === "A");
    expect(rows.length).toBe(40);
    expect(rows[0]).toHaveAttribute("href", expect.stringContaining("?run=r1"));
    expect(screen.getByText(/Show more \(1,460 sections remaining\)/)).toBeInTheDocument();
  });
  it("shows the empty state with a reset when filters hide everything", () => {
    const onFilters = vi.fn();
    render(
      <TooltipProvider>
        <ChangeTree changes={[mk(1, { in_footprint: false })]} filters={DEFAULT_FILTERS} onFilters={onFilters} selectedId={null} hrefFor={(id) => id} />
      </TooltipProvider>,
    );
    expect(screen.getByText("No changes match these filters")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Reset filters"));
    expect(onFilters).toHaveBeenCalled();
  });
});

describe("buildLedger", () => {
  const change = { change_class: "cosmetic" as const, citation: "170 IAC 1-2-1", characterization: null };
  it("separates findings from cleared rows and gives every cleared row a reason and a reader link", () => {
    const cands = [
      { candidate_id: "k1", run_id: "r", change_id: "c", clause_id: "DOC-1:2", doc_id: "DOC-1", match_path: "direct_section", path_detail: [], outcome: "cleared", skip_reason: null, rationale: null, finding_id: null },
      { candidate_id: "k2", run_id: "r", change_id: "c", clause_id: "DOC-1:3", doc_id: "DOC-1", match_path: "direct_rule", path_detail: [], outcome: "affected", finding_id: "f1" },
    ] as const;
    const finding = {
      finding_id: "f1", verdict: "action_required", citation: "170 IAC 1-2-1", finding_type: "x", rationale: "Because.",
      required_change: { from_text: "10 days", to_text: "14 days" },
    };
    const out = buildLedger(change, cands as never, [finding] as never);
    expect(out.findings).toHaveLength(1);
    expect(out.findings[0].id).toBe("f1");
    expect(out.findings[0].reason).toContain("10 days");
    expect(out.cleared[0].reason).toBe("Checked: no impact — cosmetic change to 170 IAC 1-2-1.");
    expect(out.cleared[0].href).toBe("/app/documents/DOC-1?clause=DOC-1%3A2");
  });
});

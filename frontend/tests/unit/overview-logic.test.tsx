import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Funnel } from "@/components/overview/Funnel";
import { Tiles } from "@/components/overview/Tiles";
import { findingLine } from "@/components/overview/Attention";
import { newestBaseline } from "@/components/overview/TrustPage";
import { noiseSplit, topFindings, totalFindings, verdictCounts } from "@/components/overview/logic";
import type { Finding, Run } from "@/lib/api/schemas";

afterEach(cleanup);

const stats: Run["stats"] = {
  changes_raw: 1114,
  by_class: { cosmetic: 1004, punctuation_only: 1, cross_ref_only: 10, substantive: 63 },
  substantive: 99,
  noise: 1015,
  in_footprint: 96,
  in_footprint_real: 9,
  obligation_changed: 9,
  candidates_by_path: {},
  findings_by_verdict: { action_required: 4, review: 3 },
  clauses_cleared: 718,
  docs_flagged: 2,
  docs_cleared: 10,
  radar: { applicable: 20, screened_out: 53, unclear: 17 },
  decided_by: { rule: 0, ai: 411 },
  llm_calls: 0,
};

const f = (o: Partial<Finding>): Finding =>
  ({
    finding_id: "x", clause_id: "D:7.2", doc_id: "D", citation: "170 IAC 4-1-16", finding_type: "t", verdict: "review", severity: "low",
    required_change: { from_text: "10 days", to_text: "14 days" }, rationale: "Because. More.", path_detail: [], ...o,
  }) as Finding;

describe("overview logic", () => {
  it("sums findings and splits noise", () => {
    expect(totalFindings(stats)).toBe(7);
    expect(noiseSplit(stats.by_class).map((n) => n.count)).toEqual([1004, 10, 1]);
    expect(verdictCounts(stats.findings_by_verdict)).toHaveLength(2);
  });
  it("orders by severity then verdict, max 7", () => {
    const list = [f({ finding_id: "a", severity: "low", verdict: "action_required" }), f({ finding_id: "b", severity: "high", verdict: "review" }), f({ finding_id: "c", severity: "high", verdict: "action_required" })];
    expect(topFindings(list).map((x) => x.finding_id)).toEqual(["c", "b", "a"]);
    expect(topFindings(Array.from({ length: 12 }, (_, i) => f({ finding_id: String(i) })))).toHaveLength(7);
  });
  it("uses rationale when required_change is a paragraph", () => {
    const long = "x".repeat(100);
    const text = findingLine(f({ required_change: { from_text: long, to_text: long } })).map((s) => s.text).join("");
    expect(text).toContain("Because.");
    expect(text).not.toContain("xxxx");
  });
  it("picks the newest baseline run", () => {
    const r = (id: string, at: string, kind: Run["kind"]) => ({ run_id: id, started_at: at, kind }) as Run;
    expect(newestBaseline([r("a", "2026-01-01", "baseline"), r("b", "2026-02-01", "baseline"), r("c", "2026-03-01", "kb")])?.run_id).toBe("b");
    expect(newestBaseline([])).toBeNull();
  });
});

describe("overview components", () => {
  it("funnel shows run.stats numbers and the cleared figure", () => {
    render(<TooltipProvider><Funnel stats={stats} /></TooltipProvider>);
    for (const n of ["1,114", "99", "1,015", "9", "87", "7", "718"]) expect(screen.getAllByText(n).length).toBeGreaterThan(0);
    expect(screen.getByText(/checked and cleared/)).toBeInTheDocument();
    expect(screen.getByText("Real changes in your documents' rules")).toBeInTheDocument();
    expect(screen.getByText(/noise changes also touched your documents/)).toBeInTheDocument();
    expect(screen.queryByText("96")).toBeNull();
  });
  it("trust tile shows document agreement from the score", () => {
    const score = { precision: 0, recall: 0, fp_rate_must_not_flag: 0, routing_accuracy: 0, baseline_findings: 0, doc_agreement: { agree: 12, total: 12 } } as never;
    render(<TooltipProvider><Tiles stats={stats} score={score} /></TooltipProvider>);
    expect(screen.getByText("12 of 12 documents correct")).toBeInTheDocument();
  });
  it("trust tile shows Not scored for a null score", () => {
    render(<TooltipProvider><Tiles stats={stats} score={null} /></TooltipProvider>);
    expect(screen.getByText("Not scored")).toBeInTheDocument();
    expect(screen.queryByText("null")).toBeNull();
  });
});

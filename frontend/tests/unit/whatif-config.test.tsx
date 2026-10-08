import { describe, expect, it } from "vitest";
import { resolveCustomWhatIf } from "@/components/whatif/config";
import { hasChanges, previewSegments } from "@/components/whatif/diff";
import { filterSections } from "@/components/whatif/StudioSidebar";
import { stageCountsFor, runSummary } from "@/components/whatif/RunPanel";
import type { Run } from "@/lib/api/schemas";

describe("custom what-if flag", () => {
  it("is blocked unless explicitly enabled", () => {
    expect(resolveCustomWhatIf(undefined)).toBe(false);
    expect(resolveCustomWhatIf("")).toBe(false);
    expect(resolveCustomWhatIf("0")).toBe(false);
  });
  it("=1 or true enables", () => {
    expect(resolveCustomWhatIf("1")).toBe(true);
    expect(resolveCustomWhatIf("true")).toBe(true);
  });
});

describe("preview diff (jsdiff)", () => {
  it("marks inserted and deleted words and merges runs", () => {
    const segs = previewSegments("notice within 10 days", "notice within 14 days");
    expect(hasChanges(segs)).toBe(true);
    expect(segs.map((s) => s.op)).toEqual(["equal", "delete", "insert", "equal"]);
    expect(segs.map((s) => s.text).join("")).toContain("14");
    expect(segs.filter((s) => s.op !== "insert").map((s) => s.text).join("")).toBe("notice within 10 days");
  });
  it("reports no change for identical text", () => {
    expect(hasChanges(previewSegments("same", "same"))).toBe(false);
    expect(previewSegments("", "")).toEqual([]);
  });
});

describe("section filter", () => {
  const rows = [
    { citation: "170 IAC 1-1-1", source_system: "iac" as const, heading: "Scope", cited_clause_count: 2 },
    { citation: "170 IAC 4-1-16", source_system: "iac" as const, heading: "Disconnection", cited_clause_count: 90 },
  ];
  it("sorts by cited clauses and searches citation or heading", () => {
    expect(filterSections(rows, "").map((r) => r.citation)[0]).toBe("170 IAC 4-1-16");
    expect(filterSections(rows, "scope")).toHaveLength(1);
    expect(filterSections(rows, "4-1-16")).toHaveLength(1);
    expect(filterSections(rows, "zzz")).toHaveLength(0);
  });
});

describe("run summary", () => {
  const run = {
    run_id: "r",
    kind: "whatif",
    title: "t",
    status: "succeeded",
    started_at: "2025-01-01",
    finished_at: "2025-01-01",
    progress: null,
    stats: {
      changes_raw: 1,
      by_class: {},
      substantive: 1,
      noise: 0,
      in_footprint: 1,
      obligation_changed: 1,
      candidates_by_path: { direct_section: 4, value_echo: 1 },
      findings_by_verdict: { action_required: 2 },
      clauses_cleared: 1,
      docs_flagged: 1,
      docs_cleared: 2,
      radar: { applicable: 0, screened_out: 0, unclear: 0 },
      decided_by: { rule: 1, ai: 1 },
      llm_calls: 0,
    },
  } as unknown as Run;
  it("builds plain sentences and stage counts", () => {
    expect(runSummary(run)).toBe("2 findings across 1 document; 1 clause checked and cleared.");
    expect(stageCountsFor(run)?.candidates).toBe("5 candidate clauses");
    expect(stageCountsFor({ ...run, status: "running" })).toBeUndefined();
  });
});

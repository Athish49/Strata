import { describe, expect, it } from "vitest";
import {
  clauseLabel,
  clearedReason,
  docClearedLine,
  findingSentence,
  findingSentenceSegments,
  localClauseId,
} from "@/lib/sentences";

const finding = {
  verdict: "action_required" as const,
  citation: "170 IAC 4-1-16",
  finding_type: "tightened",
  rationale: "Fallback rationale",
  required_change: { from_text: "30 days", to_text: "15 days" },
};

describe("clauseLabel", () => {
  it("labels each unit kind", () => {
    expect(clauseLabel({ clause_id: "d1:4.2", doc_id: "d1", unit_kind: "section" })).toBe("§4.2");
    expect(clauseLabel({ clause_id: "§4.2", unit_kind: "section" })).toBe("§4.2");
    expect(clauseLabel({ clause_id: "d1:R-12", doc_id: "d1", unit_kind: "register_row" })).toBe("row R-12");
    expect(clauseLabel({ clause_id: "d1:r3", doc_id: "d1", unit_kind: "table_row" })).toBe("row r3");
    expect(clauseLabel({ clause_id: "d1:f1", doc_id: "d1", unit_kind: "form_field", heading_path: ["Form", "Meter class"] })).toBe("field Meter class");
    expect(clauseLabel({ clause_id: "d1:3.1", doc_id: "d1", unit_kind: "tariff_subrule" })).toBe("rule 3.1");
  });
  it("localClauseId strips doc prefix only when something remains", () => {
    expect(localClauseId({ clause_id: "doc-1/4.2", doc_id: "doc-1" })).toBe("4.2");
    expect(localClauseId({ clause_id: "doc-1", doc_id: "doc-1" })).toBe("doc-1");
  });
});

describe("findingSentence", () => {
  it("standard", () => {
    expect(findingSentence(finding, "§4.2")).toBe("§4.2 states 30 days; 170 IAC 4-1-16 now requires 15 days.");
  });
  it("structured marks key values strong", () => {
    const segs = findingSentenceSegments(finding, "§4.2");
    expect(segs.filter((s) => s.strong).map((s) => s.text)).toEqual(["§4.2", "30 days", "170 IAC 4-1-16", "15 days"]);
  });
  it("repeal", () => {
    expect(findingSentence(finding, "§4.2", { change_class: "repealed" })).toBe(
      "§4.2 relies on 170 IAC 4-1-16, which was repealed.",
    );
  });
  it("update_citation", () => {
    const f = { ...finding, verdict: "update_citation" as const, required_change: { from_text: "170 IAC 4-1-16", to_text: "170 IAC 4-1-17" } };
    expect(findingSentence(f, "row R-1")).toBe("row R-1 cites 170 IAC 4-1-16; the rule is now 170 IAC 4-1-17.");
  });
  it("falls back to summary then rationale", () => {
    const f = { ...finding, required_change: { from_text: "", to_text: "" } };
    expect(findingSentence(f, "§1", { characterization: { obligation_changed: true, direction: "clarified", summary: "Summary", value_changes: [] } })).toBe("Summary");
    expect(findingSentence(f, "§1")).toBe("Fallback rationale");
  });
});

describe("clearedReason", () => {
  const change = { change_class: "cross_ref_only" as const, citation: "170 IAC 4-1-2" };
  it("default sentence", () => {
    expect(clearedReason({}, change)).toBe("Checked: no impact — cross-reference only change to 170 IAC 4-1-2.");
  });
  it("prefers backend text", () => {
    expect(clearedReason({ skip_reason: "Different tariff class" }, change)).toBe("Different tariff class");
    expect(clearedReason({ skip_reason: null, rationale: "Rationale" }, change)).toBe("Rationale");
  });
});

describe("docClearedLine", () => {
  it("builds from rollup, largest first, skipping zeros", () => {
    expect(docClearedLine({ changes_considered: 12, considered_by_class: { cosmetic: 7, style_only: 5, metadata_only: 0 } })).toBe(
      "12 changes considered: 7 cosmetic, 5 style-only",
    );
  });
  it("singular and none", () => {
    expect(docClearedLine({ changes_considered: 1, considered_by_class: { cosmetic: 1 } })).toBe("1 change considered: 1 cosmetic");
    expect(docClearedLine({ changes_considered: 0, considered_by_class: {} })).toBe("No cited section changed");
    expect(docClearedLine({ changes_considered: 3, considered_by_class: {} })).toBe("3 changes considered");
  });
});

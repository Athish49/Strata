import { describe, expect, it } from "vitest";
import * as L from "@/lib/labels";

describe("labels", () => {
  it("verdict labels per §11.1", () => {
    expect(L.verdictLabel("action_required")).toBe("Action required");
    expect(L.verdictLabel("optional_relaxed")).toBe("Relaxed (optional update)");
    expect(L.verdictLabel("update_citation")).toBe("Update citation");
    expect(L.verdictLabel("review")).toBe("Needs review");
    expect(L.verdictLabel("info")).toBe("Info");
    expect(L.verdictLabel("cleared")).toBe("Cleared");
  });
  it("change class labels, incl. noise", () => {
    expect(L.changeClassLabel("new_section")).toBe("New section");
    expect(L.changeClassLabel("cross_ref_only")).toBe("Cross-reference only");
    expect(L.changeClassLabel("metadata_only")).toBe("Metadata only");
    expect(Object.keys(L.CHANGE_CLASS_LABELS)).toHaveLength(8);
    expect(L.isNoiseClass("cosmetic")).toBe(true);
    expect(L.isNoiseClass("substantive")).toBe(false);
  });
  it("direction labels", () => {
    expect(L.directionLabel("new_requirement")).toBe("New requirement");
    expect(L.directionLabel("style_only")).toBe("Style only");
    expect(Object.keys(L.DIRECTION_LABELS)).toHaveLength(7);
    expect(L.directionLabel("mixed")).toBe("Mixed");
  });
  it("run kind", () => {
    expect(L.runKindLabel({ kind: "kb", title: "x" })).toBe("Real wave · S1→S2");
    expect(L.runKindLabel({ kind: "baseline", title: "x" })).toBe("Baseline · S1 vs S1");
    expect(L.runKindLabel({ kind: "whatif", title: "Repeal 170 IAC 4-1-1" })).toBe("What-if: Repeal 170 IAC 4-1-1");
  });
  it("decided by", () => {
    expect(L.decidedByLabel("rule")).toBe("Decided by rule");
    expect(L.decidedByLabel("ai", 0.82)).toBe("AI judgment · 82%");
    expect(L.decidedByLabel("ai")).toBe("AI judgment");
  });
  it("applicable, severity, streams, doc status", () => {
    expect(L.applicableLabel("yes")).toBe("Possibly applicable");
    expect(L.applicableLabel("no")).toBe("Screened out");
    expect(L.applicableLabel("unclear")).toBe("Unclear");
    expect(L.severityLabel("high")).toBe("High");
    expect(L.streamLabel("federal_register")).toBe("Federal Register");
    expect(L.streamLabel("iurc_gaos")).toBe("Orders");
    expect(L.streamLabel("iurc_investigations")).toBe("Investigations");
    expect(L.streamLabel("iurc_rulemakings")).toBe("Rulemakings");
    expect(L.streamLabel("idem_rulemakings")).toBe("Rulemakings");
    expect(L.streamLabel("some_new_stream")).toBe("Some new stream");
    expect(L.docStatusLabel("action_needed")).toBe("Action needed");
    expect(L.docStatusLabel("review")).toBe("Review");
    expect(L.docStatusLabel("cleared")).toBe("Cleared");
    expect(L.docStatusLabel("not_monitored")).toBe("Not monitored");
  });
  it("match path words", () => {
    expect(L.matchPathWords("direct_section")).toBe("Cites this section directly");
    expect(L.matchPathWords("direct_rule", { ruleKey: "170 IAC 4-1" })).toBe("Cites the parent rule (170 IAC 4-1)");
    expect(L.matchPathWords("register_hop", { ref: "row R-12" })).toBe("Linked through row R-12");
    expect(L.matchPathWords("value_echo", { oldValue: "30 days" })).toBe("Restates the old value (30 days) without citing it");
  });
});

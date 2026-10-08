import { describe, expect, it } from "vitest";
import { documentStatus } from "@/lib/status";

const rollup = (over = {}) => ({
  status: "cleared" as const,
  counts_by_verdict: {},
  changes_considered: 4,
  considered_by_class: { cosmetic: 4 },
  cleared_reason: null,
  ...over,
});

describe("documentStatus", () => {
  it("action needed when flagged with action_required", () => {
    const s = documentStatus({ monitored: true }, rollup({ status: "flagged", counts_by_verdict: { action_required: 1, review: 2 } }));
    expect(s).toMatchObject({ key: "action_needed", label: "Action needed" });
  });
  it("review when flagged without action_required", () => {
    expect(documentStatus({ monitored: true }, rollup({ status: "flagged", counts_by_verdict: { review: 1, action_required: 0 } }))).toMatchObject({
      key: "review",
      label: "Review",
    });
  });
  it("cleared with reasons", () => {
    expect(documentStatus({ monitored: true }, rollup())).toMatchObject({ key: "cleared", label: "Cleared", reason: "4 changes considered: 4 cosmetic" });
    expect(documentStatus({ monitored: true }, rollup({ cleared_reason: "Backend reason" })).reason).toBe("Backend reason");
  });
  it("cleared with 'No cited section changed' when no rollup or no candidates", () => {
    expect(documentStatus({ monitored: true }, undefined)).toMatchObject({ key: "cleared", reason: "No cited section changed" });
    expect(documentStatus({ monitored: true }, rollup({ changes_considered: 0, considered_by_class: {} })).reason).toBe("No cited section changed");
  });
  it("not monitored wins", () => {
    expect(documentStatus({ monitored: false }, rollup({ status: "flagged" }))).toMatchObject({ key: "not_monitored", label: "Not monitored" });
    expect(documentStatus({ monitored: false }, undefined).key).toBe("not_monitored");
  });
});

import { describe, expect, it } from "vitest";
import {
  VERTICALS,
  compareVerticals,
  getVertical,
  isVerticalSlug,
  realVerticals,
  verticalFromBackend,
  verticalName,
} from "@/lib/verticals";

describe("verticals", () => {
  it("has 14 in fixed order with unique slugs", () => {
    expect(VERTICALS).toHaveLength(14);
    expect(VERTICALS.map((v) => v.order)).toEqual(Array.from({ length: 14 }, (_, i) => i + 1));
    expect(new Set(VERTICALS.map((v) => v.slug)).size).toBe(14);
    expect(VERTICALS[0].slug).toBe("compliance-legal");
    expect(VERTICALS[13].slug).toBe("capital-infrastructure");
  });
  it("every vertical has a one-sentence description", () => {
    for (const v of VERTICALS) {
      expect(v.description.length).toBeGreaterThan(20);
      expect(v.description.endsWith(".")).toBe(true);
      expect(v.description.slice(0, -1)).not.toMatch(/[.!?]/);
    }
  });
  it("backend mapping", () => {
    expect(realVerticals().map((v) => v.slug)).toEqual([
      "compliance-legal",
      "policy-governance",
      "operations-processes",
      "workforce-hr",
      "environmental-esg",
    ]);
    expect(verticalFromBackend("Workforce & Safety")?.slug).toBe("workforce-hr");
    expect(verticalFromBackend("environmental")?.slug).toBe("environmental-esg");
    expect(verticalFromBackend("Nope")).toBeUndefined();
  });
  it("helpers", () => {
    expect(verticalName("revenue-pricing")).toBe("Revenue & Pricing");
    expect(verticalName("unknown")).toBe("unknown");
    expect(getVertical("technology-systems")?.name).toBe("Technology & Systems");
    expect(isVerticalSlug("workforce-hr")).toBe(true);
    expect(isVerticalSlug("x")).toBe(false);
    expect(["risk-insurance", "compliance-legal"].sort(compareVerticals)).toEqual(["compliance-legal", "risk-insurance"]);
  });
});

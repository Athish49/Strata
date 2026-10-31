import { describe, expect, it } from "vitest";
import {
  UNCLASSIFIED_SLUG,
  VERTICALS,
  VERTICAL_GROUPS,
  canUploadToVertical,
  compareVerticals,
  isKnownVerticalSlug,
  normalizeVerticalSlug,
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
  it("unclassified fallback group", () => {
    expect(VERTICALS.map((v) => v.slug)).not.toContain(UNCLASSIFIED_SLUG);
    expect(VERTICAL_GROUPS).toHaveLength(15);
    expect(VERTICAL_GROUPS.at(-1)?.slug).toBe("unclassified");
    expect(getVertical("unclassified")?.name).toBe("Unclassified");
    expect(verticalName("unclassified")).toBe("Unclassified");
    expect(isVerticalSlug("unclassified")).toBe(false);
    expect(isKnownVerticalSlug("unclassified")).toBe(true);
    expect(normalizeVerticalSlug("nope")).toBe("unclassified");
    expect(normalizeVerticalSlug(null)).toBe("unclassified");
    expect(normalizeVerticalSlug("workforce-hr")).toBe("workforce-hr");
    expect(["unclassified", "capital-infrastructure", "zzz"].sort(compareVerticals)).toEqual(["capital-infrastructure", "unclassified", "zzz"]);
  });
  it("every one of the 14 verticals accepts uploads, and unclassified never does", () => {
    // The backend maps all 14 (it once mapped only the 5 the synthetic corpus used, so uploads
    // into the other 9 returned 422). `unclassified` is a fallback group, not an upload target.
    expect(VERTICAL_GROUPS.filter((v) => canUploadToVertical(v.slug)).map((v) => v.slug)).toEqual(VERTICALS.map((v) => v.slug));
    expect(VERTICALS).toHaveLength(14);
    expect(canUploadToVertical("unclassified")).toBe(false);
    expect(canUploadToVertical("revenue-pricing")).toBe(true);
    expect(canUploadToVertical("not-a-vertical")).toBe(false);
  });
});

import { describe, expect, it } from "vitest";
import { formatConfidence, formatCount, formatDate, formatNumber, formatPercent, pluralize } from "@/lib/format";

describe("format", () => {
  it("formats dates without timezone shift", () => {
    expect(formatDate("2025-02-05")).toBe("Feb 5, 2025");
    expect(formatDate("2025-02-05T23:59:59Z")).toBe("Feb 5, 2025");
    expect(formatDate("2024-12-31T00:00:00")).toBe("Dec 31, 2024");
  });
  it("handles empty and invalid dates", () => {
    expect(formatDate(null)).toBe("—");
    expect(formatDate("")).toBe("—");
    expect(formatDate("garbage")).toBe("—");
    expect(formatDate("2025-13-40")).toBe("—");
  });
  it("formats counts and numbers", () => {
    expect(formatCount(1234567)).toBe("1,234,567");
    expect(formatCount(0)).toBe("0");
    expect(formatCount(NaN)).toBe("—");
    expect(formatNumber(1234.567, 1)).toBe("1,234.6");
  });
  it("formats percent and confidence", () => {
    expect(formatPercent(0.5)).toBe("50%");
    expect(formatPercent(0.825, 1)).toBe("82.5%");
    expect(formatConfidence(0.82)).toBe("82%");
    expect(formatConfidence(1.2)).toBe("100%");
    expect(formatConfidence(-1)).toBe("0%");
  });
  it("pluralizes", () => {
    expect(pluralize(1, "change")).toBe("1 change");
    expect(pluralize(1200, "change")).toBe("1,200 changes");
  });
});

import "@testing-library/jest-dom/vitest";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { RadarItemCard } from "@/components/radar/RadarItemCard";
import { filterItems, formatBasisValue, groupItems, humanizeKey, screenedLine } from "@/components/radar/logic";
import type { RadarItem } from "@/lib/api/schemas";

afterEach(cleanup);
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("run=run_x"),
  usePathname: () => "/app/radar",
}));

const item = (over: Partial<RadarItem>): RadarItem => ({
  radar_id: "r1",
  run_id: "run_x",
  change_id: "c1",
  citation: "326 IAC 2-1",
  heading: "Standby generators",
  agency_id: "idem",
  applicable: "yes",
  attribute_basis: [{ key: "standby_generator_count", value: 3 }],
  affected_activity: "operating standby generators",
  reason: "RPL runs 3 generators.",
  quote: "",
  docs_covering_same_rule: [],
  ...over,
});

describe("radar logic", () => {
  it("humanizes keys and values", () => {
    expect(humanizeKey("owns_generating_units")).toBe("Owns generating units");
    expect(formatBasisValue(false)).toBe("No");
    expect(formatBasisValue(1200)).toBe("1,200");
  });
  it("groups and filters", () => {
    const items = [item({}), item({ radar_id: "r2", applicable: "no", agency_id: "epa", citation: "40 CFR 60" })];
    expect(groupItems(items).no).toHaveLength(1);
    expect(filterItems(items, { agency: "epa", query: "" })).toHaveLength(1);
    expect(filterItems(items, { agency: null, query: "standby" })).toHaveLength(2);
    expect(filterItems(items, { agency: null, query: "cfr" })).toHaveLength(1);
  });
  it("falls back to a basis line when screened reason is empty", () => {
    const i = item({ applicable: "no", reason: "", attribute_basis: [{ key: "owns_generating_units", value: false }] });
    expect(screenedLine(i)).toContain("owns generating units = no");
  });
});

describe("RadarItemCard", () => {
  it("links change and attribute chips, omits empty quote, shows cues", () => {
    render(
      <TooltipProvider>
        <ul>
          <RadarItemCard item={item({})} agencyName="IDEM" />
        </ul>
      </TooltipProvider>,
    );
    expect(screen.getByRole("link", { name: "326 IAC 2-1" })).toHaveAttribute("href", "/app/changes/c1?run=run_x");
    expect(screen.getByRole("link", { name: /Standby generator count/ })).toHaveAttribute(
      "href",
      "/app/company?run=run_x#standby_generator_count",
    );
    expect(screen.queryByRole("blockquote")).toBeNull();
    expect(screen.getAllByText(/coming soon/i).length).toBeGreaterThan(0);
  });
  it("renders quote when present", () => {
    const { container } = render(
      <TooltipProvider>
        <ul>
          <RadarItemCard item={item({ quote: "The owner shall report." })} />
        </ul>
      </TooltipProvider>,
    );
    expect(container.querySelector("blockquote")).toHaveTextContent("The owner shall report.");
  });
});

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, fireEvent } from "@testing-library/react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { AgencyCard } from "@/components/kb/AgencyCard";
import { ActionList } from "@/components/kb/ActionList";
import { SectionTree } from "@/components/kb/SectionTree";
import { StreamChips } from "@/components/kb/StreamChips";
import type { Agency, CodeSection, RegulatoryAction } from "@/lib/api/schemas";

afterEach(cleanup);

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("run=run_x"),
  usePathname: () => "/app/regulations",
}));

const agency = (over: Partial<Agency>): Agency => ({
  agency_id: "iurc",
  slug: "iurc",
  name: "Indiana Utility Regulatory Commission",
  level: "state",
  geo: "IN",
  domains: [],
  codebook_titles: ["170 IAC"],
  section_count: 352,
  action_count: 199,
  s1_snapshot: "2024-12-31",
  s2_snapshot: "2025-12-31",
  last_sync_at: "2026-10-07T02:17:11Z",
  has_activity_feed: true,
  streams: ["iurc_gaos", "iurc_rulemakings"],
  ...over,
});

describe("AgencyCard", () => {
  it("shows counts, stream chips, dates and a run-preserving link", () => {
    render(
      <TooltipProvider>
        <AgencyCard agency={agency({})} changedInRun={4} />
      </TooltipProvider>,
    );
    expect(screen.getByText("352")).toBeInTheDocument();
    expect(screen.getByText("Orders")).toBeInTheDocument();
    expect(screen.getByText("Rulemakings")).toBeInTheDocument();
    expect(screen.getByText(/4 sections changed in this run/)).toBeInTheDocument();
    expect(screen.getByText(/Dec 31, 2024/)).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/app/regulations/iurc?run=run_x");
  });
  it("marks codebook-only agencies and never shows null or Invalid Date", () => {
    const { container } = render(
      <TooltipProvider>
        <AgencyCard agency={agency({ slug: "idol", agency_id: "idol", has_activity_feed: false, action_count: 0, streams: [], last_sync_at: "" })} />
      </TooltipProvider>,
    );
    expect(screen.getByText("Codebook only")).toBeInTheDocument();
    expect(screen.getByText("No activity feed")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/null|undefined|Invalid Date/);
  });
});

const action = (over: Partial<RegulatoryAction>): RegulatoryAction => ({
  source_system: "iurc_gaos",
  source_id: "GAO-2019-02",
  agency: "iurc",
  stream: "iurc_gaos",
  action_type: "order",
  status: "approved",
  date_published: null,
  title: "PDF",
  abstract: "",
  cfr_references: [],
  legal_refs: [],
  docket_ids: [],
  source_url: "",
  related: [],
  ...over,
});

describe("ActionList", () => {
  it("handles null dates and junk titles", () => {
    const { container } = render(<ActionList actions={[action({})]} />);
    expect(screen.getByText("Order GAO-2019-02")).toBeInTheDocument();
    expect(screen.getByText("Date not published")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/null|Invalid Date/);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/app/regulations/actions/iurc_gaos/GAO-2019-02?run=run_x");
  });
  it("encodes ids with slashes and spaces in links", () => {
    render(<ActionList actions={[action({ source_id: "RM 26/05", title: "A proper title" })]} />);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/app/regulations/actions/iurc_gaos/RM%2026/05?run=run_x");
  });
  it("shows an empty state", () => {
    render(<ActionList actions={[]} />);
    expect(screen.getByText("No actions match these filters")).toBeInTheDocument();
  });
});

describe("StreamChips", () => {
  it("reports the chosen stream", () => {
    const onChange = vi.fn();
    render(<StreamChips streams={["iurc_gaos", "iurc_investigations"]} value={null} onChange={onChange} />);
    fireEvent.click(screen.getByRole("button", { name: "Investigations" }));
    expect(onChange).toHaveBeenCalledWith("iurc_investigations");
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute("aria-pressed", "true");
  });
});

const section = (i: number, rule: string, status: "approved" | "repealed" = "approved"): CodeSection => ({
  citation: `326 IAC ${rule}-${i}`,
  source_system: "iac",
  title_number: "326",
  part_or_article: rule.split("-")[0],
  rule_key: `326 IAC ${rule}`,
  section_number: String(i),
  heading: `Heading ${i}`,
  body_text: "",
  status,
  snapshot_date: "2025-12-31",
  owning_agency: "idem",
  federal_refs: [],
  iac_cross_refs: [],
});

describe("SectionTree", () => {
  const many = Array.from({ length: 1600 }, (_, i) => section(i + 1, `${(i % 40) + 1}-1`));
  it("keeps thousands of sections out of the DOM until a rule is opened", () => {
    render(<SectionTree sections={many} query="" includeRepealed={false} changed={new Map()} />);
    expect(screen.queryAllByRole("link").length).toBe(0);
    fireEvent.click(screen.getByRole("button", { name: /^Article 1\b/i }));
    fireEvent.click(screen.getByRole("button", { name: /326 IAC 1-1/ }));
    expect(screen.getAllByRole("link").length).toBe(40);
  });
  it("searches into a paginated flat list", () => {
    render(<SectionTree sections={many} query="heading 1" includeRepealed={false} changed={new Map()} />);
    expect(screen.getAllByRole("link").length).toBe(50);
    expect(screen.getByText(/of \d+ sections/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Next page"));
    expect(screen.getByText(/Page 2 of/)).toBeInTheDocument();
  });
  it("shows a changed badge and hides repealed sections", () => {
    const secs = [section(1, "1-1"), section(2, "1-1", "repealed")];
    render(<SectionTree sections={secs} query="IAC" includeRepealed={false} changed={new Map([["iac|326 IAC 1-1-1", "cosmetic"]])} />);
    expect(screen.getAllByRole("link")).toHaveLength(1);
    expect(screen.getByText("Changed in this run")).toBeInTheDocument();
    expect(screen.getByText("Cosmetic")).toBeInTheDocument();
  });
  it("explains an empty search", () => {
    render(<SectionTree sections={many} query="zzzz-none" includeRepealed={false} changed={new Map()} />);
    expect(screen.getByText("No sections match your search")).toBeInTheDocument();
  });
});

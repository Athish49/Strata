import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import {
  ClassPill,
  DirectionChip,
  MatchPathIcon,
  RouteChips,
  ScoreFigure,
  SeverityMark,
  TrustBadges,
  ValueChangeChip,
  VerdictPill,
} from "@/components/engine";

afterEach(cleanup);

const wrap = (ui: ReactNode) => render(<TooltipProvider>{ui}</TooltipProvider>);
const person = (name: string, title: string) => ({ person_id: name, name, title, department: "X", reports_to_id: null });

describe("VerdictPill", () => {
  it("renders the label for every verdict and cleared", () => {
    const { container } = render(
      <>
        {(["action_required", "optional_relaxed", "update_citation", "review", "info", "cleared"] as const).map((v) => (
          <VerdictPill key={v} verdict={v} />
        ))}
      </>,
    );
    for (const t of ["Action required", "Relaxed (optional update)", "Update citation", "Needs review", "Info", "Cleared"]) {
      expect(screen.getByText(t)).toBeInTheDocument();
    }
    expect(container.querySelectorAll("[data-verdict]")).toHaveLength(6);
  });
});

describe("ClassPill", () => {
  it("marks noise classes and labels real ones", () => {
    const { container } = render(
      <>
        <ClassPill changeClass="cosmetic" />
        <ClassPill changeClass="substantive" />
      </>,
    );
    expect(screen.getByText("Cosmetic")).toBeInTheDocument();
    expect(screen.getByText("Substantive")).toBeInTheDocument();
    expect(container.querySelectorAll('[data-noise="true"]')).toHaveLength(1);
  });
});

describe("SeverityMark / DirectionChip / ValueChangeChip", () => {
  it("renders severity text", () => {
    render(<SeverityMark severity="high" />);
    expect(screen.getByText("Severity · High")).toBeInTheDocument();
  });
  it("renders the mixed direction and nothing for null", () => {
    const { rerender, container } = render(<DirectionChip direction="mixed" />);
    expect(screen.getByText("Mixed")).toBeInTheDocument();
    rerender(<DirectionChip direction={null} />);
    expect(container).toBeEmptyDOMElement();
  });
  it("renders old -> new with unit", () => {
    render(<ValueChangeChip change={{ label: "Notice period", old: "10", new: "14", unit: "business days" }} />);
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("14")).toBeInTheDocument();
    expect(screen.getByText("business days")).toBeInTheDocument();
    expect(screen.getByText("Notice period")).toBeInTheDocument();
  });
});

describe("TrustBadges", () => {
  it("shows verified quote and rule", () => {
    render(<TrustBadges quotesVerified decidedBy="rule" confidence={1} />);
    expect(screen.getByText("Verified quote ✓")).toBeInTheDocument();
    expect(screen.getByText("Decided by rule")).toBeInTheDocument();
  });
  it("shows AI confidence, and degrades when confidence is null", () => {
    const { rerender } = render(<TrustBadges decidedBy="ai" confidence={0.82} quotesVerified={false} />);
    expect(screen.getByText("AI judgment · 82%")).toBeInTheDocument();
    expect(screen.getByText("Evidence unverified — review")).toBeInTheDocument();
    rerender(<TrustBadges decidedBy="ai" confidence={null} />);
    expect(screen.getByText("AI judgment")).toBeInTheDocument();
    expect(screen.queryByText(/Verified quote|unverified/)).toBeNull();
  });
});

describe("MatchPathIcon", () => {
  it("exposes the plain words", () => {
    wrap(<MatchPathIcon path="value_echo" context={{ oldValue: "10 days" }} />);
    expect(screen.getByRole("img", { name: "Restates the old value (10 days) without citing it" })).toBeInTheDocument();
  });
  it("can show words inline", () => {
    wrap(<MatchPathIcon path="direct_section" showWords />);
    expect(screen.getByText("Cites this section directly")).toBeInTheDocument();
  });
});

describe("RouteChips", () => {
  it("renders the chain and the two-signature label", () => {
    render(<RouteChips route={{ owner: person("Ann Lee", "Owner title"), reviewer: person("Bo Kim", "Reviewer title"), approver: null }} twoSignature />);
    expect(screen.getByText("Ann Lee")).toBeInTheDocument();
    expect(screen.getByText("Reviewer title")).toBeInTheDocument();
    expect(screen.getByText("Two-signature document")).toBeInTheDocument();
    expect(screen.queryByText("Approver")).toBeNull();
  });
  it("shows the approver when present and no two-signature label", () => {
    render(<RouteChips route={{ owner: person("A A", "t"), reviewer: person("B B", "t"), approver: person("C C", "t") }} twoSignature />);
    expect(screen.getByText("Approver")).toBeInTheDocument();
    expect(screen.queryByText("Two-signature document")).toBeNull();
  });
});

describe("ScoreFigure", () => {
  it("passes and fails by goal", () => {
    const { rerender } = render(<ScoreFigure label="Precision" value={0.86} target={0.8} />);
    expect(screen.getByText("0.86")).toBeInTheDocument();
    expect(screen.getByText("Meets target")).toBeInTheDocument();
    rerender(<ScoreFigure label="False positives" value={0.1} target={0} goal="max" />);
    expect(screen.getByText("Misses target")).toBeInTheDocument();
    rerender(<ScoreFigure label="False positives" value={0} target={0} goal="max" />);
    expect(screen.getByText("Meets target")).toBeInTheDocument();
  });
});

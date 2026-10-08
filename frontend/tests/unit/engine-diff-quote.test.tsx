import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { DiffView, QuoteHighlight, changeGroupStarts, resolveQuoteRange } from "@/components/engine";
import type { DiffSegment } from "@/lib/api/schemas";

afterEach(cleanup);

const long = "x".repeat(1240);
const segs: DiffSegment[] = [
  { op: "equal", text: "Notice shall be given " },
  { op: "delete", text: "10" },
  { op: "insert", text: "14" },
  { op: "equal", text: ` days. ${long} The end ` },
  { op: "delete", text: "shall not" },
  { op: "insert", text: "may not" },
  { op: "equal", text: " proceed." },
];

describe("DiffView", () => {
  it("shows a graceful state for empty segments", () => {
    render(<DiffView segments={[]} />);
    expect(screen.getByTestId("diff-empty")).toHaveTextContent("No text diff");
  });

  it("shows an identical state when nothing changed", () => {
    render(<DiffView segments={[{ op: "equal", text: "same" }]} />);
    expect(screen.getByTestId("diff-identical")).toBeInTheDocument();
  });

  it("marks deletes and inserts with real del/ins elements and collapses long unchanged runs", () => {
    const { container } = render(<DiffView segments={segs} />);
    expect(container.querySelector("del")).toHaveTextContent("10");
    expect(container.querySelector("ins")).toHaveTextContent("14");
    expect(container.querySelector("del")?.className).toContain("line-through");
    expect(container.querySelector("ins")?.className).toContain("underline");
    expect(container.textContent).not.toContain(long);
    const btn = screen.getByRole("button", { name: /unchanged characters/ });
    expect(btn).toHaveTextContent(/… 1,\d{3} unchanged characters …/);
    fireEvent.click(btn);
    expect(container.textContent).toContain(long);
    fireEvent.click(screen.getByRole("button", { name: "Collapse" }));
    expect(container.textContent).not.toContain(long);
  });

  it("navigates between changes", () => {
    render(<DiffView segments={segs} />);
    expect(screen.getByText("Change 1 of 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next change" }));
    expect(screen.getByText("Change 2 of 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next change" }));
    expect(screen.getByText("Change 1 of 2")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Previous change" }));
    expect(screen.getByText("Change 2 of 2")).toBeInTheDocument();
  });

  it("supports n / p hotkeys when enabled", () => {
    render(<DiffView segments={segs} hotkeys />);
    fireEvent.keyDown(window, { key: "n" });
    expect(screen.getByText("Change 2 of 2")).toBeInTheDocument();
    fireEvent.keyDown(window, { key: "p" });
    expect(screen.getByText("Change 1 of 2")).toBeInTheDocument();
  });

  it("switches to side-by-side with old text left and new text right", () => {
    const onMode = vi.fn();
    render(<DiffView segments={segs} onModeChange={onMode} />);
    fireEvent.click(screen.getByRole("button", { name: /Side by side/ }));
    expect(onMode).toHaveBeenCalledWith("side-by-side");
    const left = screen.getByRole("region", { name: "Old rule (S1)" });
    const right = screen.getByRole("region", { name: "New rule (S2)" });
    expect(left.querySelector("del")).toHaveTextContent("10");
    expect(left.querySelector("ins")).toBeNull();
    expect(right.querySelector("ins")).toHaveTextContent("14");
    expect(right.querySelector("del")).toBeNull();
  });

  it("toggles the raw diff and reports it", () => {
    const onToggle = vi.fn();
    render(<DiffView segments={segs} rawDiff={{ onToggle, lines: [{ op: "delete", line: "old line" }, { op: "insert", line: "new line" }] }} banner="Only the readoption stamp changed" />);
    expect(screen.getByText("Only the readoption stamp changed")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show raw diff" }));
    expect(onToggle).toHaveBeenCalledWith(true);
    expect(screen.getByRole("region", { name: "Raw line diff" })).toHaveTextContent("old line");
    fireEvent.click(screen.getByRole("button", { name: "Hide raw diff" }));
    expect(onToggle).toHaveBeenLastCalledWith(false);
  });

  it("raw diff works on empty segments and shows loading", () => {
    render(<DiffView segments={[]} rawDiff={{ loading: true }} />);
    fireEvent.click(screen.getByRole("button", { name: "Show raw diff" }));
    expect(screen.getByLabelText("Loading raw diff")).toBeInTheDocument();
  });

  it("handles a very long text", () => {
    const big: DiffSegment[] = [
      { op: "equal", text: "a".repeat(200_000) },
      { op: "delete", text: "b" },
      { op: "insert", text: "c" },
      { op: "equal", text: "d".repeat(200_000) },
    ];
    const { container } = render(<DiffView segments={big} />);
    expect(container.textContent!.length).toBeLessThan(2000);
    expect(screen.getAllByRole("button", { name: /Show 199,9\d\d unchanged characters/ })).toHaveLength(2);
  });

  it("changeGroupStarts groups consecutive non-equal segments", () => {
    expect(changeGroupStarts(segs)).toEqual([1, 4]);
    expect(changeGroupStarts([])).toEqual([]);
  });
});

describe("QuoteHighlight", () => {
  const body = "The utility shall give at least fourteen (14) days notice.";
  it("uses the span", () => {
    const { container } = render(<QuoteHighlight text={body} span={[28, 41]} />);
    expect(container.querySelector("mark")?.textContent).toBe(body.slice(28, 41));
  });
  it("falls back to text search when the span is wrong", () => {
    const { container } = render(<QuoteHighlight text={body} quote={{ text: "fourteen (14) days", span: [0, 5] }} />);
    expect(container.querySelector("mark")?.textContent).toBe("fourteen (14) days");
  });
  it("tolerates whitespace and case differences", () => {
    expect(resolveQuoteRange("a  b\nc DEF", "b c def")).toEqual([3, 10]);
  });
  it("renders plain text for an empty-string quote, even with a span", () => {
    const { container } = render(<QuoteHighlight text={body} quote={{ text: "", span: [0, 5] }} />);
    expect(container.querySelector("mark")).toBeNull();
    expect(container.textContent).toBe(body);
  });
  it("renders plain text when nothing matches or inputs are absent", () => {
    expect(render(<QuoteHighlight text={body} quote="not there" />).container.querySelector("mark")).toBeNull();
    expect(render(<QuoteHighlight text={body} />).container.querySelector("mark")).toBeNull();
    expect(resolveQuoteRange("abc", null, [5, 9])).toBeNull();
  });
  it("wires aria-describedby", () => {
    const { container } = render(<QuoteHighlight text={body} quote="days" describedBy="why" token="action_required" />);
    expect(container.querySelector("mark")).toHaveAttribute("aria-describedby", "why");
  });
});

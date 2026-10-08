import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import type { ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { resetMockState, setMockLatency } from "@/lib/api/mock";
import { MatrixView } from "@/components/matrix/MatrixView";
import { shortClause } from "@/components/matrix/CellPopoverBody";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("run=run_kb_real"),
  usePathname: () => "/app/matrix",
}));
vi.mock("@/lib/run-context", () => ({
  useRunContext: () => ({
    run: { run_id: "run_kb_real", kind: "kb", status: "succeeded" },
    runId: "run_kb_real",
    isSimulated: false,
    isLoading: false,
    setRunId: () => {},
  }),
}));

afterEach(cleanup);
beforeAll(() => setMockLatency(false));

function wrap(ui: ReactNode, searchParams = "") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter searchParams={searchParams}>
        <TooltipProvider>{ui}</TooltipProvider>
      </NuqsTestingAdapter>
    </QueryClientProvider>,
  );
}

describe("shortClause", () => {
  it("drops the doc prefix", () => {
    expect(shortClause("RPL-CS-PRO-004:8.2")).toBe("§8.2");
    expect(shortClause("8.2")).toBe("§8.2");
  });
});

describe("MatrixView (mock data)", () => {
  it("renders the grid, legend, a disabled future cue and the noise switch", async () => {
    resetMockState();
    wrap(<MatrixView />);
    await screen.findByRole("table");
    expect(screen.getAllByRole("rowheader").length).toBeGreaterThan(0);
    expect(screen.getByRole("list", { name: "Legend" })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Show noise columns" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("button", { name: /Export/ })).toHaveAttribute("aria-disabled", "true");
    expect(document.body.textContent).not.toMatch(/\bnull\b|undefined|\{"/);
  });

  it("opens a cell popover with deep links", async () => {
    resetMockState();
    wrap(<MatrixView />);
    await screen.findByRole("table");
    const cell = document.querySelector<HTMLButtonElement>("[data-cell]");
    expect(cell).not.toBeNull();
    fireEvent.click(cell!);
    const link = await screen.findByRole("link", { name: "Open document" });
    expect(link.getAttribute("href")).toMatch(/^\/app\/documents\/.+/);
    expect(screen.getByRole("link", { name: "Open change" }).getAttribute("href")).toMatch(/^\/app\/changes\//);
    await waitFor(() => expect(screen.queryByText("The clause details could not be loaded.")).toBeNull());
  });
});

import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import type { ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { resetMockState, setMockLatency } from "@/lib/api/mock";
import { ChangeDetail } from "@/components/changes/ChangeDetail";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams("run=run_kb_real"),
  usePathname: () => "/app/changes",
}));
vi.mock("@/lib/run-context", () => ({
  useRunContext: () => ({ run: { run_id: "run_kb_real", kind: "kb", status: "succeeded" }, runId: "run_kb_real", isSimulated: false, isLoading: false, setRunId: () => {} }),
}));

afterEach(cleanup);
beforeAll(() => setMockLatency(false));

function wrap(ui: ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <NuqsTestingAdapter>
        <TooltipProvider>{ui}</TooltipProvider>
      </NuqsTestingAdapter>
    </QueryClientProvider>,
  );
}

describe("ChangeDetail (mock data)", () => {
  it("shows the neutral banner, a diff and 'Cleared (94)' for the cosmetic 94-clause change", async () => {
    resetMockState();
    wrap(<ChangeDetail changeId="chg-170-iac-4-1-13" />);
    await screen.findByText(/Only the readoption stamp or formatting changed/);
    expect(await screen.findByText(/Cleared \(94\)/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Show raw diff/ })).toBeInTheDocument();
    expect(screen.getByText("Open full regulation")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Watch/ })).toHaveAttribute("aria-disabled", "true");
    expect(document.body.textContent).not.toMatch(/\bnull\b|undefined|\{"/);
  });

  it("shows direction and the proof line for a style-only substantive change", async () => {
    resetMockState();
    wrap(<ChangeDetail changeId="chg-170-iac-4-1-16" />);
    expect(await screen.findByText("Style only")).toBeInTheDocument();
    expect(await screen.findByTestId("ledger-proof")).toHaveTextContent(/cleared/);
  });
});

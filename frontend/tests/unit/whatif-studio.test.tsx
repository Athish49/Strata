import * as React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@/components/ui/tooltip";
import { api } from "@/lib/api/client";
import { resetMockState, setMockLatency } from "@/lib/api/mock";

const push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn(), back: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "/app/what-if",
  useParams: () => ({}),
}));

import { WhatIfStudio } from "@/components/whatif/WhatIfStudio";

function renderStudio(scenarioId?: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <TooltipProvider>
        <WhatIfStudio scenarioId={scenarioId} />
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  setMockLatency(false);
  resetMockState();
  push.mockClear();
});
afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
  vi.restoreAllMocks();
  setMockLatency(true);
});

async function pickFirstSection() {
  const list = await screen.findByTestId("section-list");
  fireEvent.click(list.querySelector("button")!);
  return screen.findByLabelText("Section text now in effect");
}

describe("What-if studio", () => {
  it("lists presets as instant and a disabled proposed-rule cue", async () => {
    renderStudio();
    const cards = await screen.findAllByTestId("preset-card");
    expect(cards.length).toBeGreaterThan(0);
    expect(screen.getAllByText("Instant").length).toBe(cards.length);
    expect(screen.getByText("Start from a proposed rule").closest("[aria-disabled=true]")).not.toBeNull();
  });

  it("a preset Run goes straight to its results without starting a run", async () => {
    const start = vi.spyOn(api.engine, "startWhatIf");
    renderStudio();
    const cards = await screen.findAllByTestId("preset-card");
    fireEvent.click(cards[0].querySelector("button")!);
    await waitFor(() => expect(push).toHaveBeenCalled());
    expect(push.mock.calls[0][0]).toMatch(/^\/app\?run=/);
    expect(start).not.toHaveBeenCalled();
  });

  it("shows the live diff preview and the repeal toggle for a picked section", async () => {
    renderStudio();
    const ta = (await pickFirstSection()) as HTMLTextAreaElement;
    expect(screen.getByText(/No change yet/)).toBeInTheDocument();
    fireEvent.change(ta, { target: { value: `${ta.value} Added sentence.` } });
    expect(await screen.findByText(/Added sentence\./, { selector: "ins, span, mark" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("switch", { name: /Repeal this section/ }));
    expect(ta).toBeDisabled();
  });

  it("custom run (mock mode) shows the stage stepper", async () => {
    renderStudio();
    const ta = (await pickFirstSection()) as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: `${ta.value} Added sentence.` } });
    fireEvent.click(screen.getByRole("button", { name: /Run impact/ }));
    expect(await screen.findByText("Running impact analysis")).toBeInTheDocument();
    expect(screen.getByText("Characterize")).toBeInTheDocument();
  });

  it("with custom runs paused the button is a disabled cue and no run is ever started", async () => {
    vi.stubEnv("NEXT_PUBLIC_STRATA_ALLOW_CUSTOM_WHATIF", "0");
    const start = vi.spyOn(api.engine, "startWhatIf");
    const save = vi.spyOn(api.engine, "saveScenario");
    renderStudio();
    const ta = (await pickFirstSection()) as HTMLTextAreaElement;
    fireEvent.change(ta, { target: { value: `${ta.value} Added sentence.` } });
    const paused = await screen.findByTestId("run-impact-paused");
    expect(paused).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(paused);
    expect(screen.getByText(/Custom what-if runs are paused: they use live model budget/)).toBeInTheDocument();
    const runButtons = screen.getAllByRole("button", { name: /Run impact/ });
    expect(runButtons.every((b) => b.getAttribute("aria-disabled") === "true")).toBe(true);
    expect(start).not.toHaveBeenCalled();
    expect(save).not.toHaveBeenCalled();
  });
});

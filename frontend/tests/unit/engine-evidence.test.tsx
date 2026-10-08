import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { NuqsTestingAdapter } from "nuqs/adapters/testing";
import type { ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { EvidenceCardBody, EvidenceDrawer, EvidenceDrawerView } from "@/components/engine";
import { mockApi, resetMockState, setMockLatency } from "@/lib/api/mock";
import { qk } from "@/lib/api/queries";

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

// f_a_008: propagated chain (register row -> procedure -> form field) in what-if preset A.
const FINDING = "f_a_008";

describe("EvidenceCardBody", () => {
  it("renders the verdict sentence, trust badges, evidence panes, trace chain, routing and cues", async () => {
    resetMockState();
    wrap(<EvidenceCardBody findingId={FINDING} />);
    await screen.findByRole("article", { name: "Evidence card" });
    // verdict + badges
    expect(screen.getAllByText(/Action required|Needs review|Update citation|Info|Relaxed/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Severity ·/)).toBeInTheDocument();
    expect(screen.getByText(/Decided by rule|AI judgment/)).toBeInTheDocument();
    // three panes
    expect(screen.getByRole("region", { name: "Old rule (S1)" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "New rule (S2)" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Clause" })).toBeInTheDocument();
    // trace chain mirrors path_detail
    const chain = screen.getByRole("list", { name: "Why this clause was found" });
    expect(chain.querySelectorAll(":scope > li")).toHaveLength(4);
    expect(screen.getByText("Notice letter field App-A.F6")).toBeInTheDocument();
    expect(screen.getByText("Fix once, fix everywhere.")).toBeInTheDocument();
    // future cues stay disabled
    for (const name of [/Draft full rewrite/, /Create task/, /Request sign-off/]) {
      expect(screen.getByRole("button", { name })).toHaveAttribute("aria-disabled", "true");
    }
    // never shows raw ids / json
    expect(document.body.textContent).not.toMatch(/"finding_id"|[0-9a-f]{8}-[0-9a-f]{4}-/);
  });

  it("highlights the clause quote once the clause text has loaded", async () => {
    wrap(<EvidenceCardBody findingId={FINDING} />);
    await screen.findByRole("article");
    await waitFor(() => expect(screen.getByRole("region", { name: "Clause" }).querySelector("mark")).not.toBeNull());
  });

  it("blocks rejecting without a note, then saves a note-backed rejection and shows it in the history", async () => {
    resetMockState();
    wrap(<EvidenceCardBody findingId={FINDING} />);
    await screen.findByRole("article");
    fireEvent.click(screen.getByRole("button", { name: "Reject" }));
    const submit = screen.getByRole("button", { name: "Submit rejection" });
    expect(submit).toBeDisabled();
    expect(screen.getByText("A note is required to reject a finding.")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/Why is this finding rejected/), { target: { value: "Already fixed in v4." } });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await screen.findByText("Rejected. Review saved.");
    expect(await screen.findByText("Already fixed in v4.")).toBeInTheDocument();
    expect(screen.getByText("Review history")).toBeInTheDocument();
  });

  it("accepts without a note", async () => {
    resetMockState();
    wrap(<EvidenceCardBody findingId={FINDING} />);
    await screen.findByRole("article");
    fireEvent.click(screen.getByRole("button", { name: "Accept" }));
    await screen.findByText("Accepted. Review saved.");
    expect(screen.getAllByText(/^Accepted by .+/).length).toBeGreaterThan(0);
  });

  it("shows a not-found state for an unknown finding", async () => {
    wrap(<EvidenceCardBody findingId="does-not-exist" />);
    expect(await screen.findByText("This finding could not be found.")).toBeInTheDocument();
  });
});

describe("EvidenceCardBody live-data quirks", () => {
  it("handles empty quotes, absent required change, null confidence and a null approver", async () => {
    const base = await mockApi.engine.getFinding(FINDING);
    const f = {
      ...base!,
      confidence: null,
      decided_by: "ai" as const,
      quotes_verified: false,
      quotes: { s1: { text: "" }, s2: { text: "" }, clause: { text: "", span: null } },
      required_change: { from_text: "", to_text: "" },
      rule_published_date: null,
      stale_at_approval: true,
      route: { ...base!.route, approver: null },
    };
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
    client.setQueryData(qk.finding(FINDING), f);
    render(
      <QueryClientProvider client={client}>
        <NuqsTestingAdapter>
          <TooltipProvider>
            <EvidenceCardBody findingId={FINDING} />
          </TooltipProvider>
        </NuqsTestingAdapter>
      </QueryClientProvider>,
    );
    await screen.findByRole("article");
    expect(screen.getByText("AI judgment")).toBeInTheDocument();
    expect(screen.getByText("Evidence unverified — review")).toBeInTheDocument();
    expect(screen.getByText(/No specific replacement wording/)).toBeInTheDocument();
    expect(screen.getByText("Draft full rewrite")).toBeInTheDocument();
    expect(screen.getAllByText("No quote was extracted for this pane.").length).toBeGreaterThan(0);
    expect(screen.getByText("Not recorded")).toBeInTheDocument();
    expect(document.querySelector("mark")).toBeNull();
    // falls back to the rationale instead of an empty sentence
    expect(screen.getByRole("article").querySelector("header p")?.textContent?.length).toBeGreaterThan(10);
  });
});

describe("EvidenceDrawer", () => {
  it("is closed without ?finding= and open with it", async () => {
    const { unmount } = wrap(<EvidenceDrawer />);
    expect(screen.queryByRole("dialog")).toBeNull();
    unmount();
    wrap(<EvidenceDrawer />, "?finding=" + FINDING);
    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await screen.findByRole("article");
    expect(screen.getByRole("link", { name: /Open full page/ })).toBeInTheDocument();
  });

  it("calls onClose via the Close button", async () => {
    let closed = false;
    wrap(<EvidenceDrawerView findingId={FINDING} onClose={() => (closed = true)} />);
    await screen.findByRole("article");
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(closed).toBe(true);
  });
});

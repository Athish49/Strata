import { describe, expect, it } from "vitest";
import { withRunParam } from "@/lib/app-link";
import { DEFAULT_RUN_ID, latestKbRunId, useRunContext } from "@/lib/run-context";
import { mockApi, setMockLatency } from "@/tests/support/mock-api";
import { renderHook } from "@testing-library/react";

describe("withRunParam", () => {
  it("adds ?run= to app links only", () => {
    expect(withRunParam("/app/changes", "run_x")).toBe("/app/changes?run=run_x");
    expect(withRunParam("/app", "run_x")).toBe("/app?run=run_x");
    expect(withRunParam("/app/matrix?noise=1#a", "run_x")).toBe("/app/matrix?noise=1&run=run_x#a");
    expect(withRunParam("/app/x?run=other", "run_x")).toBe("/app/x?run=other");
    expect(withRunParam("/", "run_x")).toBe("/");
    expect(withRunParam("/app/x", null)).toBe("/app/x");
  });
});

describe("useRunContext", () => {
  it("reports loading outside a provider", () => {
    const { result } = renderHook(() => useRunContext());
    expect(result.current.isLoading).toBe(true);
    expect(result.current.run).toBeNull();
  });
});

describe("latestKbRunId", () => {
  const mk = (run_id: string, kind: "kb" | "baseline" | "whatif", status: "succeeded" | "failed" | "running", started_at: string) =>
    ({ run_id, kind, status, started_at }) as never;
  it("picks the newest succeeded kb run, else null", () => {
    expect(latestKbRunId(undefined)).toBeNull();
    expect(
      latestKbRunId([
        mk("a", "kb", "succeeded", "2026-01-01T00:00:00Z"),
        mk("b", "kb", "succeeded", "2026-02-01T00:00:00Z"),
        mk("c", "kb", "failed", "2026-03-01T00:00:00Z"),
        mk("d", "whatif", "succeeded", "2026-04-01T00:00:00Z"),
      ]),
    ).toBe("b");
    expect(latestKbRunId([mk("d", "whatif", "succeeded", "2026-04-01T00:00:00Z")])).toBeNull();
  });
  it("resolves the mock real wave run", async () => {
    setMockLatency(false);
    expect(latestKbRunId(await mockApi.engine.listRuns())).toBe(DEFAULT_RUN_ID);
    setMockLatency(true);
  });
});

describe("mock parity", () => {
  it("lists light change/section rows and serves full text from detail calls", async () => {
    setMockLatency(false);
    const changes = await mockApi.engine.listChanges(DEFAULT_RUN_ID);
    expect(changes.every((c) => c.s1_text === "" && c.s2_text === "" && c.diff_segments.length === 0)).toBe(true);
    const full = await mockApi.engine.getChange(DEFAULT_RUN_ID, changes[0].change_id);
    expect(full?.diff_segments.length).toBeGreaterThan(0);
    const secs = await mockApi.kb.listSections({ limit: 5 });
    expect(secs.items.every((s) => s.body_text === "")).toBe(true);
    const editable = await mockApi.engine.listEditableSections();
    expect(editable.length).toBeGreaterThan(0);
    const t = await mockApi.engine.getSectionS1Text(editable[0].source_system, editable[0].citation);
    expect(t?.s1_text.length).toBeGreaterThan(0);
    setMockLatency(true);
  });
});

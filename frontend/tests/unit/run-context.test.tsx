import { describe, expect, it } from "vitest";
import { withRunParam } from "@/lib/app-link";
import { useRunContext } from "@/lib/run-context";
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

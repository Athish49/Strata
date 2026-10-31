import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { renderToString } from "react-dom/server";
import {
  ACTOR_STORAGE_KEY,
  MissingActorError,
  getActingPersonId,
  requireActingPersonId,
  resetActorStoreForTests,
  setActingPersonId,
  useActingPerson,
} from "@/lib/actor";

beforeEach(() => {
  localStorage.clear();
  resetActorStoreForTests();
});

afterEach(() => vi.restoreAllMocks());

describe("actor store", () => {
  it("is empty by default and persists a selection to localStorage", () => {
    expect(getActingPersonId()).toBeNull();
    setActingPersonId("P05");
    expect(getActingPersonId()).toBe("P05");
    expect(localStorage.getItem(ACTOR_STORAGE_KEY)).toBe("P05");
    resetActorStoreForTests(); // simulates a reload
    expect(getActingPersonId()).toBe("P05");
    setActingPersonId(null);
    expect(localStorage.getItem(ACTOR_STORAGE_KEY)).toBeNull();
    expect(getActingPersonId()).toBeNull();
  });

  it("tolerates a throwing localStorage (reads null, keeps the selection in memory)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("quota", "QuotaExceededError");
    });
    expect(getActingPersonId()).toBeNull();
    expect(() => setActingPersonId("P07")).not.toThrow();
    expect(getActingPersonId()).toBe("P07");
  });

  it("ignores a blank stored value", () => {
    localStorage.setItem(ACTOR_STORAGE_KEY, "   ");
    expect(getActingPersonId()).toBeNull();
  });

  it("requireActingPersonId prefers the explicit id and throws MissingActorError when none", () => {
    expect(() => requireActingPersonId()).toThrow(MissingActorError);
    expect(requireActingPersonId("P02")).toBe("P02");
    setActingPersonId("P05");
    expect(requireActingPersonId()).toBe("P05");
    expect(requireActingPersonId("  ")).toBe("P05");
  });

  it("useActingPerson re-renders on set and on a cross-tab storage event", () => {
    const { result } = renderHook(() => useActingPerson());
    expect(result.current[0]).toBeNull();
    act(() => result.current[1]("P03"));
    expect(result.current[0]).toBe("P03");
    act(() => {
      localStorage.setItem(ACTOR_STORAGE_KEY, "P09");
      window.dispatchEvent(new StorageEvent("storage", { key: ACTOR_STORAGE_KEY }));
    });
    expect(result.current[0]).toBe("P09");
  });

  it("server render uses the null snapshot (no hydration mismatch, no storage access)", () => {
    setActingPersonId("P05");
    function Who() {
      const [id] = useActingPerson();
      return <span>{id ?? "nobody"}</span>;
    }
    expect(renderToString(<Who />)).toContain("nobody");
  });
});

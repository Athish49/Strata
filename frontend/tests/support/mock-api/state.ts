// In-memory mutable mock state, mirrored to sessionStorage (all access guarded).
import type { Finding, Scenario } from "@/lib/api/schemas";

type Review = Finding["reviews"][number];

export interface CustomRun {
  run_id: string;
  scenario_id: string;
  title: string;
  /** epoch ms; progress is computed from Date.now() - started_at_ms */
  started_at_ms: number;
}

export interface MockState {
  reviews: Record<string, Review[]>;
  scenarios: Scenario[];
  /** last_run_id overrides for preset scenarios are not needed; custom scenarios carry their own. */
  customRuns: CustomRun[];
}

const KEY = "strata.mock.v1";
let state: MockState | null = null;

function empty(): MockState {
  return { reviews: {}, scenarios: [], customRuns: [] };
}

function read(): MockState {
  try {
    const raw = typeof sessionStorage !== "undefined" ? sessionStorage.getItem(KEY) : null;
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<MockState>;
      return {
        reviews: parsed.reviews ?? {},
        scenarios: parsed.scenarios ?? [],
        customRuns: parsed.customRuns ?? [],
      };
    }
  } catch {
    /* storage unavailable or corrupt: start fresh */
  }
  return empty();
}

export function getState(): MockState {
  if (!state) state = read();
  return state;
}

export function persist(): void {
  try {
    if (typeof sessionStorage !== "undefined" && state) sessionStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* ignore */
  }
}

/** Test helper: drop in-memory and stored state. */
export function resetMockState(): void {
  state = empty();
  try {
    if (typeof sessionStorage !== "undefined") sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

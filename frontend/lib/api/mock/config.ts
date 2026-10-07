// Mock-layer runtime switches. Tests flip latency off so they run instantly.
const state = { latency: true };

export function setMockLatency(enabled: boolean): void {
  state.latency = enabled;
}

export function isMockLatencyEnabled(): boolean {
  return state.latency;
}

let tick = 0;
/** 150-400 ms, deterministic-ish (cycles through a fixed sequence rather than Math.random). */
function nextLatencyMs(): number {
  const seq = [210, 320, 180, 390, 250, 160, 340, 280];
  return seq[tick++ % seq.length];
}

/** Resolve `fn()` after the artificial latency (immediately when disabled). */
export async function withLatency<T>(fn: () => T | Promise<T>): Promise<T> {
  if (state.latency) {
    await new Promise<void>((resolve) => setTimeout(resolve, nextLatencyMs()));
  }
  return fn();
}

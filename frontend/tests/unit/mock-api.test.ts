import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { z } from "zod";
import { mockApi, resetMockState, setMockLatency, CUSTOM_RUN_MS } from "@/lib/api/mock";
import {
  candidateSchema,
  changeRecordSchema,
  docRollupSchema,
  documentMetaSchema,
  findingSchema,
  lineDiffSchema,
  runSchema,
  scenarioSchema,
  scoreReportSchema,
} from "@/lib/api/schemas";

const api = mockApi;

beforeEach(() => {
  setMockLatency(false);
  resetMockState();
});
afterEach(() => {
  vi.useRealTimers();
  setMockLatency(true);
});

describe("mock api shapes", () => {
  it("returns schema-valid engine data for every fixture run", async () => {
    const runs = await api.engine.listRuns();
    z.array(runSchema).parse(runs);
    for (const run of runs) {
      z.array(changeRecordSchema).parse(await api.engine.listChanges(run.run_id));
      z.array(candidateSchema).parse(await api.engine.listCandidates(run.run_id));
      z.array(findingSchema).parse(await api.engine.listFindings(run.run_id));
      z.array(docRollupSchema).parse(await api.engine.listRollups(run.run_id));
      await api.engine.listRadar(run.run_id);
      const m = await api.engine.getMatrix(run.run_id, { include_noise: true });
      expect(Array.isArray(m.cells)).toBe(true);
    }
    z.array(scenarioSchema).parse(await api.engine.listScenarios());
    scoreReportSchema.parse(await api.engine.getScore("run_kb_real"));
    expect(await api.engine.getScore("run_whatif_preset_a")).toBeNull();
  });

  it("returns schema-valid company and kb data", async () => {
    const docs = z.array(documentMetaSchema).parse(await api.company.listDocuments());
    await api.company.listPeople();
    await api.company.getProfile();
    for (const d of docs.filter((x) => x.monitored)) {
      const reader = await api.engine.getReader(d.doc_id, "run_kb_real");
      expect(reader?.doc.doc_id).toBe(d.doc_id);
      for (const a of reader!.annotations) {
        expect(reader!.clauses.length === 0 || reader!.clauses.some((c) => c.clause_id === a.clause_id)).toBe(true);
      }
    }
    expect(await api.company.getDocument("nope")).toBeNull();
    const agencies = await api.kb.listAgencies();
    for (const a of agencies.slice(0, 3)) expect((await api.kb.getAgency(a.slug))?.slug).toBe(a.slug);
    const secs = await api.kb.listSections({ limit: 500 });
    expect(secs.limit).toBe(200);
    const acts = await api.kb.listActions({ limit: 5, page: 1 });
    expect(acts.items.length).toBeLessThanOrEqual(5);
    expect(await api.kb.getSection("iac", "does-not-exist")).toBeNull();
  });

  it("filters sections by status and produces line diffs for known versions", async () => {
    const repealed = await api.kb.listSections({ status: "repealed", limit: 200 });
    expect(repealed.items.every((s) => s.status === "repealed")).toBe(true);
    const changes = await api.engine.listChanges("run_kb_real");
    for (const c of changes.slice(0, 3)) {
      const hist = await api.kb.getVersionHistory(c.source_system, c.citation);
      if (hist.length < 2) continue;
      const diff = lineDiffSchema.parse(await api.kb.compare(c.source_system, c.citation));
      expect(diff.length).toBeGreaterThan(0);
    }
    expect(await api.kb.compare("iac", "missing")).toEqual([]);
  });
});

describe("latency flag", () => {
  it("delays when enabled and is instant when disabled", async () => {
    vi.useFakeTimers();
    setMockLatency(true);
    let done = false;
    void api.company.listPeople().then(() => (done = true));
    await vi.advanceTimersByTimeAsync(100);
    expect(done).toBe(false);
    await vi.advanceTimersByTimeAsync(400);
    expect(done).toBe(true);
    setMockLatency(false);
    done = false;
    void api.company.listPeople().then(() => (done = true));
    await vi.advanceTimersByTimeAsync(0);
    expect(done).toBe(true);
  });
});

describe("review mutation", () => {
  it("appends to the finding's reviews", async () => {
    const findings = await api.engine.listFindings("run_whatif_preset_a");
    if (findings.length === 0) return;
    const f = findings[0];
    const before = f.reviews.length;
    const updated = await api.engine.submitReview(f.finding_id, "accept", "ok");
    expect(updated.reviews.length).toBe(before + 1);
    expect(updated.reviews.at(-1)?.decision).toBe("accept");
    expect((await api.engine.getFinding(f.finding_id))?.reviews.length).toBe(before + 1);
    await expect(api.engine.submitReview("nope", "reject")).rejects.toThrow();
  });
});

describe("scenarios and custom runs", () => {
  it("saves scenarios and advances a custom run through five stages", async () => {
    vi.useFakeTimers();
    const sc = await api.engine.saveScenario({
      title: "Custom test",
      citation: "170 IAC 4-1-1",
      source_system: "iac",
      edit_kind: "text_edit",
      edited_text: "changed",
    });
    expect(sc.is_preset).toBe(false);
    expect((await api.engine.listScenarios()).some((s) => s.scenario_id === sc.scenario_id)).toBe(true);

    const run = await api.engine.startWhatIf(sc.scenario_id);
    expect(run.run_id).toBe("run_whatif_custom_1");
    expect(run.status).toBe("running");
    expect(run.title).toBe("Custom test");
    runSchema.parse(run);
    // Results must not appear before the run finishes.
    expect(await api.engine.listFindings(run.run_id)).toEqual([]);

    const stages: string[] = [];
    const step = 500;
    for (let t = 0; t < CUSTOM_RUN_MS; t += step) {
      const r = (await api.engine.getRun(run.run_id))!;
      if (r.status !== "running") break;
      const stage = r.progress!.stage;
      if (stages.at(-1) !== stage) stages.push(stage);
      vi.advanceTimersByTime(step);
    }
    expect(stages).toEqual(["delta", "characterize", "candidates", "judge", "ledger"]);

    vi.advanceTimersByTime(CUSTOM_RUN_MS);
    const done = (await api.engine.getRun(run.run_id))!;
    expect(done.status).toBe("succeeded");
    expect(done.run_id).toBe(run.run_id);
    expect((await api.engine.listRuns()).map((r) => r.run_id)).toContain(run.run_id);

    const presetA = await api.engine.listFindings("run_whatif_preset_a");
    const mine = await api.engine.listFindings(run.run_id);
    expect(mine.length).toBe(presetA.length);
    expect(mine.every((f) => f.run_id === run.run_id)).toBe(true);
    z.array(findingSchema).parse(mine);
  });

  it("returns the already-succeeded run for presets", async () => {
    const preset = (await api.engine.listScenarios()).find((s) => s.is_preset && s.last_run_id);
    if (!preset) return;
    const run = await api.engine.startWhatIf(preset.scenario_id);
    expect(run.run_id).toBe(preset.last_run_id);
    expect(run.status).toBe("succeeded");
  });
});

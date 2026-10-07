import type {
  Annotation,
  ChangeRecord,
  Finding,
  MatrixCell,
  Run,
  RunStats,
  Scenario,
  Stage,
  Verdict,
} from "../schemas";
import type { EngineApi, Matrix, Reader } from "../client";
import { fixtures, loadClauses, PRESET_A_RUN_ID, type RunData } from "./fixtures";
import { getState, persist, type CustomRun } from "./state";
import { withLatency } from "./config";

const NOISE = new Set(["cosmetic", "metadata_only", "punctuation_only", "cross_ref_only"]);
const VERDICT_RANK: Verdict[] = ["action_required", "optional_relaxed", "update_citation", "review", "info"];

/** Total custom-run duration and the stage boundaries (fraction of duration). */
export const CUSTOM_RUN_MS = 9000;
const STAGES: { stage: Stage; end: number }[] = [
  { stage: "delta", end: 0.15 },
  { stage: "characterize", end: 0.35 },
  { stage: "candidates", end: 0.55 },
  { stage: "judge", end: 0.85 },
  { stage: "ledger", end: 1 },
];

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const emptyData = (): RunData => ({ changes: [], candidates: [], findings: [], rollups: [], radar: [] });

function zeroStats(): RunStats {
  return {
    changes_raw: 0,
    by_class: {},
    substantive: 0,
    noise: 0,
    in_footprint: 0,
    obligation_changed: 0,
    candidates_by_path: {},
    findings_by_verdict: {},
    clauses_cleared: 0,
    docs_flagged: 0,
    docs_cleared: 0,
    radar: { applicable: 0, screened_out: 0, unclear: 0 },
    decided_by: { rule: 0, ai: 0 },
    llm_calls: 0,
  };
}

function presetAStats(): RunStats {
  return fixtures().runs.find((r) => r.run_id === PRESET_A_RUN_ID)?.stats ?? zeroStats();
}

// ---------- custom runs ----------

function customRunSnapshot(cr: CustomRun): Run {
  const stats = presetAStats();
  const base = {
    run_id: cr.run_id,
    kind: "whatif" as const,
    title: cr.title,
    scenario_id: cr.scenario_id,
    started_at: new Date(cr.started_at_ms).toISOString(),
  };
  const elapsed = Date.now() - cr.started_at_ms;
  if (elapsed >= CUSTOM_RUN_MS) {
    return {
      ...base,
      status: "succeeded",
      finished_at: new Date(cr.started_at_ms + CUSTOM_RUN_MS).toISOString(),
      progress: null,
      stats: clone(stats),
    };
  }
  const frac = Math.max(0, elapsed) / CUSTOM_RUN_MS;
  let idx = STAGES.findIndex((s) => frac < s.end);
  if (idx < 0) idx = STAGES.length - 1;
  const start = idx === 0 ? 0 : STAGES[idx - 1].end;
  const within = (frac - start) / (STAGES[idx].end - start);
  const nFind = Object.values(stats.findings_by_verdict).reduce((a, b) => a + b, 0);
  const nCand = Object.values(stats.candidates_by_path).reduce((a, b) => a + b, 0);
  const specs: Record<Stage, { total: number; label: string }> = {
    delta: { total: stats.changes_raw, label: "sections diffed" },
    characterize: { total: stats.substantive, label: "changes characterized" },
    candidates: { total: stats.in_footprint, label: "changes matched against clauses" },
    judge: { total: nCand, label: "candidate clauses judged" },
    ledger: { total: nFind, label: "findings written to the ledger" },
  };
  const { total, label } = specs[STAGES[idx].stage];
  const done = Math.min(total, Math.floor(total * within));
  return {
    ...base,
    status: "running",
    finished_at: null,
    progress: {
      stage: STAGES[idx].stage,
      done,
      total,
      message: `${done.toLocaleString("en-US")} of ${total.toLocaleString("en-US")} ${label}`,
    },
    stats: zeroStats(),
  };
}

const generated = new Map<string, RunData>();

function generatedData(cr: CustomRun): RunData {
  const hit = generated.get(cr.run_id);
  if (hit) return hit;
  const src = fixtures().runData[PRESET_A_RUN_ID] ?? emptyData();
  const suffix = `~${cr.run_id.replace("run_whatif_", "")}`;
  const data: RunData = clone(src);
  data.candidates = data.candidates.map((c) => ({
    ...c,
    run_id: cr.run_id,
    candidate_id: c.candidate_id + suffix,
    finding_id: c.finding_id ? c.finding_id + suffix : c.finding_id,
  }));
  data.findings = data.findings.map((f) => ({
    ...f,
    run_id: cr.run_id,
    finding_id: f.finding_id + suffix,
    propagated_from: f.propagated_from ? f.propagated_from + suffix : f.propagated_from,
    reviews: [],
  }));
  data.rollups = data.rollups.map((r) => ({ ...r, run_id: cr.run_id }));
  data.radar = data.radar.map((r) => ({ ...r, run_id: cr.run_id, radar_id: r.radar_id + suffix }));
  generated.set(cr.run_id, data);
  return data;
}

/** Data for a run, or null when the run id is unknown. Running custom runs have no results yet. */
function dataFor(run_id: string): RunData | null {
  const fx = fixtures().runData[run_id];
  if (fx) return fx;
  const cr = getState().customRuns.find((c) => c.run_id === run_id);
  if (!cr) return null;
  if (customRunSnapshot(cr).status !== "succeeded") return emptyData();
  return generatedData(cr);
}

function withReviews(f: Finding): Finding {
  const extra = getState().reviews[f.finding_id];
  return extra?.length ? { ...f, reviews: [...f.reviews, ...extra] } : f;
}

function allSucceededRunIds(): string[] {
  const ids = Object.keys(fixtures().runData);
  for (const cr of getState().customRuns) if (customRunSnapshot(cr).status === "succeeded") ids.push(cr.run_id);
  return ids;
}

function allScenarios(): Scenario[] {
  return [...fixtures().scenarios, ...getState().scenarios];
}

// ---------- API ----------

export const engineApi: EngineApi = {
  listRuns: () =>
    withLatency(() => [...fixtures().runs, ...getState().customRuns.map(customRunSnapshot)]),

  getRun: (run_id) =>
    withLatency(() => {
      const fx = fixtures().runs.find((r) => r.run_id === run_id);
      if (fx) return fx;
      const cr = getState().customRuns.find((c) => c.run_id === run_id);
      return cr ? customRunSnapshot(cr) : null;
    }),

  listChanges: (run_id) => withLatency(() => dataFor(run_id)?.changes ?? []),

  getChange: (run_id, change_id) =>
    withLatency(() => dataFor(run_id)?.changes.find((c) => c.change_id === change_id) ?? null),

  listCandidates: (run_id, q) =>
    withLatency(() =>
      (dataFor(run_id)?.candidates ?? []).filter(
        (c) => (!q?.change_id || c.change_id === q.change_id) && (!q?.doc_id || c.doc_id === q.doc_id),
      ),
    ),

  listFindings: (run_id, q) =>
    withLatency(() =>
      (dataFor(run_id)?.findings ?? [])
        .filter((f) => (!q?.doc_id || f.doc_id === q.doc_id) && (!q?.change_id || f.change_id === q.change_id))
        .map(withReviews),
    ),

  getFinding: (finding_id) =>
    withLatency(() => {
      for (const id of allSucceededRunIds()) {
        const f = dataFor(id)?.findings.find((x) => x.finding_id === finding_id);
        if (f) return withReviews(f);
      }
      return null;
    }),

  listRollups: (run_id) => withLatency(() => dataFor(run_id)?.rollups ?? []),

  getReader: (doc_id, run_id) =>
    withLatency(async (): Promise<Reader | null> => {
      const doc = fixtures().documents.find((d) => d.doc_id === doc_id);
      if (!doc) return null;
      const data = dataFor(run_id) ?? emptyData();
      const clauses = await loadClauses(doc_id);
      const annotations: Annotation[] = [];
      const changeCitation = new Map<string, string>(data.changes.map((c) => [c.change_id, c.citation]));
      for (const f of data.findings) {
        if (f.doc_id !== doc_id) continue;
        annotations.push({
          clause_id: f.clause_id,
          kind: "finding",
          verdict: f.verdict,
          finding_id: f.finding_id,
          change_id: f.change_id,
          citation: f.citation,
          quote_span: f.quotes.clause.span ?? null,
          reason: f.rationale,
        });
      }
      for (const c of data.candidates) {
        if (c.doc_id !== doc_id || c.outcome !== "cleared") continue;
        const reason = [c.skip_reason, c.rationale].filter(Boolean).join(": ") || "Checked: no impact.";
        annotations.push({
          clause_id: c.clause_id,
          kind: "cleared",
          verdict: null,
          finding_id: null,
          change_id: c.change_id,
          citation: changeCitation.get(c.change_id) ?? "",
          quote_span: null,
          reason,
        });
      }
      return { doc, clauses, annotations };
    }),

  getMatrix: (run_id, opts) =>
    withLatency((): Matrix => {
      const data = dataFor(run_id) ?? emptyData();
      const docs = fixtures()
        .documents.filter((d) => d.monitored)
        .sort((a, b) => a.doc_id.localeCompare(b.doc_id));
      const docIds = new Set(docs.map((d) => d.doc_id));
      const changes: ChangeRecord[] = data.changes.filter(
        (c) => c.in_footprint && (opts?.include_noise || !NOISE.has(c.change_class)),
      );
      const changeIds = new Set(changes.map((c) => c.change_id));
      const cells = new Map<string, MatrixCell>();
      for (const cand of data.candidates) {
        if (!docIds.has(cand.doc_id) || !changeIds.has(cand.change_id)) continue;
        const key = `${cand.doc_id}|${cand.change_id}`;
        const cell =
          cells.get(key) ??
          ({ doc_id: cand.doc_id, change_id: cand.change_id, worst_verdict: "cleared", n_findings: 0, n_cleared: 0 } as MatrixCell);
        if (cand.outcome === "cleared") cell.n_cleared += 1;
        else {
          cell.n_findings += 1;
          const f = cand.finding_id ? data.findings.find((x) => x.finding_id === cand.finding_id) : undefined;
          if (f) {
            const cur = cell.worst_verdict === "cleared" ? 99 : VERDICT_RANK.indexOf(cell.worst_verdict);
            if (VERDICT_RANK.indexOf(f.verdict) < cur) cell.worst_verdict = f.verdict;
          }
        }
        cells.set(key, cell);
      }
      return { docs, changes, cells: [...cells.values()] };
    }),

  listRadar: (run_id) => withLatency(() => dataFor(run_id)?.radar ?? []),

  listScenarios: () => withLatency(() => allScenarios()),

  saveScenario: (s) =>
    withLatency(() => {
      const st = getState();
      if (s.scenario_id) {
        const idx = st.scenarios.findIndex((x) => x.scenario_id === s.scenario_id);
        if (idx >= 0) {
          const updated: Scenario = { ...st.scenarios[idx], ...s, scenario_id: s.scenario_id };
          st.scenarios[idx] = updated;
          persist();
          return updated;
        }
        if (fixtures().scenarios.some((x) => x.scenario_id === s.scenario_id)) {
          throw new Error("Preset scenarios cannot be modified; save a copy instead.");
        }
      }
      const n = st.scenarios.length + 1;
      const created: Scenario = {
        ...s,
        scenario_id: s.scenario_id ?? `scn_custom_${n}`,
        is_preset: false,
        last_run_id: null,
      };
      st.scenarios.push(created);
      persist();
      return created;
    }),

  startWhatIf: (scenario_id) =>
    withLatency(() => {
      const st = getState();
      const sc = allScenarios().find((x) => x.scenario_id === scenario_id);
      if (!sc) throw new Error(`Unknown scenario ${scenario_id}`);
      if (sc.is_preset && sc.last_run_id) {
        const run = fixtures().runs.find((r) => r.run_id === sc.last_run_id);
        if (run) return run;
      }
      const cr: CustomRun = {
        run_id: `run_whatif_custom_${st.customRuns.length + 1}`,
        scenario_id,
        title: sc.title,
        started_at_ms: Date.now(),
      };
      st.customRuns.push(cr);
      const mine = st.scenarios.find((x) => x.scenario_id === scenario_id);
      if (mine) mine.last_run_id = cr.run_id;
      persist();
      return customRunSnapshot(cr);
    }),

  getScore: () => withLatency(() => fixtures().score),

  submitReview: (finding_id, decision, note) =>
    withLatency(() => {
      let found: Finding | undefined;
      for (const id of allSucceededRunIds()) {
        found = dataFor(id)?.findings.find((x) => x.finding_id === finding_id);
        if (found) break;
      }
      if (!found) throw new Error(`Unknown finding ${finding_id}`);
      const st = getState();
      (st.reviews[finding_id] ??= []).push({ decision, note: note ?? null, at: new Date().toISOString() });
      persist();
      return withReviews(found);
    }),
};

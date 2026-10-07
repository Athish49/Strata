import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { clauseSchema, companyProfileSchema, documentMetaSchema } from "@/lib/api/schemas/company";
import {
  candidateSchema,
  changeRecordSchema,
  docRollupSchema,
  findingSchema,
  radarItemSchema,
  runSchema,
  scoreReportSchema,
} from "@/lib/api/schemas/engine";

const FX = path.resolve(__dirname, "../../fixtures");
const load = (f: string) => JSON.parse(readFileSync(path.join(FX, f), "utf8"));

const runs = runSchema.array().parse(load("engine/runs.json"));
const score = scoreReportSchema.parse(load("engine/score.json"));
const docs = documentMetaSchema.array().parse(load("company/documents.json"));
const profile = companyProfileSchema.parse(load("company/profile.json"));
const clauseIds = new Set<string>();
const docOfClause = new Map<string, string>();
for (const f of readdirSync(path.join(FX, "company/clauses"))) {
  for (const c of clauseSchema.array().parse(load(`company/clauses/${f}`))) {
    clauseIds.add(c.clause_id);
    docOfClause.set(c.clause_id, c.doc_id);
  }
}
const docIds = new Set(docs.map((d) => d.doc_id));

function runData(id: string) {
  const d = `engine/${id}`;
  return {
    changes: changeRecordSchema.array().parse(load(`${d}/changes.json`)),
    candidates: candidateSchema.array().parse(load(`${d}/candidates.json`)),
    findings: findingSchema.array().parse(load(`${d}/findings.json`)),
    rollups: docRollupSchema.array().parse(load(`${d}/rollups.json`)),
    radar: radarItemSchema.array().parse(load(`${d}/radar.json`)),
  };
}

const real = runData("run_kb_real");
const base = runData("run_baseline");
const realRun = runs.find((r) => r.run_id === "run_kb_real")!;
const baseRun = runs.find((r) => r.run_id === "run_baseline")!;
const NOISE = ["cosmetic", "metadata_only", "punctuation_only", "cross_ref_only"];
const REAL = ["substantive", "repealed", "renumbered", "new_section"];
const MONITORED_IN_WAVE = ["RPL-REG-CAL-2025", "RPL-CS-PRO-011", "RPL-CS-PRO-004"];

describe("runs.json and score.json", () => {
  it("has the real wave and the baseline", () => {
    expect(realRun.title).toBe("Real wave · S1→S2");
    expect(realRun.kind).toBe("kb");
    expect(realRun.status).toBe("succeeded");
    expect(baseRun.title).toBe("Baseline · S1 vs S1");
    expect(baseRun.kind).toBe("baseline");
    expect(new Set(runs.map((r) => r.run_id)).size).toBe(runs.length);
  });
  it("meets the score targets", () => {
    expect(score.precision).toBeGreaterThanOrEqual(score.targets.precision);
    expect(score.recall).toBeGreaterThanOrEqual(score.targets.recall);
    expect(score.fp_rate_must_not_flag).toBe(0);
    expect(score.routing_accuracy).toBeGreaterThanOrEqual(score.targets.routing);
    expect(score.baseline_findings).toBe(0);
    expect(score.baseline_findings).toBe(baseRun.stats.findings_by_verdict.action_required ?? 0);
  });
});

describe("real wave funnel", () => {
  const st = realRun.stats;
  it("sums add up", () => {
    expect(st.changes_raw).toBe(1114);
    expect(st.substantive + st.noise).toBe(st.changes_raw);
    expect(Object.values(st.by_class).reduce((a, b) => a + b, 0)).toBe(st.changes_raw);
    expect(REAL.reduce((a, k) => a + (st.by_class[k] ?? 0), 0)).toBe(st.substantive);
    expect(NOISE.reduce((a, k) => a + (st.by_class[k] ?? 0), 0)).toBe(st.noise);
    expect(st.substantive).toBe(491);
    expect(st.noise).toBe(623);
    expect(st.by_class.cosmetic).toBe(590);
  });
  it("radar totals equal substantive changes outside the footprint", () => {
    const inFootSubst = real.changes.filter((c) => c.in_footprint && REAL.includes(c.change_class)).length;
    expect(st.radar.applicable + st.radar.screened_out + st.radar.unclear).toBe(st.substantive - inFootSubst);
  });
  it("has exactly 8 in-footprint changes in the list", () => {
    const inFoot = real.changes.filter((c) => c.in_footprint);
    expect(inFoot).toHaveLength(8);
    expect(st.in_footprint).toBe(8);
    expect(inFoot.map((c) => c.citation).sort()).toEqual(
      ["170 IAC 1-6-3", "170 IAC 1-6-4", "170 IAC 1-6-5", "170 IAC 16-1-4", "170 IAC 16-1-5", "170 IAC 16-1-7", "170 IAC 4-1-13", "170 IAC 4-1-16"].sort(),
    );
  });
  it("obligation_changed matches the in-footprint characterizations", () => {
    const n = real.changes.filter((c) => c.in_footprint && c.characterization?.obligation_changed).length;
    expect(st.obligation_changed).toBe(n);
  });
  it("has 0 action-required findings and findings_by_verdict equals the list", () => {
    expect(real.findings.filter((f) => f.verdict === "action_required")).toHaveLength(0);
    for (const v of ["action_required", "optional_relaxed", "update_citation", "review", "info"]) {
      expect(st.findings_by_verdict[v] ?? 0).toBe(real.findings.filter((f) => f.verdict === v).length);
    }
    expect(st.docs_flagged).toBe(new Set(real.findings.map((f) => f.doc_id)).size);
  });
  it("decided_by totals match the candidates", () => {
    expect(st.decided_by.rule + st.decided_by.ai).toBe(real.candidates.length);
    expect(st.llm_calls).toBeGreaterThanOrEqual(st.decided_by.ai);
  });
});

describe("real wave changes", () => {
  const ids = new Set(real.changes.map((c) => c.change_id));
  it("has unique ids and covers the demo anchors", () => {
    expect(ids.size).toBe(real.changes.length);
    for (const c of ["326 IAC 2-8-4", "40 CFR 60.4320", "18 CFR 35.28"]) {
      expect(real.changes.some((x) => x.citation === c && !x.in_footprint)).toBe(true);
    }
    for (const a of ["ferc", "epa", "iurc", "idem"]) expect(real.changes.some((c) => c.agency_id === a)).toBe(true);
    for (const k of [...REAL, ...NOISE]) expect(real.changes.some((c) => c.change_class === k)).toBe(true);
  });
  it("builds diff_segments consistent with s1/s2 text", () => {
    for (const c of real.changes) {
      const s1 = c.diff_segments.filter((s) => s.op !== "insert").map((s) => s.text).join("");
      const s2 = c.diff_segments.filter((s) => s.op !== "delete").map((s) => s.text).join("");
      expect(s1, c.change_id).toBe(c.s1_text);
      expect(s2, c.change_id).toBe(c.s2_text);
    }
  });
  it("has the 94-clause cosmetic change with a stamp-only diff", () => {
    const c = real.changes.find((x) => x.citation === "170 IAC 4-1-13")!;
    expect(c.change_class).toBe("cosmetic");
    expect(c.cited_clause_count).toBe(94);
    const changed = c.diff_segments.filter((s) => s.op !== "equal");
    expect(changed.every((s) => s.op === "insert" && /readopted/.test(s.text))).toBe(true);
    expect(c.disposition).toMatch(/Cleared/);
  });
  it("has the style-only rewording", () => {
    const c = real.changes.find((x) => x.citation === "170 IAC 4-1-16")!;
    expect(c.characterization?.direction).toBe("style_only");
    expect(c.characterization?.obligation_changed).toBe(false);
    expect(c.diff_segments.some((s) => s.op === "delete" && s.text.includes("shall"))).toBe(true);
    expect(c.diff_segments.some((s) => s.op === "insert" && s.text.includes("may"))).toBe(true);
  });
  it("cited_clause_count equals candidates; out-of-footprint is 0 and dispositioned", () => {
    for (const c of real.changes) {
      expect(c.cited_clause_count).toBe(real.candidates.filter((x) => x.change_id === c.change_id).length);
      if (!c.in_footprint) expect(c.cited_clause_count).toBe(0);
      expect(c.disposition.length).toBeGreaterThan(0);
      expect(c.disposition_reason.length).toBeGreaterThan(0);
    }
  });
});

describe("real wave candidates", () => {
  it("has 162 cleared candidates, 94 for 4-1-13", () => {
    expect(real.candidates).toHaveLength(162);
    expect(realRun.stats.clauses_cleared).toBe(162);
    const c13 = real.changes.find((c) => c.citation === "170 IAC 4-1-13")!;
    expect(real.candidates.filter((c) => c.change_id === c13.change_id)).toHaveLength(94);
  });
  it("references real clauses, docs and changes; each clause once per change", () => {
    const changeIds = new Set(real.changes.map((c) => c.change_id));
    const seen = new Set<string>();
    for (const c of real.candidates) {
      expect(clauseIds.has(c.clause_id), c.clause_id).toBe(true);
      expect(docIds.has(c.doc_id)).toBe(true);
      expect(docOfClause.get(c.clause_id)).toBe(c.doc_id);
      expect(changeIds.has(c.change_id)).toBe(true);
      expect(real.changes.find((x) => x.change_id === c.change_id)!.in_footprint).toBe(true);
      expect(c.run_id).toBe("run_kb_real");
      const k = `${c.change_id}|${c.clause_id}`;
      expect(seen.has(k)).toBe(false);
      seen.add(k);
      expect(MONITORED_IN_WAVE).toContain(c.doc_id);
      expect(c.path_detail.length).toBeGreaterThanOrEqual(2);
      expect(c.path_detail[c.path_detail.length - 1].ref).toBe(c.clause_id);
    }
    expect(new Set(real.candidates.map((c) => c.candidate_id)).size).toBe(real.candidates.length);
  });
  it("every candidate has an outcome; cleared ones have a reason", () => {
    for (const c of real.candidates) {
      expect(["affected", "cleared"]).toContain(c.outcome);
      if (c.outcome === "cleared") expect(Boolean(c.skip_reason) || Boolean(c.rationale)).toBe(true);
      expect(c.outcome === "cleared").toBe(true);
    }
  });
  it("candidates_by_path equals tallies", () => {
    const tally: Record<string, number> = {};
    for (const c of real.candidates) tally[c.match_path] = (tally[c.match_path] ?? 0) + 1;
    for (const k of Object.keys(realRun.stats.candidates_by_path)) {
      expect(realRun.stats.candidates_by_path[k]).toBe(tally[k] ?? 0);
    }
    expect(Object.values(realRun.stats.candidates_by_path).reduce((a, b) => a + b, 0)).toBe(162);
  });
});

describe("real wave rollups and radar", () => {
  it("rolls up the 3 documents with candidates, all cleared", () => {
    expect(real.rollups.map((r) => r.doc_id).sort()).toEqual([...MONITORED_IN_WAVE].sort());
    for (const r of real.rollups) {
      expect(r.status).toBe("cleared");
      const ch = new Set(real.candidates.filter((c) => c.doc_id === r.doc_id).map((c) => c.change_id));
      expect(r.changes_considered).toBe(ch.size);
      expect(Object.values(r.considered_by_class).reduce((a, b) => a + b, 0)).toBe(ch.size);
      expect(r.cleared_reason).toMatch(new RegExp(`^${ch.size} change`));
    }
    expect(realRun.stats.docs_cleared).toBe(real.rollups.filter((r) => r.status === "cleared").length);
    expect(realRun.stats.docs_flagged).toBe(real.rollups.filter((r) => r.status === "flagged").length);
  });
  it("has valid radar items with real attribute keys and quotes from S2", () => {
    const keys = new Set(profile.attributes.map((a) => a.key));
    const byId = new Map(real.changes.map((c) => [c.change_id, c]));
    expect(real.radar.length).toBeGreaterThanOrEqual(12);
    for (const r of real.radar) {
      const ch = byId.get(r.change_id)!;
      expect(ch, r.radar_id).toBeDefined();
      expect(ch.in_footprint).toBe(false);
      expect(ch.citation).toBe(r.citation);
      expect(ch.s2_text).toContain(r.quote);
      for (const a of r.attribute_basis) {
        expect(keys.has(a.key), a.key).toBe(true);
        expect(profile.attributes.find((p) => p.key === a.key)!.value).toBe(a.value);
      }
      for (const d of r.docs_covering_same_rule) expect(docIds.has(d)).toBe(true);
    }
    const by = (a: string) => real.radar.filter((r) => r.applicable === a);
    expect(by("yes").length).toBeGreaterThanOrEqual(3);
    expect(by("no").length).toBeGreaterThan(by("yes").length);
    expect(by("unclear").length).toBeGreaterThanOrEqual(2);
    const eng = real.radar.find((r) => r.citation === "326 IAC 2-8-4")!;
    expect(eng.applicable).toBe("yes");
    expect(eng.attribute_basis).toContainEqual({ key: "standby_generator_count", value: 3 });
    const tur = real.radar.find((r) => r.citation === "40 CFR 60.4320")!;
    expect(tur.applicable).toBe("no");
    expect(tur.attribute_basis).toContainEqual({ key: "owns_generating_units", value: false });
    expect(real.radar.some((r) => r.agency_id === "iurc" && r.applicable === "yes")).toBe(true);
  });
});

describe("baseline", () => {
  it("is empty with all-zero stats", () => {
    for (const k of Object.keys(base) as (keyof typeof base)[]) expect(base[k]).toHaveLength(0);
    const st = baseRun.stats;
    expect(st.changes_raw).toBe(0);
    expect(st.substantive + st.noise + st.in_footprint + st.obligation_changed + st.clauses_cleared).toBe(0);
    expect(st.docs_flagged + st.docs_cleared + st.llm_calls).toBe(0);
    expect(Object.values(st.by_class).every((n) => n === 0)).toBe(true);
    expect(Object.values(st.findings_by_verdict).every((n) => n === 0)).toBe(true);
    expect(st.radar).toEqual({ applicable: 0, screened_out: 0, unclear: 0 });
  });
});

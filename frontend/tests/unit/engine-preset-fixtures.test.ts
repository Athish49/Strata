import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { diffWords } from "diff";
import { z } from "zod";
import {
  candidateSchema,
  changeRecordSchema,
  docRollupSchema,
  findingSchema,
  radarItemSchema,
  runSchema,
  scenarioSchema,
  type Finding,
} from "@/lib/api/schemas/engine";
import { clauseSchema, documentMetaSchema } from "@/lib/api/schemas/company";

const FX = path.resolve(__dirname, "../../fixtures");
const load = (p: string): unknown => JSON.parse(readFileSync(path.join(FX, p), "utf8"));

const documents = z.array(documentMetaSchema).parse(load("company/documents.json"));
const monitored = new Map(documents.filter((d) => d.monitored).map((d) => [d.doc_id, d]));
const clausesByDoc = new Map<string, Map<string, z.infer<typeof clauseSchema>>>();
for (const d of monitored.values()) {
  clausesByDoc.set(d.doc_id, new Map(z.array(clauseSchema).parse(load(`company/clauses/${d.doc_id}.json`)).map((c) => [c.clause_id, c])));
}
const allClauseIds = new Set([...clausesByDoc.values()].flatMap((m) => [...m.keys()]));
const scenarios = z.array(scenarioSchema).parse(load("engine/scenarios.json"));

function loadRun(letter: "a" | "b") {
  const dir = `engine/run_whatif_preset_${letter}`;
  return {
    run: runSchema.parse(load(`${dir}/run.json`)),
    changes: z.array(changeRecordSchema).parse(load(`${dir}/changes.json`)),
    candidates: z.array(candidateSchema).parse(load(`${dir}/candidates.json`)),
    findings: z.array(findingSchema).parse(load(`${dir}/findings.json`)),
    rollups: z.array(docRollupSchema).parse(load(`${dir}/rollups.json`)),
    radar: z.array(radarItemSchema).parse(load(`${dir}/radar.json`)),
  };
}
const tally = <T,>(xs: T[], key: (x: T) => string) => {
  const o: Record<string, number> = {};
  for (const x of xs) o[key(x)] = (o[key(x)] ?? 0) + 1;
  return o;
};

describe("scenarios.json", () => {
  it("has exactly the two presets pointing at their runs", () => {
    expect(scenarios).toHaveLength(2);
    expect(scenarios.every((s) => s.is_preset)).toBe(true);
    const a = scenarios.find((s) => s.edit_kind === "text_edit")!;
    const b = scenarios.find((s) => s.edit_kind === "repeal")!;
    expect(a.last_run_id).toBe("run_whatif_preset_a");
    expect(b.last_run_id).toBe("run_whatif_preset_b");
    expect(a.citation).toBe("170 IAC 4-1-16");
    expect(a.title).toMatch(/14 → 20/);
    expect(a.edited_text).toContain("twenty (20) days");
    expect(b.citation).toBe("170 IAC 4-1-16.6");
    expect(b.edited_text ?? null).toBeNull();
  });
});

for (const letter of ["a", "b"] as const) {
  describe(`preset ${letter.toUpperCase()}`, () => {
    const d = loadRun(letter);
    const scenario = scenarios.find((s) => s.last_run_id === d.run.run_id)!;

    it("run metadata and stats are consistent with the data", () => {
      const { run, findings, candidates, rollups } = d;
      expect(run.kind).toBe("whatif");
      expect(run.status).toBe("succeeded");
      expect(run.scenario_id).toBe(scenario.scenario_id);
      expect(run.title).toBe(scenario.title);
      const s = run.stats;
      expect(s.changes_raw).toBe(1);
      expect(s.in_footprint).toBe(1);
      expect(s.obligation_changed).toBe(1);
      expect(s.substantive + s.noise).toBe(s.changes_raw);
      expect(Object.values(s.by_class).reduce((a, b) => a + b, 0)).toBe(s.changes_raw);
      expect(s.candidates_by_path).toEqual(tally(candidates, (c) => c.match_path));
      expect(s.findings_by_verdict).toEqual(tally(findings, (f) => f.verdict));
      expect(s.clauses_cleared).toBe(candidates.filter((c) => c.outcome === "cleared").length);
      expect(s.docs_flagged).toBe(rollups.filter((r) => r.status === "flagged").length);
      expect(s.docs_cleared).toBe(rollups.filter((r) => r.status === "cleared").length);
      expect(s.radar).toEqual({ applicable: 0, screened_out: 0, unclear: 0 });
      expect(s.decided_by).toEqual({
        rule: findings.filter((f) => f.decided_by === "rule").length,
        ai: findings.filter((f) => f.decided_by === "ai").length,
      });
      expect(s.llm_calls).toBeGreaterThanOrEqual(s.decided_by.ai);
      expect(d.radar).toEqual([]);
    });

    it("change record diff segments reproduce S1 and S2 and match jsdiff", () => {
      expect(d.changes).toHaveLength(1);
      const ch = d.changes[0];
      expect(ch.in_footprint).toBe(true);
      expect(ch.citation).toBe(scenario.citation);
      expect(ch.diff_segments.filter((x) => x.op !== "insert").map((x) => x.text).join("")).toBe(ch.s1_text);
      expect(ch.diff_segments.filter((x) => x.op !== "delete").map((x) => x.text).join("")).toBe(ch.s2_text);
      const expected = diffWords(ch.s1_text, ch.s2_text).map((p) => (p.added ? "insert" : p.removed ? "delete" : "equal"));
      expect(ch.diff_segments.map((x) => x.op)).toEqual(expected);
      expect(ch.cited_clause_count).toBe(d.candidates.length);
    });

    it("every referenced doc and clause exists and docs are monitored", () => {
      for (const c of [...d.candidates, ...d.findings]) {
        expect(monitored.has(c.doc_id), c.doc_id).toBe(true);
        expect(clausesByDoc.get(c.doc_id)!.has(c.clause_id), c.clause_id).toBe(true);
      }
      for (const f of d.findings) for (const n of f.path_detail) {
        if (["clause", "register_row", "form_field", "tariff_rule"].includes(n.kind)) expect(allClauseIds.has(n.ref), n.ref).toBe(true);
      }
      for (const r of d.rollups) expect(monitored.has(r.doc_id)).toBe(true);
    });

    it("candidates have outcomes, reasons and link to findings", () => {
      const ids = new Set(d.findings.map((f) => f.finding_id));
      expect(new Set(d.candidates.map((c) => c.candidate_id)).size).toBe(d.candidates.length);
      for (const c of d.candidates) {
        if (c.outcome === "cleared") {
          expect(c.skip_reason, c.candidate_id).toBeTruthy();
          expect(c.rationale, c.candidate_id).toBeTruthy();
          expect(c.finding_id ?? null).toBeNull();
        } else {
          expect(ids.has(c.finding_id!)).toBe(true);
          const f = d.findings.find((x) => x.finding_id === c.finding_id)!;
          expect(f.clause_id).toBe(c.clause_id);
        }
      }
      expect(d.candidates.filter((c) => c.outcome === "affected")).toHaveLength(d.findings.length);
      const keys = d.candidates.map((c) => `${c.change_id}|${c.clause_id}`);
      expect(new Set(keys).size).toBe(keys.length);
    });

    it("quote spans index into the exact S1/S2/clause text", () => {
      const ch = d.changes[0];
      for (const f of d.findings) {
        const clause = clausesByDoc.get(f.doc_id)!.get(f.clause_id)!;
        const check = (q: Finding["quotes"]["s1"], text: string) => {
          if (q.span) expect(text.slice(q.span[0], q.span[1]), f.finding_id).toBe(q.text);
        };
        check(f.quotes.s1, ch.s1_text);
        check(f.quotes.s2, ch.s2_text);
        check(f.quotes.clause, clause.text_raw);
        expect(f.quotes.s1.span).toBeTruthy();
        expect(f.quotes.s2.span).toBeTruthy();
        if (f.quotes_verified) expect(f.quotes.clause.span, f.finding_id).toBeTruthy();
        else expect(f.quotes.clause.span ?? null).toBeNull();
      }
    });

    it("route, dates and propagation are consistent", () => {
      const ids = new Set(d.findings.map((f) => f.finding_id));
      expect(ids.size).toBe(d.findings.length);
      for (const f of d.findings) {
        const doc = monitored.get(f.doc_id)!;
        expect(f.run_id).toBe(d.run.run_id);
        expect(f.change_id).toBe(d.changes[0].change_id);
        expect(f.route.owner.person_id).toBe(doc.owner.person_id);
        expect(f.route.reviewer.person_id).toBe(doc.reviewer.person_id);
        if (doc.two_signature) expect(f.route.approver).toBeNull();
        else expect(f.route.approver?.person_id).toBe(doc.approver?.person_id);
        expect(f.doc_approved_date).toBe(doc.approved_date);
        expect(f.stale_at_approval).toBe(f.rule_published_date < (doc.approved_date ?? ""));
        expect(f.reviews).toEqual([]);
        if (f.propagated_from) {
          expect(ids.has(f.propagated_from)).toBe(true);
          expect(f.propagated_from).not.toBe(f.finding_id);
        }
      }
      for (const r of d.rollups) {
        const fs = d.findings.filter((f) => f.doc_id === r.doc_id);
        expect(r.status).toBe(fs.length ? "flagged" : "cleared");
        expect(r.counts_by_verdict).toEqual(tally(fs, (f) => f.verdict));
        expect(r.changes_considered).toBe(1);
        if (!fs.length) expect(r.cleared_reason).toBeTruthy();
      }
      expect(new Set(d.rollups.map((r) => r.doc_id))).toEqual(new Set(d.candidates.map((c) => c.doc_id)));
    });
  });
}

describe("preset A coverage", () => {
  const d = loadRun("a");
  const byId = new Map(d.findings.map((f) => [f.finding_id, f]));
  const status = (doc: string) => {
    const r = d.rollups.find((x) => x.doc_id === doc)!;
    const fs = d.findings.filter((f) => f.doc_id === doc);
    return r.status === "flagged" ? (fs.some((f) => f.verdict === "action_required") ? "action" : "review") : "cleared";
  };

  it("has 10-15 findings and the notice-period characterization", () => {
    expect(d.findings.length).toBeGreaterThanOrEqual(10);
    expect(d.findings.length).toBeLessThanOrEqual(15);
    const ch = d.changes[0];
    expect(ch.change_class).toBe("substantive");
    expect(ch.characterization?.direction).toBe("tightened");
    expect(ch.characterization?.value_changes[0]).toMatchObject({ old: "14", new: "20", unit: "days" });
  });
  it("flags the three demo documents", () => {
    for (const doc of ["RPL-CS-PRO-004", "RPL-CMP-REG-001", "RPL-REG-CAL-2025"]) expect(status(doc)).not.toBe("cleared");
    expect(status("RPL-CS-PRO-004")).toBe("action");
  });
  it("covers a notice-letter form field in PRO-004 App-A", () => {
    const f = d.findings.find((x) => x.doc_id === "RPL-CS-PRO-004" && clausesByDoc.get(x.doc_id)!.get(x.clause_id)!.unit_kind === "form_field");
    expect(f).toBeTruthy();
    expect(f!.clause_id).toContain("App-A");
  });
  it("covers an obligation register row and a calendar event row", () => {
    expect(d.findings.some((f) => f.doc_id === "RPL-CMP-REG-001" && clausesByDoc.get(f.doc_id)!.get(f.clause_id)!.unit_kind === "register_row")).toBe(true);
    expect(d.findings.some((f) => f.doc_id === "RPL-REG-CAL-2025" && clausesByDoc.get(f.doc_id)!.get(f.clause_id)!.unit_kind === "register_row")).toBe(true);
  });
  it("has an AI finding at 0.82, an unverified quote, and a stale-at-approval finding", () => {
    expect(d.findings.some((f) => f.decided_by === "ai" && f.confidence === 0.82)).toBe(true);
    expect(d.findings.some((f) => !f.quotes_verified && f.verdict === "review")).toBe(true);
    expect(d.findings.some((f) => f.stale_at_approval)).toBe(true);
  });
  it("has a propagated chain register row -> procedure -> form field", () => {
    const field = d.findings.find((f) => f.propagated_from && clausesByDoc.get(f.doc_id)!.get(f.clause_id)!.unit_kind === "form_field")!;
    expect(field.path_detail.map((n) => n.kind)).toEqual(["section", "register_row", "clause", "form_field"]);
    const proc = byId.get(field.propagated_from!)!;
    expect(clausesByDoc.get(proc.doc_id)!.get(proc.clause_id)!.unit_kind).toBe("section");
    const row = byId.get(proc.propagated_from!)!;
    expect(clausesByDoc.get(row.doc_id)!.get(row.clause_id)!.unit_kind).toBe("register_row");
  });
  it("covers all four match paths and several verdicts", () => {
    expect(new Set(d.findings.map((f) => f.match_path))).toEqual(new Set(["direct_section", "direct_rule", "register_hop", "value_echo"]));
    const verdicts = new Set(d.findings.map((f) => f.verdict));
    for (const v of ["action_required", "update_citation", "review", "info"]) expect(verdicts.has(v as never)).toBe(true);
  });
  it("includes cleared clauses with reasons", () => {
    expect(d.candidates.filter((c) => c.outcome === "cleared").length).toBeGreaterThanOrEqual(10);
  });
});

describe("preset B coverage", () => {
  const d = loadRun("b");
  it("is a repeal of 170 IAC 4-1-16.6 with mostly update_citation/review findings", () => {
    expect(d.changes[0].change_class).toBe("repealed");
    expect(d.changes[0].characterization?.direction).toBe("removed");
    expect(d.findings.length).toBeGreaterThanOrEqual(5);
    const soft = d.findings.filter((f) => f.verdict === "update_citation" || f.verdict === "review").length;
    expect(soft / d.findings.length).toBeGreaterThan(0.6);
    expect(d.findings.filter((f) => f.verdict === "action_required")).toHaveLength(1);
  });
  it("has a propagated finding resolving inside the run", () => {
    const p = d.findings.find((f) => f.propagated_from);
    expect(p).toBeTruthy();
    expect(d.findings.some((f) => f.finding_id === p!.propagated_from)).toBe(true);
  });
});

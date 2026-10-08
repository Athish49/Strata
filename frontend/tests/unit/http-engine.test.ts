import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../lib/api/http/company", () => ({
  companyHttp: {
    getDocument: vi.fn(),
    listClauses: vi.fn(),
    listDocuments: vi.fn(),
    listPeople: vi.fn(),
    getProfile: vi.fn(),
  },
}));

import { companyHttp } from "../../lib/api/http/company";
import { engineHttp } from "../../lib/api/http/engine";
import { ApiError } from "../../lib/api/http/shared";

const person = (id: string) => ({ person_id: id, name: id, title: "t", department: "d", reports_to_id: null });
const stats = {
  changes_raw: 0, by_class: {}, substantive: 0, noise: 0, in_footprint: 0, obligation_changed: 0,
  candidates_by_path: {}, findings_by_verdict: {}, clauses_cleared: 0, docs_flagged: 0, docs_cleared: 0,
  radar: { applicable: 0, screened_out: 0, unclear: 0 }, decided_by: { rule: 0, ai: 0 }, llm_calls: 0,
};
const run = (id: string, status = "succeeded") => ({
  run_id: id, kind: "whatif", title: "t", status, started_at: "2026-01-01T00:00:00Z", finished_at: null, stats,
});
const finding = (id: string, reviewer: ReturnType<typeof person> | null = person("P02")) => ({
  finding_id: id, run_id: "r1", change_id: "c1", clause_id: "D:1", doc_id: "D", citation: "170 IAC 4-1-16",
  finding_type: "x", verdict: "review", severity: "low", confidence: null, decided_by: "rule",
  required_change: { from_text: "", to_text: "" },
  quotes: { s1: { text: "" }, s2: { text: "" }, clause: { text: "" } },
  quotes_verified: false, rationale: "r", match_path: "direct_section", path_detail: [],
  stale_at_approval: false, doc_approved_date: null, rule_published_date: null,
  route: { owner: person("P01"), reviewer, approver: null }, reviews: [],
});
const doc = (doc_id: string, monitored = true) => ({ doc_id, monitored });
const sections = [
  { citation: "170 IAC 4-1-16", source_system: "iac", heading: "H", cited_clause_count: 3, s1_section_id: 42 },
];

type Call = { method: string; path: string; body: unknown };
let calls: Call[];
let routes: Record<string, (call: Call) => { status?: number; body?: unknown }>;

beforeEach(() => {
  calls = [];
  routes = {};
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const u = new URL(url);
      const call: Call = {
        method: init?.method ?? "GET",
        path: u.pathname + u.search,
        body: init?.body ? JSON.parse(init.body as string) : undefined,
      };
      calls.push(call);
      const h = routes[`${call.method} ${call.path}`];
      const r = h ? h(call) : { status: 404, body: { detail: "nf" } };
      return new Response(JSON.stringify(r.body ?? null), { status: r.status ?? 200, headers: { "Content-Type": "application/json" } });
    }),
  );
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
  vi.clearAllMocks();
});

describe("engineHttp status mapping", () => {
  it("passes 5xx through as ApiError with status", async () => {
    routes["GET /engine/ui/runs?collapse=true"] = () => ({ status: 500, body: { detail: "boom" } });
    await expect(engineHttp.listRuns()).rejects.toMatchObject({ status: 500, detail: "boom" });
    await expect(engineHttp.listRuns()).rejects.toBeInstanceOf(ApiError);
  });
  it("409 gives empty results, 404 gives null / empty", async () => {
    routes["GET /engine/ui/runs/r1/changes"] = () => ({ status: 409, body: { detail: "running" } });
    routes["GET /engine/ui/runs/r1/findings"] = () => ({ status: 409 });
    routes["GET /engine/ui/runs/r1/score"] = () => ({ status: 409 });
    expect(await engineHttp.listChanges("r1")).toEqual([]);
    expect(await engineHttp.listFindings("r1")).toEqual([]);
    expect(await engineHttp.getScore("r1")).toBeNull();
    expect(await engineHttp.getRun("nope")).toBeNull();
    expect(await engineHttp.getFinding("nope")).toBeNull();
    expect(await engineHttp.getChange("r1", "nope")).toBeNull();
    expect(await engineHttp.listRadar("nope")).toEqual([]);
  });
  it("getScore accepts JSON null and builds query strings", async () => {
    routes["GET /engine/ui/runs/r1/score"] = () => ({ body: null });
    expect(await engineHttp.getScore("r1")).toBeNull();
    routes["GET /engine/ui/runs/r1/candidates?change_id=c%201&doc_id=D"] = () => ({ body: [] });
    expect(await engineHttp.listCandidates("r1", { change_id: "c 1", doc_id: "D" })).toEqual([]);
  });
});

describe("matrix and reader composition", () => {
  it("getMatrix filters monitored docs, sorts by doc_id, merges backend changes/cells", async () => {
    vi.mocked(companyHttp.listDocuments).mockResolvedValue([doc("B"), doc("C", false), doc("A")] as never);
    routes["GET /engine/ui/runs/r1/matrix?include_noise=true"] = () => ({ body: { changes: [], cells: [] } });
    const m = await engineHttp.getMatrix("r1", { include_noise: true });
    expect(m.docs.map((d) => d.doc_id)).toEqual(["A", "B"]);
    expect(m.cells).toEqual([]);
    routes["GET /engine/ui/runs/r1/matrix?include_noise=false"] = () => ({ status: 409 });
    expect(await engineHttp.getMatrix("r1")).toEqual({ docs: [], changes: [], cells: [] });
  });
  it("getReader composes company + annotations; null doc gives null", async () => {
    vi.mocked(companyHttp.getDocument).mockResolvedValue(doc("D") as never);
    vi.mocked(companyHttp.listClauses).mockResolvedValue([{ clause_id: "D:1" }] as never);
    const ann = { clause_id: "D:1", kind: "cleared", change_id: "c1", citation: "x", reason: "r" };
    routes["GET /engine/ui/runs/r1/documents/D/annotations"] = () => ({ body: [ann] });
    const r = await engineHttp.getReader("D", "r1");
    expect(r?.doc.doc_id).toBe("D");
    expect(r?.clauses).toHaveLength(1);
    expect(r?.annotations).toHaveLength(1);
    vi.mocked(companyHttp.getDocument).mockResolvedValue(null);
    expect(await engineHttp.getReader("D", "r1")).toBeNull();
  });
});

describe("scenarios and what-if", () => {
  const preset = { scenario_id: "p1", title: "P", citation: "170 IAC 4-1-16", source_system: "iac" as const, edit_kind: "repeal" as const, edited_text: null, is_preset: true, last_run_id: "r9" };

  it("saveScenario validates, stores a local draft with no POST, and listScenarios appends it", async () => {
    routes["GET /engine/ui/whatif/sections"] = () => ({ body: sections });
    routes["GET /engine/ui/scenarios"] = () => ({ body: [preset] });
    await expect(
      engineHttp.saveScenario({ title: "t", citation: "170 IAC 4-1-16", source_system: "iac", edit_kind: "text_edit", edited_text: "  " }),
    ).rejects.toThrow(/text/i);
    await expect(
      engineHttp.saveScenario({ title: "t", citation: "nope", source_system: "iac", edit_kind: "repeal" }),
    ).rejects.toThrow("Section is not cited by any RPL clause");
    const d = await engineHttp.saveScenario({ title: "t", citation: "170 IAC 4-1-16", source_system: "iac", edit_kind: "text_edit", edited_text: "new" });
    expect(d.scenario_id.startsWith("draft-")).toBe(true);
    expect(d.is_preset).toBe(false);
    expect(calls.some((c) => c.method === "POST")).toBe(false);
    const all = await engineHttp.listScenarios();
    expect(all.map((s) => s.scenario_id)).toEqual(["p1", d.scenario_id]);
    // editing a persisted scenario makes a new draft
    const copy = await engineHttp.saveScenario({ ...preset, scenario_id: "p1", edit_kind: "repeal" });
    expect(copy.scenario_id).not.toBe("p1");
  });

  it("startWhatIf on a draft POSTs, then retries the run row until it exists", async () => {
    vi.useFakeTimers();
    routes["GET /engine/ui/whatif/sections"] = () => ({ body: sections });
    routes["GET /engine/ui/scenarios"] = () => ({ body: [] });
    const d = await engineHttp.saveScenario({ title: "T", citation: "170 IAC 4-1-16", source_system: "iac", edit_kind: "text_edit", edited_text: "new" });
    routes["POST /engine/whatif/scenarios"] = () => ({ body: { scenario_id: "s7", run_id: "r7" } });
    let hits = 0;
    routes["GET /engine/ui/runs/r7"] = () => (++hits < 3 ? { status: 404, body: { detail: "nf" } } : { body: run("r7", "running") });
    const p = engineHttp.startWhatIf(d.scenario_id);
    await vi.advanceTimersByTimeAsync(2000);
    const r = await p;
    expect(r.status).toBe("running");
    expect(hits).toBe(3);
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ s1_section_id: "42", edit_kind: "text_edit", edited_text: "new", title: "T" });
    expect((await engineHttp.listScenarios()).some((s) => s.scenario_id === d.scenario_id)).toBe(false);
  });

  it("startWhatIf times out with 'Run did not start'", async () => {
    vi.useFakeTimers();
    routes["GET /engine/ui/scenarios"] = () => ({ body: [{ ...preset, is_preset: false, last_run_id: null }] });
    routes["POST /engine/whatif/scenarios/p1/run"] = () => ({ body: { run_id: "rx" } });
    const p = engineHttp.startWhatIf("p1");
    const assertion = expect(p).rejects.toThrow("Run did not start");
    await vi.advanceTimersByTimeAsync(20000);
    await assertion;
  });

  it("preset with a succeeded last run makes NO POST; persisted custom POSTs /run", async () => {
    routes["GET /engine/ui/scenarios"] = () => ({ body: [preset, { ...preset, scenario_id: "c1", is_preset: false }] });
    routes["GET /engine/ui/runs/r9"] = () => ({ body: run("r9", "succeeded") });
    const r = await engineHttp.startWhatIf("p1");
    expect(r.run_id).toBe("r9");
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
    routes["POST /engine/whatif/scenarios/c1/run"] = () => ({ body: { run_id: "r9" } });
    await engineHttp.startWhatIf("c1");
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual(["/engine/whatif/scenarios/c1/run"]);
  });
});

describe("submitReview", () => {
  it("requires a note to reject and makes no request", async () => {
    await expect(engineHttp.submitReview("f1", "reject", "  ")).rejects.toThrow("A note is required to reject");
    expect(calls).toHaveLength(0);
  });
  it("defaults reviewer to the routed reviewer, POSTs then re-fetches", async () => {
    routes["GET /engine/ui/findings/f1"] = () => ({ body: finding("f1") });
    routes["POST /engine/findings/f1/reviews"] = () => ({ body: { ok: true } });
    const f = await engineHttp.submitReview("f1", "accept");
    expect(f.finding_id).toBe("f1");
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toMatchObject({ action: "accept", person_id: "P02" });
    expect(calls.map((c) => c.method)).toEqual(["GET", "POST", "GET"]);

    calls.length = 0;
    routes["GET /engine/ui/findings/f2"] = () => ({ body: finding("f2") });
    routes["POST /engine/findings/f2/reviews"] = () => ({ body: {} });
    await engineHttp.submitReview("f2", "reject", "no");
    expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({ action: "reject", note: "no", person_id: "P02" });
  });
  it("explicit person_id skips the pre-fetch", async () => {
    routes["POST /engine/findings/f3/reviews"] = () => ({ body: {} });
    routes["GET /engine/ui/findings/f3"] = () => ({ body: finding("f3") });
    await engineHttp.submitReview("f3", "accept", undefined, "P09");
    expect(calls.map((c) => c.method)).toEqual(["POST", "GET"]);
    expect(calls[0].body).toMatchObject({ person_id: "P09" });
  });
});

describe("editable sections", () => {
  it("strips s1_section_id and resolves S1 text by citation", async () => {
    routes["GET /engine/ui/whatif/sections"] = () => ({ body: sections });
    routes["GET /engine/ui/whatif/sections/42"] = () => ({ body: { citation: "170 IAC 4-1-16", heading: "H", s1_text: "body" } });
    const list = await engineHttp.listEditableSections();
    expect(list[0]).not.toHaveProperty("s1_section_id");
    const t = await engineHttp.getSectionS1Text("iac", "170 IAC 4-1-16");
    expect(t?.s1_text).toBe("body");
    expect(await engineHttp.getSectionS1Text("iac", "unknown")).toBeNull();
  });
});

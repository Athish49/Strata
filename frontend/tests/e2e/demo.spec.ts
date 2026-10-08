/**
 * Live-mode demo walk (spec §12). READ-ONLY: no clicks on Accept/Reject, no POST, no LLM.
 * Runs against the already-running servers (frontend :3000, backend :8000).
 * Every expected number is read from the API at test time (never hardcoded).
 */
import { expect, test, type Page, type ConsoleMessage } from "@playwright/test";

const API = process.env.STRATA_API_URL ?? "http://localhost:8000";

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
const fmt = (n: number) => n.toLocaleString("en-US");
const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
/** "1 finding" / "4 findings" */
const plural = (n: number, w: string) => `${fmt(n)} ${w}${n === 1 ? "" : "s"}`;

async function api<T = Json>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return (await r.json()) as T;
}

test.describe.serial("demo script (live, read-only)", () => {
  let page: Page;
  let rid: string;
  let run: Json;
  const posts: string[] = [];
  const consoleErrors: string[] = [];

  /** Known benign noise: none ignored so far. Add entries here only with a documented reason. */
  const IGNORED_CONSOLE: RegExp[] = [];

  /** Every cue whose label says "(coming soon)" must be aria-disabled and must not be a link or carry a href. */
  async function assertCuesDisabled(where: string) {
    const bad = await page.evaluate(() => {
      const out: string[] = [];
      let n = 0;
      const all = Array.from(document.querySelectorAll<HTMLElement>("*"));
      const cues = new Set<HTMLElement>();
      for (const el of all) {
        const lbl = el.getAttribute("aria-label") ?? "";
        const own = Array.from(el.children).length === 0 ? el.textContent ?? "" : "";
        if (/\(coming soon\)/i.test(lbl) || /\(coming soon\)/i.test(own)) {
          const root = el.closest<HTMLElement>("[aria-disabled]") ?? el.closest<HTMLElement>("button,[role=link],[role=menuitem],a");
          cues.add(root ?? el);
        }
      }
      for (const c of cues) {
        n++;
        const ok = c.getAttribute("aria-disabled") === "true" && !c.closest("a[href]") && !c.hasAttribute("href") && !c.hasAttribute("onclick");
        if (!ok) out.push((c.getAttribute("aria-label") ?? c.textContent ?? "").trim().slice(0, 60));
      }
      return { n, out };
    });
    expect(bad.n, `${where}: at least one disabled coming-soon cue is present`).toBeGreaterThan(0);
    expect(bad.out, `${where}: coming-soon cues that are NOT disabled`).toEqual([]);
  }

  async function open(path: string, ready: RegExp | string) {
    await page.goto(path, { waitUntil: "domcontentloaded" });
    await expect(page.getByText(ready).first()).toBeVisible({ timeout: 90_000 });
  }

  test.beforeAll(async ({ browser }) => {
    const runs = await api<Json[]>("/engine/ui/runs");
    const r = runs.find((x) => x.kind === "kb" && x.status === "succeeded");
    if (!r) throw new Error("no succeeded kb run");
    rid = r.run_id;
    run = await api(`/engine/ui/runs/${rid}`);
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    page = await ctx.newPage();
    page.on("request", (req) => {
      if (req.method() === "POST") posts.push(`${req.method()} ${req.url()}`);
    });
    page.on("console", (m: ConsoleMessage) => {
      if (m.type() === "error" && !IGNORED_CONSOLE.some((re) => re.test(m.text()))) consoleErrors.push(`${page.url()} :: ${m.text()}`);
    });
    page.on("pageerror", (e) => consoleErrors.push(`${page.url()} :: pageerror ${e.message}`));
  });

  test.afterAll(async () => {
    await page?.context().close();
  });

  test("overview funnel equals API stats", async () => {
    const s = run.stats;
    const findings = Object.values<number>(s.findings_by_verdict).reduce((a, b) => a + b, 0);
    await open("/app", "The wave at a glance");
    const main = page.locator("main");
    await expect(main).toContainText(run.title);
    await expect(main).toContainText(`${fmt(s.changes_raw)} changes`);
    await expect(main).toContainText(`${fmt(s.substantive)} real`);
    await expect(main).toContainText(`${fmt(s.noise)} noise`);
    await expect(main).toContainText(`${fmt(s.in_footprint_real)} real`);
    await expect(main).toContainText(`${fmt(s.obligation_changed)} changed`);
    await expect(main).toContainText(new RegExp(`${esc(plural(findings, "finding"))} in ${s.docs_flagged} documents?`));
    await expect(main).toContainText(`${fmt(s.clauses_cleared)}`);
    await expect(main).toContainText(/clauses checked and cleared/);
    await expect(main).toContainText(`Across ${s.docs_flagged + s.docs_cleared} documents`);
    await expect(main).toContainText(`${s.docs_flagged} flagged`);
    await expect(main).toContainText(`${s.docs_cleared} cleared`);
    await expect(main).toContainText(`${s.radar.applicable} possibly applicable`);
    await assertCuesDisabled("overview");
  });

  test("documents board: flagged vs cleared match rollups", async () => {
    const rollups = await api<Json[]>(`/engine/ui/runs/${rid}/rollups`);
    await open("/app/documents", "Regulatory Reporting Calendar 2025");
    const flagged = rollups.filter((r) => r.status === "flagged");
    const cleared = rollups.filter((r) => r.status === "cleared");
    expect(flagged.length + cleared.length).toBeGreaterThan(0);
    for (const r of rollups) {
      const card = page.locator(`[data-doc-id="${r.doc_id}"]`).first();
      await expect(card, r.doc_id).toBeVisible();
      if (r.status === "flagged") {
        const n = Object.values<number>(r.counts_by_verdict).reduce((a, b) => a + b, 0);
        await expect(card).toContainText(r.counts_by_verdict.action_required > 0 ? "Action needed" : "Review");
        await expect(card).toContainText(`${n}`);
      } else {
        await expect(card).toContainText("Cleared");
        if (r.cleared_reason) await expect(card).toContainText(r.cleared_reason);
      }
    }
    await expect(page.getByText(`${rollups.length} monitored of`, { exact: false }).first()).toBeVisible();
    await assertCuesDisabled("documents");
  });

  test("reader: flagged document -> finding -> evidence card with three quotes, verified badge and route", async () => {
    const rollups = await api<Json[]>(`/engine/ui/runs/${rid}/rollups`);
    const doc = rollups.find((r) => r.status === "flagged");
    expect(doc, "a flagged document exists").toBeTruthy();
    const apiFindings = (await api<Json[]>(`/engine/ui/runs/${rid}/findings`)).filter((f) => f.doc_id === doc!.doc_id);
    await page.goto(`/app/documents/${doc!.doc_id}`, { waitUntil: "domcontentloaded" });
    const rail = page.getByRole("complementary", { name: "Findings" });
    await expect(rail.locator("button[data-finding-id]")).toHaveCount(apiFindings.length, { timeout: 60_000 });
    await expect(rail.getByRole("button", { name: /^Cleared \(\d/ })).toBeVisible();
    await assertCuesDisabled("reader");

    const first = rail.locator("button[data-finding-id]").first();
    const fid = (await first.getAttribute("data-finding-id"))!;
    const f = await api<Json>(`/engine/ui/findings/${fid}`);
    await first.click();
    const card = page.getByRole("dialog").getByRole("article", { name: "Evidence card" });
    await expect(card).toBeVisible({ timeout: 60_000 });
    for (const t of ["Old rule (S1)", "New rule (S2)", "Clause"]) {
      await expect(card.getByRole("region", { name: t, exact: true })).toBeVisible();
    }
    // The quote text itself is rendered in its pane (highlight marks may split it, so compare normalised text).
    const norm = (s: string) => s.replace(/\s+/g, " ").trim();
    for (const [pane, q] of [["Old rule (S1)", f.quotes.s1], ["New rule (S2)", f.quotes.s2], ["Clause", f.quotes.clause]] as const) {
      const txt = norm(await card.getByRole("region", { name: pane, exact: true }).innerText());
      expect(txt, `${pane} contains the quote`).toContain(norm(q.text).slice(0, 40));
    }
    if (f.quotes_verified) await expect(card.locator('[data-badge="verified"]')).toContainText("Verified quote");
    else await expect(card.locator('[data-badge="unverified"]')).toBeVisible();
    for (const role of ["Owner", "Reviewer"]) await expect(card.getByText(role, { exact: true }).first()).toBeVisible();
    await expect(card).toContainText(f.route.owner.name);
    await expect(card).toContainText(f.route.reviewer.name);
    if (f.route.approver) await expect(card).toContainText(f.route.approver.name);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });

  test("changes: a cleared noise change shows its reason and Cleared (N)", async () => {
    const changes = await api<Json[]>(`/engine/ui/runs/${rid}/changes`);
    const noise = changes.find(
      (c) => c.in_footprint && !["substantive", "new_section", "repealed"].includes(c.change_class) && c.cited_clause_count > 0,
    );
    expect(noise, "an in-footprint noise change exists").toBeTruthy();
    const cands = await api<Json[]>(`/engine/ui/runs/${rid}/candidates?change_id=${noise!.change_id}`);
    const clearedN = cands.filter((c) => c.outcome !== "affected").length;
    expect(clearedN).toBeGreaterThan(0);

    await open("/app/changes", "What changed in the law");
    await expect(page.getByText(`of ${fmt(changes.length)} changes`).first()).toBeVisible();
    await assertCuesDisabled("changes");

    await open(`/app/changes/${noise!.change_id}`, noise!.citation);
    const detail = page.getByTestId("change-detail");
    await expect(detail).toBeVisible({ timeout: 60_000 });
    if (noise!.disposition_reason) {
      const reason = noise!.disposition_reason.replace(/\b1 (\w+)\(s\)/g, "1 $1").replace(/\(s\)/g, "s");
      await expect(detail).toContainText(reason);
    }
    const cl = detail.getByRole("button", { name: new RegExp(`^Cleared \\(${fmt(clearedN).replace(",", ",?")}\\)`) });
    await expect(cl).toBeVisible({ timeout: 60_000 });
    await expect(detail.getByTestId("ledger-proof")).toContainText(`${fmt(cands.length)} clauses checked`);
    await cl.click();
    // each cleared row carries a reason (the engine's per-clause rationale)
    const sample = cands.find((c) => c.outcome !== "affected" && c.rationale);
    if (sample) {
      const key = norm2(sample.rationale).split(":").pop()!.trim().slice(0, 30);
      await expect(detail).toContainText(key);
    }
  });

  test("matrix: cells match the API", async () => {
    const m = await api<Json>(`/engine/ui/runs/${rid}/matrix`);
    await open("/app/matrix", "Which documents each changed rule touches");
    const grid = page.locator("[data-cell]");
    await expect(grid.first()).toBeVisible({ timeout: 60_000 });
    await expect(grid).toHaveCount(m.cells.length);
    const nonCleared = m.cells.filter((c: Json) => c.worst_verdict !== "cleared");
    await expect(page.locator('[data-cell]:not([data-verdict="cleared"])')).toHaveCount(nonCleared.length);
    for (const v of new Set<string>(m.cells.map((c: Json) => c.worst_verdict))) {
      await expect(page.locator(`[data-cell][data-verdict="${v}"]`)).toHaveCount(m.cells.filter((c: Json) => c.worst_verdict === v).length);
    }
    const sum = nonCleared.reduce((a: number, c: Json) => a + c.n_findings, 0);
    await expect(page.locator("main")).toContainText(
      `${nonCleared.length} cell${nonCleared.length === 1 ? "" : "s"} with findings, ${m.cells.length - nonCleared.length} cells checked and cleared`,
    );
    const labels = await page.locator('[data-cell]:not([data-verdict="cleared"])').evaluateAll((els) => els.map((e) => e.getAttribute("aria-label") ?? ""));
    const got = labels.reduce((a, l) => a + Number(/: (\d+) finding/.exec(l)?.[1] ?? 0), 0);
    expect(got).toBe(sum);
    await assertCuesDisabled("matrix");
  });

  test("radar: tab counts equal /radar", async () => {
    const items = await api<Json[]>(`/engine/ui/runs/${rid}/radar`);
    await open("/app/radar", "Changes your documents don't cite");
    const count = (k: string) => items.filter((i) => i.applicable === k).length;
    for (const [k, label] of [["yes", "Possibly applicable"], ["no", "Screened out"], ["unclear", "Unclear"]] as const) {
      await expect(page.getByRole("tab", { name: new RegExp(`^${label}\\s*${fmt(count(k))}$`) }), label).toBeVisible({ timeout: 60_000 });
    }
    expect(count("yes")).toBe(run.stats.radar.applicable);
    await assertCuesDisabled("radar");
  });

  test("trust: four metrics and document agreement", async () => {
    const sc = await api<Json>(`/engine/ui/runs/${rid}/score`);
    await open("/app/trust", "Trust scorecard");
    const main = page.locator("main");
    for (const t of ["Precision", "Recall", "False-positive rate on the must-not-flag set", "Routing accuracy"]) {
      await expect(main.getByText(t, { exact: true }).first()).toBeVisible({ timeout: 60_000 });
    }
    const a = sc.doc_agreement;
    await expect(main).toContainText(`${fmt(a.agree)} of ${fmt(a.total)} documents correctly flagged or cleared`);
    await expect(main).toContainText(/Baseline: S1 vs S1 → 0 findings/);
    await expect(main).toContainText(`${fmt(sc.decided_by.ai)}`);
    await assertCuesDisabled("trust");
  });

  test("what-if: open a preset -> SIMULATED banner, no POST", async () => {
    const scen = await api<Json[]>("/engine/ui/scenarios");
    const preset = scen.find((s) => s.is_preset && s.last_run_id);
    expect(preset, "a preset with a finished run exists").toBeTruthy();
    const prun = await api<Json>(`/engine/ui/runs/${preset!.last_run_id}`);
    expect(prun.status).toBe("succeeded");
    await open("/app/what-if", "What-if studio");
    await assertCuesDisabled("what-if");
    await expect(page.getByTestId("preset-card").first()).toBeVisible({ timeout: 60_000 });
    await page.getByRole("button", { name: `Run ${preset!.title}` }).click();
    await page.waitForURL(/\/app\?run=/, { timeout: 90_000 });
    await expect(page.getByRole("status").filter({ hasText: /Simulated/ })).toBeVisible({ timeout: 60_000 });
    await expect(page.getByRole("status").filter({ hasText: /not real regulatory changes/ })).toBeVisible();
    await expect(page.locator("main")).toContainText(`${fmt(prun.stats.changes_raw)} changes`, { timeout: 60_000 });
    await assertCuesDisabled("what-if run overview");
    await page.getByRole("button", { name: "Back to real wave" }).click();
    await expect(page.getByRole("status").filter({ hasText: /Simulated/ })).toHaveCount(0);
  });

  test("whole walk: no POST requests and no console errors", async () => {
    expect(posts, "POST requests made during the walk").toEqual([]);
    expect(consoleErrors, "console errors during the walk").toEqual([]);
  });
});

function norm2(s: string) {
  return s.replace(/\s+/g, " ").trim();
}

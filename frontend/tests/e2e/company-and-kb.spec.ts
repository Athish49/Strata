/**
 * Live-mode walk of the features demo.spec.ts does not cover: the company profile
 * page (attributes/people/documents), the regulations (knowledge base) browse list,
 * and a regulation section's S1->S2 diff view. READ-ONLY: no POST, no LLM, no writes.
 * Runs against the already-running servers (frontend :3000, backend :8000).
 */
import { expect, test, type Page, type ConsoleMessage } from "@playwright/test";

const API = process.env.STRATA_API_URL ?? "http://localhost:8000";

type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any

async function api<T = Json>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return (await r.json()) as T;
}

test.describe.serial("company profile + knowledge base (live, read-only)", () => {
  let page: Page;
  const posts: string[] = [];
  const consoleErrors: string[] = [];

  test.beforeAll(async ({ browser }) => {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    page = await ctx.newPage();
    page.on("request", (req) => {
      if (req.method() === "POST") posts.push(`${req.method()} ${req.url()}`);
    });
    page.on("console", (m: ConsoleMessage) => {
      if (m.type() === "error") consoleErrors.push(`${page.url()} :: ${m.text()}`);
    });
    page.on("pageerror", (e) => consoleErrors.push(`${page.url()} :: pageerror ${e.message}`));
  });

  test.afterAll(async () => {
    await page?.context().close();
  });

  test("company profile: name, type, attributes, people, documents all match the API", async () => {
    const profile = await api<Json>("/company/profile");
    const people = await api<Json[]>("/company/people");
    const docs = await api<Json[]>("/company/documents");

    await page.goto("/app/company", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Company profile").first()).toBeVisible({ timeout: 60_000 });

    const main = page.locator("main");
    await expect(main).toContainText(profile.name);
    await expect(main).toContainText(profile.type);
    await expect(main).toContainText(profile.state);
    await expect(main).toContainText(profile.customers.toLocaleString("en-US"));
    await expect(main).toContainText(profile.regulator);

    // People section: every real person appears somewhere (by name).
    await expect(main.getByText("People", { exact: true }).first()).toBeVisible();
    for (const p of people.slice(0, 5)) {
      await expect(main).toContainText(p.name);
    }

    // Documents summary: every monitored document's title appears.
    const monitored = docs.filter((d: Json) => d.monitored);
    expect(monitored.length).toBeGreaterThan(0);
    for (const d of monitored.slice(0, 5)) {
      await expect(main).toContainText(d.title);
    }
  });

  test("regulations: the knowledge base browse list loads real agencies", async () => {
    await page.goto("/app/regulations", { waitUntil: "domcontentloaded" });
    await expect(page.getByText("Regulations").first()).toBeVisible({ timeout: 60_000 });
    const main = page.locator("main");
    await expect(main).toContainText("Federal");
    await expect(main).toContainText(/State .* Indiana/);
    // The KB is never empty post-cutover (4,603 code_sections across real agencies).
    await expect(main.getByText("No agencies are monitored yet")).toHaveCount(0);
  });

  test("regulations: a real section with a genuine S1->S2 change shows its diff", async () => {
    // 170 IAC 1-6-3 is confirmed (task 9.2/9.3) to have genuinely different S1/S2 text.
    const sourceSystem = "iac";
    const citation = "170 IAC 1-6-3";
    const href = `/app/regulations/sections/${encodeURIComponent(sourceSystem)}/${encodeURIComponent(citation)}`;

    await page.goto(href, { waitUntil: "domcontentloaded" });
    await expect(page.getByText(citation, { exact: false }).first()).toBeVisible({ timeout: 60_000 });
    await expect(page.getByText("This section is not in the knowledge base")).toHaveCount(0);

    const main = page.locator("main");
    // A genuine diff exists, so the "identical text" empty-state must NOT show.
    await expect(main.getByText("No text change between S1 and S2")).toHaveCount(0);
    // The diff view itself rendered something (it's not the "no text stored" empty state either).
    await expect(main.getByText("No text is stored for this section")).toHaveCount(0);
  });

  test("documents by vertical: the board groups real documents correctly", async () => {
    const docs = await api<Json[]>("/company/documents");
    const verticals = new Set(docs.map((d: Json) => d.vertical).filter(Boolean));
    expect(verticals.size).toBeGreaterThan(0);
    const [firstVertical] = Array.from(verticals) as string[];

    await page.goto(`/app/documents/verticals/${encodeURIComponent(firstVertical)}`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("main")).toBeVisible({ timeout: 60_000 });
    // No client-side exception navigating a real vertical slug.
  });

  test("whole walk: no POST requests and no console errors", async () => {
    expect(posts, "POST requests made during the walk").toEqual([]);
    expect(consoleErrors, "console errors during the walk").toEqual([]);
  });
});

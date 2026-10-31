/**
 * Live-mode check of two more features: the "acting as" person selector (purely
 * client-side — localStorage, no API write) and the upload dialog's form rendering
 * (opened, never submitted — submitting would ingest a real document and cost real
 * LLM money, which is the user's call, not mine). Also a quick no-error smoke check
 * of two standalone pages not covered elsewhere. READ-ONLY: no POST, no LLM.
 */
import { expect, test, type ConsoleMessage } from "@playwright/test";

const API = process.env.STRATA_API_URL ?? "http://localhost:8000";
type Json = any; // eslint-disable-line @typescript-eslint/no-explicit-any
async function api<T = Json>(path: string): Promise<T> {
  const r = await fetch(`${API}${path}`);
  if (!r.ok) throw new Error(`GET ${path} -> ${r.status}`);
  return (await r.json()) as T;
}

test("acting-as: selecting a real person persists across reload, no API write", async ({ page }) => {
  const people = await api<Json[]>("/company/people");
  const someone = people.find((p: Json) => p.is_active !== false) ?? people[0];

  const posts: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST") posts.push(req.url());
  });

  await page.goto("/app", { waitUntil: "domcontentloaded" });
  await page.locator("#acting-as").first().click();
  await page.getByRole("option", { name: new RegExp(someone.name) }).click();

  const actingLabel = new RegExp(`Acting as ${someone.name}`);
  await expect(page.getByRole("button", { name: actingLabel })).toBeVisible({ timeout: 15_000 });

  await page.reload({ waitUntil: "domcontentloaded" });
  await expect(page.getByRole("button", { name: actingLabel })).toBeVisible({ timeout: 15_000 });

  expect(posts, "selecting an actor must never POST").toEqual([]);
});

test("upload dialog: opens, shows the real form, never submitted", async ({ page }) => {
  const posts: string[] = [];
  page.on("request", (req) => {
    if (req.method() === "POST") posts.push(req.url());
  });

  await page.goto("/app/documents", { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Upload", exact: true }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByText("Upload a document")).toBeVisible({ timeout: 15_000 });
  await expect(dialog.getByRole("button", { name: /Upload/i })).toBeVisible();
  // Close without submitting — never exercise the real ingest/LLM path here.
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  expect(posts, "opening/closing the upload dialog must never POST").toEqual([]);
});

test("standalone finding page and what-if scenario detail page load without error", async ({ page }) => {
  const consoleErrors: string[] = [];
  page.on("console", (m: ConsoleMessage) => {
    if (m.type() === "error") consoleErrors.push(m.text());
  });
  page.on("pageerror", (e) => consoleErrors.push(`pageerror ${e.message}`));

  const runs = await api<Json[]>("/engine/ui/runs");
  const run = runs.find((x: Json) => x.kind === "kb" && x.status === "succeeded");
  const findings = await api<Json[]>(`/engine/ui/runs/${run!.run_id}/findings`);
  await page.goto(`/app/findings/${findings[0].finding_id}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("main")).toBeVisible({ timeout: 30_000 });

  const scenarios = await api<Json[]>("/engine/ui/scenarios");
  await page.goto(`/app/what-if/${scenarios[0].scenario_id}`, { waitUntil: "domcontentloaded" });
  await expect(page.locator("main")).toBeVisible({ timeout: 30_000 });

  expect(consoleErrors, "console errors across both standalone pages").toEqual([]);
});

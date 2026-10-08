import { defineConfig } from "@playwright/test";
import { existsSync, readdirSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";

/** CHROMIUM_PATH, else the newest cached `chromium-*` build under ~/Library/Caches/ms-playwright. */
function findChromium(): string | undefined {
  if (process.env.CHROMIUM_PATH) return process.env.CHROMIUM_PATH;
  const root = join(homedir(), "Library", "Caches", "ms-playwright");
  if (!existsSync(root)) return undefined;
  const dirs = readdirSync(root)
    .filter((d) => /^chromium-\d+$/.test(d))
    .sort((a, b) => Number(b.split("-")[1]) - Number(a.split("-")[1]));
  const rels = [
    "chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "chrome-mac/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing",
    "chrome-mac/Chromium.app/Contents/MacOS/Chromium",
    "chrome-linux/chrome",
  ];
  for (const d of dirs) for (const r of rels) if (existsSync(join(root, d, r))) return join(root, d, r);
  return undefined;
}

// Runs against servers that are already up (frontend :3000 in live mode, backend :8000); never starts one.
export default defineConfig({
  testDir: "tests/e2e",
  workers: 1,
  fullyParallel: false,
  retries: 0,
  timeout: 300_000,
  expect: { timeout: 30_000 },
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3000",
    actionTimeout: 30_000,
    navigationTimeout: 90_000,
    launchOptions: { executablePath: findChromium() },
  },
  webServer: undefined,
});

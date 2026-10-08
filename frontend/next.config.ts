import type { NextConfig } from "next";

// The browser calls the backend directly, so BACKEND_URL is inlined into the client bundle at build time.
// Local: set in .env.local. Production: set in the host dashboard. No silent fallback.
const BACKEND_URL = process.env.BACKEND_URL?.trim();
if (!BACKEND_URL) {
  throw new Error("BACKEND_URL is not set (e.g. http://localhost:8000). Set it in frontend/.env.local or the host's environment variables.");
}

const nextConfig: NextConfig = {
  env: { BACKEND_URL },
  // Lets parallel dev servers use isolated build dirs (NEXT_DIST_DIR=.next-<name>).
  distDir: process.env.NEXT_DIST_DIR ?? ".next",
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
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

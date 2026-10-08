import type { Agency } from "@/lib/api/schemas";

/** Federal agencies first, then state; API order is kept within each level. */
export function groupAgencies(agencies: Agency[]) {
  return {
    federal: agencies.filter((a) => a.level === "federal"),
    state: agencies.filter((a) => a.level === "state"),
  };
}

/** Codebook-only agencies (610 / 675 IAC) have no activity feed. */
export const isCodebookOnly = (a: Pick<Agency, "has_activity_feed">) => !a.has_activity_feed;

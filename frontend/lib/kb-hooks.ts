"use client";
// Thin KB hooks that queries.ts does not provide. Uses the data-layer `api` only.
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import type { CodeSection } from "@/lib/api/schemas";

const PAGE_LIMIT = 5000;
const MAX_PAGES = 20;

/** Every (light) section row of one agency. Follows pagination when the server caps the page size. */
export async function fetchAllSections(agency: string): Promise<CodeSection[]> {
  const out: CodeSection[] = [];
  let page = 1;
  for (;;) {
    const res = await api.kb.listSections({ agency, page, limit: PAGE_LIMIT });
    out.push(...res.items);
    if (res.items.length === 0 || out.length >= res.total || page >= MAX_PAGES) break;
    page += 1;
  }
  return out;
}

export function useAllSections(agency: string | null | undefined) {
  return useQuery({
    queryKey: ["kb", "all-sections", agency ?? ""],
    queryFn: () => fetchAllSections(agency as string),
    enabled: !!agency,
    staleTime: 5 * 60_000,
  });
}

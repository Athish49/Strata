// The 14 verticals, fetched from GET /company/verticals (task 3.7) rather than hardcoded
// here. Every function below takes the fetched list as its first argument -- call
// `useVerticals()` (lib/api/queries.ts) in a component and pass `data` through, so this
// module stays plain, synchronous, and trivially testable (no React, no fetch).
import type { CompanyVertical } from "@/lib/api/schemas";

export type Vertical = CompanyVertical;

export function isVerticalSlug(verticals: readonly Vertical[], slug: string): boolean {
  return verticals.some((v) => v.slug === slug);
}

/**
 * Fallback group for documents whose vertical is not one of the 14: the backend sends the
 * literal slug "unclassified" for a NULL or unmapped vertical. Deliberately not returned by
 * `getVertical`/not included in the fetched list (it is not a navigable vertical page, and
 * the upload endpoint rejects it with 422) -- callers that need to render it alongside the
 * 14 use `verticalGroups()` or `UNCLASSIFIED_VERTICAL` explicitly.
 */
export const UNCLASSIFIED_SLUG = "unclassified";
export const UNCLASSIFIED_VERTICAL: Vertical = {
  sort_order: 15,
  slug: UNCLASSIFIED_SLUG,
  name: "Unclassified",
  description: "Documents whose vertical is missing or not one of the fourteen recognised verticals.",
};

/** The 14 verticals followed by the unclassified fallback: use this to group documents so none are hidden. */
export function verticalGroups(verticals: readonly Vertical[]): Vertical[] {
  return [...verticals, UNCLASSIFIED_VERTICAL];
}

/** True for the 14 slugs and "unclassified" (every value a document's `vertical` can hold after normalising). */
export function isKnownVerticalSlug(verticals: readonly Vertical[], slug: string): boolean {
  return slug === UNCLASSIFIED_SLUG || isVerticalSlug(verticals, slug);
}

/** A document's vertical slug, or "unclassified" when it is not one of the 14. */
export function normalizeVerticalSlug(verticals: readonly Vertical[], slug: string | null | undefined): string {
  return slug && isVerticalSlug(verticals, slug) ? slug : UNCLASSIFIED_SLUG;
}

/** True when POST /company/documents accepts this vertical: any of the 14, never `unclassified`. */
export function canUploadToVertical(verticals: readonly Vertical[], slug: string): boolean {
  return isVerticalSlug(verticals, slug);
}

/** Resolves the 14 slugs and "unclassified". */
export function getVertical(verticals: readonly Vertical[], slug: string): Vertical | undefined {
  if (slug === UNCLASSIFIED_SLUG) return UNCLASSIFIED_VERTICAL;
  return verticals.find((v) => v.slug === slug);
}

/** Display name for a slug; falls back to the slug itself. */
export function verticalName(verticals: readonly Vertical[], slug: string): string {
  return getVertical(verticals, slug)?.name ?? slug;
}

/** Sort comparator by fixed (DB) order; "unclassified" sorts after the 14, unknown slugs last. */
export function compareVerticals(verticals: readonly Vertical[], a: string, b: string): number {
  return (getVertical(verticals, a)?.sort_order ?? 99) - (getVertical(verticals, b)?.sort_order ?? 99);
}

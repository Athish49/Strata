// Pure logic + tiny module stores behind the "Acting as" selector (ActingAs.tsx).
// No React here so it is trivially testable; the hook composes lib/actor.ts.
import type { OrgPerson } from "@/lib/api/schemas";

import { ACTING_AS_SELECTOR_ID } from "@/components/documents/upload/logic";

/**
 * DOM id of the shell control's trigger, so prompts elsewhere can link to it
 * (`href="#acting-as"`). Single source of truth is the upload dialog's constant.
 */
export const ACTING_AS_CONTROL_ID = ACTING_AS_SELECTOR_ID;

/** Above this many active people the picker shows a search box. */
export const ACTOR_SEARCH_THRESHOLD = 8;

/** Only active people can act: the backend 403s writes by inactive people. */
export function activePeople(people: readonly OrgPerson[] | undefined): OrgPerson[] {
  return (people ?? [])
    .filter((p) => p.is_active)
    .sort((a, b) => a.name.localeCompare(b.name, "en", { sensitivity: "base" }));
}

/** "Title · Department", skipping blanks. */
export function personSubtitle(p: Pick<OrgPerson, "title" | "department">): string {
  return [p.title, p.department].filter((s): s is string => !!s && !!s.trim()).join(" · ");
}

export function personInitials(name: string): string {
  const p = name.split(/\s+/).filter(Boolean);
  return ((p[0]?.[0] ?? "") + (p.length > 1 ? p[p.length - 1][0] : "")).toUpperCase() || "?";
}

/** Why a stored actor id was dropped. */
export interface StaleActor {
  id: string;
  /** The person's name when the id is still known (inactive), else null (deleted). */
  name: string | null;
  reason: "inactive" | "missing";
}

export type ActorResolution =
  /** Not hydrated yet, or an id is stored and the people list is still loading. */
  | { status: "loading" }
  /** Nobody selected. */
  | { status: "none" }
  /** The stored id resolves to an active person. */
  | { status: "ok"; person: OrgPerson }
  /** The stored id is not (or no longer) an active person: treat as unset. */
  | { status: "stale"; stale: StaleActor }
  /** An id is stored but the people list failed to load, so it cannot be checked. */
  | { status: "unverified"; id: string };

/**
 * Resolve the stored id against the people list. `people` undefined = not loaded yet;
 * `peopleError` = the list failed (never treat the id as stale on a failed fetch).
 */
export function resolveActor(
  id: string | null,
  people: readonly OrgPerson[] | undefined,
  peopleError = false,
): ActorResolution {
  if (!id) return { status: "none" };
  if (!people) return peopleError ? { status: "unverified", id } : { status: "loading" };
  const p = people.find((x) => x.person_id === id);
  if (p && p.is_active) return { status: "ok", person: p };
  return { status: "stale", stale: { id, name: p?.name ?? null, reason: p ? "inactive" : "missing" } };
}

/** Sentence for a dropped actor. */
export function staleMessage(s: StaleActor): string {
  const who = s.name ?? `Person ${s.id}`;
  return s.reason === "inactive" ? `${who} is no longer active.` : `${who} is no longer in the directory.`;
}

export const NO_ACTOR_MESSAGE = "Choose who you are acting as to upload or approve.";

// ---- module stores (shared by every mounted selector/prompt; survive sidebar collapse) ----

function tinyStore<T>(initial: T) {
  let value = initial;
  const ls = new Set<() => void>();
  return {
    get: () => value,
    set: (v: T) => {
      if (Object.is(v, value)) return;
      value = v;
      for (const l of [...ls]) l();
    },
    subscribe: (l: () => void) => {
      ls.add(l);
      return () => {
        ls.delete(l);
      };
    },
  };
}

/** The last actor id dropped as stale (shown until the user picks someone). */
export const staleActorStore = tinyStore<StaleActor | null>(null);

/** Test helper. */
export function resetActingAsStoresForTests(): void {
  staleActorStore.set(null);
}

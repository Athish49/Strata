// React-free "acting as" store: which person company writes (uploads, approvals, role
// assignments) are attributed to. There is no auth; the backend validates the id.
//
// Lives under lib/api and imports nothing from React because lib/api/http/company.ts reads
// it, and `api` must stay importable from any module graph (a client hook import here would
// break `next build` if a Server Component ever imported lib/api/client). The React hook is
// in lib/actor.ts; import from there in components.
//
// localStorage can be missing (SSR), empty, or throw (private windows, blocked storage):
// every access is guarded, and an in-memory value keeps the selection for the session.

export const ACTOR_STORAGE_KEY = "strata.actingPersonId";

let memory: string | null = null;
let loaded = false;
const listeners = new Set<() => void>();

function storage(): Storage | null {
  try {
    return typeof window !== "undefined" && window.localStorage ? window.localStorage : null;
  } catch {
    return null;
  }
}

function readStored(): string | null {
  try {
    const v = storage()?.getItem(ACTOR_STORAGE_KEY);
    return v && v.trim() ? v : null;
  } catch {
    return null;
  }
}

function load(): void {
  if (loaded) return;
  if (typeof window === "undefined") return; // SSR: never cache a server-side read
  memory = readStored();
  loaded = true;
}

function emit(): void {
  for (const l of [...listeners]) l();
}

/** The current acting person id, or null when none is selected (always null on the server). */
export function getActingPersonId(): string | null {
  load();
  return memory;
}

/** Select (or clear, with null/"") the acting person. Persists when storage works; always updates memory. */
export function setActingPersonId(personId: string | null): void {
  const next = personId && personId.trim() ? personId.trim() : null;
  loaded = typeof window !== "undefined";
  memory = next;
  try {
    const s = storage();
    if (s) {
      if (next) s.setItem(ACTOR_STORAGE_KEY, next);
      else s.removeItem(ACTOR_STORAGE_KEY);
    }
  } catch {
    /* storage unavailable: the in-memory value still applies for this session */
  }
  emit();
}

function onStorage(e: StorageEvent): void {
  if (e.key !== null && e.key !== ACTOR_STORAGE_KEY) return;
  const next = readStored();
  if (next === memory) return;
  memory = next;
  loaded = true;
  emit();
}

/** useSyncExternalStore subscribe: store changes and cross-tab `storage` events. */
export function subscribeActingPerson(listener: () => void): () => void {
  listeners.add(listener);
  if (listeners.size === 1 && typeof window !== "undefined") window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    if (listeners.size === 0 && typeof window !== "undefined") window.removeEventListener("storage", onStorage);
  };
}

/** Thrown by company write methods when no acting person is selected (before any request is sent). */
export class MissingActorError extends Error {
  constructor() {
    super("Choose who you are acting as before making changes.");
    this.name = "MissingActorError";
  }
}

/** The explicit id if given, else the store's; throws MissingActorError when both are empty. */
export function requireActingPersonId(explicit?: string | null): string {
  const id = (explicit && explicit.trim()) || getActingPersonId();
  if (!id) throw new MissingActorError();
  return id;
}

/** Test helper: forget the in-memory value so the next read goes back to storage. */
export function resetActorStoreForTests(): void {
  memory = null;
  loaded = false;
}

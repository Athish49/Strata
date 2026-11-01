// The "acting as" store for components: re-exports the React-free store in
// lib/api/actor-store.ts and adds the useActingPerson() hook (useSyncExternalStore).
//
// No "use client" directive: hooks only run in Client Components anyway, and a directive
// would turn the re-exported getters into client references for any server importer.
// lib/api/* must import lib/api/actor-store.ts, never this file (it imports React hooks).
import { useSyncExternalStore } from "react";
import { getActingPersonId, setActingPersonId, subscribeActingPerson } from "./api/actor-store";

export {
  ACTOR_STORAGE_KEY,
  MissingActorError,
  getActingPersonId,
  requireActingPersonId,
  resetActorStoreForTests,
  setActingPersonId,
  subscribeActingPerson,
} from "./api/actor-store";

const getServerSnapshot = (): string | null => null;

/**
 * `[personId, setPersonId]`. Renders null on the server and during hydration, then the
 * stored value, so markup never mismatches. Persisted across reloads when storage works.
 */
export function useActingPerson(): readonly [string | null, (personId: string | null) => void] {
  const id = useSyncExternalStore(subscribeActingPerson, getActingPersonId, getServerSnapshot);
  return [id, setActingPersonId] as const;
}

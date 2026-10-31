"use client";
// "Acting as" person selector. There is no auth: every company write carries the chosen
// person as acting_person_id (lib/api/actor-store.ts). This file is the visible control.
//
// Hydration: the store's server snapshot is null and the people list is fetched on the
// client, so the server and the first client render both show a neutral placeholder
// (never "nobody selected", never a name). The real state appears after hydration once
// the list resolves, so there is no flash of the wrong actor and no mismatch.
import * as React from "react";
import { Check, ChevronsUpDown, UserRound, X } from "lucide-react";
import { setActingPersonId, useActingPerson } from "@/lib/actor";
import { useOrgPeople } from "@/lib/api/queries";
import type { OrgPerson } from "@/lib/api/schemas";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import {
  ACTING_AS_CONTROL_ID,
  ACTOR_SEARCH_THRESHOLD,
  NO_ACTOR_MESSAGE,
  activePeople,
  personInitials,
  personSubtitle,
  resolveActor,
  staleActorStore,
  staleMessage,
  type StaleActor,
} from "./acting-as";

const noopSubscribe = () => () => {};
/** false on the server and during hydration, true afterwards (no effect, no extra render pass). */
function useHydrated(): boolean {
  return React.useSyncExternalStore(noopSubscribe, () => true, () => false);
}

// Polite announcement of user-initiated changes, rendered once by the shell control.
let announcement = "";
const announceListeners = new Set<() => void>();
function announce(text: string) {
  announcement = text;
  for (const l of [...announceListeners]) l();
}
function subscribeAnnounce(l: () => void) {
  announceListeners.add(l);
  return () => {
    announceListeners.delete(l);
  };
}

export type ActingActorStatus = "loading" | "none" | "ok" | "stale" | "unverified";

export interface ActingActor {
  /**
   * loading: not hydrated / list loading. none: nobody chosen. ok: `person` is valid.
   * stale: the stored id was dropped (see `stale`). unverified: an id is stored but the
   * people list failed to load, so it could not be checked.
   */
  status: ActingActorStatus;
  /** The id writes will be attributed to (ok/unverified), else null. */
  personId: string | null;
  person: OrgPerson | null;
  /** Set when a previously chosen person was dropped (inactive or deleted). */
  stale: StaleActor | null;
  /** Active people, sorted by name (empty until loaded). */
  people: OrgPerson[];
  /** True once the people list has loaded. */
  peopleLoaded: boolean;
  /** Choose (or clear with null) the acting person. */
  select: (personId: string | null) => void;
}

/**
 * The validated "acting as" person. A stored id that is not an active person is cleared from
 * the store (so writes never carry it) and reported via `stale`. Only clears once the list
 * has loaded successfully; never on a loading or failed fetch.
 */
export function useActingActor(): ActingActor {
  const [storedId] = useActingPerson();
  const hydrated = useHydrated();
  const q = useOrgPeople();
  const stale = React.useSyncExternalStore(staleActorStore.subscribe, staleActorStore.get, () => null);
  const people = React.useMemo(() => activePeople(q.data), [q.data]);
  const id = hydrated ? storedId : null;
  const r = resolveActor(id, q.isSuccess ? q.data : undefined, q.isError);
  const dropped = r.status === "stale" ? r.stale : null;

  React.useEffect(() => {
    if (!dropped) return;
    staleActorStore.set(dropped);
    setActingPersonId(null);
    announce(`${staleMessage(dropped)} ${NO_ACTOR_MESSAGE}`);
  }, [dropped?.id, dropped?.reason]); // eslint-disable-line react-hooks/exhaustive-deps

  const select = React.useCallback((personId: string | null) => {
    staleActorStore.set(null);
    setActingPersonId(personId);
  }, []);

  let status: ActingActorStatus;
  if (!hydrated) status = "loading";
  else if (r.status === "none") status = stale ? "stale" : "none";
  else status = r.status;

  return {
    status,
    personId: r.status === "ok" ? r.person.person_id : r.status === "unverified" ? r.id : null,
    person: r.status === "ok" ? r.person : null,
    stale: dropped ?? (r.status === "none" ? stale : null),
    people,
    peopleLoaded: q.isSuccess,
    select,
  };
}

/** Searchable list of active people. Shared by the shell control and the prompt. */
function PeoplePicker({ actor, onDone }: { actor: ActingActor; onDone: () => void }) {
  const { people, personId, peopleLoaded, select } = actor;
  const choose = (p: OrgPerson | null) => {
    select(p ? p.person_id : null);
    announce(p ? `Now acting as ${p.name}${p.title ? `, ${p.title}` : ""}.` : "No longer acting as anyone.");
    onDone();
  };
  return (
    <Command label="Choose who you are acting as">
      {people.length > ACTOR_SEARCH_THRESHOLD && <CommandInput placeholder="Search people…" aria-label="Search people" />}
      <CommandList>
        {!peopleLoaded && <p className="px-2.5 py-3 text-[14px] text-ink-3">Loading people…</p>}
        {peopleLoaded && people.length === 0 && (
          <p className="px-2.5 py-3 text-[14px] text-ink-3">No active people in the directory.</p>
        )}
        {people.length > 0 && <CommandEmpty>No matching people.</CommandEmpty>}
        {people.length > 0 && (
          <CommandGroup heading="Acting as">
            {people.map((p) => {
              const sub = personSubtitle(p);
              return (
                <CommandItem
                  key={p.person_id}
                  value={p.person_id}
                  keywords={[p.name, p.title ?? "", p.department ?? ""]}
                  onSelect={() => choose(p)}
                  className="items-start"
                >
                  <Check
                    aria-hidden
                    className={cn("mt-0.5 size-4 shrink-0", p.person_id === personId ? "text-ink" : "invisible")}
                    strokeWidth={1.5}
                  />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate">{p.name}</span>
                    {sub && <span className="block truncate text-[12px] text-ink-3">{sub}</span>}
                  </span>
                  {p.person_id === personId && <span className="sr-only">(current)</span>}
                </CommandItem>
              );
            })}
          </CommandGroup>
        )}
        {personId && (
          <CommandGroup>
            <CommandItem value="__clear__" keywords={["clear", "none"]} onSelect={() => choose(null)}>
              <X aria-hidden className="size-4 shrink-0 text-ink-3" strokeWidth={1.5} />
              Clear selection
            </CommandItem>
          </CommandGroup>
        )}
      </CommandList>
      <p className="border-t border-border px-3 py-2 text-[12px] leading-4 text-ink-3">
        No sign-in: uploads and approvals are attributed to the person you choose.
      </p>
    </Command>
  );
}

/** Popover body hosting the picker; moves focus into the list (or its search box) on open. */
function PickerContent({
  actor,
  onDone,
  ...props
}: { actor: ActingActor; onDone: () => void } & Pick<React.ComponentProps<typeof PopoverContent>, "side" | "align">) {
  return (
    <PopoverContent
      {...props}
      className="w-[320px] overflow-hidden p-0"
      onOpenAutoFocus={(e) => {
        e.preventDefault();
        const root = e.currentTarget as HTMLElement | null;
        const target = root?.querySelector<HTMLElement>("[cmdk-input]") ?? root?.querySelector<HTMLElement>("[cmdk-root]");
        target?.focus();
      }}
    >
      <PeoplePicker actor={actor} onDone={onDone} />
    </PopoverContent>
  );
}

function triggerLabel(a: ActingActor): string {
  if (a.status === "ok" && a.person) return `Acting as ${a.person.name}${a.person.title ? `, ${a.person.title}` : ""}. Change`;
  if (a.status === "unverified") return `Acting as person ${a.personId}. Change`;
  if (a.status === "stale" && a.stale) return `${staleMessage(a.stale)} ${NO_ACTOR_MESSAGE}`;
  if (a.status === "loading") return "Acting as: loading";
  return NO_ACTOR_MESSAGE;
}

/** The shell control (sidebar footer, next to the company chip). `collapsed` = 64px rail. */
export function ActingAsControl({ collapsed }: { collapsed?: boolean }) {
  const actor = useActingActor();
  const [open, setOpen] = React.useState(false);
  const live = React.useSyncExternalStore(subscribeAnnounce, () => announcement, () => "");
  const { status, person, stale } = actor;
  const needsChoice = status === "none" || status === "stale";
  const label = triggerLabel(actor);

  const liveRegion = (
    <span className="sr-only" aria-live="polite" role="status">
      {live}
    </span>
  );

  if (collapsed) {
    const button = (
      <button
        type="button"
        id={ACTING_AS_CONTROL_ID}
        aria-label={label}
        disabled={status === "loading"}
        className="relative grid size-8 place-items-center rounded-[8px] text-sidebar-fg transition-colors duration-150 hover:bg-sidebar-active disabled:cursor-default"
      >
        {person ? (
          <span aria-hidden className="grid size-6 place-items-center rounded-[4px] bg-sidebar-active text-[11px] font-medium">
            {personInitials(person.name)}
          </span>
        ) : (
          <UserRound aria-hidden className="size-4 text-sidebar-muted" strokeWidth={1.5} />
        )}
        {needsChoice && <span aria-hidden className="absolute right-1 top-1 size-1.5 rounded-full bg-amber-soft" />}
      </button>
    );
    return (
      <>
        <Popover open={open} onOpenChange={setOpen}>
          <Tooltip>
            <TooltipTrigger asChild>
              <PopoverTrigger asChild>{button}</PopoverTrigger>
            </TooltipTrigger>
            <TooltipContent side="right">{label.replace(/\. Change$/, "")}</TooltipContent>
          </Tooltip>
          <PickerContent side="right" align="end" actor={actor} onDone={() => setOpen(false)} />
        </Popover>
        {liveRegion}
      </>
    );
  }

  let body: React.ReactNode;
  if (status === "loading") {
    body = (
      <span aria-hidden className="block space-y-1.5 py-0.5">
        <span className="block h-3 w-16 rounded-[3px] bg-sidebar-active" />
        <span className="block h-3.5 w-32 rounded-[3px] bg-sidebar-active" />
      </span>
    );
  } else if (status === "ok" && person) {
    const sub = personSubtitle(person);
    body = (
      <>
        <span className="block truncate text-[14px] leading-5 text-sidebar-fg">{person.name}</span>
        {sub && <span className="block truncate text-[12px] leading-4 text-sidebar-muted">{sub}</span>}
      </>
    );
  } else if (status === "unverified") {
    body = (
      <>
        <span className="block truncate text-[14px] leading-5 text-sidebar-fg">Person {actor.personId}</span>
        <span className="block truncate text-[12px] leading-4 text-sidebar-muted">Couldn&apos;t load the directory</span>
      </>
    );
  } else {
    body = (
      <>
        {stale && <span className="block text-[12px] leading-4 text-sidebar-fg">{staleMessage(stale)}</span>}
        <span className="block text-[12px] leading-4 text-sidebar-muted">{NO_ACTOR_MESSAGE}</span>
      </>
    );
  }

  return (
    <>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button
            type="button"
            id={ACTING_AS_CONTROL_ID}
            aria-label={label}
            disabled={status === "loading"}
            className={cn(
              "flex w-full items-center gap-3 rounded-[8px] px-3 py-1.5 text-left transition-colors duration-150 hover:bg-sidebar-active/60 disabled:cursor-default disabled:hover:bg-transparent",
              needsChoice && "border border-sidebar-border",
            )}
          >
            <span
              aria-hidden
              className="grid size-6 shrink-0 place-items-center rounded-[4px] bg-sidebar-active text-[11px] font-medium text-sidebar-fg"
            >
              {person ? personInitials(person.name) : <UserRound className="size-3.5 text-sidebar-muted" strokeWidth={1.5} />}
            </span>
            <span className="min-w-0 flex-1">
              <span aria-hidden className="block text-[12px] leading-4 text-sidebar-muted">
                Acting as
              </span>
              <span aria-hidden className="block">
                {body}
              </span>
            </span>
            <ChevronsUpDown aria-hidden className="size-3.5 shrink-0 text-sidebar-muted" strokeWidth={1.5} />
          </button>
        </PopoverTrigger>
        <PickerContent side="top" align="start" actor={actor} onDone={() => setOpen(false)} />
      </Popover>
      {liveRegion}
    </>
  );
}

/**
 * Inline, non-blocking prompt for screens whose action needs an actor (upload, approve).
 * Renders nothing while loading or once a valid person is chosen; otherwise explains why
 * (nobody chosen, or the previous person was dropped) with its own "Choose person" picker.
 * Works outside <AppShell> too (it does not depend on ShellContext or the tooltip provider).
 */
export function ActingAsPrompt({ message = NO_ACTOR_MESSAGE, className }: { message?: string; className?: string }) {
  const actor = useActingActor();
  const [open, setOpen] = React.useState(false);
  const show = actor.status === "none" || actor.status === "stale";
  return (
    <div role="status">
      {show && (
        <div
          className={cn(
            "flex flex-wrap items-center gap-3 rounded-[10px] border border-border bg-amber-soft px-4 py-2.5",
            className,
          )}
        >
          <UserRound aria-hidden className="size-4 shrink-0 text-amber" strokeWidth={1.5} />
          <p className="min-w-0 flex-1 text-[14px] leading-5 text-ink">
            {actor.stale && <span className="font-medium">{staleMessage(actor.stale)} </span>}
            {message}
          </p>
          <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
              <Button size="sm" variant="secondary">
                Choose person
              </Button>
            </PopoverTrigger>
            <PickerContent align="end" actor={actor} onDone={() => setOpen(false)} />
          </Popover>
        </div>
      )}
    </div>
  );
}

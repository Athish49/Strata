"use client";
import * as React from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { FutureCue } from "@/components/common/FutureCue";
import { api } from "@/lib/api/client";
import { qk, useAgencies, useChanges, useDocuments, usePeople } from "@/lib/api/queries";
import { withRunParam } from "@/lib/app-link";
import { changeClassLabel } from "@/lib/labels";
import { useRunContext } from "@/lib/run-context";
import { agencyHref, sectionHref } from "@/components/kb/links";
import { useShell } from "./ShellContext";
import { idRank, matchesAll, norm, searchClauses, snippet, toClauseEntry, type ClauseEntry } from "./search-index";

const MIN_CLAUSE_QUERY = 2;

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = React.useState(value);
  React.useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms);
    return () => window.clearTimeout(t);
  }, [value, ms]);
  return v;
}

/** Clause text of every document, fetched lazily (only once the dialog is open and a query is typed). */
function useClauseIndex(enabled: boolean, docIds: readonly string[]) {
  const qc = useQueryClient();
  const key = docIds.join("|");
  return useQuery({
    queryKey: ["search", "clause-index", key],
    enabled: enabled && docIds.length > 0,
    staleTime: 10 * 60_000,
    queryFn: async (): Promise<ClauseEntry[]> => {
      const lists = await Promise.all(
        docIds.map((id) => qc.fetchQuery({ queryKey: qk.clauses(id), queryFn: () => api.company.listClauses(id), staleTime: 10 * 60_000 })),
      );
      return lists.flat().map(toClauseEntry);
    },
  });
}

function Row({ primary, secondary, mono }: { primary: React.ReactNode; secondary?: React.ReactNode; mono?: boolean }) {
  return (
    <span className="flex min-w-0 flex-1 flex-col">
      <span className={mono ? "truncate font-mono text-[13px] text-ink" : "truncate text-ink"}>{primary}</span>
      {secondary ? <span className="truncate text-[12px] text-ink-3">{secondary}</span> : null}
    </span>
  );
}

/** cmdk dialog (⌘K / Ctrl K): documents, clauses, changed sections, regulations and people, matched client-side. */
export function GlobalSearch() {
  const { searchOpen, setSearchOpen } = useShell();
  const router = useRouter();
  const sp = useSearchParams();
  const runParam = sp?.get("run") ?? null;
  const { runId } = useRunContext();
  const [query, setQuery] = React.useState("");
  const q = query.trim();
  const dq = useDebounced(q, 150);

  // Everything below is lazy: nothing is requested until the dialog opens.
  const docsQ = useDocuments();
  const docs = React.useMemo(() => (searchOpen ? docsQ.data ?? [] : []), [searchOpen, docsQ.data]);
  const peopleQ = usePeople();
  const changesQ = useChanges(searchOpen ? runId : null);
  const agenciesQ = useAgencies();
  const docIds = React.useMemo(() => (docsQ.data ?? []).map((d) => d.doc_id), [docsQ.data]);
  const clauseIdx = useClauseIndex(searchOpen && dq.length >= MIN_CLAUSE_QUERY, docIds);
  const sectionsQ = useQuery({
    queryKey: ["search", "sections", dq],
    enabled: searchOpen && dq.length >= 3,
    staleTime: 5 * 60_000,
    queryFn: () => api.kb.listSections({ search: dq, limit: 6 }),
  });

  const results = React.useMemo(() => {
    if (dq.length < 1) return null;
    const documents = docs
      .map((d) => ({ d, rank: idRank(d.doc_id, dq) ?? (matchesAll(norm(d.title), dq) ? 3 : null) }))
      .filter((x): x is { d: (typeof docs)[number]; rank: number } => x.rank !== null)
      .sort((a, b) => a.rank - b.rank)
      .slice(0, 5)
      .map((x) => x.d);
    const clauses = searchClauses(clauseIdx.data ?? [], dq, 6);
    const changeRows = changesQ.data ?? [];
    const changes = changeRows
      .map((c) => ({ c, rank: idRank(c.citation, dq) ?? (matchesAll(norm(c.heading), dq) ? 3 : null) }))
      .filter((x): x is { c: (typeof changeRows)[number]; rank: number } => x.rank !== null)
      .sort((a, b) => a.rank - b.rank)
      .slice(0, 5)
      .map((x) => x.c);
    const agencies = (agenciesQ.data ?? []).filter((a) => matchesAll(norm(`${a.slug} ${a.name}`), dq)).slice(0, 3);
    const people = (peopleQ.data ?? []).filter((p) => matchesAll(norm(`${p.name} ${p.title} ${p.department}`), dq)).slice(0, 4);
    const sections = sectionsQ.data?.items ?? [];
    return { documents, clauses, changes, agencies, sections, people };
  }, [dq, docs, clauseIdx.data, changesQ.data, agenciesQ.data, peopleQ.data, sectionsQ.data]);

  const go = (href: string) => {
    setSearchOpen(false);
    setQuery("");
    router.push(withRunParam(href, runParam));
  };

  const total = results ? results.documents.length + results.clauses.length + results.changes.length + results.agencies.length + results.sections.length + results.people.length : 0;
  const pending = !!results && (clauseIdx.isFetching || sectionsQ.isFetching || (q !== dq));
  const docTitle = (id: string) => docs.find((d) => d.doc_id === id)?.title;

  // Clause text hits are numerous: they go last unless the query is itself a clause id.
  const clausesFirst = !!results && results.clauses.some((c) => idRank(c.clauseId, dq) !== null && idRank(c.clauseId, dq)! <= 1);
  const clauseGroup =
    results && results.clauses.length > 0 ? (
      <CommandGroup heading="Clauses">
                {results.clauses.map((c) => (
                  <CommandItem
                    key={c.clauseId}
                    value={`clause:${c.clauseId}`}
                    onSelect={() => go(`/app/documents/${encodeURIComponent(c.docId)}?clause=${encodeURIComponent(c.clauseId)}`)}
                  >
                    <Row primary={snippet(c.text, dq)} secondary={`${c.docId} · ${c.localId}${docTitle(c.docId) ? ` · ${docTitle(c.docId)}` : ""}`} />
                  </CommandItem>
                ))}
              </CommandGroup>
    ) : null;

  return (
    <Dialog
      open={searchOpen}
      onOpenChange={(o) => {
        setSearchOpen(o);
        if (!o) setQuery("");
      }}
    >
      <DialogContent showClose={false} className="max-w-[600px]">
        <DialogTitle className="sr-only">Search</DialogTitle>
        <DialogDescription className="sr-only">
          Search documents, clauses, changed sections, regulations and people.
        </DialogDescription>
        <Command shouldFilter={false} label="Search">
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder="Search doc id, clause id, citation…"
          />
          <CommandList>
            {!results && (
              <p className="px-2.5 py-3 text-[14px] leading-5 text-ink-3">
                Search documents, clauses, changed sections, regulations and people.
              </p>
            )}
            {results && total === 0 && (
              <p className="px-2.5 py-3 text-[14px] leading-5 text-ink-3" role="status">
                {pending ? "Searching…" : `No results for “${q}”.`}
              </p>
            )}
            {clausesFirst && clauseGroup}
            {results && results.documents.length > 0 && (
              <CommandGroup heading="Documents">
                {results.documents.map((d) => (
                  <CommandItem key={d.doc_id} value={`doc:${d.doc_id}`} onSelect={() => go(`/app/documents/${encodeURIComponent(d.doc_id)}`)}>
                    <Row primary={d.title} secondary={d.doc_id} />
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {results && results.changes.length > 0 && (
              <CommandGroup heading="Changed sections">
                {results.changes.map((c) => (
                  <CommandItem key={c.change_id} value={`change:${c.change_id}`} onSelect={() => go(`/app/changes/${encodeURIComponent(c.change_id)}`)}>
                    <Row mono primary={c.citation} secondary={`${c.heading || "Untitled section"} · ${changeClassLabel(c.change_class)}`} />
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {results && (results.agencies.length > 0 || results.sections.length > 0) && (
              <CommandGroup heading="Regulations">
                {results.agencies.map((a) => (
                  <CommandItem key={`agency:${a.slug}`} value={`agency:${a.slug}`} onSelect={() => go(agencyHref(a.slug))}>
                    <Row primary={a.name} secondary={`${a.level === "federal" ? "Federal" : "State"} agency`} />
                  </CommandItem>
                ))}
                {results.sections.map((s) => (
                  <CommandItem key={`sec:${s.source_system}:${s.citation}`} value={`sec:${s.source_system}:${s.citation}`} onSelect={() => go(sectionHref(s.source_system, s.citation))}>
                    <Row mono primary={s.citation} secondary={s.heading || undefined} />
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {results && results.people.length > 0 && (
              <CommandGroup heading="People">
                {results.people.map((p) => (
                  <CommandItem key={p.person_id} value={`person:${p.person_id}`} onSelect={() => go(`/app/company#person-${encodeURIComponent(p.person_id)}`)}>
                    <Row primary={p.name} secondary={`${p.title} · ${p.department}`} />
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            {!clausesFirst && clauseGroup}
            {q && (
              <FutureCue id="search-ask" variant="menu-item" side="left" label={`Ask Strata “${q}”`} />
            )}
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

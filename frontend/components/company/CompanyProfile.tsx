"use client";
import * as React from "react";
import { ChevronDown, ChevronRight, Network, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CitationText } from "@/components/common/CitationText";
import { DocChip } from "@/components/common/DocChip";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { FutureCue } from "@/components/common/FutureCue";
import { PersonChip } from "@/components/common/PersonChip";
import { SectionHeader } from "@/components/common/SectionHeader";
import { AppLink } from "@/lib/app-link";
import { useDocuments, usePeople, useProfile } from "@/lib/api/queries";
import type { CompanyProfile as Profile, DocumentMeta, Person } from "@/lib/api/schemas";
import { formatCount } from "@/lib/format";
import { compareVerticals, verticalName } from "@/lib/verticals";
import { cn } from "@/lib/utils";
import { attributeLabel, attributeValue, docsByPerson, groupByDepartment, reportingRows, type PersonDoc } from "./people";

export function CompanyHeader({ profile, docs, peopleCount }: { profile: Profile; docs: number; peopleCount: number }) {
  const facts: { label: string; value: string }[] = [
    { label: "Type", value: profile.type },
    { label: "State", value: profile.state },
    { label: "Customers", value: profile.customers > 0 ? formatCount(profile.customers) : "" },
    { label: "Regulator", value: profile.regulator },
  ].filter((f) => f.value);
  return (
    <div className="rounded-[12px] border border-border bg-surface p-6">
      <div className="flex items-start gap-4">
        <span aria-hidden className="grid size-10 place-items-center rounded-[8px] bg-ink font-serif text-[20px] text-white">
          {(profile.name || "R").charAt(0)}
        </span>
        <div className="min-w-0">
          <h2 className="font-serif text-[24px] leading-8 text-ink">{profile.name}</h2>
          <p className="text-[14px] text-ink-3">
            {formatCount(docs)} documents · {formatCount(peopleCount)} people
          </p>
        </div>
      </div>
      <dl className="mt-5 grid gap-x-8 gap-y-3 sm:grid-cols-2 xl:grid-cols-4">
        {facts.map((f) => (
          <div key={f.label}>
            <dt className="text-[12px] font-medium text-ink-3">{f.label}</dt>
            <dd className="text-[14px] text-ink">{f.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function AttributesTable({ profile, highlight }: { profile: Profile; highlight?: string | null }) {
  const rows = [...profile.attributes].sort((a, b) => a.key.localeCompare(b.key));
  if (rows.length === 0) {
    return <EmptyState title="No attributes recorded" description="Radar screens changes against these attributes once they are set." />;
  }
  return (
    <div className="overflow-hidden rounded-[12px] border border-border bg-surface">
      <table className="w-full text-left text-[13px]">
        <thead>
          <tr className="h-10 border-b border-border text-[12px] font-medium text-ink-3">
            <th className="w-12 px-4 font-medium">#</th>
            <th className="px-4 font-medium">Attribute</th>
            <th className="px-4 font-medium">Value</th>
            <th className="px-4 font-medium">Source</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((a, i) => (
            <tr
              key={a.key}
              id={a.key}
              className={cn("h-10 scroll-mt-24 border-b border-border last:border-b-0 hover:bg-surface-muted", highlight === a.key && "bg-surface-muted")}
            >
              <td className="px-4 tabular-nums text-ink-3">{i + 1}</td>
              <td className="px-4">
                <div className="text-ink">{attributeLabel(a.key)}</div>
                <CitationText className="text-[11.5px] text-ink-3">{a.key}</CitationText>
              </td>
              <td className="px-4 tabular-nums text-ink">{attributeValue(a.value)}</td>
              <td className="px-4 text-ink-3">{a.source || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DocLinks({ items }: { items: PersonDoc[] }) {
  if (items.length === 0) return <span className="text-ink-4">—</span>;
  return (
    <span className="flex flex-wrap gap-x-3 gap-y-1">
      {items.map(({ doc, role }) => (
        <span key={`${doc.doc_id}|${role}`} className="inline-flex items-center gap-1.5">
          <DocChip docId={doc.doc_id} href={doc.monitored ? `/app/documents/${encodeURIComponent(doc.doc_id)}` : undefined} />
          <span className="text-[11.5px] text-ink-3">{role.toLowerCase()}</span>
        </span>
      ))}
    </span>
  );
}

type PeopleView = "department" | "reporting";

export function PeopleSection({ people, docs }: { people: Person[]; docs: DocumentMeta[] }) {
  const [view, setView] = React.useState<PeopleView>("department");
  const [collapsed, setCollapsed] = React.useState<Set<string>>(new Set());
  const byId = React.useMemo(() => new Map(people.map((p) => [p.person_id, p])), [people]);
  const personDocs = React.useMemo(() => docsByPerson(docs), [docs]);
  const groups = React.useMemo(() => groupByDepartment(people), [people]);
  const rows = React.useMemo(() => reportingRows(people), [people]);

  const row = (p: Person, depth = 0) => (
    <tr key={p.person_id} id={`person-${p.person_id}`} className="min-h-10 border-b border-border align-top last:border-b-0 hover:bg-surface-muted">
      <td className="px-4 py-2" style={{ paddingLeft: 16 + depth * 20 }}>
        <PersonChip name={p.name} />
      </td>
      <td className="px-4 py-2 text-ink-2">{p.title}</td>
      <td className="px-4 py-2 text-ink-3">{view === "reporting" ? p.department : (p.reports_to_id && byId.get(p.reports_to_id)?.name) || "—"}</td>
      <td className="px-4 py-2 text-[13px]">
        <DocLinks items={personDocs.get(p.person_id) ?? []} />
      </td>
    </tr>
  );

  return (
    <div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <div role="tablist" className="inline-flex gap-1">
          {(
            [
              { key: "department", label: "By department", icon: Users },
              { key: "reporting", label: "Reporting line", icon: Network },
            ] as const
          ).map((t) => (
            <button
              key={t.key}
              role="tab"
              type="button"
              aria-selected={view === t.key}
              onClick={() => setView(t.key)}
              className={cn(
                "inline-flex h-8 items-center gap-2 rounded-[8px] border px-3 text-[14px] font-medium",
                view === t.key ? "border-border bg-surface text-ink" : "border-transparent text-ink-3 hover:text-ink",
              )}
            >
              <t.icon className="size-4" strokeWidth={1.5} />
              {t.label}
            </button>
          ))}
        </div>
        <FutureCue id="sync-directory" />
      </div>
      <div className="overflow-hidden rounded-[12px] border border-border bg-surface">
        <table className="w-full text-left text-[13px]">
          <thead>
            <tr className="h-10 border-b border-border text-[12px] font-medium text-ink-3">
              <th className="px-4 font-medium">Name</th>
              <th className="px-4 font-medium">Title</th>
              <th className="px-4 font-medium">{view === "reporting" ? "Department" : "Reports to"}</th>
              <th className="px-4 font-medium">Documents</th>
            </tr>
          </thead>
          <tbody>
            {view === "department"
              ? groups.map((g) => {
                  const closed = collapsed.has(g.department);
                  return (
                    <React.Fragment key={g.department}>
                      <tr className="h-10 bg-surface-muted">
                        <td colSpan={4} className="px-4">
                          <button
                            type="button"
                            aria-expanded={!closed}
                            onClick={() =>
                              setCollapsed((prev) => {
                                const n = new Set(prev);
                                if (n.has(g.department)) n.delete(g.department);
                                else n.add(g.department);
                                return n;
                              })
                            }
                            className="inline-flex items-center gap-2"
                          >
                            {closed ? <ChevronRight className="size-4 text-ink-3" strokeWidth={1.5} /> : <ChevronDown className="size-4 text-ink-3" strokeWidth={1.5} />}
                            <span className="text-[13px] font-medium text-ink">{g.department}</span>
                            <span className="text-[13px] text-ink-3">· {g.people.length} {g.people.length === 1 ? "person" : "people"}</span>
                          </button>
                        </td>
                      </tr>
                      {!closed && g.people.map((p) => row(p))}
                    </React.Fragment>
                  );
                })
              : rows.map((r) => row(r.person, r.depth))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function DocumentsSummary({ docs }: { docs: DocumentMeta[] }) {
  const monitored = docs.filter((d) => d.monitored);
  const twoSig = docs.filter((d) => d.two_signature).length;
  const byVertical = new Map<string, DocumentMeta[]>();
  for (const d of docs) byVertical.set(d.vertical, [...(byVertical.get(d.vertical) ?? []), d]);
  const groups = [...byVertical.entries()].sort(([a], [b]) => compareVerticals(a, b));
  if (docs.length === 0) return <EmptyState title="No documents on file" description="Company documents appear here once they are loaded and split into clauses." />;
  return (
    <div className="rounded-[12px] border border-border bg-surface">
      <div className="flex flex-wrap gap-x-8 gap-y-1 border-b border-border px-5 py-3 text-[13px] text-ink-3">
        <span><span className="font-medium text-ink">{formatCount(docs.length)}</span> documents</span>
        <span><span className="font-medium text-ink">{formatCount(monitored.length)}</span> monitored</span>
        <span><span className="font-medium text-ink">{formatCount(twoSig)}</span> two-signature</span>
        <span><span className="font-medium text-ink">{formatCount(groups.length)}</span> verticals</span>
      </div>
      <div className="divide-y divide-border">
        {groups.map(([vertical, list]) => (
          <div key={vertical} className="px-5 py-3">
            <div className="mb-1.5 flex items-center gap-2 text-[13px] font-medium text-ink">
              {verticalName(vertical)} <span className="font-normal text-ink-3">· {list.length}</span>
            </div>
            <ul className="space-y-1">
              {list.map((d) => (
                <li key={d.doc_id} className="flex items-center gap-3 text-[13px]">
                  <DocChip docId={d.doc_id} title={d.title} href={d.monitored ? `/app/documents/${encodeURIComponent(d.doc_id)}` : undefined} className="flex-1" />
                  <PersonChip name={d.owner.name} className="hidden md:inline-flex" />
                  {d.two_signature && <Badge variant="tag">Two-signature</Badge>}
                  {!d.monitored && <Badge variant="tag">Not monitored</Badge>}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-border px-5 py-3 text-[13px]">
        <AppLink href="/app/documents" className="font-medium text-ink-2 hover:text-ink">
          Open the documents board
        </AppLink>
      </div>
    </div>
  );
}

/** The whole company page body (header, attributes, people, documents) with loading and error states. */
export function CompanyPage({ highlight }: { highlight?: string | null }) {
  const profile = useProfile();
  const people = usePeople();
  const docs = useDocuments();

  // Deep links (/app/company#owns_generating_units) need the table in the DOM first.
  const ready = !!profile.data;
  React.useEffect(() => {
    if (!ready) return;
    const id = decodeURIComponent(window.location.hash.replace(/^#/, ""));
    if (id) document.getElementById(id)?.scrollIntoView({ block: "center" });
  }, [ready]);

  if (profile.isError) {
    return <ErrorState message="The company profile could not be loaded." source="Company data" onRetry={() => void profile.refetch()} />;
  }
  if (profile.isLoading || !profile.data) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-[150px] rounded-[12px]" />
        <Skeleton className="h-[360px] rounded-[12px]" />
      </div>
    );
  }
  return (
    <div className="space-y-10">
      <CompanyHeader profile={profile.data} docs={docs.data?.length ?? 0} peopleCount={people.data?.length ?? 0} />
      <section>
        <SectionHeader title="Attributes" subtitle="The facts Radar screens every regulatory change against" className="mb-4" />
        <AttributesTable profile={profile.data} highlight={highlight} />
      </section>
      <section>
        <SectionHeader title="People" subtitle="Who owns, reviews and approves each document" className="mb-4" />
        {people.isError ? (
          <ErrorState message="The people directory could not be loaded." source="Company data" onRetry={() => void people.refetch()} />
        ) : people.isLoading ? (
          <Skeleton className="h-[300px] rounded-[12px]" />
        ) : (people.data ?? []).length === 0 ? (
          <EmptyState title="No people on file" description="The directory is empty." />
        ) : (
          <PeopleSection people={people.data ?? []} docs={docs.data ?? []} />
        )}
      </section>
      <section>
        <SectionHeader title="Documents" subtitle="Company documents by vertical" viewAllHref="/app/documents" viewAllLabel="Open board" className="mb-4" />
        {docs.isError ? (
          <ErrorState message="Documents could not be loaded." source="Company data" onRetry={() => void docs.refetch()} />
        ) : docs.isLoading ? (
          <Skeleton className="h-[200px] rounded-[12px]" />
        ) : (
          <DocumentsSummary docs={docs.data ?? []} />
        )}
      </section>
    </div>
  );
}

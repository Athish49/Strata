"use client";
import * as React from "react";
import { useParams } from "next/navigation";
import { ArrowRight } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { useRecordRecent } from "@/components/shell/Recents";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { AttributeChip } from "@/components/common/AttributeChip";
import { CitationText } from "@/components/common/CitationText";
import { DocChip } from "@/components/common/DocChip";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { FutureCue } from "@/components/common/FutureCue";
import { AppLink } from "@/lib/app-link";
import { ClassTag } from "@/components/kb/bits";
import { LineDiffView } from "@/components/kb/LineDiffView";
import { SectionBody } from "@/components/kb/SectionBody";
import { agencyHref, decodeCatchAll, safeDecode, sectionHref } from "@/components/kb/links";
import { amendmentTarget, citedByDocuments, crossRefs } from "@/components/kb/section-utils";
import { useChanges, useCompare, useDocuments, useSection, useVersionHistory } from "@/lib/api/queries";
import { formatDate } from "@/lib/format";
import { useRunContext } from "@/lib/run-context";
import { cn } from "@/lib/utils";

type View = "text" | "s1" | "compare";

function Segmented({ value, onChange, items }: { value: View; onChange: (v: View) => void; items: { key: View; label: string; disabled?: boolean }[] }) {
  return (
    <div role="tablist" className="inline-flex items-center gap-1">
      {items.map((it) => (
        <button
          key={it.key}
          role="tab"
          type="button"
          aria-selected={value === it.key}
          disabled={it.disabled}
          onClick={() => onChange(it.key)}
          className={cn(
            "h-8 rounded-[8px] border px-3 text-[14px] font-medium transition-colors duration-150 disabled:text-ink-4",
            value === it.key ? "border-border bg-surface text-ink" : "border-transparent text-ink-3 hover:text-ink",
          )}
        >
          {it.label}
        </button>
      ))}
    </div>
  );
}

export default function Page() {
  const params = useParams<{ sourceSystem: string; citation: string[] }>();
  const sourceSystem = safeDecode(String(params?.sourceSystem ?? ""));
  const citation = decodeCatchAll(params?.citation);
  const section = useSection(sourceSystem, citation);
  const versions = useVersionHistory(sourceSystem, citation);
  const [view, setView] = React.useState<View>("text");
  const hasCompare = (versions.data?.length ?? 0) >= 2;
  const compare = useCompare(view === "compare" && hasCompare ? sourceSystem : null, citation);
  const docs = useDocuments();
  const { runId } = useRunContext();
  const changes = useChanges(runId);
  const s = section.data;
  const change = (changes.data ?? []).find((c) => c.citation === citation && c.source_system === sourceSystem);
  const citedBy = React.useMemo(() => citedByDocuments(docs.data ?? [], citation), [docs.data, citation]);
  useRecordRecent(s ? { href: sectionHref(s.source_system, s.citation), label: s.citation } : null);

  const agencyCrumb = s?.owning_agency ? { label: s.owning_agency.toUpperCase(), href: agencyHref(s.owning_agency) } : { label: "Agency" };
  const crumbs = [{ label: "Regulations", href: "/app/regulations" }, agencyCrumb, { label: citation, mono: true }];

  if (section.isError) {
    return (
      <PageContainer>
        <PageHeader title={citation} breadcrumbs={crumbs.slice(0, 1).concat({ label: citation, mono: true })} />
        <ErrorState message="This section could not be loaded." source="Knowledge base · sections" onRetry={() => void section.refetch()} />
      </PageContainer>
    );
  }
  if (section.isLoading) {
    return (
      <PageContainer>
        <PageHeader title={citation} breadcrumbs={crumbs} />
        <Skeleton className="mb-4 h-8 w-1/2" />
        <Skeleton className="h-[320px] rounded-[12px]" />
      </PageContainer>
    );
  }
  if (!s) {
    return (
      <PageContainer>
        <PageHeader title={citation} breadcrumbs={[{ label: "Regulations", href: "/app/regulations" }, { label: citation, mono: true }]} />
        <EmptyState
          title="This section is not in the knowledge base"
          description="It may be a reference to a rule outside the codebooks Strata tracks."
          action={<AppLink href="/app/regulations" className="text-[14px] font-medium text-ink underline">Back to regulations</AppLink>}
        />
      </PageContainer>
    );
  }

  const amend = amendmentTarget(s);
  const refs = crossRefs(s);
  const vs = versions.data ?? [];
  const s1 = vs.find((v) => v.snapshot === "S1");
  const text = s.body_text || vs[vs.length - 1]?.text || "";

  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={crumbs}
        caption={`${s.rule_key} · snapshot ${formatDate(s.snapshot_date)}`}
        title={<span className="font-mono text-[28px] tracking-normal">{s.citation}</span>}
        actions={
          <>
            <FutureCue id="add-note" />
            <FutureCue id="watch" />
          </>
        }
      />
      <h2 className="mb-4 max-w-[80ch] font-serif text-[22px] leading-[30px] text-ink">{s.heading || "Untitled section"}</h2>
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Badge variant={s.status === "repealed" ? "red" : "green"}>{s.status === "repealed" ? "Repealed" : "Approved"}</Badge>
        {s.owning_agency && (
          <AppLink href={agencyHref(s.owning_agency)}>
            <AttributeChip label="Agency">{s.owning_agency.toUpperCase()}</AttributeChip>
          </AppLink>
        )}
        <AttributeChip label="Title">{s.title_number}</AttributeChip>
        {s.part_or_article && <AttributeChip label={s.source_system === "cfr" ? "Part" : "Article"}>{s.part_or_article}</AttributeChip>}
        {amend && (
          <AttributeChip label="Amended by">
            {amend.href ? (
              <AppLink href={amend.href} className="font-mono text-[12px] underline-offset-2 hover:underline">
                {amend.label}
              </AppLink>
            ) : (
              <span className="font-mono text-[12px]">{amend.label}</span>
            )}
          </AttributeChip>
        )}
      </div>

      {change && (
        <AppLink
          href={`/app/changes/${encodeURIComponent(change.change_id)}`}
          className="mb-6 flex items-center gap-3 rounded-[12px] border border-border bg-surface px-5 py-3 text-[14px] text-ink-2 hover:bg-surface-muted"
        >
          <ClassTag cls={change.change_class} />
          <span className="flex-1">Changed in this run — view analysis</span>
          <ArrowRight className="size-4 text-ink-3" strokeWidth={1.5} />
        </AppLink>
      )}

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 rounded-[12px] border border-border bg-surface">
          <div className="flex items-center justify-between gap-3 border-b border-border px-3 py-2">
            <Segmented
              value={view}
              onChange={setView}
              items={[
                { key: "text", label: s.status === "repealed" ? "Last text" : "Current text" },
                { key: "s1", label: "S1 text", disabled: !s1 },
                { key: "compare", label: "Compare S1 ↔ S2", disabled: !hasCompare },
              ]}
            />
            {vs.length > 0 && (
              <span className="text-[12px] text-ink-3">
                {vs.map((v) => `${v.snapshot} ${formatDate(v.snapshot_date)}`).join(" → ")}
              </span>
            )}
          </div>
          <div className="p-6">
            {view === "text" &&
              (text ? <SectionBody text={text} /> : <EmptyState className="px-0" title="No text is stored for this section" description="The knowledge base holds the heading but no body text for this snapshot." />)}
            {view === "s1" && s1 && <SectionBody text={s1.text} />}
            {view === "compare" &&
              (compare.isLoading ? (
                <Skeleton className="h-40" />
              ) : compare.isError ? (
                <ErrorState className="px-0" message="The comparison could not be loaded." source="Knowledge base · versions" onRetry={() => void compare.refetch()} />
              ) : (compare.data ?? []).every((l) => l.op === "equal") ? (
                <EmptyState className="px-0" title="No text change between S1 and S2" description="The two snapshots hold identical text for this section." />
              ) : (
                <LineDiffView diff={compare.data ?? []} />
              ))}
            {!hasCompare && !versions.isLoading && (
              <p className="mt-6 border-t border-border pt-3 text-[13px] text-ink-3">
                {vs.length === 1 ? `Only the ${vs[0].snapshot} snapshot exists for this section, so there is nothing to compare.` : "No version history is recorded for this section."}
              </p>
            )}
          </div>
        </div>

        <aside className="space-y-8">
          <section>
            <h3 className="mb-2 text-[14px] font-medium text-ink">Cross-references</h3>
            {refs.length === 0 ? (
              <p className="text-[13px] text-ink-3">This section does not reference other rules.</p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {refs.map((r) => (
                  <li key={r.citation}>
                    <AppLink href={r.href} className="inline-flex h-6 items-center rounded-[6px] bg-surface-muted px-2 hover:bg-border">
                      <CitationText className="text-[12px]">{r.citation}</CitationText>
                    </AppLink>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section>
            <h3 className="mb-2 text-[14px] font-medium text-ink">Cited by RPL</h3>
            {citedBy.length === 0 ? (
              <p className="text-[13px] text-ink-3">No Rockridge document cites this section.</p>
            ) : (
              <div className="space-y-4">
                {citedBy.map((g) => (
                  <div key={g.vertical}>
                    <div className="mb-1 text-[12px] font-medium text-ink-3">{g.name}</div>
                    <ul className="space-y-1.5">
                      {g.docs.map((d) => (
                        <li key={d.doc_id} className="min-w-0">
                          <DocChip docId={d.doc_id} href={d.monitored ? `/app/documents/${encodeURIComponent(d.doc_id)}` : undefined} />
                          <div className="truncate pl-5 text-[12px] text-ink-3" title={d.title}>
                            {d.title}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </section>
        </aside>
      </div>
    </PageContainer>
  );
}

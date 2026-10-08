"use client";
import * as React from "react";
import { useParams } from "next/navigation";
import { ExternalLink } from "lucide-react";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { useRecordRecent } from "@/components/shell/Recents";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { CitationText } from "@/components/common/CitationText";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { FutureCue } from "@/components/common/FutureCue";
import { AppLink } from "@/lib/app-link";
import { actionDisplayTitle, actionTypeLabel, StatusPill, streamLabel, stripMarkup } from "@/components/kb/bits";
import { actionHref, agencyHref, decodeCatchAll, safeDecode, sectionHref, sourceSystemOfCitation } from "@/components/kb/links";
import { useAction } from "@/lib/api/queries";
import { formatDate } from "@/lib/format";

const COMMENTABLE = new Set(["proposed_rule", "advance_notice"]);
const RELATION_LABELS = { supersedes: "Supersedes", corrects: "Corrects", related_to: "Related to" } as const;

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex gap-4 border-b border-border py-2.5 last:border-b-0">
      <dt className="w-[140px] shrink-0 text-[12px] font-medium leading-5 text-ink-3">{label}</dt>
      <dd className="min-w-0 flex-1 text-[14px] leading-5 text-ink">{children}</dd>
    </div>
  );
}

/** http(s) only; anything else is not rendered as a link. */
function safeUrl(u: string): string | null {
  try {
    const p = new URL(u);
    return p.protocol === "http:" || p.protocol === "https:" ? u : null;
  } catch {
    return null;
  }
}

export default function Page() {
  const params = useParams<{ sourceSystem: string; sourceId: string[] }>();
  const sourceSystem = safeDecode(String(params?.sourceSystem ?? ""));
  const sourceId = decodeCatchAll(params?.sourceId);
  const action = useAction(sourceSystem, sourceId);
  const a = action.data;
  useRecordRecent(a ? { href: actionHref(a.source_system, a.source_id), label: a.source_id } : null);

  const crumbs = [
    { label: "Regulations", href: "/app/regulations" },
    ...(a?.agency ? [{ label: a.agency.toUpperCase(), href: agencyHref(a.agency, "activity") }] : []),
    { label: sourceId, mono: true },
  ];

  if (action.isError) {
    return (
      <PageContainer>
        <PageHeader title={sourceId} breadcrumbs={crumbs} />
        <ErrorState message="This action could not be loaded." source="Knowledge base · actions" onRetry={() => void action.refetch()} />
      </PageContainer>
    );
  }
  if (action.isLoading) {
    return (
      <PageContainer>
        <PageHeader title={sourceId} breadcrumbs={crumbs} />
        <Skeleton className="h-[280px] rounded-[12px]" />
      </PageContainer>
    );
  }
  if (!a) {
    return (
      <PageContainer>
        <PageHeader title={sourceId} breadcrumbs={crumbs} />
        <EmptyState
          title="This action is not in the knowledge base"
          description="It may not have been synced yet."
          action={<AppLink href="/app/regulations" className="text-[14px] font-medium text-ink underline">Back to regulations</AppLink>}
        />
      </PageContainer>
    );
  }

  const url = safeUrl(a.source_url);
  const sections = [...new Set(a.cfr_references)];
  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={crumbs}
        caption={`${streamLabel(a.stream || a.source_system)} · ${a.source_id}`}
        title={<span className="block text-[28px] leading-9">{actionDisplayTitle(a)}</span>}
        actions={
          <>
            {COMMENTABLE.has(a.action_type) && <FutureCue id="comment-letter" />}
            <FutureCue id="track-docket" variant="button" />
          </>
        }
      />
      <div className="mb-6 flex flex-wrap items-center gap-2">
        <Badge variant="neutral">{actionTypeLabel(a.action_type)}</Badge>
        <StatusPill status={a.status} />
        {url && (
          <a
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 inline-flex items-center gap-1 text-[13px] font-medium text-ink-2 hover:text-ink"
          >
            View source <ExternalLink className="size-3.5" strokeWidth={1.5} />
          </a>
        )}
      </div>

      <div className="grid gap-8 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          <section className="rounded-[12px] border border-border bg-surface p-6">
            <h2 className="mb-3 text-[14px] font-medium text-ink">Summary</h2>
            {stripMarkup(a.abstract).trim() ? (
              <p className="max-w-[72ch] whitespace-pre-line font-serif text-[16px] leading-[26px] text-ink">{stripMarkup(a.abstract)}</p>
            ) : (
              <p className="text-[14px] text-ink-3">No abstract is available for this action.</p>
            )}
          </section>
          <section className="rounded-[12px] border border-border bg-surface p-6">
            <h2 className="mb-3 text-[14px] font-medium text-ink">Details</h2>
            <dl>
              <Field label="Agency">
                {a.agency ? <AppLink href={agencyHref(a.agency)} className="underline-offset-2 hover:underline">{a.agency.toUpperCase()}</AppLink> : "—"}
              </Field>
              <Field label="Published">{a.date_published ? formatDate(a.date_published) : "No publication date recorded"}</Field>
              {a.docket_ids.length > 0 && (
                <Field label="Docket">
                  <span className="flex flex-wrap gap-x-3 gap-y-1">
                    {a.docket_ids.map((d) => (
                      <CitationText key={d}>{d}</CitationText>
                    ))}
                  </span>
                </Field>
              )}
              {a.rin && (
                <Field label="RIN">
                  <CitationText>{a.rin}</CitationText>
                </Field>
              )}
              {a.din && (
                <Field label="DIN">
                  <CitationText>{a.din}</CitationText>
                </Field>
              )}
              {a.legal_refs.length > 0 && (
                <Field label="Legal authority">
                  <span className="flex flex-wrap gap-x-3 gap-y-1">
                    {a.legal_refs.map((r) => (
                      <CitationText key={r}>{r}</CitationText>
                    ))}
                  </span>
                </Field>
              )}
            </dl>
          </section>
        </div>

        <aside className="space-y-8">
          <section>
            <h3 className="mb-2 text-[14px] font-medium text-ink">Sections affected</h3>
            {sections.length === 0 ? (
              <p className="text-[13px] text-ink-3">This action does not list any CFR sections.</p>
            ) : (
              <ul className="flex flex-wrap gap-2">
                {sections.map((c) => (
                  <li key={c}>
                    <AppLink href={sectionHref(sourceSystemOfCitation(c), c)} className="inline-flex h-6 items-center rounded-[6px] bg-surface-muted px-2 hover:bg-border">
                      <CitationText className="text-[12px]">{c}</CitationText>
                    </AppLink>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section>
            <h3 className="mb-2 text-[14px] font-medium text-ink">Related actions</h3>
            {a.related.length === 0 ? (
              <p className="text-[13px] text-ink-3">No related actions are recorded.</p>
            ) : (
              <ul className="space-y-2">
                {a.related.map((r) => (
                  <li key={`${r.relationship_type}|${r.source_id}`} className="flex items-center gap-2 text-[13px]">
                    <Badge variant="tag">{RELATION_LABELS[r.relationship_type]}</Badge>
                    <AppLink href={actionHref(a.source_system, r.source_id)} className="font-mono text-[12.5px] text-ink underline-offset-2 hover:underline">
                      {r.source_id}
                    </AppLink>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>
    </PageContainer>
  );
}

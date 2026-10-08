"use client";
import * as React from "react";
import { useParams } from "next/navigation";
import { parseAsStringLiteral, useQueryState } from "nuqs";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { AttributeChip } from "@/components/common/AttributeChip";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { FutureCue } from "@/components/common/FutureCue";
import { useRecordRecent } from "@/components/shell/Recents";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { AppLink } from "@/lib/app-link";
import { AgencyActivity } from "@/components/kb/AgencyActivity";
import { AgencyRules } from "@/components/kb/AgencyRules";
import { agencyHref, safeDecode } from "@/components/kb/links";
import { isCodebookOnly } from "@/components/kb/agencies";
import { useAgency } from "@/lib/api/queries";
import { formatCount, formatDate } from "@/lib/format";

export default function Page() {
  const params = useParams<{ agencyId: string }>();
  const slug = safeDecode(String(params?.agencyId ?? ""));
  const agency = useAgency(slug);
  const [tab, setTab] = useQueryState("tab", parseAsStringLiteral(["rules", "activity"] as const).withDefault("rules"));
  const a = agency.data;
  useRecordRecent(a ? { href: agencyHref(a.slug), label: a.name } : null);

  const crumbs = [{ label: "Regulations", href: "/app/regulations" }, { label: a?.name ?? "Agency" }];

  if (agency.isError) {
    return (
      <PageContainer>
        <PageHeader title="Agency" breadcrumbs={crumbs} />
        <ErrorState message="This agency could not be loaded." source="Knowledge base" onRetry={() => void agency.refetch()} />
      </PageContainer>
    );
  }
  if (agency.isLoading) {
    return (
      <PageContainer>
        <PageHeader title="Agency" breadcrumbs={crumbs} />
        <Skeleton className="mb-6 h-16" />
        <Skeleton className="h-[320px] rounded-[12px]" />
      </PageContainer>
    );
  }
  if (!a) {
    return (
      <PageContainer>
        <PageHeader title="Agency not found" breadcrumbs={crumbs} />
        <EmptyState
          title="This agency is not in the knowledge base"
          description="It may have been renamed or not loaded yet."
          action={<AppLink href="/app/regulations" className="text-[14px] font-medium text-ink underline">Back to all agencies</AppLink>}
        />
      </PageContainer>
    );
  }

  const codebookOnly = isCodebookOnly(a);
  const activeTab = codebookOnly ? "rules" : tab;
  return (
    <PageContainer>
      <PageHeader
        breadcrumbs={crumbs}
        caption={`${a.level === "federal" ? "Federal" : "State"} · ${a.geo || "US"}`}
        title={a.name}
        actions={<FutureCue id="add-data-source" />}
      />
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {a.codebook_titles.map((t) => (
          <AttributeChip key={t}>
            <span className="font-mono text-[12px]">{t}</span>
          </AttributeChip>
        ))}
        {a.domains.length > 0 && <AttributeChip label="Domains">{a.domains.join(", ")}</AttributeChip>}
      </div>
      <p className="mb-6 text-[13px] leading-5 text-ink-3">
        {formatCount(a.section_count)} sections
        {!codebookOnly && <> · {formatCount(a.action_count)} actions</>} · Snapshots {formatDate(a.s1_snapshot)} →{" "}
        {formatDate(a.s2_snapshot)} · Last sync {formatDate(a.last_sync_at)}
      </p>

      <Tabs value={activeTab} onValueChange={(v) => void setTab(v === "activity" ? "activity" : "rules")}>
        <TabsList className="mb-4">
          <TabsTrigger value="rules">Rules in force</TabsTrigger>
          {codebookOnly ? (
            <TabsTrigger value="activity" disabled aria-disabled="true" className="cursor-default text-ink-4 hover:text-ink-4">
              Activity
            </TabsTrigger>
          ) : (
            <TabsTrigger value="activity">Activity</TabsTrigger>
          )}
        </TabsList>
      </Tabs>
      {codebookOnly && <p className="-mt-2 mb-4 text-[13px] text-ink-3">No activity feed tracked for this agency.</p>}

      <div className="overflow-hidden rounded-[12px] border border-border bg-surface">
        {activeTab === "rules" ? <AgencyRules agency={a} /> : <AgencyActivity agency={a} />}
      </div>
    </PageContainer>
  );
}

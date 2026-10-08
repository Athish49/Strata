"use client";
import { EvidenceCardBody } from "@/components/engine";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { useRecordRecent } from "@/components/shell/Recents";
import { useFinding } from "@/lib/api/queries";

/** Full-page variant of the §9.5 evidence card (the card body is shared with the drawer). */
export function FindingPage({ findingId }: { findingId: string }) {
  const { data: finding } = useFinding(findingId);
  const label = finding ? `${finding.clause_id} · ${finding.citation}` : null;
  useRecordRecent(label ? { href: `/app/findings/${encodeURIComponent(findingId)}`, label } : null);
  return (
    <PageContainer className="max-w-[960px]">
      <PageHeader
        breadcrumbs={[
          { label: "Overview", href: "/app" },
          ...(finding ? [{ label: "Documents", href: "/app/documents" }, { label: finding.doc_id, href: `/app/documents/${encodeURIComponent(finding.doc_id)}`, mono: true }] : []),
          { label: "Evidence card" },
        ]}
        caption={finding ? <span className="font-mono text-[12.5px]">{finding.citation}</span> : "Finding"}
        title="Why this clause is out of line"
        showRunSelector={false}
      />
      <div className="overflow-hidden rounded-[12px] border border-border">
        <EvidenceCardBody findingId={findingId} variant="page" />
      </div>
    </PageContainer>
  );
}

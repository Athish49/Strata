import { InfoStrip } from "@/components/common/InfoStrip";
import { SectionHeader } from "@/components/common/SectionHeader";
import { EmptyState } from "@/components/common/EmptyState";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";

// Placeholder: milestone M1 replaces this with the real Overview.
export default function OverviewPage() {
  return (
    <PageContainer>
      <PageHeader title="The wave at a glance" caption="Overview" />
      <InfoStrip>The Overview is being built. Run results will be summarized here.</InfoStrip>
      <div className="mt-6 grid grid-cols-2 gap-6">
        {["Impact by verdict", "From changes to clauses"].map((t) => (
          <section key={t} className="rounded-[12px] border border-border bg-surface p-6">
            <SectionHeader title={t} subtitle="Placeholder" />
            <EmptyState className="px-0" title="Nothing to show yet" description="This card is filled in a later milestone." />
          </section>
        ))}
      </div>
    </PageContainer>
  );
}

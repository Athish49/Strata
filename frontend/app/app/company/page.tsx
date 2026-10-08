"use client";
import * as React from "react";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { FutureCue } from "@/components/common/FutureCue";
import { CompanyPage } from "@/components/company/CompanyProfile";

export default function Page() {
  const [hash, setHash] = React.useState<string | null>(null);
  React.useEffect(() => {
    const read = () => setHash(decodeURIComponent(window.location.hash.replace(/^#/, "")) || null);
    read();
    window.addEventListener("hashchange", read);
    return () => window.removeEventListener("hashchange", read);
  }, []);
  return (
    <PageContainer>
      <PageHeader
        caption="Knowledge base"
        title="Company profile"
        actions={<FutureCue id="edit-profile" />}
      />
      <CompanyPage highlight={hash} />
    </PageContainer>
  );
}

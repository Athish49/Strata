import { FindingPage } from "@/components/overview/FindingPage";

export default async function Page({ params }: { params: Promise<{ findingId: string }> }) {
  const { findingId } = await params;
  return <FindingPage findingId={decodeURIComponent(findingId)} />;
}

import { ChangeDetailPage } from "@/components/changes/ChangeDetailPage";

export default async function Page({ params }: { params: Promise<{ changeId: string }> }) {
  const { changeId } = await params;
  return <ChangeDetailPage changeId={decodeURIComponent(changeId)} />;
}

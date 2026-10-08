import { notFound } from "next/navigation";
import { VerticalView } from "@/components/documents/board/VerticalView";
import { isVerticalSlug } from "@/lib/verticals";

export default async function Page({ params }: { params: Promise<{ vertical: string }> }) {
  const { vertical } = await params;
  if (!isVerticalSlug(vertical)) notFound();
  return <VerticalView slug={vertical} />;
}

"use client";
import { useParams } from "next/navigation";
import { ReaderPage } from "@/components/documents/reader";

export default function Page() {
  const params = useParams<{ docId: string }>();
  const docId = decodeURIComponent(String(params?.docId ?? ""));
  return <ReaderPage docId={docId} />;
}

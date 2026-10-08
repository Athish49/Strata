"use client";
import { useParams } from "next/navigation";
import { WhatIfStudio } from "@/components/whatif/WhatIfStudio";

export default function Page() {
  const params = useParams<{ scenarioId: string }>();
  const raw = String(params?.scenarioId ?? "");
  let id = raw;
  try {
    id = decodeURIComponent(raw);
  } catch {
    // keep the raw segment
  }
  return <WhatIfStudio scenarioId={id} />;
}

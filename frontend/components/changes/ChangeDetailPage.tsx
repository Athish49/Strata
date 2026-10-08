"use client";
import { ChangeDetail } from "./ChangeDetail";

export function ChangeDetailPage({ changeId }: { changeId: string }) {
  return <ChangeDetail changeId={changeId} />;
}

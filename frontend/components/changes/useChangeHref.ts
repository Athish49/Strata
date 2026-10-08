"use client";
import { useCallback } from "react";
import { useSearchParams } from "next/navigation";

/** Builds /app/changes/<id> hrefs that keep the filters and ?run= (but drop ?finding=). */
export function useChangeHref(): (changeId: string) => string {
  const sp = useSearchParams();
  const str = sp?.toString() ?? "";
  return useCallback(
    (changeId: string) => {
      const p = new URLSearchParams(str);
      p.delete("finding");
      const qs = p.toString();
      return `/app/changes/${encodeURIComponent(changeId)}${qs ? `?${qs}` : ""}`;
    },
    [str],
  );
}

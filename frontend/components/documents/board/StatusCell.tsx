import { Skeleton } from "@/components/ui/skeleton";
import { DocStatusPill } from "./DocStatusPill";
import type { DocRow } from "./logic";

/** The status pill, or a skeleton while rollups for the run are still loading. */
export function StatusCell({ row }: { row: Pick<DocRow, "status" | "pending"> }) {
  if (row.pending) return <Skeleton aria-label="Checking status" className="h-[22px] w-24 rounded-[6px]" />;
  return <DocStatusPill status={row.status.key} />;
}

// Document status derivation (spec §11.5).
import type { DocRollup, DocumentMeta } from "@/lib/api/schemas";
import { DOC_STATUS_LABELS, type DocStatusKey } from "@/lib/labels";
import { docClearedLine } from "@/lib/sentences";

export interface DocStatus {
  key: DocStatusKey;
  label: string;
  /** Reason line, set for "cleared" and "not monitored". */
  reason?: string;
}

export const NO_CANDIDATES_REASON = "No cited section changed";

export function documentStatus(
  meta: Pick<DocumentMeta, "monitored">,
  rollup?: Pick<DocRollup, "status" | "counts_by_verdict" | "changes_considered" | "considered_by_class" | "cleared_reason">,
): DocStatus {
  const make = (key: DocStatusKey, reason?: string): DocStatus => ({
    key,
    label: DOC_STATUS_LABELS[key],
    ...(reason ? { reason } : {}),
  });

  if (meta.monitored === false) return make("not_monitored", "Not monitored against regulatory changes");
  if (rollup?.status === "flagged") {
    return make((rollup.counts_by_verdict?.action_required ?? 0) > 0 ? "action_needed" : "review");
  }
  if (!rollup || rollup.changes_considered === 0) return make("cleared", NO_CANDIDATES_REASON);
  return make("cleared", rollup.cleared_reason?.trim() || docClearedLine(rollup));
}

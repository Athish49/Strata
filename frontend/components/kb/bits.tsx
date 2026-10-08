"use client";
import * as React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { changeClassLabel, isNoiseClass, streamLabel } from "@/lib/labels";
import type { ChangeClass } from "@/lib/api/schemas";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Change class marker. Noise classes get the hatched neutral tag; real classes a soft ink pill. */
export function ClassTag({ cls, className }: { cls: ChangeClass; className?: string }) {
  const noise = isNoiseClass(cls);
  return (
    <Badge
      variant={noise ? "tag" : "outline"}
      className={cn(noise && "border-dashed bg-[repeating-linear-gradient(45deg,transparent_0_3px,var(--surface-muted)_3px_4px)]", className)}
    >
      {changeClassLabel(cls)}
    </Badge>
  );
}

const ACTION_TYPE_LABELS: Record<string, string> = {
  final_rule: "Final rule",
  proposed_rule: "Proposed rule",
  direct_final_rule: "Direct final rule",
  interim_final_rule: "Interim final rule",
  advance_notice: "Advance notice",
  correction: "Correction",
  order: "Order",
  commission_investigation: "Commission investigation",
  rulemaking: "Rulemaking",
};
export const ACTION_TYPES = Object.keys(ACTION_TYPE_LABELS);

const STATUS_LABELS: Record<string, string> = { approved: "Approved", in_progress: "In progress", repealed: "Repealed" };
export const ACTION_STATUSES = ["approved", "in_progress"];

function humanize(v: string): string {
  const s = v.replace(/_/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : "";
}
export const actionTypeLabel = (t: string) => ACTION_TYPE_LABELS[t] ?? (humanize(t) || "Action");
export const actionStatusLabel = (s: string) => STATUS_LABELS[s] ?? (humanize(s) || "Unknown");
export { streamLabel };

/** Federal Register text carries inline markup such as <INF>2.5</INF>; keep the text, drop the tags. */
export function stripMarkup(text: string): string {
  return (text ?? "").replace(/<[^>]+>/g, "").replace(/&amp;/g, "&").replace(/&lt;/g, "<").replace(/&gt;/g, ">");
}

/** Titles like "PDF" or "" carry no meaning; fall back to the type and id. */
export function actionDisplayTitle(a: { title: string; action_type: string; source_id: string }): string {
  const t = stripMarkup(a.title ?? "").trim();
  if (t.length >= 6 && !/^(pdf|link|download|untitled)$/i.test(t)) return t;
  return `${actionTypeLabel(a.action_type)} ${a.source_id}`;
}

export function StatusPill({ status }: { status: string }) {
  return <Badge variant={status === "approved" ? "green" : "neutral"}>{actionStatusLabel(status)}</Badge>;
}

/** Previous / next with a range summary. Renders nothing when everything fits on one page. */
export function Pager({
  page,
  pages,
  total,
  size,
  onPage,
  noun = "items",
}: {
  page: number;
  pages: number;
  total: number;
  size: number;
  onPage: (p: number) => void;
  noun?: string;
}) {
  if (total === 0) return null;
  const from = (page - 1) * size + 1;
  const to = Math.min(total, page * size);
  return (
    <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3 text-[13px] text-ink-3">
      <span>
        {formatCount(from)}–{formatCount(to)} of {formatCount(total)} {noun}
      </span>
      {pages > 1 && (
        <div className="flex items-center gap-1">
          <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page">
            <ChevronLeft />
          </Button>
          <span className="px-2 tabular-nums">
            Page {page} of {pages}
          </span>
          <Button variant="secondary" size="sm" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page">
            <ChevronRight />
          </Button>
        </div>
      )}
    </div>
  );
}

/** Native select styled as the spec's select control (h-32, radius 8). */
export function SelectControl({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <label className="inline-flex items-center gap-2 text-[13px] text-ink-3">
      <span>{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-8 rounded-[8px] border border-border-strong bg-surface px-2 text-[13px] text-ink"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

/** Page number that resets to 1 whenever `key` (the active filters) changes, without an effect. */
export function useKeyedPage(key: string): [number, (p: number) => void] {
  const [state, setState] = React.useState({ key, page: 1 });
  const page = state.key === key ? state.page : 1;
  return [page, (p: number) => setState({ key, page: p })];
}

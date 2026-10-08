"use client";
import { ArrowRight, Landmark } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { FutureCue } from "@/components/common/FutureCue";
import { AppLink } from "@/lib/app-link";
import type { Agency } from "@/lib/api/schemas";
import { formatCount, formatDate, pluralize } from "@/lib/format";
import { MORE_SOURCES_ITEMS, SHOW_FUTURE_CUES } from "@/lib/future-features";
import { streamLabel } from "@/lib/labels";
import { agencyHref } from "./links";

/** Short display code for an agency: its slug in caps, e.g. "IURC"; codebook-only slugs read as "610 IAC". */
export function agencyCode(a: Pick<Agency, "slug" | "codebook_titles">): string {
  return a.slug.toUpperCase();
}

export function AgencyCard({ agency, changedInRun }: { agency: Agency; changedInRun?: number }) {
  const codebookOnly = !agency.has_activity_feed;
  const streams = [...new Set(agency.streams.map(streamLabel))];
  return (
    <AppLink
      href={agencyHref(agency.slug)}
      className="group flex min-h-[200px] flex-col gap-3 rounded-[12px] border border-border bg-surface p-6 transition-colors duration-150 hover:bg-surface-muted/60"
    >
      <div className="flex items-start justify-between gap-3">
        <span aria-hidden className="grid size-8 place-items-center rounded-[8px] bg-surface-muted text-ink-2">
          <Landmark className="size-4" strokeWidth={1.5} />
        </span>
        <div className="flex flex-wrap justify-end gap-1.5">
          {codebookOnly && <Badge variant="tag">Codebook only</Badge>}
          <Badge variant="tag">{agencyCode(agency)}</Badge>
        </div>
      </div>
      <div className="min-w-0">
        <h3 className="text-[16px] font-medium leading-6 text-ink">{agency.name}</h3>
        <p className="mt-0.5 text-[13px] text-ink-3">
          {agency.level === "federal" ? "Federal" : "State"}
          {agency.codebook_titles.length > 0 && (
            <>
              {" · "}
              <span className="font-mono text-[12.5px]">{agency.codebook_titles.join(", ")}</span>
            </>
          )}
        </p>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-ink-2">
        <span>
          <span className="tabular-nums font-medium text-ink">{formatCount(agency.section_count)}</span> sections
        </span>
        {codebookOnly ? (
          <span className="text-ink-3">No activity feed</span>
        ) : (
          <span>
            <span className="tabular-nums font-medium text-ink">{formatCount(agency.action_count)}</span> actions
          </span>
        )}
      </div>
      {streams.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {streams.map((s) => (
            <Badge key={s} variant="neutral">
              {s}
            </Badge>
          ))}
        </div>
      )}
      {changedInRun !== undefined && changedInRun > 0 && (
        <div>
          <Badge variant="outline">{pluralize(changedInRun, "section")} changed in this run</Badge>
        </div>
      )}
      <div className="mt-auto flex items-end justify-between gap-3 border-t border-border pt-3 text-[12px] text-ink-3">
        <div className="min-w-0 space-y-0.5">
          <div className="whitespace-nowrap">
            S1 {formatDate(agency.s1_snapshot)} → S2 {formatDate(agency.s2_snapshot)}
          </div>
          <div>Last sync {formatDate(agency.last_sync_at)}</div>
        </div>
        <ArrowRight className="size-4 shrink-0 text-ink-4 transition-colors group-hover:text-ink" strokeWidth={1.5} />
      </div>
    </AppLink>
  );
}

/** Dashed future cue that ends each level section. */
export function AddAgencyCard({ cueId, subtitle }: { cueId: "add-agency-federal" | "add-agency-state"; subtitle: string }) {
  if (!SHOW_FUTURE_CUES) return null;
  return (
    <div className="flex flex-col">
      <FutureCue id={cueId} variant="card" className="min-h-[200px] flex-1" />
      <p className="mt-2 text-center text-[12px] text-ink-4">{subtitle}</p>
    </div>
  );
}

/** "More source types": one compact row of three disabled cards (counts as one cue). */
export function MoreSourcesRow() {
  if (!SHOW_FUTURE_CUES) return null;
  return (
    <div className="grid gap-4 md:grid-cols-3">
      {MORE_SOURCES_ITEMS.map((item) => (
        <Tooltip key={item.title}>
          <TooltipTrigger asChild>
            <button
              type="button"
              aria-disabled="true"
              className="flex h-14 cursor-default select-none items-center justify-between gap-3 rounded-[12px] border border-dashed border-border-strong px-4 text-left text-[14px] text-ink-4"
            >
              <span className="truncate">
                {item.title}
                <span className="sr-only"> (coming soon)</span>
              </span>
              <span className="inline-flex h-[18px] shrink-0 items-center rounded-[4px] border border-border-strong px-1.5 text-[11px] font-medium leading-none text-ink-3">
                Soon
              </span>
            </button>
          </TooltipTrigger>
          <TooltipContent>
            <div className="font-medium">{item.title}</div>
            <div className="mt-0.5 text-white/90">{item.tooltip}</div>
            <div className="mt-1 text-ink-4">Coming soon</div>
          </TooltipContent>
        </Tooltip>
      ))}
    </div>
  );
}

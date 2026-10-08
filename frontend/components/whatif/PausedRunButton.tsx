"use client";
import { ArrowRight } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { CUSTOM_WHATIF_PAUSED } from "./config";

/**
 * Disabled "Run impact" for custom scenarios while custom runs are paused. Same look and behaviour as a
 * `button`-variant FutureCue (aria-disabled, no handler, "Soon" tag, tooltip), with a local registry entry.
 */
export function PausedRunButton() {
  const f = CUSTOM_WHATIF_PAUSED;
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <button
          type="button"
          aria-disabled="true"
          data-testid="run-impact-paused"
          className="inline-flex h-9 cursor-default select-none items-center gap-2 rounded-[8px] border border-border bg-surface px-3.5 text-[14px] font-medium text-ink-4"
        >
          {f.label}
          <ArrowRight className="size-4 text-ink-4" strokeWidth={1.5} />
          <span className="sr-only"> (coming soon)</span>
          <span className="inline-flex h-[18px] items-center rounded-[4px] border border-border-strong px-1.5 text-[11px] font-medium leading-none text-ink-3">
            Soon
          </span>
        </button>
      </TooltipTrigger>
      <TooltipContent side="top">
        <div className="font-medium">{f.label}</div>
        <div className="mt-0.5 text-white/90">{f.tooltip}</div>
        <div className="mt-1 text-ink-4">Coming soon</div>
      </TooltipContent>
    </Tooltip>
  );
}

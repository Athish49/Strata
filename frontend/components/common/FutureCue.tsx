"use client";
import * as React from "react";
import { icons, Plus, Circle } from "lucide-react";
import { FUTURE_FEATURES, SHOW_FUTURE_CUES } from "@/lib/future-features";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

interface FutureCueProps {
  id: string;
  /** Override the registry variant (rare). */
  variant?: "button" | "toolbar" | "inline-add" | "card" | "nav" | "icon" | "chip" | "menu-item";
  /** Rendered on the dark sidebar (muted light text instead of ink-4). */
  onDark?: boolean;
  /** Tooltip side; defaults to top (right for nav). */
  side?: "top" | "right" | "bottom" | "left";
  /** Replaces the registry label in the visible text (e.g. 'Ask Strata "query"'). */
  label?: string;
  className?: string;
}

function SoonTag({ onDark }: { onDark?: boolean }) {
  return (
    <span
      className={cn(
        "inline-flex h-[18px] items-center rounded-[4px] border px-1.5 text-[11px] font-medium leading-none",
        onDark ? "border-sidebar-border text-sidebar-muted" : "border-border-strong text-ink-3",
      )}
    >
      Soon
    </span>
  );
}

/**
 * A disabled affordance from the §18.2 registry. Never does anything: aria-disabled (not disabled),
 * no handlers, tooltip only. Renders nothing when SHOW_FUTURE_CUES is false or the id is unknown.
 */
export function FutureCue({ id, variant, onDark, side, label, className }: FutureCueProps) {
  const f = FUTURE_FEATURES[id];
  if (!SHOW_FUTURE_CUES || !f) return null;
  const v = variant ?? f.variant;
  // House rule: no "AI sparkle" icons anywhere.
  const iconName = f.icon === "Sparkles" || f.icon === "Sparkle" ? "MessageSquareText" : f.icon;
  const Icon = (icons as Record<string, React.ComponentType<{ className?: string; strokeWidth?: number }>>)[iconName] ?? Circle;
  const text = label ?? f.label;
  const muted = onDark ? "text-sidebar-muted" : "text-ink-4";
  const ico = <Icon className={cn("size-4 shrink-0", muted)} strokeWidth={1.5} />;
  const sr = <span className="sr-only"> (coming soon)</span>;
  const base = "cursor-default select-none";

  let node: React.ReactNode;
  switch (v) {
    case "icon":
      node = (
        <button
          type="button"
          aria-disabled="true"
          aria-label={`${f.label} (coming soon)`}
          className={cn(base, "grid size-8 place-items-center rounded-[8px]", className)}
        >
          {ico}
        </button>
      );
      break;
    case "nav":
      node = (
        <div
          role="link"
          tabIndex={0}
          aria-disabled="true"
          className={cn(base, "flex h-9 items-center gap-3 rounded-[8px] px-3 text-[15px] leading-5", muted, className)}
        >
          {ico}
          <span className="flex-1 truncate">{text}</span>
          {sr}
          <SoonTag onDark={onDark} />
        </div>
      );
      break;
    case "menu-item":
      node = (
        <div
          role="menuitem"
          tabIndex={-1}
          aria-disabled="true"
          className={cn(base, "flex items-center gap-2 rounded-[6px] px-2.5 py-2 text-[14px] text-ink-4", className)}
        >
          {ico}
          <span className="flex-1 truncate">{text}</span>
          {sr}
          <SoonTag />
        </div>
      );
      break;
    case "inline-add":
      node = (
        <button
          type="button"
          aria-disabled="true"
          className={cn(base, "inline-flex items-center gap-1 text-[13px] text-ink-4", className)}
        >
          <Plus className="size-3.5" strokeWidth={1.5} />
          {text}
          {sr}
        </button>
      );
      break;
    case "card":
      node = (
        <button
          type="button"
          aria-disabled="true"
          className={cn(
            base,
            "flex min-h-[96px] w-full flex-col items-center justify-center gap-2 rounded-[12px] border border-dashed border-border-strong bg-transparent p-4 text-[14px] text-ink-4",
            className,
          )}
        >
          <Plus className="size-4" strokeWidth={1.5} />
          <span>{text}</span>
          {sr}
          <SoonTag />
        </button>
      );
      break;
    case "chip":
      node = (
        <button
          type="button"
          aria-disabled="true"
          className={cn(
            base,
            "inline-flex h-7 items-center gap-1.5 rounded-full border border-border-strong px-3 text-[13px] text-ink-4",
            className,
          )}
        >
          {text}
          {sr}
          <SoonTag />
        </button>
      );
      break;
    case "toolbar":
      node = (
        <button
          type="button"
          aria-disabled="true"
          className={cn(base, "inline-flex h-8 items-center gap-2 px-3 text-[14px] text-ink-4", className)}
        >
          {ico}
          {text}
          {sr}
          <SoonTag />
        </button>
      );
      break;
    default:
      node = (
        <button
          type="button"
          aria-disabled="true"
          className={cn(
            base,
            "inline-flex h-9 items-center gap-2 rounded-[8px] border border-border bg-surface px-3.5 text-[14px] font-medium text-ink-4",
            className,
          )}
        >
          {ico}
          {text}
          {sr}
          <SoonTag />
        </button>
      );
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>{node}</TooltipTrigger>
      <TooltipContent side={side ?? (v === "nav" ? "right" : "top")}>
        <div className="font-medium">{text}</div>
        <div className="mt-0.5 text-white/90">{f.tooltip}</div>
        <div className="mt-1 text-ink-4">Coming soon</div>
      </TooltipContent>
    </Tooltip>
  );
}

"use client";
import * as React from "react";
import { ArrowRight } from "lucide-react";
import { DiffView } from "@/components/engine";
import { ErrorState } from "@/components/common/ErrorState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { hasChanges, previewSegments } from "./diff";
import { PausedRunButton } from "./PausedRunButton";

export interface EditorSection {
  citation: string;
  heading: string;
  citedBy: number | null;
}

export interface EditorSubmit {
  title: string;
  repeal: boolean;
  editedText: string | null;
  /** True when the edit is exactly an existing preset (runs instantly, no model budget). */
  matchesPreset: boolean;
}

/**
 * Title, S1 text, repeal toggle and live jsdiff preview. Remount (via `key`) to reset for a new section/scenario.
 * `initial*` seed the editor from a scenario.
 */
export function ScenarioEditor({
  section,
  s1Text,
  s1State,
  onRetryS1,
  initialTitle,
  initialRepeal,
  initialText,
  presetMatch,
  customAllowed,
  busy,
  error,
  onRun,
}: {
  section: EditorSection;
  s1Text: string | null;
  s1State: "loading" | "error" | "ready";
  onRetryS1: () => void;
  initialTitle?: string;
  initialRepeal?: boolean;
  initialText?: string | null;
  /** Called with the current edit; returns true when it equals an existing preset. */
  presetMatch: (edit: { repeal: boolean; editedText: string | null }) => boolean;
  customAllowed: boolean;
  busy: boolean;
  error: string | null;
  onRun: (e: EditorSubmit) => void;
}) {
  const [titleDraft, setTitleDraft] = React.useState<string | null>(initialTitle ?? null);
  const [repeal, setRepeal] = React.useState<boolean>(initialRepeal ?? false);
  const [textDraft, setTextDraft] = React.useState<string | null>(initialText ?? null);

  const base = s1Text ?? "";
  const text = textDraft ?? base;
  const autoTitle = repeal ? `Repeal ${section.citation}` : `${section.citation}: edited text`;
  const title = titleDraft ?? autoTitle;

  const segments = React.useMemo(
    () => (s1State !== "ready" ? [] : repeal ? (base ? [{ op: "delete" as const, text: base }] : []) : previewSegments(base, text)),
    [s1State, repeal, base, text],
  );
  const changed = hasChanges(segments);
  const edit = { repeal, editedText: repeal ? null : text };
  const isPreset = s1State === "ready" && changed && presetMatch(edit);
  const canSubmit = s1State === "ready" && changed && title.trim() !== "" && (isPreset || customAllowed);

  return (
    <section aria-label="Scenario editor" className="rounded-[12px] border border-border bg-surface p-6">
      <div className="mb-5">
        <h2 className="font-mono text-[13px] font-medium leading-[18px] text-ink">{section.citation}</h2>
        <p className="text-[14px] leading-5 text-ink-3">
          {section.heading}
          {section.citedBy != null && ` · cited by ${section.citedBy} ${section.citedBy === 1 ? "clause" : "clauses"}`}
        </p>
      </div>

      <label className="mb-1 block text-[12px] font-medium leading-4 text-ink-3" htmlFor="whatif-title">
        Scenario title
      </label>
      <Input id="whatif-title" value={title} onChange={(e) => setTitleDraft(e.target.value)} className="mb-5" />

      <div className="mb-1 flex items-center justify-between gap-3">
        <label className="text-[12px] font-medium leading-4 text-ink-3" htmlFor="whatif-text">
          Section text now in effect
        </label>
        <button
          type="button"
          role="switch"
          aria-checked={repeal}
          onClick={() => setRepeal((r) => !r)}
          className="inline-flex items-center gap-2 text-[14px] text-ink"
        >
          <span aria-hidden className={cn("relative h-5 w-9 rounded-full border border-border-strong transition-colors duration-150", repeal ? "bg-ink" : "bg-surface-muted")}>
            <span className={cn("absolute top-[1px] size-4 rounded-full bg-white shadow-sm transition-all duration-150", repeal ? "left-[17px]" : "left-[1px] border border-border-strong")} />
          </span>
          Repeal this section
        </button>
      </div>

      {s1State === "loading" ? (
        <Skeleton className="h-[220px] w-full" />
      ) : s1State === "error" ? (
        <ErrorState className="px-0 py-4" message="The text of this section could not be loaded." source="What-if sections" onRetry={onRetryS1} />
      ) : (
        <textarea
          id="whatif-text"
          value={repeal ? base : text}
          disabled={repeal}
          onChange={(e) => setTextDraft(e.target.value)}
          spellCheck={false}
          className="h-[220px] w-full resize-y rounded-[8px] border border-border-strong bg-surface p-3 font-serif text-[15px] leading-6 text-ink disabled:bg-surface-muted disabled:text-ink-3"
        />
      )}
      {repeal && <p className="mt-1 text-[12px] text-ink-3">The whole section is treated as removed. Turn the switch off to edit its text.</p>}

      <div className="mt-5">
        <h3 className="mb-2 text-[12px] font-medium leading-4 text-ink-3">Preview of your edit</h3>
        {s1State !== "ready" ? (
          <p className="text-[14px] text-ink-3">The preview appears once the section text has loaded.</p>
        ) : changed ? (
          <DiffView segments={segments} mode="inline" collapseThreshold={240} maxHeightClass="max-h-[320px]" />
        ) : (
          <p className="rounded-[8px] bg-surface-muted px-3 py-2 text-[14px] text-ink-3">No change yet. Edit the text or repeal the section to see what would differ.</p>
        )}
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3 border-t border-border pt-4">
        {isPreset || customAllowed ? (
          <Button variant="primary" disabled={!canSubmit || busy} onClick={() => onRun({ title, ...edit, matchesPreset: isPreset })}>
            {busy ? "Starting…" : "Run impact"}
            <ArrowRight />
          </Button>
        ) : (
          <PausedRunButton />
        )}
        <p className="min-w-0 flex-1 text-[13px] leading-[18px] text-ink-3" role="status">
          {error ? (
            <span className="text-red">{error}</span>
          ) : isPreset ? (
            "This matches a preset, so its results open instantly."
          ) : !customAllowed ? (
            "Custom what-if runs are paused: they use live model budget. You can still edit and preview, and the presets run instantly."
          ) : !changed ? (
            "Make an edit to enable the run."
          ) : (
            "Runs take about ten seconds."
          )}
        </p>
      </div>
    </section>
  );
}

"use client";
import * as React from "react";
import { useRouter } from "next/navigation";
import { EmptyState } from "@/components/common/EmptyState";
import { FutureCue } from "@/components/common/FutureCue";
import { ErrorState } from "@/components/common/ErrorState";
import { PageContainer, PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { AppLink } from "@/lib/app-link";
import { api } from "@/lib/api/client";
import {
  useEditableSections,
  useRunById,
  useSaveScenario,
  useScenarios,
  useSectionS1Text,
  useStartWhatIf,
} from "@/lib/api/queries";
import type { EditableSection, Scenario } from "@/lib/api/schemas";
import { customWhatIfAllowed } from "./config";
import { RunPanel } from "./RunPanel";
import { ScenarioEditor, type EditorSubmit } from "./ScenarioEditor";
import { PresetList, SectionPicker, YourScenarios, sectionKey } from "./StudioSidebar";

function message(e: unknown, fallback: string): string {
  return e instanceof Error && e.message ? e.message : fallback;
}

/** `/app/what-if` (no scenario) and `/app/what-if/[scenarioId]`. */
export function WhatIfStudio({ scenarioId }: { scenarioId?: string }) {
  const router = useRouter();
  const allowCustom = customWhatIfAllowed();
  const scenarios = useScenarios();
  const sections = useEditableSections();
  const save = useSaveScenario();
  const start = useStartWhatIf();

  const [picked, setPicked] = React.useState<EditableSection | null>(null);
  const [activeRunId, setActiveRunId] = React.useState<string | null>(null);
  const [starting, setStarting] = React.useState(false);
  const [busyPreset, setBusyPreset] = React.useState<string | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const run = useRunById(activeRunId);

  const all = scenarios.data ?? [];
  const presets = all.filter((s) => s.is_preset);
  const mine = all.filter((s) => !s.is_preset);
  const scenario: Scenario | null = !picked && scenarioId ? (all.find((s) => s.scenario_id === scenarioId) ?? null) : null;
  const target = picked ?? (scenario ? { source_system: scenario.source_system, citation: scenario.citation } : null);
  const meta = target ? (sections.data ?? []).find((s) => sectionKey(s) === sectionKey(target)) : undefined;
  const s1 = useSectionS1Text(target?.source_system, target?.citation);

  /** Presets (and any scenario that already has a finished run) never need a POST: open the stored run. */
  async function runPreset(s: Scenario) {
    setError(null);
    setBusyPreset(s.scenario_id);
    try {
      const last = s.last_run_id ? await api.engine.getRun(s.last_run_id) : null;
      if (last && last.status === "succeeded") {
        router.push(`/app?run=${encodeURIComponent(last.run_id)}`);
        return;
      }
      if (!customWhatIfAllowed()) {
        setError("This preset has no finished run yet.");
        return;
      }
      setStarting(true);
      const started = await start.mutateAsync(s.scenario_id);
      setActiveRunId(started.run_id);
    } catch (e) {
      setError(message(e, "This preset could not be opened."));
    } finally {
      setStarting(false);
      setBusyPreset(null);
    }
  }

  async function startCustom(e: EditorSubmit) {
    // Single gate: custom runs POST to the shared backend and spend model budget.
    if (!customWhatIfAllowed() || !target) return;
    setError(null);
    setActiveRunId(null);
    setStarting(true);
    try {
      const saved = await save.mutateAsync({
        scenario_id: scenario && !scenario.is_preset ? scenario.scenario_id : undefined,
        title: e.title.trim(),
        citation: target.citation,
        source_system: target.source_system as Scenario["source_system"],
        edit_kind: e.repeal ? "repeal" : "text_edit",
        edited_text: e.repeal ? null : e.editedText,
      });
      const started = await start.mutateAsync(saved.scenario_id);
      setActiveRunId(started.run_id);
    } catch (err) {
      setError(message(err, "The run could not be started."));
    } finally {
      setStarting(false);
    }
  }

  function submit(e: EditorSubmit) {
    if (e.matchesPreset) {
      const p = presets.find((x) => x.citation === target?.citation && x.source_system === target?.source_system && matches(x, e));
      if (p) return void runPreset(p);
    }
    void startCustom(e);
  }

  const presetMatch = (edit: { repeal: boolean; editedText: string | null }) =>
    presets.some(
      (p) =>
        p.citation === target?.citation &&
        p.source_system === target?.source_system &&
        (edit.repeal ? p.edit_kind === "repeal" : p.edit_kind === "text_edit" && p.edited_text === edit.editedText),
    );

  const crumbs = scenarioId
    ? [{ label: "What-if studio", href: "/app/what-if" }, { label: scenario?.title ?? "Scenario" }]
    : undefined;
  const header = (
    <PageHeader
      caption="Simulate a rule change and see which clauses it would touch"
      title="What-if studio"
      breadcrumbs={crumbs}
      actions={<FutureCue id="compare-scenarios" />}
    />
  );

  const missing = !!scenarioId && !picked && scenarios.isSuccess && !scenario;
  const s1State = s1.isError ? "error" : s1.data ? "ready" : s1.isSuccess ? "error" : "loading";
  const editorKey = `${target ? sectionKey(target) : "none"}|${scenario?.scenario_id ?? ""}|${picked ? "p" : ""}`;
  const showRun = starting || !!activeRunId;

  return (
    <PageContainer>
      {header}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[340px_minmax(0,1fr)] lg:gap-8">
        <div className="min-w-0 space-y-8">
          <PresetList
            presets={presets}
            loading={scenarios.isLoading}
            error={scenarios.isError}
            onRetry={() => void scenarios.refetch()}
            activeId={scenario?.scenario_id ?? null}
            busyId={busyPreset}
            onRun={(s) => void runPreset(s)}
            runDisabled={() => starting}
          />
          <YourScenarios scenarios={mine} activeId={scenario?.scenario_id ?? null} />
          <SectionPicker
            sections={sections.data}
            loading={sections.isLoading}
            error={sections.isError}
            onRetry={() => void sections.refetch()}
            selectedKey={target ? sectionKey(target) : null}
            onPick={(s) => {
              setPicked(s);
              setActiveRunId(null);
              setError(null);
            }}
          />
        </div>
        <div className="min-w-0 space-y-6">
          {missing ? (
            <div className="rounded-[12px] border border-border bg-surface">
              <EmptyState
                title="This scenario is no longer available"
                description="Scenarios you create live only in this session. Pick a preset or a section to start again."
                action={
                  <Button variant="secondary" asChild>
                    <AppLink href="/app/what-if">Back to the studio</AppLink>
                  </Button>
                }
              />
            </div>
          ) : target ? (
            <ScenarioEditor
              key={editorKey}
              section={{ citation: target.citation, heading: s1.data?.heading ?? meta?.heading ?? "", citedBy: meta?.cited_clause_count ?? null }}
              s1Text={s1.data?.s1_text ?? null}
              s1State={s1State}
              onRetryS1={() => void s1.refetch()}
              initialTitle={scenario?.title}
              initialRepeal={scenario?.edit_kind === "repeal"}
              initialText={scenario?.edit_kind === "text_edit" ? scenario.edited_text : null}
              presetMatch={presetMatch}
              customAllowed={allowCustom}
              busy={starting}
              error={error}
              onRun={submit}
            />
          ) : scenarioId && scenarios.isLoading ? (
            <Skeleton className="h-[480px] w-full rounded-[12px]" />
          ) : scenarios.isError ? (
            <ErrorState message="Scenarios could not be loaded." source="What-if scenarios" onRetry={() => void scenarios.refetch()} />
          ) : (
            <div className="rounded-[12px] border border-border bg-surface">
              <EmptyState
                title="Choose what to change"
                description="Run a preset for an instant result, or pick a section your documents cite, edit its text or repeal it, and preview the difference."
              />
              {error && <p className="px-6 pb-6 text-[13px] text-red">{error}</p>}
            </div>
          )}
          {showRun && <RunPanel run={run.data} starting={starting} />}
        </div>
      </div>
    </PageContainer>
  );
}

function matches(p: Scenario, e: EditorSubmit): boolean {
  return e.repeal ? p.edit_kind === "repeal" : p.edit_kind === "text_edit" && p.edited_text === e.editedText;
}

/**
 * The ONE place that decides whether custom (non-preset) what-if runs may be started.
 * Custom runs POST to the shared backend and spend model budget, so they are off unless enabled.
 *
 *   NEXT_PUBLIC_STRATA_ALLOW_CUSTOM_WHATIF=1 (or "true") -> allowed; anything else -> not allowed
 */
export function resolveCustomWhatIf(flag: string | undefined): boolean {
  const f = (flag ?? "").trim().toLowerCase();
  return f === "1" || f === "true";
}

/** Literal `process.env.NEXT_PUBLIC_*` read so Next inlines it into the client bundle. */
export function customWhatIfAllowed(): boolean {
  return resolveCustomWhatIf(process.env.NEXT_PUBLIC_STRATA_ALLOW_CUSTOM_WHATIF);
}

/** Local registry entry for the paused-run cue (the shared registry in lib/future-features.ts is not edited). */
export const CUSTOM_WHATIF_PAUSED = {
  id: "custom-whatif-paused",
  label: "Run impact",
  tooltip: "Custom what-if runs are paused: they use live model budget.",
} as const;

export const EDIT_KIND_LABELS = { text_edit: "Text edit", repeal: "Repeal" } as const;

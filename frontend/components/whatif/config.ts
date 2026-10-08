/**
 * The ONE place that decides whether custom (non-preset) what-if runs may be started.
 * Custom runs POST to the shared backend and spend model budget, so they are off in live mode.
 *
 *   NEXT_PUBLIC_STRATA_ALLOW_CUSTOM_WHATIF=1  -> allowed
 *   NEXT_PUBLIC_STRATA_ALLOW_CUSTOM_WHATIF=0  -> not allowed
 *   unset                                     -> allowed in mock mode, NOT allowed when NEXT_PUBLIC_STRATA_DATA=http
 */
export function resolveCustomWhatIf(flag: string | undefined, dataMode: string | undefined): boolean {
  const f = (flag ?? "").trim().toLowerCase();
  if (f === "1" || f === "true") return true;
  if (f === "0" || f === "false") return false;
  return dataMode !== "http";
}

/** Literal `process.env.NEXT_PUBLIC_*` reads so Next inlines them into the client bundle. */
export function customWhatIfAllowed(): boolean {
  return resolveCustomWhatIf(process.env.NEXT_PUBLIC_STRATA_ALLOW_CUSTOM_WHATIF, process.env.NEXT_PUBLIC_STRATA_DATA);
}

/** Local registry entry for the paused-run cue (the shared registry in lib/future-features.ts is not edited). */
export const CUSTOM_WHATIF_PAUSED = {
  id: "custom-whatif-paused",
  label: "Run impact",
  tooltip: "Custom what-if runs are paused: they use live model budget.",
} as const;

export const EDIT_KIND_LABELS = { text_edit: "Text edit", repeal: "Repeal" } as const;

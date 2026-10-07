// STUB — filled by the lib-core agent from spec §18.2. Types are the contract.
export type FutureVariant =
  | "button"
  | "toolbar"
  | "inline-add"
  | "card"
  | "nav"
  | "icon"
  | "chip"
  | "menu-item";

export interface FutureFeature {
  id: string;
  label: string;
  tooltip: string;
  /** lucide-react icon export name, e.g. "Bell". Resolved by <FutureCue/>. */
  icon: string;
  variant: FutureVariant;
}

export const SHOW_FUTURE_CUES = true;
export const FUTURE_FEATURES: Record<string, FutureFeature> = {};

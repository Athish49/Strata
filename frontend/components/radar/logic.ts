import type { RadarItem } from "@/lib/api/schemas";
import { formatCount } from "@/lib/format";

export type RadarGroup = RadarItem["applicable"];
export const GROUP_ORDER: readonly RadarGroup[] = ["yes", "no", "unclear"];

/** "standby_generator_count" -> "Standby generator count". */
export function humanizeKey(key: string): string {
  const s = key.replace(/[_-]+/g, " ").trim();
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : key;
}

export function formatBasisValue(v: string | number | boolean): string {
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") return Number.isInteger(v) ? formatCount(v) : String(v);
  return v;
}

export function groupItems(items: readonly RadarItem[]): Record<RadarGroup, RadarItem[]> {
  const out: Record<RadarGroup, RadarItem[]> = { yes: [], no: [], unclear: [] };
  for (const i of items) out[i.applicable].push(i);
  return out;
}

export interface RadarFilter {
  agency: string | null;
  query: string;
}

export function filterItems(items: readonly RadarItem[], f: RadarFilter): RadarItem[] {
  const q = f.query.trim().toLowerCase();
  return items.filter((i) => {
    if (f.agency && i.agency_id !== f.agency) return false;
    if (!q) return true;
    const hay = [i.citation, i.heading, i.affected_activity, i.reason, ...i.attribute_basis.map((a) => humanizeKey(a.key))]
      .join(" ")
      .toLowerCase();
    return hay.includes(q);
  });
}

/** Screened-out reason line: the stored reason, else the profile facts that screened it out. */
export function screenedLine(i: RadarItem): string {
  if (i.reason.trim()) return i.reason.trim();
  if (i.attribute_basis.length) {
    return `Not applicable given: ${i.attribute_basis.map((a) => `${humanizeKey(a.key).toLowerCase()} = ${formatBasisValue(a.value).toLowerCase()}`).join(", ")}.`;
  }
  return "Screened out against the company profile.";
}

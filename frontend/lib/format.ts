const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/**
 * ISO 8601 date or datetime -> "Feb 5, 2025". Date-only strings and datetimes are read by
 * their calendar date as written (no timezone shift). Returns "—" for empty or invalid input.
 */
export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso.trim());
  if (m) {
    const month = Number(m[2]);
    const day = Number(m[3]);
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) {
      return `${MONTHS[month - 1]} ${day}, ${Number(m[1])}`;
    }
    return "—";
  }
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
}

/** 12345 -> "12,345". */
export function formatCount(n: number): string {
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(Math.round(n));
}

/** Generic number with thousands separators and up to `digits` decimals. */
export function formatNumber(n: number, digits = 0): string {
  if (!Number.isFinite(n)) return "—";
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: digits }).format(n);
}

/** Ratio 0..1 -> "82%" (or "82.5%" with digits=1). */
export function formatPercent(ratio: number, digits = 0): string {
  if (!Number.isFinite(ratio)) return "—";
  return `${new Intl.NumberFormat("en-US", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(ratio * 100)}%`;
}

/** Model confidence 0..1 -> "82%". */
export function formatConfidence(confidence: number): string {
  return formatPercent(Math.min(1, Math.max(0, confidence)), 0);
}

/** "1 change" / "3 changes". */
export function pluralize(n: number, singular: string, plural = `${singular}s`): string {
  return `${formatCount(n)} ${n === 1 ? singular : plural}`;
}

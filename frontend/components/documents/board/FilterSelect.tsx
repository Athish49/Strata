import { ChevronDown } from "lucide-react";

/** Native select styled as the spec's select control (h-32, border-strong, radius 8). "" means all. */
export function FilterSelect({
  label,
  value,
  onChange,
  options,
  allLabel,
}: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
  options: { value: string; label: string }[];
  allLabel: string;
}) {
  return (
    <label className="relative inline-flex h-8 items-center">
      <span className="sr-only">{label}</span>
      <select
        aria-label={label}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
        className="h-8 max-w-[240px] cursor-pointer appearance-none rounded-[8px] border border-border-strong bg-surface pl-3 pr-8 text-[14px] text-ink focus-visible:outline-2 focus-visible:outline-offset-2"
      >
        <option value="">{allLabel}</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      <ChevronDown aria-hidden className="pointer-events-none absolute right-2.5 size-3.5 text-ink-3" strokeWidth={1.5} />
    </label>
  );
}

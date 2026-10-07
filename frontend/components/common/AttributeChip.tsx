import { cn } from "@/lib/utils";

/** Label: value pair as a small neutral chip, e.g. 'Owner: Compliance'. */
export function AttributeChip({
  label,
  children,
  icon,
  className,
}: {
  label?: string;
  children: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-[6px] bg-surface-muted px-2 text-[12px] font-medium text-ink-2 [&_svg]:size-3.5 [&_svg]:stroke-[1.5]",
        className,
      )}
    >
      {icon}
      {label && <span className="font-normal text-ink-3">{label}</span>}
      {children}
    </span>
  );
}

import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

/** Pills (h-22, radius 6, sans 12 medium) and Tags (11px medium, radius 4, 1px border). */
export const badgeVariants = cva("inline-flex shrink-0 items-center gap-1 whitespace-nowrap font-medium", {
  variants: {
    variant: {
      neutral: "h-[22px] rounded-[6px] bg-surface-muted px-2 text-[12px] text-ink-2",
      red: "h-[22px] rounded-[6px] bg-red-soft px-2 text-[12px] text-red",
      green: "h-[22px] rounded-[6px] bg-green-soft px-2 text-[12px] text-green",
      amber: "h-[22px] rounded-[6px] bg-amber-soft px-2 text-[12px] text-amber",
      outline: "h-[22px] rounded-[6px] border border-border-strong px-2 text-[12px] text-ink-2",
      tag: "h-[18px] rounded-[4px] border border-border-strong px-1.5 text-[11px] leading-none text-ink-3",
    },
  },
  defaultVariants: { variant: "neutral" },
});

export function Badge({
  className,
  variant,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

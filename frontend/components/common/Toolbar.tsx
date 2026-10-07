import * as React from "react";
import { cn } from "@/lib/utils";

/** Row of ghost icon+label actions separated by 1px vertical dividers; h-44 with a hairline bottom border. */
export function Toolbar({ children, className }: { children: React.ReactNode; className?: string }) {
  const items = React.Children.toArray(children).filter(Boolean);
  return (
    <div role="toolbar" className={cn("flex h-11 items-center border-b border-border px-2", className)}>
      {items.map((c, i) => (
        <React.Fragment key={i}>
          {i > 0 && <span aria-hidden className="mx-1 h-4 w-px bg-border-strong" />}
          {c}
        </React.Fragment>
      ))}
    </div>
  );
}

/** Ghost toolbar action. */
export function ToolbarButton({
  icon,
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { icon?: React.ReactNode }) {
  return (
    <button
      type="button"
      className={cn(
        "inline-flex h-8 items-center gap-2 rounded-[8px] px-3 text-[14px] text-ink-2 transition-colors duration-150 hover:bg-surface-muted hover:text-ink [&_svg]:size-4 [&_svg]:stroke-[1.5]",
        className,
      )}
      {...props}
    >
      {icon}
      {children}
    </button>
  );
}

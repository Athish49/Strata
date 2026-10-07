import * as React from "react";
import { cn } from "@/lib/utils";

export function Input({ className, type = "text", ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      className={cn(
        "h-9 w-full rounded-[8px] border border-border-strong bg-surface px-3 text-[14px] text-ink placeholder:text-ink-3",
        className,
      )}
      {...props}
    />
  );
}

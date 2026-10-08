"use client";
import * as React from "react";
import { Popover as P } from "radix-ui";
import { cn } from "@/lib/utils";

export const Popover = P.Root;
export const PopoverTrigger = P.Trigger;
export const PopoverAnchor = P.Anchor;

export function PopoverContent({
  className,
  sideOffset = 6,
  align = "start",
  ...props
}: React.ComponentProps<typeof P.Content>) {
  return (
    <P.Portal>
      <P.Content
        sideOffset={sideOffset}
        align={align}
        className={cn(
          "z-[70] w-72 rounded-[10px] border border-border bg-surface p-3 text-[14px] text-ink shadow-[var(--shadow-float)]",
          className,
        )}
        {...props}
      />
    </P.Portal>
  );
}

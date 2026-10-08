"use client";
import * as React from "react";
import { Tooltip as T } from "radix-ui";
import { cn } from "@/lib/utils";

export const TooltipProvider = ({ children }: { children: React.ReactNode }) => (
  <T.Provider delayDuration={250} skipDelayDuration={100}>
    {children}
  </T.Provider>
);
export const Tooltip = T.Root;
export const TooltipTrigger = T.Trigger;

export function TooltipContent({
  className,
  sideOffset = 6,
  ...props
}: React.ComponentProps<typeof T.Content>) {
  return (
    <T.Portal>
      <T.Content
        sideOffset={sideOffset}
        className={cn(
          "z-[80] max-w-[280px] rounded-[6px] bg-ink px-2.5 py-1.5 text-[12px] leading-4 text-white shadow-[var(--shadow-float)]",
          className,
        )}
        {...props}
      />
    </T.Portal>
  );
}

"use client";
import * as React from "react";
import { Tabs as T } from "radix-ui";
import { cn } from "@/lib/utils";

export const Tabs = T.Root;

/** Segmented: transparent track, active tab is a white pill with a hairline (§17.5). */
export function TabsList({ className, ...props }: React.ComponentProps<typeof T.List>) {
  return <T.List className={cn("inline-flex items-center gap-1", className)} {...props} />;
}

export function TabsTrigger({ className, ...props }: React.ComponentProps<typeof T.Trigger>) {
  return (
    <T.Trigger
      className={cn(
        "h-8 rounded-[8px] border border-transparent px-3 text-[14px] font-medium text-ink-3 transition-colors duration-150 hover:text-ink data-[state=active]:border-border data-[state=active]:bg-surface data-[state=active]:text-ink",
        className,
      )}
      {...props}
    />
  );
}

export const TabsContent = T.Content;

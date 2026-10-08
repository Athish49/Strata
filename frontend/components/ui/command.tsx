"use client";
import * as React from "react";
import { Command as C } from "cmdk";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

export function Command({ className, ...props }: React.ComponentProps<typeof C>) {
  return <C className={cn("flex w-full flex-col bg-surface text-ink", className)} {...props} />;
}

export function CommandInput({ className, ...props }: React.ComponentProps<typeof C.Input>) {
  return (
    <div className="flex h-12 items-center gap-3 border-b border-border px-4">
      <Search className="size-4 shrink-0 text-ink-3" strokeWidth={1.5} aria-hidden />
      <C.Input
        className={cn(
          "h-full flex-1 bg-transparent text-[15px] text-ink outline-none focus-visible:outline-none placeholder:text-ink-3",
          className,
        )}
        {...props}
      />
    </div>
  );
}

export function CommandList({ className, ...props }: React.ComponentProps<typeof C.List>) {
  return <C.List className={cn("max-h-[340px] overflow-y-auto p-1.5", className)} {...props} />;
}

export function CommandEmpty({ className, ...props }: React.ComponentProps<typeof C.Empty>) {
  return <C.Empty className={cn("px-3 py-6 text-[14px] text-ink-3", className)} {...props} />;
}

export function CommandGroup({ className, ...props }: React.ComponentProps<typeof C.Group>) {
  return (
    <C.Group
      className={cn(
        "[&_[cmdk-group-heading]]:px-2.5 [&_[cmdk-group-heading]]:py-1.5 [&_[cmdk-group-heading]]:text-[12px] [&_[cmdk-group-heading]]:font-medium [&_[cmdk-group-heading]]:text-ink-3",
        className,
      )}
      {...props}
    />
  );
}

export function CommandItem({ className, ...props }: React.ComponentProps<typeof C.Item>) {
  return (
    <C.Item
      className={cn(
        "flex cursor-default items-center gap-2 rounded-[6px] px-2.5 py-2 text-[14px] data-[selected=true]:bg-surface-muted",
        className,
      )}
      {...props}
    />
  );
}

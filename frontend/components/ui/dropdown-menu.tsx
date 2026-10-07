"use client";
import * as React from "react";
import { DropdownMenu as D } from "radix-ui";
import { cn } from "@/lib/utils";

export const DropdownMenu = D.Root;
export const DropdownMenuTrigger = D.Trigger;
export const DropdownMenuGroup = D.Group;

export function DropdownMenuContent({
  className,
  sideOffset = 6,
  align = "end",
  ...props
}: React.ComponentProps<typeof D.Content>) {
  return (
    <D.Portal>
      <D.Content
        sideOffset={sideOffset}
        align={align}
        className={cn(
          "z-[70] min-w-[220px] rounded-[10px] border border-border bg-surface p-1 text-[14px] text-ink shadow-[var(--shadow-float)]",
          className,
        )}
        {...props}
      />
    </D.Portal>
  );
}

export function DropdownMenuItem({ className, ...props }: React.ComponentProps<typeof D.Item>) {
  return (
    <D.Item
      className={cn(
        "relative flex cursor-default select-none items-center gap-2 rounded-[6px] px-2.5 py-2 outline-none data-[highlighted]:bg-surface-muted data-[disabled]:text-ink-4",
        className,
      )}
      {...props}
    />
  );
}

export function DropdownMenuLabel({ className, ...props }: React.ComponentProps<typeof D.Label>) {
  return (
    <D.Label className={cn("px-2.5 pb-1 pt-2 text-[12px] font-medium text-ink-3", className)} {...props} />
  );
}

export function DropdownMenuSeparator({ className, ...props }: React.ComponentProps<typeof D.Separator>) {
  return <D.Separator className={cn("-mx-1 my-1 h-px bg-border", className)} {...props} />;
}

"use client";
import * as React from "react";
import { Dialog as D } from "radix-ui";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Sheet = D.Root;
export const SheetTrigger = D.Trigger;
export const SheetClose = D.Close;
export const SheetTitle = D.Title;
export const SheetDescription = D.Description;

/** Right-hand drawer: 640px, surface, 1px left border, drawer shadow (§17.5). */
export function SheetContent({
  className,
  children,
  width = 640,
  ...props
}: React.ComponentProps<typeof D.Content> & { width?: number }) {
  return (
    <D.Portal>
      <D.Overlay className="fixed inset-0 z-50 bg-ink/30" />
      <D.Content
        style={{ width }}
        className={cn(
          "fixed inset-y-0 right-0 z-50 flex max-w-full flex-col border-l border-border bg-surface shadow-[var(--shadow-drawer)] motion-safe:animate-[sheet-in_200ms_ease-out]",
          className,
        )}
        {...props}
      >
        {children}
        <D.Close
          aria-label="Close"
          className="absolute right-4 top-4 grid size-8 place-items-center rounded-[8px] text-ink-2 hover:bg-surface-muted"
        >
          <X className="size-4" strokeWidth={1.5} />
        </D.Close>
      </D.Content>
    </D.Portal>
  );
}

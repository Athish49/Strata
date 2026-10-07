"use client";
import * as React from "react";
import { Dialog as D } from "radix-ui";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

export const Dialog = D.Root;
export const DialogTrigger = D.Trigger;
export const DialogClose = D.Close;
export const DialogTitle = D.Title;
export const DialogDescription = D.Description;

export function DialogOverlay({ className, ...props }: React.ComponentProps<typeof D.Overlay>) {
  return <D.Overlay className={cn("fixed inset-0 z-50 bg-ink/40", className)} {...props} />;
}

export function DialogContent({
  className,
  children,
  showClose = true,
  ...props
}: React.ComponentProps<typeof D.Content> & { showClose?: boolean }) {
  return (
    <D.Portal>
      <DialogOverlay />
      <D.Content
        className={cn(
          "fixed left-1/2 top-[18vh] z-50 w-[calc(100%-32px)] max-w-[560px] -translate-x-1/2 overflow-hidden rounded-[12px] border border-border bg-surface shadow-[var(--shadow-drawer)]",
          className,
        )}
        {...props}
      >
        {children}
        {showClose && (
          <D.Close
            aria-label="Close"
            className="absolute right-3 top-3 grid size-8 place-items-center rounded-[8px] text-ink-2 hover:bg-surface-muted"
          >
            <X className="size-4" strokeWidth={1.5} />
          </D.Close>
        )}
      </D.Content>
    </D.Portal>
  );
}

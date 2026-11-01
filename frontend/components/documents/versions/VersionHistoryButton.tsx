"use client";
import * as React from "react";
import { Clock } from "lucide-react";
import type { DocumentMeta } from "@/lib/api/schemas";
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { VersionHistoryPanel } from "./VersionHistoryPanel";

export interface VersionHistoryButtonProps {
  docId: string;
  doc?: DocumentMeta | null;
  className?: string;
}

/**
 * Clock icon that opens the version history drawer. The panel (and its queries) mounts only
 * while the drawer is open, so the reader header never fetches versions on its own.
 */
export function VersionHistoryButton({ docId, doc, className }: VersionHistoryButtonProps) {
  const [open, setOpen] = React.useState(false);
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <Tooltip>
        <TooltipTrigger asChild>
          <SheetTrigger asChild>
            <button
              type="button"
              aria-label="Version history"
              data-version-history-trigger=""
              className={cn("grid size-8 place-items-center rounded-[8px] text-ink-3 hover:bg-surface-muted hover:text-ink", className)}
            >
              <Clock aria-hidden className="size-4" strokeWidth={1.5} />
            </button>
          </SheetTrigger>
        </TooltipTrigger>
        <TooltipContent side="bottom">Version history and approvals</TooltipContent>
      </Tooltip>
      <SheetContent width={560}>
        <div className="border-b border-border px-6 py-5 pr-14">
          <SheetTitle className="font-serif text-[24px] font-normal leading-8 text-ink">Version history</SheetTitle>
          <SheetDescription className="text-[14px] text-ink-3">
            Every version{doc?.title ? ` of ${doc.title}` : ""}, its approval and who signed it.
          </SheetDescription>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <VersionHistoryPanel docId={docId} doc={doc} />
        </div>
      </SheetContent>
    </Sheet>
  );
}

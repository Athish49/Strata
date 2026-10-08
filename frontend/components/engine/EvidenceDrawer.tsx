"use client";
import * as React from "react";
import { Maximize2, Minimize2 } from "lucide-react";
import { parseAsString, useQueryState } from "nuqs";
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet";
import { EvidenceCardBody } from "./EvidenceCardBody";

export interface EvidenceDrawerViewProps {
  /** Open when non-null. */
  findingId: string | null;
  /** Called on Esc / overlay / close button. */
  onClose: () => void;
  /** Switch to a sibling / parent finding inside the drawer. */
  onOpenFinding?: (findingId: string) => void;
}

/** Controlled evidence drawer (640px, expandable to 880px). Focus is trapped and returned by the Sheet. */
export function EvidenceDrawerView({ findingId, onClose, onOpenFinding }: EvidenceDrawerViewProps) {
  const [wide, setWide] = React.useState(false);
  return (
    <Sheet open={!!findingId} onOpenChange={(o) => !o && onClose()}>
      <SheetContent width={wide ? 880 : 640} aria-describedby={undefined} className="gap-0">
        <SheetTitle className="sr-only">Evidence card</SheetTitle>
        <button
          type="button"
          aria-label={wide ? "Narrow drawer" : "Widen drawer"}
          onClick={() => setWide((w) => !w)}
          className="absolute right-14 top-4 z-20 grid size-8 place-items-center rounded-[8px] text-ink-2 hover:bg-surface-muted"
        >
          {wide ? <Minimize2 aria-hidden className="size-4" strokeWidth={1.5} /> : <Maximize2 aria-hidden className="size-4" strokeWidth={1.5} />}
        </button>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {findingId && <EvidenceCardBody findingId={findingId} variant="drawer" onOpenFinding={onOpenFinding} />}
        </div>
      </SheetContent>
    </Sheet>
  );
}

export interface EvidenceDrawerProps {
  /** Query-string key (default "finding"). */
  param?: string;
}

/** Self-driven drawer: open whenever `?finding=<id>` is present; closing removes it. Mount once per page. */
export function EvidenceDrawer({ param = "finding" }: EvidenceDrawerProps) {
  const [id, setId] = useQueryState(param, parseAsString);
  return <EvidenceDrawerView findingId={id} onClose={() => void setId(null)} onOpenFinding={(next) => void setId(next)} />;
}

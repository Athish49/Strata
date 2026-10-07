"use client";
import * as React from "react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Command, CommandInput, CommandList } from "@/components/ui/command";
import { FutureCue } from "@/components/common/FutureCue";
import { useShell } from "./ShellContext";

/** cmdk dialog shell (⌘K / Ctrl K). Real results arrive in M10; for now an empty-state line only. */
export function GlobalSearch() {
  const { searchOpen, setSearchOpen } = useShell();
  const [query, setQuery] = React.useState("");

  return (
    <Dialog
      open={searchOpen}
      onOpenChange={(o) => {
        setSearchOpen(o);
        if (!o) setQuery("");
      }}
    >
      <DialogContent showClose={false} className="max-w-[600px]">
        <DialogTitle className="sr-only">Search</DialogTitle>
        <DialogDescription className="sr-only">
          Search documents, clauses, changed sections, regulations and people.
        </DialogDescription>
        <Command shouldFilter={false} label="Search">
          <CommandInput
            value={query}
            onValueChange={setQuery}
            placeholder="Search doc id, clause id, citation…"
          />
          <CommandList>
            <p className="px-2.5 py-3 text-[14px] leading-5 text-ink-3">
              {query.trim()
                ? "Results will appear here."
                : "Search documents, clauses, changed sections, regulations and people."}
            </p>
            {query.trim() && (
              <FutureCue id="search-ask" variant="menu-item" side="left" label={`Ask Strata “${query.trim()}”`} />
            )}
          </CommandList>
        </Command>
      </DialogContent>
    </Dialog>
  );
}

"use client";
import * as React from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { GlobalSearch } from "./GlobalSearch";
import { ShortcutsSheet } from "./ShortcutsSheet";
import { Sidebar } from "./Sidebar";
import { SimulatedBanner } from "./SimulatedBanner";
import { ShellProvider, useShell } from "./ShellContext";

function Keys() {
  const { setSearchOpen, setShortcutsOpen } = useShell();
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setSearchOpen(true);
        return;
      }
      const t = e.target as HTMLElement | null;
      const typing = t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName));
      if (e.key === "?" && !typing && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        setShortcutsOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setSearchOpen, setShortcutsOpen]);
  return null;
}

/** Sidebar (264px, or 64px rail) + canvas. SimulatedBanner pinned above the scrolling content. */
export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <ShellProvider>
      <TooltipProvider>
        <div className="flex h-screen overflow-hidden bg-canvas">
          <Sidebar />
          <div className="flex min-w-0 flex-1 flex-col">
            <SimulatedBanner />
            <main id="main" className="min-h-0 flex-1 overflow-y-auto">
              {children}
            </main>
          </div>
        </div>
        <GlobalSearch />
        <ShortcutsSheet />
        <Keys />
      </TooltipProvider>
    </ShellProvider>
  );
}

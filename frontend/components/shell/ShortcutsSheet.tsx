"use client";
import { Sheet, SheetContent, SheetDescription, SheetTitle } from "@/components/ui/sheet";
import { useShell } from "./ShellContext";

const GROUPS: { title: string; rows: [string, string][] }[] = [
  { title: "Anywhere", rows: [["Search", "⌘K / Ctrl K"], ["Show shortcuts", "?"], ["Close drawer or dialog", "Esc"]] },
  { title: "Document reader", rows: [["Next finding", "j / ↓"], ["Previous finding", "k / ↑"], ["Open evidence", "Enter"]] },
  { title: "Change diff", rows: [["Next change", "n"], ["Previous change", "p"]] },
];

export function ShortcutsSheet() {
  const { shortcutsOpen, setShortcutsOpen } = useShell();
  return (
    <Sheet open={shortcutsOpen} onOpenChange={setShortcutsOpen}>
      <SheetContent width={420}>
        <div className="border-b border-border px-6 py-5">
          <SheetTitle className="font-serif text-[24px] font-normal leading-8 text-ink">Keyboard shortcuts</SheetTitle>
          <SheetDescription className="text-[14px] text-ink-3">Move through findings without the mouse.</SheetDescription>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {GROUPS.map((g) => (
            <section key={g.title} className="mb-6">
              <h3 className="mb-2 text-[12px] font-medium text-ink-3">{g.title}</h3>
              <dl>
                {g.rows.map(([k, v]) => (
                  <div key={k} className="flex items-center justify-between border-b border-border py-2.5 text-[14px]">
                    <dt className="text-ink">{k}</dt>
                    <dd className="font-mono text-[12.5px] text-ink-2">{v}</dd>
                  </div>
                ))}
              </dl>
            </section>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}

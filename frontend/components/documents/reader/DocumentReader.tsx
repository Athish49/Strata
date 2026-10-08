"use client";
import * as React from "react";
import { useVirtualizer } from "@tanstack/react-virtual";
import { parseAsString, useQueryState } from "nuqs";
import type { Annotation, Clause } from "@/lib/api/schemas";
import { FutureCue } from "@/components/common/FutureCue";
import { Toolbar } from "@/components/common/Toolbar";
import { EvidenceDrawer, Minimap, type MinimapTick } from "@/components/engine";
import { verdictLabel } from "@/lib/labels";
import { clauseLabel } from "@/lib/sentences";
import { ClauseRenderer } from "./ClauseRenderer";
import { FindingsRail } from "./FindingsRail";
import { buildReaderModel, clearedClauses, notesByClause, notesFor, railFindings, type ReaderItem, type RailFinding } from "./model";

export interface DocumentReaderProps {
  docId: string;
  clauses: Clause[];
  annotations: Annotation[];
  /** finding key (finding_id) -> plain-English sentence. */
  sentences?: ReadonlyMap<string, string>;
  /** Shown above the document (for example "No change in this run touched this document"). */
  notice?: React.ReactNode;
  /** Findings are still loading. */
  loadingFindings?: boolean;
  /** Scroll container of the page. Defaults to the shell's `#main`. */
  scrollElement?: HTMLElement | null;
  /** Virtual rows rendered beyond the viewport (tests raise it to render everything). */
  overscan?: number;
}

const NO_SENTENCES: ReadonlyMap<string, string> = new Map();

function estimate(item: ReaderItem, notesMap: ReturnType<typeof notesByClause>): number {
  switch (item.kind) {
    case "heading":
      return item.level === 0 ? 72 : item.level === 1 ? 52 : 44;
    case "table-head":
      return 48;
    case "table-row": {
      const n = notesFor(notesMap, item.clause.clause_id);
      return 46 + n.findings.length * 150;
    }
    case "clause": {
      const n = notesFor(notesMap, item.clause.clause_id);
      const lines = Math.max(1, Math.ceil(item.clause.text_raw.length / 80));
      return 18 + lines * 26 + n.findings.length * 64;
    }
  }
}

function prefersReducedMotion() {
  try {
    return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  } catch {
    return false;
  }
}

function isTyping(t: EventTarget | null) {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
}

/** Virtualized clause list + findings rail + minimap + keyboard navigation + evidence drawer (`?finding=`). */
export function DocumentReader({
  docId,
  clauses,
  annotations,
  sentences = NO_SENTENCES,
  notice,
  loadingFindings,
  scrollElement,
  overscan = 8,
}: DocumentReaderProps) {
  const notes = React.useMemo(() => notesByClause(annotations), [annotations]);
  const model = React.useMemo(() => buildReaderModel(clauses, notes, docId), [clauses, notes, docId]);
  const findings = React.useMemo(() => railFindings(model.clauses, annotations), [model.clauses, annotations]);
  const cleared = React.useMemo(() => clearedClauses(model.clauses, notes), [model.clauses, notes]);
  const total = Math.max(1, model.clauses.length);

  const [param, setParam] = useQueryState("finding", parseAsString);
  const paramRef = React.useRef<string | null>(param);
  paramRef.current = param;
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [pulseClause, setPulseClause] = React.useState<string | null>(null);
  const [openRows, setOpenRows] = React.useState<Map<string, boolean>>(() => new Map());
  const [openCleared, setOpenCleared] = React.useState<Set<string>>(() => new Set());

  // Scroll container + geometry -------------------------------------------------
  const [scroller, setScroller] = React.useState<HTMLElement | null>(scrollElement ?? null);
  const listRef = React.useRef<HTMLDivElement | null>(null);
  const [scrollMargin, setScrollMargin] = React.useState(0);
  const [viewportH, setViewportH] = React.useState(720);
  React.useLayoutEffect(() => {
    const el = scrollElement ?? document.getElementById("main");
    setScroller(el);
  }, [scrollElement]);
  // Runs after every render on purpose: the header above the list can change height.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  React.useLayoutEffect(() => {
    const list = listRef.current;
    if (!scroller || !list) return;
    const m = Math.round(list.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop);
    setScrollMargin((prev) => (prev === m ? prev : m));
  });
  React.useEffect(() => {
    if (!scroller) return;
    const measure = () => {
      const h = scroller.clientHeight;
      if (h > 0) setViewportH(h);
      const list = listRef.current;
      if (list) setScrollMargin(Math.round(list.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop));
    };
    measure();
    window.addEventListener("resize", measure);
    const RO = typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null;
    RO?.observe(scroller);
    return () => {
      window.removeEventListener("resize", measure);
      RO?.disconnect();
    };
  }, [scroller]);

  // eslint-disable-next-line react-hooks/incompatible-library
  const virt = useVirtualizer({
    count: model.items.length,
    getScrollElement: () => scroller,
    estimateSize: (i) => estimate(model.items[i], notes),
    overscan,
    scrollMargin,
    getItemKey: (i) => model.items[i].key,
  });

  const scrollToClause = React.useCallback(
    (clauseId: string) => {
      const idx = model.indexByClause.get(clauseId);
      if (idx === undefined) return;
      virt.scrollToIndex(idx, { align: "center" });
      // Row heights are measured lazily; settle on the right spot once they are known.
      window.setTimeout(() => virt.scrollToIndex(idx, { align: "center" }), 90);
      window.setTimeout(() => virt.scrollToIndex(idx, { align: "center" }), 260);
      if (!prefersReducedMotion()) {
        setPulseClause(clauseId);
        window.setTimeout(() => setPulseClause((c) => (c === clauseId ? null : c)), 600);
      }
    },
    [model.indexByClause, virt],
  );

  const select = React.useCallback(
    (f: RailFinding, openCard: boolean) => {
      setActiveId(f.id);
      scrollToClause(f.clause.clause_id);
      if (openCard && f.findingId) void setParam(f.findingId);
    },
    [scrollToClause, setParam],
  );

  // A shared ?finding= URL reopens its card and brings the clause into view.
  const syncedRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (!param || syncedRef.current === param) return;
    const f = findings.find((x) => x.findingId === param);
    if (!f) return;
    syncedRef.current = param;
    setActiveId(f.id);
    scrollToClause(f.clause.clause_id);
  }, [param, findings, scrollToClause]);

  // A ?clause= link (global search) scrolls to that clause once.
  const [clauseParam] = useQueryState("clause", parseAsString);
  const clauseSyncedRef = React.useRef<string | null>(null);
  React.useEffect(() => {
    if (!clauseParam || clauseSyncedRef.current === clauseParam) return;
    if (!model.indexByClause.has(clauseParam)) return;
    clauseSyncedRef.current = clauseParam;
    scrollToClause(clauseParam);
  }, [clauseParam, model.indexByClause, scrollToClause]);

  // Keyboard: j/k and arrows between findings, Enter opens the card, Esc clears the selection.
  const findingsRef = React.useRef(findings);
  findingsRef.current = findings;
  const activeRef = React.useRef(activeId);
  activeRef.current = activeId;
  const selectRef = React.useRef(select);
  selectRef.current = select;
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || e.defaultPrevented || isTyping(e.target)) return;
      if (paramRef.current) return; // drawer open: it owns the keyboard
      if (document.querySelector('[role="dialog"]')) return;
      const list = findingsRef.current;
      const cur = list.findIndex((f) => f.id === activeRef.current);
      const target = e.target as HTMLElement | null;
      const onControl = !!target && !!target.closest?.("button, a, summary, [role='button']");
      if (e.key === "j" || e.key === "k" || e.key === "ArrowDown" || e.key === "ArrowUp") {
        if (list.length === 0) return;
        if ((e.key === "ArrowDown" || e.key === "ArrowUp") && onControl && target?.closest?.("[role='group'], [role='toolbar']")) return;
        const down = e.key === "j" || e.key === "ArrowDown";
        const next = cur < 0 ? (down ? 0 : list.length - 1) : Math.min(list.length - 1, Math.max(0, cur + (down ? 1 : -1)));
        e.preventDefault();
        selectRef.current(list[next], false);
      } else if (e.key === "Enter" && !onControl) {
        const f = list[cur];
        if (f?.findingId) {
          e.preventDefault();
          void setParam(f.findingId);
        }
      } else if (e.key === "Escape") {
        setActiveId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setParam]);

  // Minimap ticks: ordinal / clause count, in the verdict token.
  const ticks: MinimapTick[] = React.useMemo(
    () =>
      findings.map((f) => ({
        id: f.id,
        position: (f.clause.ordinal - 0.5) / total,
        token: f.verdict,
        label: `${clauseLabel(f.clause)} · ${verdictLabel(f.verdict)}`,
      })),
    [findings, total],
  );

  const activeClause = findings.find((f) => f.id === activeId)?.clause.clause_id ?? null;
  const toggleRow = React.useCallback((id: string, current: boolean) => setOpenRows((m) => new Map(m).set(id, !current)), []);
  const toggleCleared = React.useCallback(
    (id: string) =>
      setOpenCleared((s) => {
        const n = new Set(s);
        if (n.has(id)) n.delete(id);
        else n.add(id);
        return n;
      }),
    [],
  );
  const selectCleared = React.useCallback(
    (id: string) => {
      setOpenCleared((s) => new Set(s).add(id));
      scrollToClause(id);
    },
    [scrollToClause],
  );
  const openFromCallout = React.useCallback(
    (findingId: string, clauseId: string) => {
      const f = findings.find((x) => x.findingId === findingId);
      setActiveId(f?.id ?? null);
      scrollToClause(clauseId);
      void setParam(findingId);
    },
    [findings, scrollToClause, setParam],
  );

  const railHeight = Math.max(360, viewportH - 32);
  // Below md the rail and minimap are hidden unless toggled open (shown above the document).
  const [railOpen, setRailOpen] = React.useState(false);

  return (
    <div className="flex flex-col items-stretch gap-5 px-4 pb-16 pt-5 md:flex-row md:items-start md:px-10">
      <div className="min-w-0 flex-1">
        <button
          type="button"
          aria-expanded={railOpen}
          aria-controls="reader-findings-rail"
          onClick={() => setRailOpen((o) => !o)}
          className="mb-3 w-full rounded-[10px] border border-border bg-surface px-3 py-2 text-left text-[14px] text-ink-2 hover:bg-surface-muted md:hidden"
        >
          {railOpen ? "Hide findings" : `Show findings (${findings.length})`}
        </button>
        <Toolbar className="mb-4 rounded-[10px] border border-border bg-surface">
          <FutureCue id="ask-document" />
          <FutureCue id="export-redline" />
          <FutureCue id="view-original" />
          <span className="ml-auto hidden pr-3 text-[12px] text-ink-3 xl:inline">
            <kbd className="font-mono">j</kbd> / <kbd className="font-mono">k</kbd> next or previous finding · <kbd className="font-mono">Enter</kbd> evidence · <kbd className="font-mono">Esc</kbd> close
          </span>
        </Toolbar>
        {notice}
        <div ref={listRef} data-reader-list="" className="relative" style={{ height: virt.getTotalSize() }}>
          {virt.getVirtualItems().map((v) => {
            const item = model.items[v.index];
            const clauseId = item.kind === "clause" || item.kind === "table-row" ? item.clause.clause_id : null;
            const n = clauseId ? notesFor(notes, clauseId) : notesFor(notes, "");
            const defaultOpen = item.kind === "table-row" && n.findings.length > 0;
            const rowOpen = clauseId ? (openRows.get(clauseId) ?? defaultOpen) : false;
            return (
              <div
                key={v.key}
                data-index={v.index}
                ref={virt.measureElement}
                className="absolute left-0 top-0 w-full"
                style={{ transform: `translateY(${v.start - virt.options.scrollMargin}px)` }}
              >
                <ClauseRenderer
                  item={item}
                  notes={n}
                  sentences={sentences}
                  active={!!clauseId && clauseId === activeClause}
                  pulse={!!clauseId && clauseId === pulseClause}
                  rowExpanded={rowOpen}
                  onToggleRow={(id) => toggleRow(id, openRows.get(id) ?? defaultOpen)}
                  clearedOpen={!!clauseId && openCleared.has(clauseId)}
                  onToggleCleared={toggleCleared}
                  onOpenFinding={openFromCallout}
                />
              </div>
            );
          })}
        </div>
      </div>
      <div
        id="reader-findings-rail"
        className={`order-first h-[420px] shrink-0 gap-3 md:sticky md:top-4 md:order-none md:flex md:h-[var(--rail-h)] ${railOpen ? "flex" : "hidden"}`}
        style={{ "--rail-h": `${railHeight}px` } as React.CSSProperties}
      >
        <FindingsRail
          findings={findings}
          sentences={sentences}
          activeId={activeId}
          onSelect={(f) => select(f, true)}
          cleared={cleared}
          onSelectCleared={selectCleared}
          loading={loadingFindings}
          className="h-full w-full md:w-[340px]"
        />
        <Minimap ticks={ticks} activeId={activeId} height="100%" onTickClick={(id) => {
          const f = findings.find((x) => x.id === id);
          if (f) select(f, false);
        }} />
      </div>
      <EvidenceDrawer />
    </div>
  );
}

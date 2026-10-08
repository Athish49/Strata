"use client";
import * as React from "react";
import { ChevronDown, ChevronUp, Columns2, FileDiff, Rows2 } from "lucide-react";
import type { DiffSegment, LineDiff } from "@/lib/api/schemas";
import { formatCount } from "@/lib/format";
import { DIFF_TOKENS } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";

export type DiffMode = "inline" | "side-by-side";

export interface DiffViewProps {
  /** `change.diff_segments`. May be empty (list rows / unavailable): a "no text diff" state is shown. */
  segments: DiffSegment[];
  /** Controlled mode; omit for uncontrolled (see defaultMode). */
  mode?: DiffMode;
  defaultMode?: DiffMode;
  onModeChange?: (mode: DiffMode) => void;
  /** Collapse unchanged runs longer than this many characters (default 300). */
  collapseThreshold?: number;
  /** Neutral explanation above the diff, e.g. "Only the readoption stamp changed" (noise classes). */
  banner?: React.ReactNode;
  /**
   * Enables the "Show raw diff" toggle. `lines` is the line diff from api.kb.compare (undefined until loaded);
   * pass `onToggle` to lazy-load it when the toggle turns on.
   */
  rawDiff?: { lines?: LineDiff; loading?: boolean; error?: boolean; onToggle?: (on: boolean) => void };
  /** Bind n / p to next / previous change (only while no input is focused). Default false. */
  hotkeys?: boolean;
  /** Tailwind max-height class of the scroll area. Default "max-h-[480px]". */
  maxHeightClass?: string;
  className?: string;
}

const CONTEXT_CHARS = 80;

/** Pure: indexes (into `segments`) where a change group begins; a group is a run of consecutive non-equal segments. */
export function changeGroupStarts(segments: readonly DiffSegment[]): number[] {
  const starts: number[] = [];
  segments.forEach((s, i) => {
    if (s.op !== "equal" && (i === 0 || segments[i - 1].op === "equal")) starts.push(i);
  });
  return starts;
}

interface Piece {
  seg: DiffSegment;
  i: number;
  /** group number if this segment is part of a change group. */
  group: number | null;
}

function toPieces(segments: readonly DiffSegment[]): Piece[] {
  let g = -1;
  return segments.map((seg, i) => {
    if (seg.op === "equal") return { seg, i, group: null };
    if (i === 0 || segments[i - 1].op === "equal") g++;
    return { seg, i, group: g };
  });
}

function EqualRun({
  piece,
  last,
  threshold,
  expanded,
  toggle,
}: {
  piece: Piece;
  last: boolean;
  threshold: number;
  expanded: Set<number>;
  toggle: (i: number) => void;
}) {
  const text = piece.seg.text;
  if (text.length <= threshold) return <>{text}</>;
  if (expanded.has(piece.i)) {
    return (
      <>
        {text}{" "}
        <button type="button" onClick={() => toggle(piece.i)} className="rounded-[4px] border border-border-strong bg-surface px-1.5 font-sans text-[11px] text-ink-3 hover:text-ink">
          Collapse
        </button>
      </>
    );
  }
  const head = piece.i > 0 ? text.slice(0, CONTEXT_CHARS) : "";
  const tail = !last ? text.slice(text.length - CONTEXT_CHARS) : "";
  const hidden = text.length - head.length - tail.length;
  return (
    <>
      {head}
      <button
        type="button"
        onClick={() => toggle(piece.i)}
        aria-label={`Show ${formatCount(hidden)} unchanged characters`}
        className="mx-1 rounded-[4px] border border-border-strong bg-surface-muted px-1.5 font-sans text-[11px] leading-4 text-ink-3 hover:text-ink"
      >
        … {formatCount(hidden)} unchanged characters …
      </button>
      {tail}
    </>
  );
}

function Mark({ op, children }: { op: "delete" | "insert"; children: React.ReactNode }) {
  const Tag = op === "delete" ? "del" : "ins";
  return <Tag className={cn("rounded-[2px] px-px", op === "delete" ? "no-underline" : "", DIFF_TOKENS[op])}>{children}</Tag>;
}

function Pane({
  pieces,
  side,
  threshold,
  expanded,
  toggle,
  current,
  className,
  onScroll,
  paneRef,
  label,
}: {
  pieces: Piece[];
  side: "both" | "left" | "right";
  threshold: number;
  expanded: Set<number>;
  toggle: (i: number) => void;
  current: number;
  className?: string;
  onScroll?: React.UIEventHandler<HTMLDivElement>;
  paneRef?: React.Ref<HTMLDivElement>;
  label: string;
}) {
  // Side panes only show the text that exists on their side; equal runs stay in both so collapsing aligns.
  const nodes: React.ReactNode[] = [];
  let k = 0;
  while (k < pieces.length) {
    const p = pieces[k];
    if (p.group === null) {
      nodes.push(<EqualRun key={`e${p.i}`} piece={p} last={k === pieces.length - 1} threshold={threshold} expanded={expanded} toggle={toggle} />);
      k++;
      continue;
    }
    const g = p.group;
    const members: Piece[] = [];
    while (k < pieces.length && pieces[k].group === g) members.push(pieces[k++]);
    const shown = members.filter((m) => (side === "both" ? true : side === "left" ? m.seg.op === "delete" : m.seg.op === "insert"));
    nodes.push(
      <span
        key={`g${g}`}
        data-change-group={g}
        data-current={g === current ? "true" : undefined}
        className={cn("rounded-[3px]", g === current && "outline outline-2 outline-offset-2 outline-ink")}
      >
        {shown.map((m) => (
          <Mark key={m.i} op={m.seg.op as "delete" | "insert"}>
            {m.seg.text}
          </Mark>
        ))}
      </span>,
    );
  }
  return (
    <div
      ref={paneRef}
      onScroll={onScroll}
      tabIndex={0}
      role="region"
      aria-label={label}
      className={cn("overflow-auto whitespace-pre-wrap break-words rounded-[8px] border border-border bg-surface p-4 font-serif text-[15px] leading-6 text-ink", className)}
    >
      {nodes}
    </div>
  );
}

function RawLines({ lines, maxHeightClass }: { lines: LineDiff; maxHeightClass: string }) {
  return (
    <div role="region" aria-label="Raw line diff" tabIndex={0} className={cn("overflow-auto rounded-[8px] border border-border bg-surface-muted py-2 font-mono text-[12.5px] leading-[18px]", maxHeightClass)}>
      {lines.map((l, i) => (
        <div
          key={i}
          className={cn(
            "whitespace-pre-wrap break-words px-3",
            l.op === "delete" && "bg-red-soft text-red",
            l.op === "insert" && "bg-green-soft text-green",
            l.op === "equal" && "text-ink-3",
          )}
        >
          <span aria-hidden className="mr-2 select-none">
            {l.op === "delete" ? "−" : l.op === "insert" ? "+" : " "}
          </span>
          <span className={l.op === "delete" ? "line-through" : l.op === "insert" ? "underline" : undefined}>{l.line || " "}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Renders `diff_segments` as an inline redline or side-by-side (synchronized scroll), collapsing long unchanged runs,
 * with a change navigator and an optional raw line-diff toggle. Deletions are struck through and insertions underlined
 * (never colour-only). Safe on empty segments and very long texts.
 */
export function DiffView({
  segments,
  mode: modeProp,
  defaultMode = "inline",
  onModeChange,
  collapseThreshold = 300,
  banner,
  rawDiff,
  hotkeys = false,
  maxHeightClass = "max-h-[480px]",
  className,
}: DiffViewProps) {
  const [modeState, setModeState] = React.useState<DiffMode>(defaultMode);
  const mode = modeProp ?? modeState;
  const [expanded, setExpanded] = React.useState<Set<number>>(() => new Set());
  const [current, setCurrent] = React.useState(0);
  const [raw, setRaw] = React.useState(false);
  const rootRef = React.useRef<HTMLDivElement>(null);
  const leftRef = React.useRef<HTMLDivElement>(null);
  const rightRef = React.useRef<HTMLDivElement>(null);
  const syncing = React.useRef(false);

  const pieces = React.useMemo(() => toPieces(segments), [segments]);
  const groupCount = React.useMemo(() => changeGroupStarts(segments).length, [segments]);
  const cur = groupCount === 0 ? 0 : Math.min(current, groupCount - 1);

  const setMode = (m: DiffMode) => {
    setModeState(m);
    onModeChange?.(m);
  };
  const toggle = React.useCallback((i: number) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });
  }, []);

  const goTo = React.useCallback(
    (n: number) => {
      if (groupCount === 0) return;
      const idx = ((n % groupCount) + groupCount) % groupCount;
      setCurrent(idx);
      requestAnimationFrame(() => {
        const el = rootRef.current?.querySelector<HTMLElement>(`[data-change-group="${idx}"]`);
        if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "center", inline: "nearest" });
      });
    },
    [groupCount],
  );

  React.useEffect(() => {
    if (!hotkeys || groupCount === 0) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      if (e.key === "n") goTo(cur + 1);
      else if (e.key === "p") goTo(cur - 1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [hotkeys, groupCount, cur, goTo]);

  const syncScroll = (from: "left" | "right") => () => {
    if (syncing.current) return;
    const a = from === "left" ? leftRef.current : rightRef.current;
    const b = from === "left" ? rightRef.current : leftRef.current;
    if (!a || !b) return;
    syncing.current = true;
    const ratio = a.scrollHeight - a.clientHeight > 0 ? a.scrollTop / (a.scrollHeight - a.clientHeight) : 0;
    b.scrollTop = ratio * (b.scrollHeight - b.clientHeight);
    requestAnimationFrame(() => {
      syncing.current = false;
    });
  };

  const empty = segments.length === 0;
  const identical = !empty && groupCount === 0;

  return (
    <div ref={rootRef} className={cn("space-y-3", className)} data-diff-mode={mode}>
      <div className="flex flex-wrap items-center gap-2">
        {!raw && (
          <div role="group" aria-label="Diff layout" className="inline-flex rounded-[8px] border border-border p-0.5">
            {(
              [
                ["inline", "Inline redline", Rows2],
                ["side-by-side", "Side by side", Columns2],
              ] as const
            ).map(([m, text, Icon]) => (
              <button
                key={m}
                type="button"
                aria-pressed={mode === m}
                onClick={() => setMode(m)}
                className={cn(
                  "inline-flex h-7 items-center gap-1.5 rounded-[6px] px-2.5 text-[13px] transition-colors",
                  mode === m ? "border border-border bg-surface font-medium text-ink" : "border border-transparent text-ink-3 hover:text-ink",
                )}
              >
                <Icon aria-hidden className="size-3.5" strokeWidth={1.5} />
                {text}
              </button>
            ))}
          </div>
        )}
        {!raw && groupCount > 0 && (
          <div className="inline-flex items-center gap-1 text-[13px] text-ink-2">
            <span aria-live="polite" className="tabular-nums">
              Change {cur + 1} of {groupCount}
            </span>
            <button type="button" aria-label="Previous change" onClick={() => goTo(cur - 1)} className="grid size-7 place-items-center rounded-[6px] text-ink-2 hover:bg-surface-muted">
              <ChevronUp aria-hidden className="size-4" strokeWidth={1.5} />
            </button>
            <button type="button" aria-label="Next change" onClick={() => goTo(cur + 1)} className="grid size-7 place-items-center rounded-[6px] text-ink-2 hover:bg-surface-muted">
              <ChevronDown aria-hidden className="size-4" strokeWidth={1.5} />
            </button>
          </div>
        )}
        {rawDiff && (
          <button
            type="button"
            aria-pressed={raw}
            onClick={() => {
              const next = !raw;
              setRaw(next);
              rawDiff.onToggle?.(next);
            }}
            className="ml-auto inline-flex h-7 items-center gap-1.5 rounded-[6px] px-2.5 text-[13px] text-ink-2 hover:bg-surface-muted hover:text-ink"
          >
            <FileDiff aria-hidden className="size-3.5" strokeWidth={1.5} />
            {raw ? "Hide raw diff" : "Show raw diff"}
          </button>
        )}
      </div>

      {banner && <div className="rounded-[8px] border border-border bg-surface-muted px-3 py-2 text-[13px] text-ink-2">{banner}</div>}

      {raw ? (
        rawDiff?.loading ? (
          <div className="skeleton h-24 w-full" aria-label="Loading raw diff" />
        ) : rawDiff?.error ? (
          <p className="text-[13px] text-ink-3">The raw diff could not be loaded.</p>
        ) : rawDiff?.lines && rawDiff.lines.length > 0 ? (
          <RawLines lines={rawDiff.lines} maxHeightClass={maxHeightClass} />
        ) : (
          <p className="text-[13px] text-ink-3">No raw diff is available for this section.</p>
        )
      ) : empty ? (
        <p data-testid="diff-empty" className="rounded-[8px] border border-dashed border-border-strong px-4 py-6 text-center text-[13px] text-ink-3">
          No text diff is available for this change.
        </p>
      ) : identical ? (
        <p data-testid="diff-identical" className="rounded-[8px] border border-dashed border-border-strong px-4 py-6 text-center text-[13px] text-ink-3">
          The text is identical in both snapshots.
        </p>
      ) : mode === "inline" ? (
        <Pane pieces={pieces} side="both" threshold={collapseThreshold} expanded={expanded} toggle={toggle} current={cur} className={maxHeightClass} label="Inline redline" />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <div className="mb-1 text-[12px] font-medium text-ink-3">Old rule (S1)</div>
            <Pane pieces={pieces} side="left" threshold={collapseThreshold} expanded={expanded} toggle={toggle} current={cur} className={maxHeightClass} paneRef={leftRef} onScroll={syncScroll("left")} label="Old rule (S1)" />
          </div>
          <div>
            <div className="mb-1 text-[12px] font-medium text-ink-3">New rule (S2)</div>
            <Pane pieces={pieces} side="right" threshold={collapseThreshold} expanded={expanded} toggle={toggle} current={cur} className={maxHeightClass} paneRef={rightRef} onScroll={syncScroll("right")} label="New rule (S2)" />
          </div>
        </div>
      )}
    </div>
  );
}

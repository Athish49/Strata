"use client";
import * as React from "react";
import { Check, ChevronDown, ChevronRight } from "lucide-react";
import type { Annotation, Clause } from "@/lib/api/schemas";
import { VerdictPill } from "@/components/engine";
import { clauseLabel, localClauseId } from "@/lib/sentences";
import { verdictToken, VERDICT_SEVERITY_ORDER } from "@/lib/verdict-tokens";
import { cn } from "@/lib/utils";
import { Inline, MarkdownText, type Highlight } from "./markdown";
import { annotationKey, cellOffset, columnLabel, type ClauseNotes, type Edge, type ReaderItem, type TableGroup } from "./model";

export interface ClauseRendererProps {
  item: ReaderItem;
  notes: ClauseNotes;
  /** finding key -> plain-English sentence (falls back to the annotation's reason). */
  sentences: ReadonlyMap<string, string>;
  /** The clause holds the finding currently selected in the rail / by keyboard. */
  active?: boolean;
  /** Briefly true after a jump to this clause (600 ms highlight pulse). */
  pulse?: boolean;
  /** Register row: all cells shown. */
  rowExpanded?: boolean;
  onToggleRow?: (clauseId: string) => void;
  /** Cleared reasons panel open. */
  clearedOpen?: boolean;
  onToggleCleared?: (clauseId: string) => void;
  /** Open the evidence card for a finding (sets ?finding=). */
  onOpenFinding?: (findingId: string, clauseId: string) => void;
}

function worstVerdict(notes: ClauseNotes) {
  for (const v of VERDICT_SEVERITY_ORDER) if (notes.findings.some((f) => f.verdict === v)) return v;
  return notes.findings.length ? "info" : null;
}

/** Quote highlights for a clause: only spans that fit inside the text are used. */
export function highlightsFor(clause: Pick<Clause, "text_raw">, notes: ClauseNotes): Highlight[] {
  const out: Highlight[] = [];
  for (const a of notes.findings) {
    const s = a.quote_span;
    if (!s || !(s[1] > s[0]) || s[0] < 0 || s[1] > clause.text_raw.length) continue;
    out.push({ range: [s[0], s[1]], token: a.verdict ?? "info", describedBy: noteId(a) });
  }
  return out;
}

const noteId = (a: Annotation) => `reader-note-${annotationKey(a).replace(/[^A-Za-z0-9_-]/g, "_")}`;

/* ------------------------------------------------------------------ headings */

function HeadingRow({ level, text, anchors }: { level: number; text: string; anchors: string[] }) {
  const lvl = Math.min(4, level + 2) as 2 | 3 | 4;
  const Tag = (`h${lvl}`) as "h2" | "h3" | "h4";
  return (
    <div className="pl-14 pr-2" data-clause-anchor={anchors[0]}>
      <Tag
        className={cn(
          "text-ink",
          level === 0 && "mt-10 border-b border-border pb-2 font-serif text-[24px] font-normal leading-8 tracking-[-0.01em]",
          level === 1 && "mt-6 font-serif text-[19px] font-normal leading-[26px]",
          level >= 2 && "mt-4 text-[15px] font-semibold leading-6",
        )}
      >
        {text}
      </Tag>
    </div>
  );
}

/* ------------------------------------------------------------------ frame, gutter, callouts */

function ClearedMarker({ clauseId, notes, open, onToggle }: { clauseId: string; notes: ClauseNotes; open?: boolean; onToggle?: (id: string) => void }) {
  const n = notes.cleared.length;
  if (n === 0) return null;
  const title = n === 1 ? notes.cleared[0].reason || "Checked: no impact." : `Checked against ${n} changes, no impact`;
  return (
    <button
      type="button"
      data-cleared-marker=""
      aria-expanded={!!open}
      aria-label={n === 1 ? "Checked: no impact" : `Checked against ${n} changes, no impact`}
      title={title}
      onClick={() => onToggle?.(clauseId)}
      className="grid size-5 place-items-center rounded-[4px] text-[color:var(--state-cleared)] transition-colors duration-150 hover:bg-[color:var(--green-soft)]"
    >
      <Check aria-hidden className="size-3.5" strokeWidth={2} />
    </button>
  );
}

function ClearedPanel({ notes }: { notes: ClauseNotes }) {
  const [all, setAll] = React.useState(false);
  const rows = all ? notes.cleared : notes.cleared.slice(0, 4);
  return (
    <div data-cleared-panel="" className="mt-2 rounded-[8px] border border-border bg-surface-muted/60 px-3 py-2">
      <p className="text-[12px] font-medium text-[color:var(--state-cleared)]">
        {notes.cleared.length === 1 ? "Checked against 1 change, no impact" : `Checked against ${notes.cleared.length} changes, no impact`}
      </p>
      <ul className="mt-1.5 space-y-1.5">
        {rows.map((a, i) => (
          <li key={`${a.change_id}-${i}`} className="text-[13px] leading-[18px] text-ink-2">
            {a.citation && <span className="mr-2 font-mono text-[12.5px] text-ink">{a.citation}</span>}
            {a.reason || "Checked: no impact."}
          </li>
        ))}
      </ul>
      {notes.cleared.length > 4 && (
        <button type="button" onClick={() => setAll((v) => !v)} className="mt-1.5 text-[12px] text-ink-3 hover:text-ink">
          {all ? "Show fewer" : `Show all ${notes.cleared.length}`}
        </button>
      )}
    </div>
  );
}

function FindingCallouts({
  notes,
  sentences,
  onOpen,
  clauseId,
}: {
  notes: ClauseNotes;
  sentences: ReadonlyMap<string, string>;
  onOpen?: (findingId: string, clauseId: string) => void;
  clauseId: string;
}) {
  if (notes.findings.length === 0) return null;
  return (
    <div className="mt-3 space-y-2 font-sans">
      {notes.findings.map((a) => {
        const text = sentences.get(annotationKey(a)) ?? a.reason;
        return (
          <div key={annotationKey(a)} id={noteId(a)} data-finding-callout="" className="flex items-start gap-3 rounded-[8px] border border-border bg-surface px-3 py-2">
            <VerdictPill verdict={a.verdict ?? "info"} size="sm" className="mt-0.5" />
            <p className="min-w-0 flex-1 text-[13px] leading-[19px] text-ink">
              {text}
              {a.citation && <span className="ml-2 font-mono text-[12.5px] text-ink-3">{a.citation}</span>}
            </p>
            {a.finding_id && onOpen && (
              <button
                type="button"
                onClick={() => onOpen(a.finding_id as string, clauseId)}
                className="shrink-0 rounded-[6px] px-2 py-0.5 text-[12px] font-medium text-ink-2 underline-offset-2 hover:bg-surface-muted hover:text-ink hover:underline"
              >
                View evidence
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface FrameProps {
  clause: Clause;
  notes: ClauseNotes;
  sentences: ReadonlyMap<string, string>;
  active?: boolean;
  pulse?: boolean;
  clearedOpen?: boolean;
  onToggleCleared?: (id: string) => void;
  onOpenFinding?: (findingId: string, clauseId: string) => void;
  /** Extra classes for the content column. */
  contentClass?: string;
  /** Table rows: no vertical padding so rows touch. */
  flush?: boolean;
  children: React.ReactNode;
}

/** Gutter (✓ marker / clause id) + verdict-coloured left border + content + callouts. One per clause. */
function ClauseFrame({ clause, notes, sentences, active, pulse, clearedOpen, onToggleCleared, onOpenFinding, contentClass, flush, children }: FrameProps) {
  const worst = worstVerdict(notes);
  const tok = worst ? verdictToken(worst) : null;
  return (
    <div
      data-clause={clause.clause_id}
      data-clause-state={worst ? "finding" : notes.cleared.length ? "cleared" : "plain"}
      className={cn(
        "group relative flex gap-0 border-l-2 transition-colors duration-500 motion-reduce:transition-none",
        tok ? tok.border : "border-transparent",
        (pulse || active) && "bg-surface-muted",
      )}
    >
      <div className="flex w-[54px] shrink-0 flex-col items-end gap-1 pr-2.5 pt-[3px]">
        <ClearedMarker clauseId={clause.clause_id} notes={notes} open={clearedOpen} onToggle={onToggleCleared} />
        <span
          className={cn(
            "max-w-full truncate font-mono text-[10.5px] leading-4 text-ink-4 opacity-0 transition-opacity duration-150 group-hover:opacity-100 motion-reduce:transition-none",
            (active || notes.findings.length > 0) && "opacity-100",
          )}
          title={clause.clause_id}
        >
          {localClauseId(clause)}
        </span>
      </div>
      <div className={cn("min-w-0 flex-1 pr-2", flush ? "py-0" : "py-1.5", contentClass)}>
        {children}
        <FindingCallouts notes={notes} sentences={sentences} onOpen={onOpenFinding} clauseId={clause.clause_id} />
        {clearedOpen && notes.cleared.length > 0 && <ClearedPanel notes={notes} />}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ sub-renderers, one per unit_kind */

type ClauseProps = Omit<FrameProps, "children" | "contentClass" | "flush"> & { edge: Edge };

/** `section`: paragraphs in the document serif. */
export function SectionClause(p: ClauseProps) {
  const hs = highlightsFor(p.clause, p.notes);
  const blank = !p.clause.text_raw.trim();
  return (
    <ClauseFrame {...p}>
      {blank ? (
        <p className="font-sans text-[13px] text-ink-3">{clauseLabel(p.clause)}</p>
      ) : (
        <MarkdownText raw={p.clause.text_raw} highlights={hs} className="max-w-[72ch] font-serif text-[16px] leading-[26px] text-ink" />
      )}
    </ClauseFrame>
  );
}

/** `tariff_subrule`: text with a sheet / rule label. */
export function TariffSubruleClause(p: ClauseProps) {
  const hs = highlightsFor(p.clause, p.notes);
  return (
    <ClauseFrame {...p}>
      <div className="max-w-[72ch]">
        <span className="mb-1 inline-flex h-[18px] items-center rounded-[4px] border border-border-strong px-1.5 font-mono text-[11px] text-ink-3">
          Rule {localClauseId(p.clause)}
        </span>
        <MarkdownText raw={p.clause.text_raw} highlights={hs} className="font-serif text-[16px] leading-[26px] text-ink" />
      </div>
    </ClauseFrame>
  );
}

/** `appendix`: a titled block. */
export function AppendixClause(p: ClauseProps) {
  const hs = highlightsFor(p.clause, p.notes);
  return (
    <ClauseFrame {...p}>
      <div className="max-w-[72ch] rounded-[12px] border border-border bg-surface px-6 py-4">
        <MarkdownText raw={p.clause.text_raw} highlights={hs} className="font-serif text-[16px] leading-[26px] text-ink" />
      </div>
    </ClauseFrame>
  );
}

/** `form_field`: a labelled field inside an "Appendix / Form" block, so a notice letter reads like a letter. */
export function FormFieldClause(p: ClauseProps) {
  const hs = highlightsFor(p.clause, p.notes);
  const first = p.edge === "first" || p.edge === "only";
  const last = p.edge === "last" || p.edge === "only";
  return (
    <ClauseFrame {...p} flush>
      <div
        data-form-block=""
        className={cn(
          "max-w-[72ch] border-x border-border bg-surface px-6 font-serif",
          first && "rounded-t-[12px] border-t pt-4",
          last && "rounded-b-[12px] border-b pb-4",
          !first && "pt-1",
        )}
      >
        {first && (
          <span className="mb-2 inline-flex h-[18px] items-center rounded-[4px] border border-border-strong px-1.5 font-sans text-[11px] font-medium text-ink-3">
            Appendix / Form
          </span>
        )}
        <MarkdownText raw={p.clause.text_raw} highlights={hs} variant="form" className="text-[16px] leading-[26px] text-ink" />
      </div>
    </ClauseFrame>
  );
}

/* ------------------------------------------------------------------ register / table rows */

function gridTemplate(widths: number[], lead = false) {
  return `${lead ? "28px " : ""}${widths.map((w) => `minmax(0, ${w}fr)`).join(" ")}`;
}

/** Header row of a register / table group. */
export function TableHead({ group }: { group: TableGroup }) {
  return (
    <div className="pl-14 pr-2 pt-3" role="presentation">
      <div
        role="row"
        className="grid items-center gap-3 rounded-t-[8px] border border-border bg-surface-muted px-3 py-2 text-[12px] font-medium leading-4 text-ink-3"
        style={{ gridTemplateColumns: gridTemplate(group.visible.map((_, i) => group.widths[i]), group.columns.length > group.visible.length) }}
      >
        {group.columns.length > group.visible.length && <span aria-hidden />}
        {group.visible.map((c) => (
          <span key={c} role="columnheader" className="truncate" title={columnLabel(c)}>
            {columnLabel(c)}
          </span>
        ))}
      </div>
    </div>
  );
}

/** `register_row` / `table_row`: a real table row from `row_cells`; wide registers expand to show every field. */
export function TableRowClause({
  clause,
  group,
  cells,
  notes,
  sentences,
  active,
  pulse,
  rowExpanded,
  onToggleRow,
  clearedOpen,
  onToggleCleared,
  onOpenFinding,
  edge,
}: Omit<FrameProps, "children" | "contentClass" | "flush"> & {
  group: TableGroup;
  cells: Record<string, string>;
  rowExpanded?: boolean;
  onToggleRow?: (id: string) => void;
  edge: Edge;
}) {
  const hs = highlightsFor(clause, notes);
  const wide = group.columns.length > group.visible.length;
  const shown = rowExpanded ? group.columns : group.visible;
  const last = edge === "last" || edge === "only";
  const cellNode = (key: string, clamp: boolean) => {
    const v = cells[key] ?? "";
    const off = cellOffset(clause, key, v);
    return (
      <span className={cn("min-w-0", v.length <= 18 ? "whitespace-nowrap" : "break-words", clamp && "line-clamp-2")}>
        {off !== null ? <Inline text={v} base={off} highlights={hs} /> : v || <span className="text-ink-4">—</span>}
      </span>
    );
  };
  return (
    <ClauseFrame
      clause={clause}
      notes={notes}
      sentences={sentences}
      active={active}
      pulse={pulse}
      clearedOpen={clearedOpen}
      onToggleCleared={onToggleCleared}
      onOpenFinding={onOpenFinding}
      flush
    >
      <div role="row" data-register-row="" className={cn("border-x border-b border-border bg-surface text-[13px] leading-[18px] text-ink", last && "rounded-b-[8px]")}>
        <div className="grid items-start gap-3 px-3 py-2" style={{ gridTemplateColumns: gridTemplate(group.visible.map((_, i) => group.widths[i]), wide) }}>
          {wide && (
            <button
              type="button"
              aria-expanded={!!rowExpanded}
              aria-label={rowExpanded ? "Hide all fields" : "Show all fields"}
              onClick={() => onToggleRow?.(clause.clause_id)}
              className="grid size-6 place-items-center rounded-[4px] text-ink-3 hover:bg-surface-muted hover:text-ink"
            >
              {rowExpanded ? <ChevronDown aria-hidden className="size-4" strokeWidth={1.5} /> : <ChevronRight aria-hidden className="size-4" strokeWidth={1.5} />}
            </button>
          )}
          {group.visible.map((c) => (
            <span key={c} role="cell" className="min-w-0">
              {cellNode(c, !rowExpanded)}
            </span>
          ))}
        </div>
        {wide && rowExpanded && (
          <dl className="grid grid-cols-[minmax(0,1fr)_minmax(0,2.2fr)] gap-x-4 gap-y-1.5 border-t border-border bg-surface-muted/50 px-3 py-2.5 pl-12">
            {shown
              .filter((c) => !group.visible.includes(c))
              .map((c) => (
                <React.Fragment key={c}>
                  <dt className="text-[12px] text-ink-3">{columnLabel(c)}</dt>
                  <dd className="min-w-0 break-words">{cellNode(c, false)}</dd>
                </React.Fragment>
              ))}
          </dl>
        )}
      </div>
    </ClauseFrame>
  );
}

/* ------------------------------------------------------------------ dispatcher */

/** One renderer per `unit_kind`; headings and table headers are separate items. */
export function ClauseRenderer({ item, notes, sentences, active, pulse, rowExpanded, onToggleRow, clearedOpen, onToggleCleared, onOpenFinding }: ClauseRendererProps) {
  switch (item.kind) {
    case "heading":
      return <HeadingRow level={item.level} text={item.text} anchors={item.anchors} />;
    case "table-head":
      return <TableHead group={item.group} />;
    case "table-row":
      return (
        <TableRowClause
          clause={item.clause}
          group={item.group}
          cells={item.cells}
          edge={item.edge}
          notes={notes}
          sentences={sentences}
          active={active}
          pulse={pulse}
          rowExpanded={rowExpanded}
          onToggleRow={onToggleRow}
          clearedOpen={clearedOpen}
          onToggleCleared={onToggleCleared}
          onOpenFinding={onOpenFinding}
        />
      );
    case "clause": {
      const p: ClauseProps = { clause: item.clause, edge: item.edge, notes, sentences, active, pulse, clearedOpen, onToggleCleared, onOpenFinding };
      switch (item.clause.unit_kind) {
        case "form_field":
          return <FormFieldClause {...p} />;
        case "tariff_subrule":
          return <TariffSubruleClause {...p} />;
        case "appendix":
          return <AppendixClause {...p} />;
        default:
          return <SectionClause {...p} />;
      }
    }
  }
}

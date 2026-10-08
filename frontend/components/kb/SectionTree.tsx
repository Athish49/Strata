"use client";
import * as React from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/common/EmptyState";
import { AppLink } from "@/lib/app-link";
import type { ChangeClass, CodeSection } from "@/lib/api/schemas";
import { formatCount } from "@/lib/format";
import { cn } from "@/lib/utils";
import { ClassTag, Pager, useKeyedPage } from "./bits";
import { sectionHref } from "./links";
import { buildTree, filterSections, paginate, type PartNode, type RuleNode, type TitleNode } from "./tree";

export type ChangedMap = Map<string, ChangeClass>;
const FLAT_PAGE = 50;

function changedKey(ss: string, citation: string) {
  return `${ss}|${citation}`;
}
export function makeChangedMap(changes: { source_system: string; citation: string; change_class: ChangeClass }[] | undefined): ChangedMap {
  const m: ChangedMap = new Map();
  for (const c of changes ?? []) m.set(changedKey(c.source_system, c.citation), c.change_class);
  return m;
}

/** Light list row: one section. No body text is ever rendered here. */
export function SectionRow({ section, changed }: { section: CodeSection; changed?: ChangeClass }) {
  return (
    <AppLink
      href={sectionHref(section.source_system, section.citation)}
      className="flex min-h-9 items-center gap-3 px-4 py-1.5 transition-colors duration-150 hover:bg-surface-muted"
    >
      <span className="w-[150px] shrink-0 truncate font-mono text-[12.5px] leading-[18px] text-ink" title={section.citation}>
        {section.citation}
      </span>
      <span className="min-w-0 flex-1 truncate text-[13px] text-ink-2" title={section.heading}>
        {section.heading || "Untitled section"}
      </span>
      {section.status === "repealed" && <Badge variant="tag">Repealed</Badge>}
      {changed && (
        <span className="flex shrink-0 items-center gap-1.5">
          <span className="text-[12px] text-ink-3">Changed in this run</span>
          <ClassTag cls={changed} />
        </span>
      )}
    </AppLink>
  );
}

function GroupRow({
  depth,
  open,
  onToggle,
  label,
  count,
  mono,
  band,
}: {
  depth: number;
  open: boolean;
  onToggle: () => void;
  label: string;
  count: number;
  mono?: boolean;
  band?: boolean;
}) {
  const Chev = open ? ChevronDown : ChevronRight;
  return (
    <button
      type="button"
      aria-expanded={open}
      onClick={onToggle}
      style={{ paddingLeft: 16 + depth * 20 }}
      className={cn(
        "flex h-10 w-full items-center gap-2 pr-4 text-left transition-colors duration-150 hover:bg-surface-muted",
        band && "bg-surface-muted",
      )}
    >
      <Chev className="size-4 shrink-0 text-ink-3" strokeWidth={1.5} />
      <span className={cn("text-[13px] font-medium text-ink", mono && "font-mono text-[12.5px]")}>{label}</span>
      <span className="text-[13px] text-ink-3">· {formatCount(count)}</span>
    </button>
  );
}

function RuleGroup({ rule, changed, depth }: { rule: RuleNode<CodeSection>; changed: ChangedMap; depth: number }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div>
      <GroupRow depth={depth} open={open} onToggle={() => setOpen((o) => !o)} label={rule.label} count={rule.sections.length} mono />
      {open && (
        <div style={{ paddingLeft: depth * 20 + 16 }} className="divide-y divide-border">
          {rule.sections.map((s) => (
            <SectionRow key={`${s.source_system}|${s.citation}`} section={s} changed={changed.get(changedKey(s.source_system, s.citation))} />
          ))}
        </div>
      )}
    </div>
  );
}

function PartGroup({ part, changed, depth }: { part: PartNode<CodeSection>; changed: ChangedMap; depth: number }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div>
      <GroupRow depth={depth} open={open} onToggle={() => setOpen((o) => !o)} label={part.label} count={part.count} />
      {open && part.rules.map((r) => <RuleGroup key={r.key} rule={r} changed={changed} depth={depth + 1} />)}
    </div>
  );
}

function TitleGroup({ title, changed }: { title: TitleNode<CodeSection>; changed: ChangedMap }) {
  const [open, setOpen] = React.useState(true);
  return (
    <div className="border-b border-border last:border-b-0">
      <GroupRow band depth={0} open={open} onToggle={() => setOpen((o) => !o)} label={title.label} count={title.count} />
      {open && title.parts.map((p) => <PartGroup key={p.key} part={p} changed={changed} depth={1} />)}
    </div>
  );
}

/**
 * Rules in force. Browsing is a collapsed Title > Part > Rule tree (sections only mount when their
 * rule is open, so a 1,600-section codebook stays a few dozen DOM nodes). A search query switches
 * to a flat, paginated result list.
 */
export function SectionTree({
  sections,
  query,
  includeRepealed,
  changed,
}: {
  sections: CodeSection[];
  query: string;
  includeRepealed: boolean;
  changed: ChangedMap;
}) {
  const [page, setPage] = useKeyedPage(`${query}|${includeRepealed}`);
  const filtered = React.useMemo(() => filterSections(sections, query, includeRepealed), [sections, query, includeRepealed]);
  const tree = React.useMemo(() => (query.trim() ? [] : buildTree(filtered)), [filtered, query]);

  if (filtered.length === 0) {
    return (
      <EmptyState
        title={query.trim() ? "No sections match your search" : "No sections to show"}
        description={
          query.trim()
            ? `Nothing in this codebook matches "${query.trim()}". Try a citation like 170 IAC 4-1 or a word from the heading.`
            : sections.length > 0
              ? "Every section here is repealed. Turn on “Show repealed” to see them."
              : "No section rows are available to browse for this agency yet."
        }
      />
    );
  }

  if (query.trim()) {
    const p = paginate(filtered, page, FLAT_PAGE);
    return (
      <div>
        <div className="divide-y divide-border">
          {p.items.map((s) => (
            <SectionRow key={`${s.source_system}|${s.citation}`} section={s} changed={changed.get(changedKey(s.source_system, s.citation))} />
          ))}
        </div>
        <Pager page={p.page} pages={p.pages} total={filtered.length} size={FLAT_PAGE} onPage={setPage} noun="sections" />
      </div>
    );
  }
  return (
    <div>
      {tree.map((t) => (
        <TitleGroup key={t.key} title={t} changed={changed} />
      ))}
    </div>
  );
}

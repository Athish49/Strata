import * as React from "react";
import { BookOpen, ChevronRight, FileText, GitBranch, Rows3, ScrollText, TextCursorInput, type LucideIcon } from "lucide-react";
import type { PathNode } from "@/lib/api/schemas";
import { AppLink } from "@/lib/app-link";
import { cn } from "@/lib/utils";

const KIND_LABEL: Record<PathNode["kind"], string> = {
  section: "Regulation section",
  rule: "Rule",
  register_row: "Register row",
  form_field: "Form field",
  tariff_rule: "Tariff rule",
  clause: "Clause",
};

const KIND_ICON: Record<PathNode["kind"], LucideIcon> = {
  section: ScrollText,
  rule: BookOpen,
  register_row: Rows3,
  form_field: TextCursorInput,
  tariff_rule: FileText,
  clause: FileText,
};

/** Where a trace node leads, or null when no route exists (e.g. a bare rule key). Run param is added by AppLink. */
export function defaultTraceHref(node: PathNode): string | null {
  switch (node.kind) {
    case "section": {
      const ss = /\bCFR\b/i.test(node.ref) ? "cfr" : "iac";
      return `/app/regulations/sections/${ss}/${encodeURIComponent(node.ref)}`;
    }
    case "register_row":
    case "form_field":
    case "tariff_rule":
    case "clause": {
      const i = node.ref.indexOf(":");
      if (i <= 0) return null;
      return `/app/documents/${encodeURIComponent(node.ref.slice(0, i))}?clause=${encodeURIComponent(node.ref)}`;
    }
    default:
      return null;
  }
}

export interface TraceChainProps {
  /** `path_detail` of a candidate or finding, in order. */
  nodes: PathNode[];
  /** Resolve a node to a route; return null for none. Defaults to {@link defaultTraceHref}. */
  resolveHref?: (node: PathNode, index: number) => string | null;
  /** When the finding was propagated from another finding, a link/label for that finding. */
  propagatedFrom?: { label: string; href?: string; onOpen?: () => void } | null;
  /** Show the "Fix once, fix everywhere." caption (default true). */
  showCaption?: boolean;
  className?: string;
}

/** Horizontal chain of small cards built from path_detail; each node links via AppLink where a route exists. */
export function TraceChain({ nodes, resolveHref = defaultTraceHref, propagatedFrom, showCaption = true, className }: TraceChainProps) {
  return (
    <div className={cn("space-y-2", className)}>
      {nodes.length > 0 && (
        <ol aria-label="Why this clause was found" className="flex flex-wrap items-stretch gap-y-2">
          {nodes.map((node, i) => {
            const Icon = KIND_ICON[node.kind];
            const href = resolveHref(node, i);
            const last = i === nodes.length - 1;
            const body = (
              <>
                <span className="flex items-center gap-1 text-[11px] leading-4 text-ink-3">
                  <Icon aria-hidden className="size-3" strokeWidth={1.5} />
                  {KIND_LABEL[node.kind]}
                </span>
                <span className="block max-w-[200px] truncate font-mono text-[12.5px] leading-[18px] text-ink" title={node.label}>
                  {node.label}
                </span>
              </>
            );
            const card = cn(
              "block rounded-[8px] border bg-surface px-2.5 py-1.5",
              last ? "border-ink" : "border-border-strong",
              href && "transition-colors hover:bg-surface-muted",
            );
            return (
              <li key={`${node.kind}-${node.ref}-${i}`} className="flex items-center" aria-current={last ? "step" : undefined}>
                {href ? (
                  <AppLink href={href} className={card}>
                    {body}
                  </AppLink>
                ) : (
                  <span className={card}>{body}</span>
                )}
                {!last && <ChevronRight aria-hidden className="mx-1 size-4 shrink-0 text-ink-4" strokeWidth={1.5} />}
              </li>
            );
          })}
        </ol>
      )}
      {propagatedFrom && (
        <p className="flex items-center gap-1.5 text-[13px] text-ink-2">
          <GitBranch aria-hidden className="size-3.5 text-ink-3" strokeWidth={1.5} />
          Propagated from{" "}
          {propagatedFrom.href ? (
            <AppLink href={propagatedFrom.href} className="font-medium text-ink underline-offset-2 hover:underline">
              {propagatedFrom.label}
            </AppLink>
          ) : propagatedFrom.onOpen ? (
            <button type="button" onClick={propagatedFrom.onOpen} className="font-medium text-ink underline-offset-2 hover:underline">
              {propagatedFrom.label}
            </button>
          ) : (
            <span className="font-medium text-ink">{propagatedFrom.label}</span>
          )}
        </p>
      )}
      {showCaption && <p className="text-[12px] text-ink-3">Fix once, fix everywhere.</p>}
    </div>
  );
}

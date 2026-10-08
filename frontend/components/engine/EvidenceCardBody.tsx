"use client";
import * as React from "react";
import { ArrowRight, Columns2, Rows2, ExternalLink } from "lucide-react";
import type { Clause, Finding, UnitKind } from "@/lib/api/schemas";
import { AppLink } from "@/lib/app-link";
import { useChange, useClauses, useDocument, useFinding, useFindings, useSubmitReview } from "@/lib/api/queries";
import { Button } from "@/components/ui/button";
import { DocChip } from "@/components/common/DocChip";
import { ErrorState } from "@/components/common/ErrorState";
import { FutureCue } from "@/components/common/FutureCue";
import { formatDate, pluralize } from "@/lib/format";
import { matchPathWords, severityLabel } from "@/lib/labels";
import { clauseLabel } from "@/lib/sentences";
import { findingHeadline, cleanRationale, hasLongRequiredChange } from "./findingLine";
import { cn } from "@/lib/utils";
import { DiffView } from "./DiffView";
import { QuoteHighlight, type QuoteInput } from "./QuoteHighlight";
import { RouteChips } from "./RouteChips";
import { SeverityMark } from "./SeverityMark";
import { TimelineStrip } from "./TimelineStrip";
import { TraceChain } from "./TraceChain";
import { TrustBadges } from "./TrustBadges";
import { VerdictPill } from "./VerdictPill";
import type { TokenKey } from "@/lib/verdict-tokens";

export interface EvidenceCardBodyProps {
  /** Finding to show (a URL id; never displayed). */
  findingId: string;
  /** "drawer": sticky verdict header + "Open full page" link. "page": plain flow. Default "page". */
  variant?: "page" | "drawer";
  /** Open a sibling / parent finding. Drawer: set `?finding=`. Omit on the full page to link to /app/findings/<id>. */
  onOpenFinding?: (findingId: string) => void;
  className?: string;
}

const NODE_UNIT: Record<string, UnitKind> = { form_field: "form_field", register_row: "register_row", tariff_rule: "tariff_subrule" };

function Section({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("border-t border-border px-6 py-5", className)}>
      <h3 className="mb-3 text-[12px] font-medium leading-4 text-ink-3">{title}</h3>
      {children}
    </section>
  );
}

interface EvidencePaneProps {
  id: string;
  title: string;
  meta?: React.ReactNode;
  text: string;
  quote: QuoteInput;
  token?: TokenKey;
}

function EvidencePane({ id, title, meta, text, quote, token }: EvidencePaneProps) {
  const ref = React.useRef<HTMLDivElement>(null);
  const quoteText = typeof quote === "string" ? quote : (quote?.text ?? "");
  const body = text || quoteText;
  const noQuote = quoteText === "";
  React.useEffect(() => {
    const box = ref.current;
    const mark = box?.querySelector<HTMLElement>("mark");
    if (box && mark) box.scrollTop = Math.max(0, mark.offsetTop - 48);
  }, [body, quoteText]);
  return (
    <div className="min-w-0 rounded-[8px] border border-border">
      <div className="flex items-baseline justify-between gap-2 border-b border-border bg-surface-muted px-3 py-1.5">
        <span className="text-[12px] font-medium text-ink-2">{title}</span>
        <span className="min-w-0 truncate text-[12px] text-ink-3">{meta}</span>
      </div>
      <div ref={ref} className="relative max-h-56 overflow-auto px-3 py-2.5 font-serif text-[15px] leading-6 text-ink" tabIndex={0} role="region" aria-label={title}>
        {body ? (
          <QuoteHighlight text={body} quote={text ? quote : quoteText} token={token} describedBy={id} />
        ) : (
          <span className="font-sans text-[13px] text-ink-3">No text is available for this pane.</span>
        )}
      </div>
      <p id={id} className="border-t border-border px-3 py-1 text-[11px] leading-4 text-ink-3">
        {noQuote ? "No quote was extracted for this pane." : "Highlighted: the words this finding rests on."}
      </p>
    </div>
  );
}

function ReviewPanel({ finding }: { finding: Finding }) {
  const submit = useSubmitReview();
  const [rejecting, setRejecting] = React.useState(false);
  const [note, setNote] = React.useState("");
  const [saved, setSaved] = React.useState<string | null>(null);
  const noteId = React.useId();
  const noteOk = note.trim().length > 0;

  const send = (decision: "accept" | "reject") => {
    setSaved(null);
    submit.mutate(
      { findingId: finding.finding_id, decision, note: decision === "reject" ? note.trim() : undefined },
      {
        onSuccess: () => {
          setSaved(decision === "accept" ? "Accepted. Review saved." : "Rejected. Review saved.");
          setRejecting(false);
          setNote("");
        },
      },
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="primary" size="sm" disabled={submit.isPending} onClick={() => send("accept")}>
          Accept
        </Button>
        <Button variant="secondary" size="sm" aria-expanded={rejecting} disabled={submit.isPending} onClick={() => setRejecting((r) => !r)}>
          Reject
        </Button>
        <FutureCue id="create-task" variant="button" />
        <FutureCue id="request-signoff" variant="button" />
      </div>
      {rejecting && (
        <div className="space-y-2 rounded-[8px] border border-border p-3">
          <label htmlFor={noteId} className="block text-[13px] font-medium text-ink">
            Why is this finding rejected? <span className="font-normal text-ink-3">(required)</span>
          </label>
          <textarea
            id={noteId}
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={3}
            className="w-full rounded-[8px] border border-border-strong bg-surface px-3 py-2 text-[14px] text-ink placeholder:text-ink-4"
            placeholder="e.g. The clause was already updated in version 4."
          />
          {!noteOk && <p className="text-[12px] text-ink-3">A note is required to reject a finding.</p>}
          <div className="flex gap-2">
            <Button variant="primary" size="sm" disabled={!noteOk || submit.isPending} onClick={() => send("reject")}>
              Submit rejection
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setRejecting(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      <div role="status" aria-live="polite" className="text-[13px] text-green">
        {saved}
      </div>
      {submit.isError && <p className="text-[13px] text-red">The review could not be saved. Try again.</p>}
      {finding.reviews.length > 0 && (
        <div data-review-state={finding.reviews[finding.reviews.length - 1].decision}>
          <p className="mb-2 text-[13px] font-medium text-ink">
            {finding.reviews[finding.reviews.length - 1].decision === "accept" ? "Accepted" : "Rejected"}
            {finding.reviews[finding.reviews.length - 1].by ? ` by ${finding.reviews[finding.reviews.length - 1].by}` : ""} on{" "}
            {formatDate(finding.reviews[finding.reviews.length - 1].at)}
          </p>
          <h4 className="mb-1.5 text-[12px] font-medium text-ink-3">Review history</h4>
          <ul className="divide-y divide-border rounded-[8px] border border-border">
            {finding.reviews.map((r, i) => (
              <li key={`${r.at}-${i}`} className="px-3 py-2 text-[13px]">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-ink">{r.decision === "accept" ? "Accepted" : "Rejected"}{r.by ? ` by ${r.by}` : ""}</span>
                  <span className="text-ink-3">{formatDate(r.at)}</span>
                </div>
                {r.note ? <p className="mt-0.5 text-ink-2">{r.note}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function CardSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading evidence card" className="space-y-4 p-6">
      <div className="skeleton h-7 w-4/5" />
      <div className="skeleton h-5 w-1/2" />
      <div className="skeleton h-40 w-full" />
      <div className="skeleton h-16 w-full" />
    </div>
  );
}

/**
 * The §9.5 evidence card body: verdict sentence, trust badges, three-pane evidence, required change, trace chain,
 * sibling findings, stale-at-approval timeline, routing and review. Fetches everything from `findingId` via the
 * data hooks; shared by the drawer (`variant="drawer"`) and the full page.
 */
export function EvidenceCardBody({ findingId, variant = "page", onOpenFinding, className }: EvidenceCardBodyProps) {
  const fq = useFinding(findingId);
  const finding = fq.data ?? null;
  const changeQ = useChange(finding?.run_id, finding?.change_id);
  const clausesQ = useClauses(finding?.doc_id);
  const docQ = useDocument(finding?.doc_id);
  const siblingsQ = useFindings(finding?.run_id, finding ? { change_id: finding.change_id } : undefined);
  const [merged, setMerged] = React.useState(false);
  const uid = React.useId();

  if (fq.isLoading) return <CardSkeleton />;
  if (fq.isError) return <ErrorState message="The evidence card could not be loaded." source="Findings" onRetry={() => void fq.refetch()} />;
  if (!finding) return <ErrorState message="This finding could not be found." source="Findings" />;

  const change = changeQ.data ?? null;
  const clause: Clause | undefined = clausesQ.data?.find((c) => c.clause_id === finding.clause_id);
  const doc = docQ.data ?? null;
  const lastKind = finding.path_detail[finding.path_detail.length - 1]?.kind ?? "clause";
  const label = clauseLabel({
    clause_id: finding.clause_id,
    doc_id: finding.doc_id,
    unit_kind: clause?.unit_kind ?? NODE_UNIT[lastKind] ?? "section",
    heading_path: clause?.heading_path,
  });
  const segs = findingHeadline(finding, label, change ?? undefined);
  const siblings = (siblingsQ.data ?? []).filter((f) => f.finding_id !== finding.finding_id);
  const parent = finding.propagated_from ? (siblingsQ.data ?? []).find((f) => f.finding_id === finding.propagated_from) : undefined;
  const { from_text, to_text } = finding.required_change;
  const hasRequired = !!(from_text || to_text);
  const openSibling = (id: string) => onOpenFinding?.(id);
  const findingHref = (id: string) => `/app/findings/${encodeURIComponent(id)}`;
  const pathCtx = { ruleKey: change?.rule_key, ref: finding.path_detail.find((n) => n.kind !== "section")?.label, oldValue: from_text || undefined };
  const drawer = variant === "drawer";

  return (
    <article aria-label="Evidence card" data-finding={finding.finding_id} className={cn("bg-surface", className)}>
      <header className={cn("space-y-3 px-6 pb-5 pt-6", drawer && "sticky top-0 z-10 border-b border-border bg-surface pr-24")}>
        <p className="font-serif text-[22px] font-normal leading-[30px] text-ink">
          {segs.map((s, i) => (s.strong ? <strong key={i} className="font-semibold">{s.text}</strong> : <React.Fragment key={i}>{s.text}</React.Fragment>))}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <VerdictPill verdict={finding.verdict} />
          <SeverityMark severity={finding.severity} />
          <TrustBadges quotesVerified={finding.quotes_verified} decidedBy={finding.decided_by} confidence={finding.confidence} />
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[13px] text-ink-2">
          <DocChip docId={finding.doc_id} title={doc?.title} href={`/app/documents/${encodeURIComponent(finding.doc_id)}?clause=${encodeURIComponent(finding.clause_id)}`} />
          <span className="font-mono text-[12.5px]">{finding.clause_id}</span>
          <span className="font-mono text-[12.5px]">{finding.citation}</span>
          {drawer && (
            <AppLink href={findingHref(finding.finding_id)} className="ml-auto inline-flex items-center gap-1 text-ink-3 hover:text-ink">
              <ExternalLink aria-hidden className="size-3.5" strokeWidth={1.5} />
              Open full page
            </AppLink>
          )}
        </div>
        {finding.rationale.trim() && <p className="text-[14px] leading-5 text-ink-2">{cleanRationale(finding.rationale)}</p>}
      </header>

      <Section title="Evidence">
        <div className="mb-3 flex items-center justify-between gap-2">
          <p className="text-[13px] text-ink-3">The old rule, the new rule and the clause, with the matching words highlighted.</p>
          <Button variant="ghost" size="sm" aria-pressed={merged} onClick={() => setMerged((m) => !m)} className="shrink-0">
            {merged ? <Columns2 aria-hidden /> : <Rows2 aria-hidden />}
            {merged ? "Show separate panes" : "Merge into redline"}
          </Button>
        </div>
        <div className="space-y-3">
          {merged && change && change.diff_segments.length > 0 ? (
            <DiffView segments={change.diff_segments} maxHeightClass="max-h-64" />
          ) : (
            <>
              <EvidencePane id={`${uid}-s1`} title="Old rule (S1)" meta={change ? formatDate(change.s1_snapshot) : undefined} text={change?.s1_text ?? ""} quote={finding.quotes.s1} />
              <EvidencePane id={`${uid}-s2`} title="New rule (S2)" meta={change ? formatDate(change.s2_snapshot) : undefined} text={change?.s2_text ?? ""} quote={finding.quotes.s2} />
            </>
          )}
          <EvidencePane
            id={`${uid}-clause`}
            title="Clause"
            meta={<span className="font-mono">{finding.clause_id}</span>}
            text={clause?.text_raw ?? ""}
            quote={finding.quotes.clause}
            token={finding.verdict}
          />
        </div>
      </Section>

      <Section title="Required change">
        {hasRequired ? (
          hasLongRequiredChange(finding) ? (
            <div className="space-y-2">
              {from_text ? (
                <div>
                  <p className="mb-1 text-[12px] text-ink-3">Current wording</p>
                  <p className="rounded-[6px] bg-red-soft px-3 py-2 text-[13px] leading-5 text-red line-through">{from_text}</p>
                </div>
              ) : null}
              {to_text ? (
                <div>
                  <p className="mb-1 text-[12px] text-ink-3">Suggested wording</p>
                  <p className="rounded-[6px] bg-green-soft px-3 py-2 text-[13px] leading-5 text-green">{to_text}</p>
                </div>
              ) : null}
              <span className="text-[12px] text-ink-3">Suggested update — not applied</span>
            </div>
          ) : (
            <div className="flex flex-wrap items-center gap-2">
              {from_text ? <span className="rounded-[6px] bg-red-soft px-2 py-0.5 text-[13px] text-red line-through">{from_text}</span> : null}
              {from_text && to_text ? <ArrowRight aria-label="should become" className="size-4 text-ink-3" strokeWidth={1.5} /> : null}
              {to_text ? <span className="rounded-[6px] bg-green-soft px-2 py-0.5 text-[13px] text-green underline">{to_text}</span> : null}
              <span className="text-[12px] text-ink-3">Suggested update — not applied</span>
            </div>
          )
        ) : (
          <p className="text-[13px] text-ink-2">No specific replacement wording was proposed. Suggested update — not applied.</p>
        )}
        <div className="mt-2">
          <FutureCue id="draft-rewrite" variant="inline-add" />
        </div>
      </Section>

      <Section title="Why this clause was found">
        <p className="mb-3 text-[13px] text-ink-2">{matchPathWords(finding.match_path, pathCtx)}</p>
        <TraceChain
          nodes={finding.path_detail}
          propagatedFrom={
            finding.propagated_from
              ? {
                  label: parent ? `${parent.clause_id} (${parent.doc_id})` : "another finding",
                  ...(onOpenFinding ? { onOpen: () => openSibling(finding.propagated_from as string) } : { href: findingHref(finding.propagated_from) }),
                }
              : null
          }
        />
      </Section>

      {siblings.length > 0 && (
        <Section title={`Also affected by this change (${siblings.length})`}>
          <ul className="divide-y divide-border rounded-[8px] border border-border">
            {siblings.slice(0, 10).map((s) => {
              const inner = (
                <>
                  <VerdictPill verdict={s.verdict} size="sm" />
                  <span className="min-w-0 flex-1 truncate font-mono text-[12.5px]">{s.clause_id}</span>
                  <span className="shrink-0 font-mono text-[12px] text-ink-3">{s.doc_id}</span>
                </>
              );
              const cls = "flex h-9 w-full items-center gap-3 px-3 text-left hover:bg-surface-muted";
              return (
                <li key={s.finding_id}>
                  {onOpenFinding ? (
                    <button type="button" className={cls} onClick={() => openSibling(s.finding_id)}>
                      {inner}
                    </button>
                  ) : (
                    <AppLink href={findingHref(s.finding_id)} className={cls}>
                      {inner}
                    </AppLink>
                  )}
                </li>
              );
            })}
          </ul>
          {siblings.length > 10 && <p className="mt-1.5 text-[12px] text-ink-3">and {pluralize(siblings.length - 10, "more finding")}.</p>}
        </Section>
      )}

      {finding.stale_at_approval && (
        <Section title="Timeline">
          <TimelineStrip
            points={[
              { key: "rule", label: "Rule published", date: finding.rule_published_date },
              { key: "approved", label: "Document approved", date: finding.doc_approved_date },
            ]}
            caption={`This document was approved on ${formatDate(finding.doc_approved_date)}, after the rule change was published on ${formatDate(finding.rule_published_date)}.`}
          />
        </Section>
      )}

      <Section title="Routing and review">
        <div className="space-y-5">
          <RouteChips route={finding.route} twoSignature={doc?.two_signature} />
          <ReviewPanel finding={finding} />
          <p className="sr-only">{severityLabel(finding.severity)} severity finding</p>
        </div>
      </Section>
    </article>
  );
}

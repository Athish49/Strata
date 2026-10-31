"use client";
// Version history + approval panel for one company document (task 8.3).
import * as React from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronDown } from "lucide-react";
import type { ApprovalStep, DocumentMeta, DocumentRole, DocumentVersion, IngestJobState, OrgPerson } from "@/lib/api/schemas";
import { canApproveVersion, isTerminalJobState } from "@/lib/api/schemas";
import {
  useApprovalRequest,
  useAssignDocumentRole,
  useCancelApprovalRequest,
  useDecideApprovalStep,
  useDocument,
  useDocumentRoles,
  useDocumentVersions,
  useIngestJob,
  useOrgPeople,
  useRetryIngestJob,
} from "@/lib/api/queries";
import { useActingPerson } from "@/lib/actor";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import {
  DOCUMENT_ROLES,
  JOB_STATE_LABEL,
  JOB_STATE_TONE,
  ROLE_LABEL,
  VERSION_STATUS_LABEL,
  VERSION_STATUS_TONE,
  activePeople,
  errorMessage,
  invalidateEngineReader,
  roleHolders,
  roleLabel,
  sortNewestFirst,
  versionTag,
  type RoleHolder,
} from "./logic";

export interface VersionHistoryPanelProps {
  docId: string;
  /** The document as the page already has it (used for legacy role holders until the fresh record loads). */
  doc?: DocumentMeta | null;
  className?: string;
}

type Announce = (message: string) => void;
type NameOf = (personId: string | null | undefined) => string;

interface PanelCtx {
  docId: string;
  actor: string | null;
  holders: Record<DocumentRole, RoleHolder[]>;
  nameOf: NameOf;
  announce: Announce;
  /** Preselect a role in the "Assign role" form and move focus there. */
  requestAssign: (role: DocumentRole) => void;
}

const SELECT_CLASS =
  "h-8 w-full cursor-pointer appearance-none rounded-[8px] border border-border-strong bg-surface pl-3 pr-8 text-[14px] text-ink focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-default disabled:text-ink-4";

function NativeSelect({ className, children, ...props }: React.ComponentProps<"select">) {
  return (
    <span className={cn("relative inline-flex h-8 w-full items-center", className)}>
      <select className={SELECT_CLASS} {...props}>
        {children}
      </select>
      <ChevronDown aria-hidden className="pointer-events-none absolute right-2.5 size-4 text-ink-3" strokeWidth={1.5} />
    </span>
  );
}

function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p role="alert" className="mt-2 rounded-[8px] bg-red-soft px-3 py-2 text-[13px] leading-5 text-red">
      {message}
    </p>
  );
}

/** "Acting as" is required for every write; task 8.4 adds the shell-wide selector. */
function ActorPrompt({ people, onChoose }: { people: OrgPerson[]; onChoose: (id: string) => void }) {
  const id = React.useId();
  return (
    <section aria-labelledby={`${id}-t`} data-actor-prompt="" className="mb-5 rounded-[10px] border border-border bg-amber-soft px-4 py-3">
      <h3 id={`${id}-t`} className="text-[14px] font-medium text-ink">
        Choose who you are acting as
      </h3>
      <p className="mt-0.5 text-[13px] leading-5 text-ink-2">Approving, rejecting, cancelling and assigning roles are recorded against a person.</p>
      <label htmlFor={`${id}-s`} className="sr-only">
        Act as
      </label>
      <NativeSelect id={`${id}-s`} className="mt-2 max-w-[320px]" defaultValue="" onChange={(e) => e.target.value && onChoose(e.target.value)}>
        <option value="">Select a person…</option>
        {people.map((p) => (
          <option key={p.person_id} value={p.person_id}>
            {p.name}
            {p.title ? ` · ${p.title}` : ""}
          </option>
        ))}
      </NativeSelect>
    </section>
  );
}

function decisionBadge(step: ApprovalStep) {
  if (step.decision === "approved") return <Badge variant="green">Approved</Badge>;
  if (step.decision === "rejected") return <Badge variant="red">Rejected</Badge>;
  return <Badge variant="neutral">Pending</Badge>;
}

const REQUEST_STATE_LABEL = { open: "Open", approved: "Approved", rejected: "Rejected", cancelled: "Cancelled" } as const;

function ApprovalProgress({
  requestId,
  version,
  canApprove,
  ctx,
}: {
  requestId: string;
  version: DocumentVersion;
  canApprove: boolean;
  ctx: PanelCtx;
}) {
  const qc = useQueryClient();
  const reqQ = useApprovalRequest(requestId);
  const decide = useDecideApprovalStep();
  const cancel = useCancelApprovalRequest();
  const [rejecting, setRejecting] = React.useState(false);
  const [note, setNote] = React.useState("");
  const [confirmCancel, setConfirmCancel] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const uid = React.useId();
  const tag = versionTag(version);

  const req = reqQ.data;
  if (reqQ.isLoading) return <Skeleton className="mt-3 h-16 w-full" />;
  if (!req) {
    return <p className="mt-3 text-[13px] text-ink-3">{reqQ.isError ? "The approval request could not be loaded." : "The approval request was not found."}</p>;
  }

  const approvedCount = req.steps.filter((s) => s.decision === "approved").length;
  const next = req.state === "open" ? req.steps.find((s) => s.decision === null) : undefined;
  const nextRole = next?.required_role as DocumentRole | undefined;
  const nobodyCanSign = !!next && !next.assignee_person_id && !!nextRole && (ctx.holders[nextRole]?.length ?? 0) === 0;
  const busy = decide.isPending || cancel.isPending;
  const noActor = !ctx.actor;
  const approveReasonId = `${uid}-approve-why`;
  const approveReason = noActor
    ? "Choose who you are acting as to sign."
    : !canApprove
      ? "Approval opens once this version's ingest has succeeded."
      : null;

  const onApprove = async () => {
    if (!next || !ctx.actor) return;
    setError(null);
    try {
      const r = await decide.mutateAsync({ requestId, stepNo: next.step_no, decision: "approved", actingPersonId: ctx.actor });
      if (r.request_state === "approved") {
        void invalidateEngineReader(qc, ctx.docId);
        ctx.announce(`${tag} approved. It is now the current version.`);
      } else {
        ctx.announce(`Step ${next.step_no} approved for ${tag}.`);
      }
    } catch (e) {
      setError(errorMessage(e, "approve", next.required_role));
    }
  };

  const onReject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!next || !ctx.actor || !note.trim()) return;
    setError(null);
    try {
      await decide.mutateAsync({ requestId, stepNo: next.step_no, decision: "rejected", note: note.trim(), actingPersonId: ctx.actor });
      setRejecting(false);
      setNote("");
      ctx.announce(`Step ${next.step_no} rejected for ${tag}.`);
    } catch (err) {
      setError(errorMessage(err, "reject", next.required_role));
    }
  };

  const onCancel = async () => {
    if (!ctx.actor) return;
    setError(null);
    try {
      await cancel.mutateAsync({ requestId, actingPersonId: ctx.actor });
      setConfirmCancel(false);
      void invalidateEngineReader(qc, ctx.docId);
      ctx.announce(`Approval request cancelled. ${tag} is retired.`);
    } catch (err) {
      setError(errorMessage(err, "cancel"));
    }
  };

  return (
    <section aria-label={`Approval for ${tag}`} data-approval={req.state} className="mt-3 rounded-[10px] border border-border bg-surface-muted/50 px-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-[13px] font-medium text-ink">
          Approval · {REQUEST_STATE_LABEL[req.state]}
        </h4>
        <span className="text-[12px] text-ink-3">
          {approvedCount} of {req.steps.length} steps approved
        </span>
      </div>
      {req.steps.length === 0 ? (
        <p className="mt-1 text-[13px] text-ink-3">No sign-off steps: approved automatically once ingest succeeds.</p>
      ) : (
        <ol className="mt-2 space-y-2" aria-label="Approval steps">
          {req.steps.map((s) => (
            <li key={s.step_no} data-step={s.step_no} className="rounded-[8px] border border-border bg-surface px-3 py-2">
              <div className="flex flex-wrap items-center gap-2 text-[13px]">
                <span className="font-medium text-ink">Step {s.step_no}</span>
                <span className="text-ink-2">{roleLabel(s.required_role)}</span>
                <span className="text-ink-3">
                  {s.assignee_person_id ? ctx.nameOf(s.assignee_person_id) : `Any ${roleLabel(s.required_role).toLowerCase()}`}
                </span>
                <span className="ml-auto">{decisionBadge(s)}</span>
              </div>
              {(s.decided_at || s.note) && (
                <p className="mt-1 text-[12.5px] leading-5 text-ink-3">
                  {s.decided_at && <span>Decided {formatDate(s.decided_at)}</span>}
                  {s.decided_at && s.note && " · "}
                  {s.note && <span className="text-ink-2">“{s.note}”</span>}
                </p>
              )}
            </li>
          ))}
        </ol>
      )}

      {next && nobodyCanSign && nextRole && (
        <div data-no-role="" className="mt-3 rounded-[8px] border border-border bg-amber-soft px-3 py-2 text-[13px] leading-5 text-ink">
          <p>
            Nobody holds the {roleLabel(nextRole).toLowerCase()} role on this document yet, so step {next.step_no} can&apos;t be signed. Assign a{" "}
            {roleLabel(nextRole).toLowerCase()} first.
          </p>
          <Button variant="secondary" size="sm" className="mt-2" onClick={() => ctx.requestAssign(nextRole)}>
            Assign a {roleLabel(nextRole).toLowerCase()}
          </Button>
        </div>
      )}

      {next && (
        <div className="mt-3">
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="primary"
              size="sm"
              disabled={!!approveReason || busy}
              aria-describedby={approveReason ? approveReasonId : undefined}
              onClick={onApprove}
            >
              Approve step {next.step_no}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={noActor || busy}
              aria-expanded={rejecting}
              aria-controls={`${uid}-reject`}
              onClick={() => setRejecting((o) => !o)}
            >
              Reject…
            </Button>
            {!confirmCancel ? (
              <Button variant="ghost" size="sm" disabled={noActor || busy} onClick={() => setConfirmCancel(true)}>
                Cancel request
              </Button>
            ) : null}
          </div>
          {approveReason && (
            <p id={approveReasonId} className="mt-1.5 text-[12.5px] text-ink-3">
              {approveReason}
            </p>
          )}
          {rejecting && (
            <form id={`${uid}-reject`} onSubmit={onReject} className="mt-3 space-y-2">
              <label htmlFor={`${uid}-note`} className="block text-[13px] font-medium text-ink">
                Reason for rejecting (required)
              </label>
              <textarea
                id={`${uid}-note`}
                value={note}
                onChange={(e) => setNote(e.target.value)}
                required
                rows={3}
                className="w-full rounded-[8px] border border-border-strong bg-surface px-3 py-2 text-[14px] text-ink placeholder:text-ink-3"
                placeholder="What needs to change before this can be approved?"
              />
              <div className="flex gap-2">
                <Button type="submit" variant="primary" size="sm" disabled={!note.trim() || busy}>
                  Reject step {next.step_no}
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setRejecting(false)}>
                  Keep reviewing
                </Button>
              </div>
            </form>
          )}
          {confirmCancel && (
            <div role="group" aria-label="Confirm cancel" className="mt-3 rounded-[8px] border border-border bg-surface px-3 py-2">
              <p className="text-[13px] leading-5 text-ink">Cancel this approval request? {tag} will be retired and can&apos;t be approved later.</p>
              <div className="mt-2 flex gap-2">
                <Button variant="primary" size="sm" disabled={busy} onClick={onCancel}>
                  Yes, cancel request
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setConfirmCancel(false)}>
                  Keep request
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
      <ErrorNote message={error} />
    </section>
  );
}

/** Polls one ingest attempt while it is in flight and reports its state up (renders nothing). */
function JobWatcher({ watchKey, jobId, onState }: { watchKey: string; jobId: string; onState: (key: string, s: IngestJobState) => void }) {
  const live = useIngestJob(jobId);
  const state = live.data?.job.job_id === jobId ? live.data.job.state : undefined;
  React.useEffect(() => {
    if (state) onState(watchKey, state);
  }, [state, watchKey, onState]);
  return null;
}

function VersionCard({
  version: v,
  isCurrent,
  tagById,
  ctx,
}: {
  version: DocumentVersion;
  isCurrent: boolean;
  tagById: ReadonlyMap<string, string>;
  ctx: PanelCtx;
}) {
  const job = v.ingest_job ?? null;
  // Each retry is a new attempt on the same job id; a fresh watcher per attempt makes
  // useIngestJob invalidate the document/clauses again when that attempt finishes.
  const [attempt, setAttempt] = React.useState(0);
  const watchKey = job ? `${job.job_id}#${attempt}` : "";
  const [liveState, setLiveState] = React.useState<{ key: string; state: IngestJobState } | null>(null);
  const onLiveState = React.useCallback((key: string, state: IngestJobState) => setLiveState({ key, state }), []);
  // A terminal state in the list is authoritative; while in flight, the poller is fresher.
  const jobState = !job ? null : isTerminalJobState(job.state) ? job.state : liveState?.key === watchKey ? liveState.state : job.state;
  const canApprove = canApproveVersion({ ingest_job: job && jobState ? { job_id: job.job_id, state: jobState } : null });
  const retry = useRetryIngestJob();
  const [error, setError] = React.useState<string | null>(null);
  const tag = versionTag(v);
  const supersedes = v.supersedes_version_id ? (tagById.get(v.supersedes_version_id) ?? "an earlier version") : null;
  const supersededBy = v.superseded_by ? (tagById.get(v.superseded_by) ?? "a later version") : null;

  const onRetry = async () => {
    if (!job) return;
    setError(null);
    try {
      await retry.mutateAsync(job.job_id);
      setAttempt((n) => n + 1);
      ctx.announce(`Ingest retry queued for ${tag}.`);
    } catch (e) {
      setError(errorMessage(e, "retry"));
    }
  };

  const facts: [string, React.ReactNode][] = [];
  facts.push(["Uploaded", formatDate(v.created_at)]);
  if (v.effective_date) facts.push(["Effective", formatDate(v.effective_date)]);
  if (v.approved_date) facts.push(["Approved", formatDate(v.approved_date)]);
  facts.push(["Author", v.created_by_person_id ? ctx.nameOf(v.created_by_person_id) : "—"]);
  if (supersedes) facts.push(["Supersedes", supersedes]);
  if (supersededBy) facts.push(["Superseded by", supersededBy]);

  return (
    <li
      data-version={v.version_id}
      data-version-no={v.version_no ?? ""}
      data-current={isCurrent ? "true" : undefined}
      aria-current={isCurrent ? "true" : undefined}
      className={cn("rounded-[12px] border bg-surface px-4 py-3", isCurrent ? "border-ink/40" : "border-border")}
    >
      {job && !isTerminalJobState(job.state) && <JobWatcher key={watchKey} watchKey={watchKey} jobId={job.job_id} onState={onLiveState} />}
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-[15px] font-medium text-ink">
          {tag}
          {v.version && v.version_no != null && <span className="ml-1.5 font-normal text-ink-3">· Version {v.version}</span>}
        </h3>
        <Badge variant={VERSION_STATUS_TONE[v.status]} data-status={v.status}>
          {VERSION_STATUS_LABEL[v.status]}
        </Badge>
        {isCurrent && (
          <Badge variant="outline" data-current-marker="" className="border-ink text-ink">
            Current
          </Badge>
        )}
        {jobState && (
          <Badge variant={JOB_STATE_TONE[jobState]} data-job-state={jobState} className="ml-auto">
            {JOB_STATE_LABEL[jobState]}
          </Badge>
        )}
      </div>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-0.5 text-[13px] leading-5">
        {facts.map(([k, val]) => (
          <React.Fragment key={k}>
            <dt className="text-ink-3">{k}</dt>
            <dd className="text-ink-2">{val}</dd>
          </React.Fragment>
        ))}
      </dl>
      {v.change_reason && <p className="mt-2 text-[13px] leading-5 text-ink-2">“{v.change_reason}”</p>}
      {jobState === "failed" && job && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-[13px] text-ink-2">Strata couldn&apos;t process this version.</span>
          <Button variant="secondary" size="sm" disabled={retry.isPending || v.status === "retired"} onClick={onRetry}>
            Retry ingest
          </Button>
        </div>
      )}
      <ErrorNote message={error} />
      {v.approval && <ApprovalProgress requestId={v.approval.request_id} version={v} canApprove={canApprove} ctx={ctx} />}
    </li>
  );
}

function RolesSection({
  ctx,
  people,
  preset,
  roleRef,
}: {
  ctx: PanelCtx;
  people: OrgPerson[];
  preset: { role: DocumentRole; nonce: number } | null;
  roleRef: React.RefObject<HTMLElement | null>;
}) {
  const assign = useAssignDocumentRole();
  const [role, setRole] = React.useState<DocumentRole>("reviewer");
  const [personId, setPersonId] = React.useState("");
  const [error, setError] = React.useState<string | null>(null);
  const personRef = React.useRef<HTMLSelectElement | null>(null);
  const uid = React.useId();

  React.useEffect(() => {
    if (!preset) return;
    setRole(preset.role);
    personRef.current?.focus();
  }, [preset]);

  const noneHeld = DOCUMENT_ROLES.every((r) => ctx.holders[r].length === 0);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!personId || !ctx.actor) return;
    setError(null);
    try {
      await assign.mutateAsync({ docId: ctx.docId, personId, role, actingPersonId: ctx.actor });
      ctx.announce(`${ctx.nameOf(personId)} assigned as ${ROLE_LABEL[role].toLowerCase()}.`);
      setPersonId("");
    } catch (err) {
      setError(errorMessage(err, "assign"));
    }
  };

  return (
    <section ref={roleRef as React.RefObject<HTMLElement>} tabIndex={-1} aria-labelledby={`${uid}-t`} data-roles="" className="mt-6 outline-none">
      <h3 id={`${uid}-t`} className="text-[12px] font-medium text-ink-3">
        Roles on this document
      </h3>
      {noneHeld && (
        <p data-no-roles="" className="mt-2 rounded-[8px] bg-amber-soft px-3 py-2 text-[13px] leading-5 text-ink">
          No one holds a role on this document yet, so nobody can sign its approval. Assign an owner, a reviewer and an approver.
        </p>
      )}
      <dl className="mt-2">
        {DOCUMENT_ROLES.map((r) => (
          <div key={r} className="flex items-baseline justify-between gap-4 border-b border-border py-2 text-[13px]">
            <dt className="text-ink">{ROLE_LABEL[r]}</dt>
            <dd className="text-right text-ink-2" data-role-holders={r}>
              {ctx.holders[r].length ? ctx.holders[r].map((h) => h.name || ctx.nameOf(h.person_id)).join(", ") : <span className="text-ink-3">Nobody yet</span>}
            </dd>
          </div>
        ))}
      </dl>
      <form onSubmit={onSubmit} aria-label="Assign role" className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[140px_1fr_auto] sm:items-end">
        <div>
          <label htmlFor={`${uid}-role`} className="mb-1 block text-[12px] text-ink-3">
            Role
          </label>
          <NativeSelect id={`${uid}-role`} value={role} onChange={(e) => setRole(e.target.value as DocumentRole)}>
            {DOCUMENT_ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABEL[r]}
              </option>
            ))}
          </NativeSelect>
        </div>
        <div>
          <label htmlFor={`${uid}-person`} className="mb-1 block text-[12px] text-ink-3">
            Person
          </label>
          <NativeSelect id={`${uid}-person`} ref={personRef} value={personId} onChange={(e) => setPersonId(e.target.value)}>
            <option value="">Select a person…</option>
            {people.map((p) => (
              <option key={p.person_id} value={p.person_id}>
                {p.name}
                {p.title ? ` · ${p.title}` : ""}
              </option>
            ))}
          </NativeSelect>
        </div>
        <Button type="submit" size="sm" disabled={!personId || !ctx.actor || assign.isPending}>
          Assign role
        </Button>
      </form>
      {!ctx.actor && <p className="mt-1.5 text-[12.5px] text-ink-3">Choose who you are acting as to assign roles.</p>}
      <ErrorNote message={error} />
    </section>
  );
}

/** Versions newest-first with status, current marker, ingest state, approval progress and actions. */
export function VersionHistoryPanel({ docId, doc, className }: VersionHistoryPanelProps) {
  const [actor, setActor] = useActingPerson();
  const versionsQ = useDocumentVersions(docId);
  const peopleQ = useOrgPeople();
  const rolesQ = useDocumentRoles(docId);
  const docQ = useDocument(docId);
  const meta = docQ.data ?? doc ?? null;

  const [live, setLive] = React.useState("");
  const announce = React.useCallback<Announce>((m) => setLive(m), []);
  const [preset, setPreset] = React.useState<{ role: DocumentRole; nonce: number } | null>(null);
  const rolesRef = React.useRef<HTMLElement | null>(null);
  const requestAssign = React.useCallback((role: DocumentRole) => {
    setPreset((p) => ({ role, nonce: (p?.nonce ?? 0) + 1 }));
    rolesRef.current?.scrollIntoView?.({ block: "nearest" });
  }, []);

  const peopleById = React.useMemo(() => new Map((peopleQ.data ?? []).map((p) => [p.person_id, p])), [peopleQ.data]);
  const active = React.useMemo(() => activePeople(peopleQ.data), [peopleQ.data]);
  const nameOf = React.useCallback<NameOf>((id) => (id ? (peopleById.get(id)?.name ?? id) : "—"), [peopleById]);
  const holders = React.useMemo(() => roleHolders(rolesQ.data, meta), [rolesQ.data, meta]);
  const ctx: PanelCtx = { docId, actor, holders, nameOf, announce, requestAssign };

  const list = versionsQ.data;
  const versions = React.useMemo(() => sortNewestFirst(list?.versions ?? []), [list]);
  const tagById = React.useMemo(() => new Map(versions.map((v) => [v.version_id, versionTag(v)])), [versions]);
  // One source of truth for "Current": the list's current_version_id.
  const currentId = list?.current_version_id ?? null;

  let body: React.ReactNode;
  if (versionsQ.isLoading) {
    body = (
      <div aria-busy="true" aria-label="Loading versions" className="space-y-3">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  } else if (versionsQ.isError) {
    body = <ErrorState className="px-0 py-4" message="Version history could not be loaded." source="Company documents" onRetry={() => void versionsQ.refetch()} />;
  } else if (list === null) {
    body = <p className="text-[14px] text-ink-2">We could not find this document&apos;s versions.</p>;
  } else if (versions.length === 0) {
    body = <p className="text-[14px] text-ink-2">No versions have been uploaded yet.</p>;
  } else {
    body = (
      <ol aria-label="Versions, newest first" className="space-y-3">
        {versions.map((v) => (
          <VersionCard key={v.version_id} version={v} isCurrent={v.version_id === currentId} tagById={tagById} ctx={ctx} />
        ))}
      </ol>
    );
  }

  return (
    <div data-version-history="" className={className}>
      <p aria-live="polite" role="status" className="sr-only" data-live="">
        {live}
      </p>
      {!actor && <ActorPrompt people={active} onChoose={(id) => setActor(id)} />}
      {currentId === null && versions.length > 0 && (
        <p className="mb-3 text-[13px] text-ink-3">No version is current yet. The first approved version becomes current.</p>
      )}
      {body}
      {list && <RolesSection ctx={ctx} people={active} preset={preset} roleRef={rolesRef} />}
    </div>
  );
}

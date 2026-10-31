"use client";
// Building blocks shared by UploadDocumentDialog and UploadVersionDialog.
import * as React from "react";
import { Loader2, Plus, Upload } from "lucide-react";
import type { UploadResult } from "@/lib/api/client";
import { ApiError } from "@/lib/api/http/shared";
import { MissingActorError } from "@/lib/actor";
import { useIngestJob, useOrgPeople, useRetryIngestJob } from "@/lib/api/queries";
import { AppLink } from "@/lib/app-link";
import { Button, buttonVariants } from "@/components/ui/button";
import { DialogClose } from "@/components/ui/dialog";
import { docHref } from "@/components/documents/board/logic";
import { cn } from "@/lib/utils";
import { ACTING_AS_SELECTOR_ID, UPLOAD_MESSAGES, duplicateTitle } from "./logic";

export const LABEL = "mb-1.5 block text-[13px] font-medium leading-[18px] text-ink-2";
export const HINT = "mt-1 text-[12.5px] leading-[18px] text-ink-3";
export const ERROR_TEXT = "mt-1 text-[13px] leading-[18px] text-[color:var(--red)]";
export const SELECT =
  "h-9 w-full cursor-pointer appearance-none rounded-[8px] border border-border-strong bg-surface px-3 text-[14px] text-ink focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-default disabled:text-ink-4";

/** The control that opens a dialog: a secondary header button, or the inline "Add a document" link style. */
export const TriggerButton = React.forwardRef<
  HTMLButtonElement,
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "button" | "inline"; label: string }
>(function TriggerButton({ variant = "button", label, className, ...props }, ref) {
  if (variant === "inline") {
    return (
      <button
        ref={ref}
        type="button"
        className={cn("inline-flex items-center gap-1 text-[13px] font-medium text-ink-2 underline-offset-2 hover:text-ink hover:underline", className)}
        {...props}
      >
        <Plus className="size-3.5" strokeWidth={1.5} aria-hidden />
        {label}
      </button>
    );
  }
  return (
    <button ref={ref} type="button" className={cn(buttonVariants({ variant: "secondary" }), className)} {...props}>
      <Upload aria-hidden />
      {label}
    </button>
  );
});

/** The message to show for a thrown upload/retry error (ApiError carries the server's `.detail`). */
export function errorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.detail || `The upload failed (HTTP ${err.status}).`;
  if (err instanceof MissingActorError) return UPLOAD_MESSAGES.noActor;
  return "The upload failed. Check your connection and try again.";
}

/** "Uploading as Dana Reyes", or the prompt to choose an actor (the selector itself is task 8.4). */
export function ActorNotice({ actorId }: { actorId: string | null }) {
  const people = useOrgPeople();
  if (!actorId) {
    return (
      <div role="alert" data-testid="actor-prompt" className="rounded-[8px] border border-[color:var(--amber)]/30 bg-[color:var(--amber-soft)] px-3 py-2.5 text-[13px] leading-5 text-[color:var(--amber)]">
        <p className="font-medium">Choose who you are acting as before uploading.</p>
        <p className="mt-0.5">
          Uploads are recorded against a person. Pick one in the{" "}
          <a href={`#${ACTING_AS_SELECTOR_ID}`} className="font-medium underline underline-offset-2">
            Acting as
          </a>{" "}
          selector in the sidebar, under the company name.
        </p>
      </div>
    );
  }
  const name = people.data?.find((p) => p.person_id === actorId)?.name;
  return (
    <p className="text-[13px] leading-5 text-ink-3" data-testid="actor-notice">
      Uploading as <span className="font-medium text-ink-2">{name ?? actorId}</span>
    </p>
  );
}

/** Polite live region for progress, assertive alert for errors. */
export function ServerError({ message }: { message: string | null }) {
  return (
    <div role="alert" aria-live="assertive" className="empty:hidden">
      {message && (
        <p className="rounded-[8px] border border-[color:var(--red-line)] bg-[color:var(--red-soft)] px-3 py-2.5 text-[13px] leading-5 text-[color:var(--red)]">
          {message}
        </p>
      )}
    </div>
  );
}

const JOB_LABEL: Record<string, string> = {
  queued: "Queued for processing…",
  running: "Splitting the document into clauses…",
  succeeded: "Processed.",
  failed: "Processing failed.",
};

const STEPS = ["queued", "running", "succeeded"] as const;

function JobStatus({
  jobId,
  docId,
  title,
  versionNo,
  onRetried,
}: {
  jobId: string;
  docId: string;
  title?: string;
  versionNo?: number;
  onRetried: () => void;
}) {
  const job = useIngestJob(jobId);
  const retry = useRetryIngestJob();
  const state = job.data?.job.state ?? "queued";
  const failed = state === "failed";
  const done = state === "succeeded";
  const reached = failed ? 2 : Math.max(0, STEPS.indexOf(state as (typeof STEPS)[number]));
  const name = title || docId;
  return (
    <div className="space-y-3" data-job-state={state}>
      <div role="status" aria-live="polite" className="space-y-1">
        <p className="flex items-center gap-2 text-[14px] font-medium leading-5 text-ink">
          {!done && !failed && <Loader2 aria-hidden className="size-4 animate-spin text-ink-3" strokeWidth={1.5} />}
          {job.isError ? "Could not check processing status." : JOB_LABEL[state]}
        </p>
        {done && (
          <p className="text-[13px] leading-5 text-ink-2">
            {versionNo && versionNo > 1 ? `Version ${versionNo} of ` : ""}
            <span className="font-medium">{name}</span> is ready and awaiting approval before it becomes current.
          </p>
        )}
        {failed && job.data?.job.error && <p className="text-[13px] leading-5 text-[color:var(--red)]">{job.data.job.error}</p>}
      </div>
      <ol className="flex items-center gap-4" aria-label="Processing steps">
        {["Queued", "Processing", failed ? "Failed" : "Done"].map((label, i) => {
          const step = failed && i === 2 ? "failed" : i < reached || done ? "complete" : i === reached ? "current" : "pending";
          return (
            <li key={label} data-step={step} className="flex items-center gap-1.5 text-[12.5px]">
              <span
                aria-hidden
                className={cn(
                  "size-2 rounded-full",
                  step === "failed" ? "bg-[color:var(--red)]" : step === "pending" ? "bg-border-strong" : "bg-ink",
                )}
              />
              <span className={step === "pending" ? "text-ink-4" : "text-ink-2"}>
                {label}
                <span className="sr-only"> ({step})</span>
              </span>
            </li>
          );
        })}
      </ol>
      {done && (
        <AppLink href={docHref(docId)} className="inline-flex text-[14px] font-medium text-ink underline underline-offset-2">
          Open {name}
        </AppLink>
      )}
      {failed && (
        <div className="space-y-2">
          <Button
            variant="primary"
            size="sm"
            disabled={retry.isPending}
            onClick={() => retry.mutate(jobId, { onSuccess: onRetried })}
          >
            {retry.isPending ? "Retrying…" : "Retry"}
          </Button>
          <ServerError message={retry.isError ? errorMessage(retry.error) : null} />
        </div>
      )}
    </div>
  );
}

/** Live ingest progress (queued → running → succeeded/failed) with Retry on failure. */
export function JobProgress(props: { jobId: string; docId: string; title?: string; versionNo?: number }) {
  // Remount after a retry so the poller's once-per-job invalidation runs again for the new attempt.
  const [attempt, setAttempt] = React.useState(0);
  return <JobStatus key={`${props.jobId}:${attempt}`} {...props} onRetried={() => setAttempt((a) => a + 1)} />;
}

/** retry_available: the same bytes already failed as a version; offer Retry on that job. */
export function RetryAvailable({ result }: { result: Extract<UploadResult, { kind: "retry_available" }> }) {
  const retry = useRetryIngestJob();
  const [started, setStarted] = React.useState(false);
  if (started) return <JobProgress jobId={result.job_id} docId={result.doc_id} />;
  return (
    <div className="space-y-3" data-upload-result="retry_available">
      <p role="status" aria-live="polite" className="text-[14px] leading-5 text-ink-2">
        {result.message}
      </p>
      <Button variant="primary" disabled={retry.isPending} onClick={() => retry.mutate(result.job_id, { onSuccess: () => setStarted(true) })}>
        {retry.isPending ? "Retrying…" : "Retry"}
      </Button>
      <ServerError message={retry.isError ? errorMessage(retry.error) : null} />
    </div>
  );
}

/** duplicate / unchanged: a message, nothing was written. */
export function NothingWritten({ result }: { result: Extract<UploadResult, { kind: "duplicate" | "unchanged" }> }) {
  if (result.kind === "unchanged") {
    return (
      <p role="status" aria-live="polite" data-upload-result="unchanged" className="text-[14px] leading-5 text-ink-2">
        No changes compared to the current version.
      </p>
    );
  }
  const title = duplicateTitle(result.message);
  return (
    <div role="status" aria-live="polite" data-upload-result="duplicate" className="space-y-2">
      <p className="text-[14px] leading-5 text-ink-2">
        {title ? (
          <>
            Already in the system as <span className="font-medium text-ink">{title}</span>.
          </>
        ) : (
          result.message
        )}{" "}
        Nothing was uploaded.
      </p>
      {result.doc_id && (
        <AppLink href={docHref(result.doc_id)} className="inline-flex text-[14px] font-medium text-ink underline underline-offset-2">
          Open {title ?? result.doc_id}
        </AppLink>
      )}
    </div>
  );
}

export function DialogFooter({ children }: { children: React.ReactNode }) {
  return <div className="flex items-center justify-end gap-2 border-t border-border px-6 py-4">{children}</div>;
}

export function CloseButton({ label = "Close" }: { label?: string }) {
  return (
    <DialogClose asChild>
      <Button variant="secondary">{label}</Button>
    </DialogClose>
  );
}

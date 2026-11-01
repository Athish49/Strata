"use client";
import * as React from "react";
import type { UploadResult } from "@/lib/api/client";
import { useUploadVersion } from "@/lib/api/queries";
import { useActingPerson } from "@/lib/actor";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { FileField } from "./FileField";
import type { UploadFormat } from "./logic";
import {
  ActorNotice,
  CloseButton,
  DialogFooter,
  ERROR_TEXT,
  HINT,
  JobProgress,
  LABEL,
  NothingWritten,
  RetryAvailable,
  ServerError,
  TriggerButton,
  errorMessage,
} from "./parts";

export interface UploadVersionDialogProps {
  docId: string;
  /** Shown in the dialog title and the success link. */
  docTitle?: string;
  /** "register" for CSV registers (the spec is inherited from the latest version). Default "docx". */
  format?: UploadFormat;
  variant?: "button" | "inline";
  /** Trigger text; defaults to "Upload new version". */
  label?: string;
  className?: string;
}

function UploadVersionForm({ docId, docTitle, format }: { docId: string; docTitle?: string; format: UploadFormat }) {
  const uid = React.useId();
  const [actorId] = useActingPerson();
  const upload = useUploadVersion();
  const [file, setFile] = React.useState<File | null>(null);
  const [reason, setReason] = React.useState("");
  const [submitted, setSubmitted] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<UploadResult | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    setServerError(null);
    if (!actorId || !file) return;
    try {
      setResult(
        await upload.mutateAsync({
          docId,
          file,
          meta: { change_reason: reason.trim() || undefined, acting_person_id: actorId },
        }),
      );
    } catch (err) {
      setServerError(errorMessage(err));
    }
  };

  if (result) {
    return (
      <>
        <div className="px-6 py-5" data-upload-result={result.kind}>
          {result.kind === "created" ? (
            <JobProgress jobId={result.job_id} docId={result.doc_id} title={docTitle} versionNo={result.version_no} />
          ) : result.kind === "retry_available" ? (
            <RetryAvailable result={result} />
          ) : (
            <NothingWritten result={result} />
          )}
        </div>
        <DialogFooter>
          <CloseButton label="Done" />
        </DialogFooter>
      </>
    );
  }

  const busy = upload.isPending;
  const reasonId = `${uid}-reason`;
  return (
    <form onSubmit={submit} noValidate aria-busy={busy || undefined} className="flex min-h-0 flex-col">
      <div className="min-h-0 space-y-4 overflow-y-auto px-6 py-5">
        <ActorNotice actorId={actorId} />
        <FileField
          id={`${uid}-file`}
          format={format}
          file={file}
          onChange={(f) => {
            setFile(f);
            setServerError(null);
          }}
          disabled={busy}
        />
        {submitted && !file && <p className={ERROR_TEXT}>Choose a file to upload.</p>}
        <div>
          <label htmlFor={reasonId} className={LABEL}>
            Reason for change <span className="font-normal text-ink-3">(optional)</span>
          </label>
          <textarea
            id={reasonId}
            name="change_reason"
            value={reason}
            disabled={busy}
            rows={3}
            onChange={(e) => setReason(e.target.value)}
            aria-describedby={`${reasonId}-hint`}
            className="w-full rounded-[8px] border border-border-strong bg-surface px-3 py-2 text-[14px] leading-5 text-ink placeholder:text-ink-3"
            placeholder="e.g. Updated notice period to match the amended rule."
          />
          <p id={`${reasonId}-hint`} className={HINT}>
            Recorded on the version and shown to approvers. The current version stays in effect until this one is approved.
          </p>
        </div>
        <ServerError message={serverError} />
        <div role="status" aria-live="polite" className="sr-only">
          {busy ? "Uploading…" : ""}
        </div>
      </div>
      <DialogFooter>
        <CloseButton label="Cancel" />
        <Button type="submit" variant="primary" disabled={busy || !actorId}>
          {busy ? "Uploading…" : "Upload version"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** "Upload new version" control + dialog for an existing document. */
export function UploadVersionDialog({ docId, docTitle, format = "docx", variant = "button", label, className }: UploadVersionDialogProps) {
  const [open, setOpen] = React.useState(false);
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <TriggerButton variant={variant} label={label ?? "Upload new version"} className={className} />
      </DialogTrigger>
      <DialogContent className="top-[10vh] flex max-h-[80vh] flex-col">
        <div className="border-b border-border px-6 py-5 pr-12">
          <DialogTitle className="font-serif text-[24px] font-normal leading-8 text-ink">Upload a new version</DialogTitle>
          <DialogDescription className="text-[14px] text-ink-3">
            {docTitle ? (
              <>
                Replaces <span className="font-medium text-ink-2">{docTitle}</span> ({docId}) once approved.
              </>
            ) : (
              <>Replaces {docId} once approved.</>
            )}
          </DialogDescription>
        </div>
        {open && <UploadVersionForm docId={docId} docTitle={docTitle} format={format} />}
      </DialogContent>
    </Dialog>
  );
}

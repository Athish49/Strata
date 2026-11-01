"use client";
import * as React from "react";
import { ChevronDown } from "lucide-react";
import type { UploadResult } from "@/lib/api/client";
import { useUploadDocument, useVerticals } from "@/lib/api/queries";
import { useActingPerson } from "@/lib/actor";
import { verticalName, type Vertical } from "@/lib/verticals";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { FileField } from "./FileField";
import {
  REGISTER_TYPES,
  buildRegisterSpec,
  columnOptions,
  isUploadTarget,
  readCsvHeader,
  titleFromFilename,
  uploadableVerticals,
  type RegisterType,
  type UploadFormat,
} from "./logic";
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
  SELECT,
  ServerError,
  TriggerButton,
  errorMessage,
} from "./parts";

export interface UploadDocumentDialogProps {
  /**
   * Target vertical slug from the entry point (a vertical page or section). Must satisfy
   * canUploadToVertical() and is never "unclassified"; otherwise nothing renders. When omitted
   * (the Documents board header) the dialog asks for one of the uploadable verticals.
   */
  vertical?: string;
  /** Preselected vertical when `vertical` is omitted (e.g. the board's vertical filter). Ignored if not uploadable. */
  defaultVertical?: string | null;
  /** "button": secondary header button. "inline": the "Add a document" link used in empty states. */
  variant?: "button" | "inline";
  /** Trigger text; defaults to "Upload" (button) or "Add a document" (inline). */
  label?: string;
  className?: string;
}

function NativeSelect({ id, value, onChange, children, invalid, describedBy, disabled }: {
  id: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
  invalid?: boolean;
  describedBy?: string;
  disabled?: boolean;
}) {
  return (
    <div className="relative">
      <select
        id={id}
        value={value}
        disabled={disabled}
        aria-invalid={invalid || undefined}
        aria-describedby={describedBy}
        onChange={(e) => onChange(e.target.value)}
        className={`${SELECT} pr-8`}
      >
        {children}
      </select>
      <ChevronDown aria-hidden className="pointer-events-none absolute right-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-3" strokeWidth={1.5} />
    </div>
  );
}

function UploadDocumentForm({
  fixedVertical,
  defaultVertical,
  verticals,
}: {
  fixedVertical?: string;
  defaultVertical?: string | null;
  verticals: readonly Vertical[];
}) {
  const uid = React.useId();
  const [actorId] = useActingPerson();
  const upload = useUploadDocument();
  const options = React.useMemo(() => uploadableVerticals(verticals), [verticals]);

  const [vertical, setVertical] = React.useState<string>(
    fixedVertical ?? (isUploadTarget(defaultVertical, verticals) ? defaultVertical : ""),
  );
  const [format, setFormat] = React.useState<UploadFormat>("docx");
  const [file, setFile] = React.useState<File | null>(null);
  const [title, setTitle] = React.useState("");
  const [titleTouched, setTitleTouched] = React.useState(false);
  const [docNumber, setDocNumber] = React.useState("");
  const [registerType, setRegisterType] = React.useState<RegisterType | "">("");
  const [columns, setColumns] = React.useState<string[] | null>(null);
  const [columnsError, setColumnsError] = React.useState<string | null>(null);
  const [idColumn, setIdColumn] = React.useState("");
  const [submitted, setSubmitted] = React.useState(false);
  const [serverError, setServerError] = React.useState<string | null>(null);
  const [result, setResult] = React.useState<{ r: UploadResult; title: string } | null>(null);

  const onFile = (f: File | null) => {
    setFile(f);
    setServerError(null);
    if (f && !titleTouched) setTitle(titleFromFilename(f.name));
    setColumns(null);
    setColumnsError(null);
    setIdColumn("");
    if (f && format === "register") {
      readCsvHeader(f).then(
        (h) => setColumns(columnOptions(h)),
        (e: unknown) => setColumnsError(e instanceof Error ? e.message : "The CSV header could not be read."),
      );
    }
  };

  const changeFormat = (f: UploadFormat) => {
    setFormat(f);
    setFile(null);
    setColumns(null);
    setColumnsError(null);
    setIdColumn("");
    setRegisterType("");
    setServerError(null);
    if (!titleTouched) setTitle("");
  };

  const spec = format === "register" ? buildRegisterSpec(registerType, idColumn) : null;
  const missing = {
    vertical: !isUploadTarget(vertical, verticals),
    file: !file,
    registerType: format === "register" && !registerType,
    idColumn: format === "register" && !idColumn,
  };
  const valid = !missing.vertical && !missing.file && !missing.registerType && !missing.idColumn;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
    setServerError(null);
    if (!actorId || !valid || !file) return;
    const finalTitle = title.trim() || titleFromFilename(file.name);
    try {
      const r = await upload.mutateAsync({
        vertical,
        file,
        meta: {
          title: finalTitle,
          doc_number: docNumber.trim() || undefined,
          register_spec: spec ? { ...spec } : undefined,
          acting_person_id: actorId,
        },
      });
      setResult({ r, title: finalTitle });
    } catch (err) {
      setServerError(errorMessage(err));
    }
  };

  if (result) {
    const { r } = result;
    return (
      <>
        <div className="space-y-4 px-6 py-5" data-upload-result={r.kind}>
          {r.kind === "created" ? (
            <JobProgress jobId={r.job_id} docId={r.doc_id} title={result.title} versionNo={r.version_no} />
          ) : r.kind === "retry_available" ? (
            <RetryAvailable result={r} />
          ) : (
            <NothingWritten result={r} />
          )}
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => { setResult(null); setFile(null); setTitle(""); setTitleTouched(false); setDocNumber(""); setSubmitted(false); }}>
            Upload another
          </Button>
          <CloseButton label="Done" />
        </DialogFooter>
      </>
    );
  }

  const ids = {
    vertical: `${uid}-vertical`,
    file: `${uid}-file`,
    title: `${uid}-title`,
    number: `${uid}-number`,
    regType: `${uid}-register-type`,
    idCol: `${uid}-id-column`,
  };
  const busy = upload.isPending;

  return (
    <form onSubmit={submit} noValidate aria-busy={busy || undefined} className="flex min-h-0 flex-col">
      <div className="min-h-0 space-y-4 overflow-y-auto px-6 py-5">
        <ActorNotice actorId={actorId} />

        {fixedVertical ? (
          <p className="text-[13px] leading-5 text-ink-3">
            Filed under <span className="font-medium text-ink-2">{verticalName(verticals, fixedVertical)}</span>
          </p>
        ) : (
          <div>
            <label htmlFor={ids.vertical} className={LABEL}>
              Vertical
            </label>
            <NativeSelect
              id={ids.vertical}
              value={vertical}
              onChange={setVertical}
              disabled={busy}
              invalid={submitted && missing.vertical}
              describedBy={submitted && missing.vertical ? `${ids.vertical}-error` : undefined}
            >
              <option value="">Choose a vertical</option>
              {options.map((v) => (
                <option key={v.slug} value={v.slug}>
                  {v.name}
                </option>
              ))}
            </NativeSelect>
            {submitted && missing.vertical && (
              <p id={`${ids.vertical}-error`} className={ERROR_TEXT}>
                Choose the vertical this document belongs to.
              </p>
            )}
          </div>
        )}

        <fieldset>
          <legend className={LABEL}>Kind of file</legend>
          <div className="flex flex-wrap gap-x-5 gap-y-2">
            {(
              [
                ["docx", "Document (.docx)"],
                ["register", "Register (CSV)"],
              ] as const
            ).map(([value, label]) => (
              <label key={value} className="inline-flex cursor-pointer items-center gap-2 text-[14px] text-ink">
                <input
                  type="radio"
                  name={`${uid}-format`}
                  value={value}
                  checked={format === value}
                  disabled={busy}
                  onChange={() => changeFormat(value)}
                  className="size-4 accent-[color:var(--ink)]"
                />
                {label}
              </label>
            ))}
          </div>
        </fieldset>

        <FileField id={ids.file} format={format} file={file} onChange={onFile} disabled={busy} />
        {submitted && missing.file && <p className={ERROR_TEXT}>Choose a file to upload.</p>}

        {format === "register" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor={ids.regType} className={LABEL}>
                Register type
              </label>
              <NativeSelect
                id={ids.regType}
                value={registerType}
                onChange={(v) => setRegisterType(v as RegisterType | "")}
                disabled={busy}
                invalid={submitted && missing.registerType}
                describedBy={submitted && missing.registerType ? `${ids.regType}-error` : undefined}
              >
                <option value="">Choose a type</option>
                {REGISTER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </NativeSelect>
              {submitted && missing.registerType && (
                <p id={`${ids.regType}-error`} className={ERROR_TEXT}>
                  Choose what the rows of this register are.
                </p>
              )}
            </div>
            <div>
              <label htmlFor={ids.idCol} className={LABEL}>
                ID column
              </label>
              <NativeSelect
                id={ids.idCol}
                value={idColumn}
                onChange={setIdColumn}
                disabled={busy || !columns || columns.length === 0}
                invalid={(submitted && missing.idColumn) || !!columnsError}
                describedBy={`${ids.idCol}-hint`}
              >
                <option value="">{columns ? "Choose a column" : "Choose a CSV file first"}</option>
                {(columns ?? []).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </NativeSelect>
              <p id={`${ids.idCol}-hint`} className={columnsError || (submitted && missing.idColumn) ? ERROR_TEXT : HINT}>
                {columnsError ?? (submitted && missing.idColumn ? "Choose the column holding each row’s stable ID." : "The column holding each row’s stable ID, from the CSV header.")}
              </p>
            </div>
          </div>
        )}

        <div>
          <label htmlFor={ids.title} className={LABEL}>
            Title
          </label>
          <Input
            id={ids.title}
            value={title}
            disabled={busy}
            onChange={(e) => {
              setTitle(e.target.value);
              setTitleTouched(true);
            }}
            aria-describedby={`${ids.title}-hint`}
          />
          <p id={`${ids.title}-hint`} className={HINT}>
            Defaults to the file name.
          </p>
        </div>

        <div>
          <label htmlFor={ids.number} className={LABEL}>
            Document number <span className="font-normal text-ink-3">(optional)</span>
          </label>
          <Input id={ids.number} value={docNumber} disabled={busy} onChange={(e) => setDocNumber(e.target.value)} placeholder="e.g. OPS-014" />
        </div>

        <ServerError message={serverError} />
        <div role="status" aria-live="polite" className="sr-only">
          {busy ? "Uploading…" : ""}
        </div>
      </div>
      <DialogFooter>
        <CloseButton label="Cancel" />
        <Button type="submit" variant="primary" disabled={busy || !actorId}>
          {busy ? "Uploading…" : "Upload"}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** "Upload" control + dialog for a new document. Renders nothing for a vertical that cannot take uploads. */
export function UploadDocumentDialog({ vertical, defaultVertical, variant = "button", label, className }: UploadDocumentDialogProps) {
  const [open, setOpen] = React.useState(false);
  const verticalsQuery = useVerticals();
  const verticals = verticalsQuery.data ?? [];
  // Only hide the trigger once the verticals list has actually loaded and says this
  // target is invalid -- while it's still loading, assume valid (matches the old
  // static-data behaviour, where this was never in doubt) rather than flashing the
  // button away and back.
  if (verticalsQuery.data) {
    if (vertical !== undefined && !isUploadTarget(vertical, verticals)) return null;
    if (vertical === undefined && uploadableVerticals(verticals).length === 0) return null;
  }
  const text = label ?? (variant === "inline" ? "Add a document" : "Upload");
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <TriggerButton variant={variant} label={text} className={className} />
      </DialogTrigger>
      <DialogContent className="top-[10vh] flex max-h-[80vh] flex-col">
        <div className="border-b border-border px-6 py-5 pr-12">
          <DialogTitle className="font-serif text-[24px] font-normal leading-8 text-ink">Upload a document</DialogTitle>
          <DialogDescription className="text-[14px] text-ink-3">
            Strata splits it into clauses and checks it against every regulatory change once it is approved.
          </DialogDescription>
        </div>
        {/* Remounted on every open so a closed dialog never keeps a half-filled form or old result. */}
        {open && <UploadDocumentForm fixedVertical={vertical} defaultVertical={defaultVertical} verticals={verticals} />}
      </DialogContent>
    </Dialog>
  );
}

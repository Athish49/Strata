"use client";
import * as React from "react";
import { ACCEPT, fileProblem, type UploadFormat } from "./logic";
import { ERROR_TEXT, HINT, LABEL } from "./parts";

/**
 * Native file input with client-side checks (type, 25 MB cap). The `accept` filter is only a
 * hint to the OS picker ("All files" bypasses it), so every selection is re-checked here.
 */
export function FileField({
  id,
  format,
  file,
  onChange,
  disabled,
}: {
  id: string;
  format: UploadFormat;
  file: File | null;
  onChange: (file: File | null, problem: string | null) => void;
  disabled?: boolean;
}) {
  const [problem, setProblem] = React.useState<string | null>(null);
  // A new format clears any earlier selection and its error.
  const [prevFormat, setPrevFormat] = React.useState(format);
  if (prevFormat !== format) {
    setPrevFormat(format);
    setProblem(null);
  }
  const hintId = `${id}-hint`;
  const errId = `${id}-error`;
  return (
    <div>
      <label htmlFor={id} className={LABEL}>
        File
      </label>
      <input
        key={format}
        id={id}
        name="file"
        type="file"
        accept={ACCEPT[format]}
        disabled={disabled}
        aria-invalid={problem ? true : undefined}
        aria-describedby={problem ? `${hintId} ${errId}` : hintId}
        onChange={(e) => {
          const f = e.target.files?.[0] ?? null;
          const p = f ? fileProblem(f, format) : null;
          setProblem(p);
          if (p) e.target.value = "";
          onChange(p ? null : f, p);
        }}
        className="block w-full rounded-[8px] border border-border-strong bg-surface text-[14px] text-ink-2 file:mr-3 file:h-9 file:cursor-pointer file:border-0 file:border-r file:border-border-strong file:bg-surface-muted file:px-3.5 file:text-[14px] file:font-medium file:text-ink focus-visible:outline-2 focus-visible:outline-offset-2"
      />
      <p id={hintId} className={HINT}>
        {format === "docx" ? "Word documents (.docx) only, up to 25 MB. PDF is not yet available." : "A CSV register (.csv, UTF-8), up to 25 MB."}
        {file && <span className="sr-only"> Selected: {file.name}.</span>}
      </p>
      {problem && (
        <p id={errId} role="alert" className={ERROR_TEXT}>
          {problem}
        </p>
      )}
    </div>
  );
}

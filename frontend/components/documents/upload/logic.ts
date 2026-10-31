// Pure helpers for the upload dialogs: client-side file checks, the CSV header reader for the
// register id-column picker, and the register_spec builder (mirrors backend/app/company_ingest/register_spec.py).
import { canUploadToVertical, UNCLASSIFIED_SLUG, VERTICALS, type Vertical } from "@/lib/verticals";

/** Server cap (413 above this). Enforced client-side too so nothing is sent. */
export const MAX_UPLOAD_BYTES = 25 * 1024 * 1024;

/** The `id` the "Acting as" selector (task 8.4, in the sidebar under the company name) renders on its control. */
export const ACTING_AS_SELECTOR_ID = "acting-as";

export type UploadFormat = "docx" | "register";

export const UPLOAD_MESSAGES = {
  pdf: "Only .docx documents are supported. PDF is not yet available.",
  notDocx: "Only .docx documents are supported. PDF is not yet available.",
  csvInDocxMode: "This is a CSV file. Choose “Register (CSV)” to upload a register.",
  notCsv: "A register must be a .csv file.",
  tooLarge: "This file is larger than the 25 MB limit.",
  emptyFile: "This file is empty.",
  noActor: "Choose who you are acting as before uploading.",
} as const;

export const ACCEPT: Record<UploadFormat, string> = {
  docx: ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  register: ".csv,text/csv",
};

/** register_type values the backend accepts (RegisterSpec.register_type). */
export const REGISTER_TYPES = [
  { value: "obligation", label: "Obligations" },
  { value: "event", label: "Events" },
  { value: "retention", label: "Retention schedule" },
  { value: "other", label: "Other" },
] as const;
export type RegisterType = (typeof REGISTER_TYPES)[number]["value"];

export interface RegisterSpec {
  register_type: RegisterType;
  id_column: string;
  citation_columns?: string[];
}

const ext = (name: string) => {
  const i = name.lastIndexOf(".");
  return i >= 0 ? name.slice(i + 1).toLowerCase() : "";
};

/** A user-facing reason this file cannot be uploaded in `format`, or null when it can. */
export function fileProblem(file: Pick<File, "name" | "size">, format: UploadFormat): string | null {
  const e = ext(file.name);
  if (e === "pdf") return UPLOAD_MESSAGES.pdf;
  if (format === "docx") {
    if (e === "csv") return UPLOAD_MESSAGES.csvInDocxMode;
    if (e !== "docx") return UPLOAD_MESSAGES.notDocx;
  } else if (e !== "csv") {
    return UPLOAD_MESSAGES.notCsv;
  }
  if (file.size > MAX_UPLOAD_BYTES) return UPLOAD_MESSAGES.tooLarge;
  if (file.size === 0) return UPLOAD_MESSAGES.emptyFile;
  return null;
}

/** Default title: the file name without its extension (the backend's default too). */
export function titleFromFilename(name: string): string {
  const base = name.replace(/^.*[\\/]/, "");
  const i = base.lastIndexOf(".");
  return (i > 0 ? base.slice(0, i) : base).trim();
}

/**
 * The first CSV record's cells (RFC 4180: quoted fields may hold commas, quotes and newlines).
 * A leading UTF-8 BOM is dropped. Throws with a user-facing message when there is no header row.
 */
export function parseCsvHeader(text: string): string[] {
  const src = text.replace(/^﻿/, "");
  if (!src.trim()) throw new Error("This CSV file is empty.");
  const cells: string[] = [];
  let cur = "";
  let quoted = false;
  let i = 0;
  for (; i < src.length; i++) {
    const ch = src[i];
    if (quoted) {
      if (ch === '"') {
        if (src[i + 1] === '"') {
          cur += '"';
          i++;
        } else quoted = false;
      } else cur += ch;
      continue;
    }
    if (ch === '"') quoted = true;
    else if (ch === ",") {
      cells.push(cur);
      cur = "";
    } else if (ch === "\n" || ch === "\r") break;
    else cur += ch;
  }
  cells.push(cur);
  if (!cells.some((c) => c.trim())) throw new Error("The first line of this CSV must be the header row naming the columns.");
  return cells;
}

/** Reads only the start of the file (the header row), client-side. */
export async function readCsvHeader(file: Blob): Promise<string[]> {
  const head = file.slice(0, 64 * 1024);
  const text =
    typeof head.text === "function"
      ? await head.text()
      : await new Promise<string>((resolve, reject) => {
          const r = new FileReader();
          r.onload = () => resolve(String(r.result ?? ""));
          r.onerror = () => reject(r.error);
          r.readAsText(head);
        });
  return parseCsvHeader(text);
}

/** Usable header names (non-blank, de-duplicated, in order) for the id-column picker. */
export function columnOptions(header: readonly string[]): string[] {
  return [...new Set(header.filter((c) => c.trim()))];
}

export function buildRegisterSpec(registerType: RegisterType | "", idColumn: string): RegisterSpec | null {
  if (!registerType || !idColumn.trim()) return null;
  return { register_type: registerType, id_column: idColumn };
}

/** True when the dialog may target this vertical: one of the 14 with a backend mapping, never "unclassified". */
export function isUploadTarget(slug: string | null | undefined): slug is string {
  return !!slug && slug !== UNCLASSIFIED_SLUG && canUploadToVertical(slug);
}

/** Verticals offered when the entry point has none (the Documents board header). */
export function uploadableVerticals(): Vertical[] {
  return VERTICALS.filter((v) => isUploadTarget(v.slug));
}

/** "This document is already in the system as 'X'." -> "X" (null when the message has another shape). */
export function duplicateTitle(message: string): string | null {
  const m = /already in the system as ['‘"“](.+?)['’"”]\.?\s*$/.exec(message);
  return m ? m[1] : null;
}

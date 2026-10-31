// Pure helpers for the version-history panel (task 8.3). No React, no fetching.
import type { QueryClient } from "@tanstack/react-query";
import type { DocumentMeta, DocumentRole, DocumentVersion, IngestJobState, OrgPerson, RoleAssignment, VersionStatus } from "@/lib/api/schemas";
import { ApiError } from "@/lib/api/http/shared";
import { MissingActorError } from "@/lib/actor";

export const VERSION_STATUS_LABEL: Record<VersionStatus, string> = {
  draft: "Draft",
  in_review: "In review",
  approved: "Approved",
  effective: "Effective",
  superseded: "Superseded",
  retired: "Retired",
};

export type BadgeTone = "neutral" | "green" | "amber" | "red" | "outline";

export const VERSION_STATUS_TONE: Record<VersionStatus, BadgeTone> = {
  draft: "neutral",
  in_review: "amber",
  approved: "green",
  effective: "green",
  superseded: "neutral",
  retired: "outline",
};

export const JOB_STATE_LABEL: Record<IngestJobState, string> = {
  queued: "Queued",
  running: "Processing",
  succeeded: "Ingested",
  failed: "Ingest failed",
};

export const JOB_STATE_TONE: Record<IngestJobState, BadgeTone> = {
  queued: "neutral",
  running: "neutral",
  succeeded: "green",
  failed: "red",
};

export const ROLE_LABEL: Record<DocumentRole, string> = { owner: "Owner", reviewer: "Reviewer", approver: "Approver" };
export const DOCUMENT_ROLES: readonly DocumentRole[] = ["owner", "reviewer", "approver"];

export function roleLabel(role: string): string {
  return (ROLE_LABEL as Record<string, string>)[role] ?? role.charAt(0).toUpperCase() + role.slice(1);
}

/** Versions newest-first (the endpoint already sorts; this is a safety net). */
export function sortNewestFirst(versions: readonly DocumentVersion[]): DocumentVersion[] {
  return [...versions].sort((a, b) => (b.version_no ?? 0) - (a.version_no ?? 0));
}

/** "v3" or the version label when there is no number. */
export function versionTag(v: Pick<DocumentVersion, "version_no" | "version">): string {
  return v.version_no != null ? `v${v.version_no}` : (v.version ?? "Version");
}

export interface RoleHolder {
  person_id: string;
  name: string;
}

/**
 * Who holds each role on the document: explicit assignments (GET …/roles) plus the document's
 * legacy owner/reviewer/approver ids, which the backend's `_holds_role` also accepts.
 * A brand-new document has neither, so every list is empty.
 */
export function roleHolders(roles: readonly RoleAssignment[] | undefined, doc: DocumentMeta | null | undefined): Record<DocumentRole, RoleHolder[]> {
  const out: Record<DocumentRole, RoleHolder[]> = { owner: [], reviewer: [], approver: [] };
  const add = (role: DocumentRole, h: RoleHolder) => {
    if (!h.person_id || out[role].some((x) => x.person_id === h.person_id)) return;
    out[role].push(h);
  };
  for (const r of roles ?? []) add(r.role, { person_id: r.person_id, name: r.name });
  if (doc) {
    if (doc.owner?.person_id) add("owner", { person_id: doc.owner.person_id, name: doc.owner.name });
    if (doc.reviewer?.person_id) add("reviewer", { person_id: doc.reviewer.person_id, name: doc.reviewer.name });
    if (doc.approver?.person_id) add("approver", { person_id: doc.approver.person_id, name: doc.approver.name });
  }
  return out;
}

export function activePeople(people: readonly OrgPerson[] | undefined): OrgPerson[] {
  return (people ?? []).filter((p) => p.is_active).sort((a, b) => a.name.localeCompare(b.name));
}

/**
 * The data layer does not refresh the engine reader cache `["engine", runId, "reader", docId]`
 * after an approval; a promotion changes the current version the reader shows, so invalidate it
 * for every run.
 */
export function invalidateEngineReader(qc: QueryClient, docId: string) {
  return qc.invalidateQueries({
    predicate: (q) => q.queryKey[0] === "engine" && q.queryKey[2] === "reader" && q.queryKey[3] === docId,
  });
}

export type ActionKind = "approve" | "reject" | "cancel" | "retry" | "assign";

/** A user-facing message for a failed write; 403s explain how to unblock signing. */
export function errorMessage(err: unknown, kind: ActionKind, requiredRole?: string | null): string {
  if (err instanceof MissingActorError) return "Choose who you are acting as before making changes.";
  if (err instanceof ApiError) {
    const detail = err.detail || err.message;
    if (err.status === 403) {
      const role = requiredRole ? roleLabel(requiredRole).toLowerCase() : "required";
      return `You can't sign this step: ${detail}. Only the step's assignee or someone holding the ${role} role can sign. Assign the role below, or act as someone who holds it.`;
    }
    if (err.status === 409) {
      if (kind === "approve") return `Approval was refused: ${detail}. Approval opens once the version's ingest has succeeded and earlier steps are decided.`;
      return `This could not be done right now: ${detail}.`;
    }
    if (err.status === 404) return `Not found: ${detail}.`;
    return detail;
  }
  return err instanceof Error ? err.message : "Something went wrong.";
}

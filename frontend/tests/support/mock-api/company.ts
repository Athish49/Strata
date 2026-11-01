// In-memory CompanyApi test double. Reads come from the fixtures; writes are simulated with
// deterministic triggers so UI tests can drive every upload / job / approval state.
//
// Upload triggers (case-insensitive, on the file name):
//   *.pdf or any non-.docx/.csv     -> ApiError 415 (MOCK_MESSAGES.unsupported)
//   name contains "empty"           -> ApiError 422 (MOCK_MESSAGES.empty)
//   name contains "toolarge"        -> ApiError 413
//   name contains "duplicate"       -> { kind: "duplicate" } pointing at MOCK_DUPLICATE_DOC_ID
//   name contains "unchanged"       -> { kind: "unchanged" }        (uploadVersion only)
//   name contains "retry"           -> { kind: "retry_available" }  (uploadVersion only; creates a failed version)
//   name contains "fail"            -> created; its ingest job ends `failed` (a retry then succeeds)
//   anything else                   -> created; its job goes queued -> running -> succeeded, one step per poll
// A vertical without a backend mapping (canUploadToVertical false) -> ApiError 422.
// An unknown acting person -> ApiError 404; no acting person -> MissingActorError.
//
// New documents open an approval request with two unassigned steps (reviewer, approver);
// nobody can sign an unassigned step without holding its role (assignDocumentRole, or a fixture
// document's owner/reviewer/approver), else 403; approving is refused (409) until the version's
// job succeeded; the final approval promotes the version. Call resetCompanyMock() in beforeEach.
import type { CompanyApi, UploadResult } from "@/lib/api/client";
import type {
  ApprovalRequest,
  ApprovalStep,
  DocumentMeta,
  DocumentRole,
  DocumentVersion,
  IngestJob,
  IngestJobState,
  OrgPerson,
  Person,
  RoleAssignment,
} from "@/lib/api/schemas";
import { normalizeDocument } from "@/lib/api/http/company";
import { ApiError } from "@/lib/api/http/shared";
import { requireActingPersonId } from "@/lib/api/actor-store";
import type { Vertical } from "@/lib/verticals";
import { canUploadToVertical, getVertical } from "@/lib/verticals";
import { fixtures, loadClauses } from "./fixtures";
import { withLatency } from "./config";

// Self-contained offline copy of the 14 verticals GET /company/verticals would return
// (same name/slug/sort_order as migrations/versions/9c1e4b7a2f05_verticals_retaxonomy.py's
// NEW_VERTICALS -- backend/tests/api_company/test_verticals_contract.py guards that file).
export const MOCK_VERTICALS: Vertical[] = [
  { sort_order: 1, slug: "corporate-governance-board", name: "Corporate Governance & Board", description: "Board structure, bylaws, charters, fiduciary duties, shareholder rights, entity management, annual filings, regulatory disclosure obligations." },
  { sort_order: 2, slug: "compliance-ethics", name: "Compliance & Ethics", description: "Code of conduct, anti-corruption (FCPA), anti-bribery, whistleblower protections, compliance training, conflicts of interest, FTC consumer/advertising compliance." },
  { sort_order: 3, slug: "legal-contractual", name: "Legal & Contractual", description: "Contract governance, litigation holds, IP protection, licensing, entity structure, NDAs, antitrust compliance." },
  { sort_order: 4, slug: "financial-compliance-reporting", name: "Financial Compliance & Reporting", description: "SOX/ICFR, GAAP/IFRS, financial disclosures, audit requirements, internal controls, revenue recognition, pricing regulations, fee disclosures." },
  { sort_order: 5, slug: "tax-trade-compliance", name: "Tax & Trade Compliance", description: "Corporate tax, payroll tax, sales tax, international tax (FATCA), transfer pricing, export controls, customs, OFAC sanctions, tariffs." },
  { sort_order: 6, slug: "workforce-employment", name: "Workforce & Employment", description: "Labor laws, wage & hour, FMLA, ADA, anti-discrimination, benefits (ERISA), immigration/work authorization, DEI policies." },
  { sort_order: 7, slug: "health-safety", name: "Health & Safety", description: "Workplace safety, emergency preparedness, hazard communication, PPE, incident reporting, product/consumer safety." },
  { sort_order: 8, slug: "data-privacy-cybersecurity", name: "Data Privacy & Cybersecurity", description: "GDPR, CCPA/CPRA, state privacy laws, data breach notification, cybersecurity frameworks, data retention, information security." },
  { sort_order: 9, slug: "environmental-sustainability", name: "Environmental & Sustainability", description: "EPA regulations, emissions, waste management, environmental permits, GHG reporting, ESG disclosures, climate risk, energy management." },
  { sort_order: 10, slug: "operations-quality", name: "Operations & Quality", description: "Quality management, process compliance, GMP, FDA product regulations, CAPA, operational standards, business process documentation." },
  { sort_order: 11, slug: "information-technology-records", name: "Information Technology & Records", description: "IT policies, system access controls, change management, records retention, digital accessibility (ADA/WCAG), AI governance and responsible use." },
  { sort_order: 12, slug: "supply-chain-third-party-risk", name: "Supply Chain & Third-Party Risk", description: "Vendor compliance, third-party risk, supplier due diligence, modern slavery/forced labor, supply chain transparency, conflict minerals." },
  { sort_order: 13, slug: "policy-training-management", name: "Policy & Training Management", description: "Policy lifecycle, document control, version management, compliance training programs, employee acknowledgments." },
  { sort_order: 14, slug: "risk-resilience", name: "Risk & Resilience", description: "Enterprise risk management, insurance requirements, business continuity, disaster recovery, operational resilience." },
];

export const MOCK_DUPLICATE_DOC_ID = "RPL-CMP-REG-001";
export const MOCK_MESSAGES = {
  unsupported: "Only .docx documents are supported. PDF is not yet available.",
  empty: "No extractable text found in this document.",
  tooLarge: "The file is larger than the 25 MB limit.",
  unchanged: "No changes compared to the current version.",
} as const;

interface MockVersion extends DocumentVersion {
  doc_id: string;
}
interface MockJob {
  job: IngestJob["job"];
  stats: Record<string, unknown>;
  /** Terminal state this attempt ends in. */
  outcome: Extract<IngestJobState, "succeeded" | "failed">;
}
interface MockState {
  seq: number;
  docs: DocumentMeta[];
  /** Overrides for fixture documents (e.g. after a role change). */
  overrides: Record<string, Partial<DocumentMeta>>;
  versions: MockVersion[];
  jobs: Record<string, MockJob>;
  requests: Record<string, ApprovalRequest>;
  roles: RoleAssignment[];
}

const fresh = (): MockState => ({ seq: 0, docs: [], overrides: {}, versions: [], jobs: {}, requests: {}, roles: [] });
let s: MockState = fresh();

/** Drop every simulated write (uploads, jobs, approvals, roles). */
export function resetCompanyMock(): void {
  s = fresh();
}

/** Add a document to the mock list as the backend would send it (normalised like the HTTP adapter). */
export function addMockDocument(doc: DocumentMeta): void {
  s.docs.push(doc);
}

const nextId = (prefix: string) => `${prefix}-${String(++s.seq).padStart(4, "0")}`;
const now = () => new Date(Date.UTC(2026, 0, 1, 0, 0, s.seq)).toISOString();

function allDocs(): DocumentMeta[] {
  return [...fixtures().documents.map((d) => ({ ...d, ...s.overrides[d.doc_id] })), ...s.docs].map(normalizeDocument);
}
const findDoc = (doc_id: string) => allDocs().find((d) => d.doc_id === doc_id) ?? null;

function person(person_id: string): Person {
  const p = fixtures().people.find((x) => x.person_id === person_id);
  if (!p) throw new ApiError(404, `acting person not found: ${person_id}`);
  return p;
}

const blankPerson = (): Person => ({ person_id: "", name: "", title: "", department: "", reports_to_id: null });

/** Backend _holds_role: an explicit role assignment, or the document's legacy owner/reviewer/approver id. */
function holdsRole(doc_id: string, role: string, person_id: string): boolean {
  if (s.roles.some((r) => r.doc_id === doc_id && r.role === role && r.person_id === person_id)) return true;
  const doc = findDoc(doc_id);
  if (!doc) return false;
  const legacy = role === "owner" ? doc.owner : role === "reviewer" ? doc.reviewer : role === "approver" ? doc.approver : null;
  return !!legacy && legacy.person_id !== "" && legacy.person_id === person_id;
}

function nameOf(file: Blob, filename?: string): string {
  if (filename) return filename;
  return typeof File !== "undefined" && file instanceof File ? file.name : "upload.docx";
}

function checkFile(file: Blob, name: string): string {
  const n = name.toLowerCase();
  if (!n.endsWith(".docx") && !n.endsWith(".csv")) throw new ApiError(415, MOCK_MESSAGES.unsupported);
  if (n.includes("toolarge") || file.size > 25 * 1024 * 1024) throw new ApiError(413, MOCK_MESSAGES.tooLarge);
  if (n.includes("empty")) throw new ApiError(422, MOCK_MESSAGES.empty);
  return n;
}

function duplicateOf(): UploadResult {
  const holder = findDoc(MOCK_DUPLICATE_DOC_ID);
  return {
    kind: "duplicate",
    message: `This document is already in the system as '${holder?.title ?? MOCK_DUPLICATE_DOC_ID}'.`,
    doc_id: MOCK_DUPLICATE_DOC_ID,
  };
}

function createJob(doc_id: string, version_id: string, outcome: MockJob["outcome"]): string {
  const job_id = nextId("job");
  s.jobs[job_id] = {
    job: { job_id, doc_id, version_id, state: "queued", error: null, created_at: now(), started_at: null, finished_at: null },
    stats: {},
    outcome,
  };
  return job_id;
}

function openApproval(doc_id: string, version_id: string, version_no: number): ApprovalRequest {
  const steps: ApprovalStep[] = (["reviewer", "approver"] as const).map((role, i) => ({
    step_no: i + 1,
    required_role: role,
    assignee_person_id: null,
    decision: null,
    decided_at: null,
    note: null,
  }));
  const req: ApprovalRequest = {
    request_id: nextId("req"),
    version_id,
    doc_id,
    version_no,
    version_status: "in_review",
    policy_id: "policy-default",
    state: "open",
    created_at: now(),
    completed_at: null,
    steps,
  };
  s.requests[req.request_id] = req;
  return req;
}

function addVersion(doc_id: string, version_no: number, actor: string, change_reason: string | null, outcome: MockJob["outcome"]) {
  const version_id = nextId("ver");
  const job_id = createJob(doc_id, version_id, outcome);
  const req = openApproval(doc_id, version_id, version_no);
  const current = s.versions.find((v) => v.doc_id === doc_id && v.is_current);
  s.versions.push({
    doc_id,
    version_id,
    version_no,
    version: `${version_no}.0`,
    status: "in_review",
    is_current: false,
    effective_date: null,
    approved_date: null,
    created_at: now(),
    created_by_person_id: actor,
    change_reason,
    supersedes_version_id: current?.version_id ?? null,
    superseded_by: null,
    ingest_status: "pending",
  });
  return { version_id, job_id, req };
}

/** A fixture document's history: one synthetic effective, current version. */
function ensureFixtureVersion(doc: DocumentMeta): void {
  if (s.versions.some((v) => v.doc_id === doc.doc_id)) return;
  s.versions.push({
    doc_id: doc.doc_id,
    version_id: `ver-${doc.doc_id}-1`,
    version_no: 1,
    version: doc.version,
    status: "effective",
    is_current: true,
    effective_date: doc.effective_date,
    approved_date: doc.approved_date,
    created_at: doc.approved_date,
    created_by_person_id: doc.owner.person_id,
    change_reason: null,
    supersedes_version_id: null,
    superseded_by: null,
    ingest_status: "ingested",
  });
}

function versionView(v: MockVersion): DocumentVersion {
  const { doc_id: _doc, ...rest } = v;
  void _doc;
  const job = Object.values(s.jobs)
    .filter((j) => j.job.version_id === v.version_id)
    .at(-1);
  const req = Object.values(s.requests)
    .filter((r) => r.version_id === v.version_id)
    .at(-1);
  const next = req?.state === "open" ? req.steps.find((x) => x.decision === null) : undefined;
  return {
    ...rest,
    ingest_job: job ? { job_id: job.job.job_id, state: job.job.state } : null,
    approval: req
      ? {
          request_id: req.request_id,
          state: req.state,
          created_at: req.created_at,
          completed_at: req.completed_at,
          steps_total: req.steps.length,
          steps_decided: req.steps.filter((x) => x.decision !== null).length,
          steps_approved: req.steps.filter((x) => x.decision === "approved").length,
          next_step_no: next?.step_no ?? null,
          next_required_role: next?.required_role ?? null,
          next_assignee_person_id: next?.assignee_person_id ?? null,
        }
      : null,
  };
}

function setDoc(doc_id: string, patch: Partial<DocumentMeta>): void {
  const i = s.docs.findIndex((d) => d.doc_id === doc_id);
  if (i >= 0) s.docs[i] = { ...s.docs[i], ...patch };
  else s.overrides[doc_id] = { ...s.overrides[doc_id], ...patch };
}

function promote(version_id: string): void {
  const v = s.versions.find((x) => x.version_id === version_id);
  if (!v) return;
  const date = now().slice(0, 10);
  for (const o of s.versions) {
    if (o.doc_id === v.doc_id && o.is_current) {
      o.is_current = false;
      o.status = "superseded";
      o.superseded_by = v.version_id;
    }
  }
  Object.assign(v, { is_current: true, status: "effective", effective_date: date, approved_date: date });
  setDoc(v.doc_id, {
    version: v.version ?? String(v.version_no),
    status: "Approved",
    effective_date: date,
    approved_date: date,
    lifecycle_state: "active",
    has_current_version: true,
    ingest_status: "ingested",
    monitored: true,
    latest_version_no: v.version_no,
    latest_version_status: "effective",
    latest_ingest_status: "ingested",
  });
}

function advance(j: MockJob): void {
  const t = now();
  if (j.job.state === "queued") {
    j.job.state = "running";
    j.job.started_at = t;
    return;
  }
  if (j.job.state !== "running") return;
  j.job.state = j.outcome;
  j.job.finished_at = t;
  const v = s.versions.find((x) => x.version_id === j.job.version_id);
  if (j.outcome === "succeeded") {
    j.stats = { clause_count: 3 };
    if (v) v.ingest_status = "ingested";
    // `monitored` / `ingest_status` describe the CURRENT version, so they change on promotion
    // (approval), not here. Only the newest version's ingest state moves.
    setDoc(j.job.doc_id, { latest_ingest_status: "ingested" });
  } else {
    j.job.error = "IngestError: simulated failure";
    if (v) v.ingest_status = "failed";
    setDoc(j.job.doc_id, { latest_ingest_status: "failed" });
    if (v?.version_no === 1) setDoc(j.job.doc_id, { ingest_status: "failed", lifecycle_state: "failed" });
  }
}

const clone = <T>(v: T): T => structuredClone(v);

export const companyApi: CompanyApi = {
  listVerticals: () => withLatency(() => MOCK_VERTICALS),
  listDocuments: () => withLatency(() => allDocs()),
  getDocument: (doc_id) => withLatency(() => findDoc(doc_id)),
  listClauses: (doc_id) => withLatency(() => (s.docs.some((d) => d.doc_id === doc_id) ? [] : loadClauses(doc_id))),
  listPeople: () => withLatency(() => fixtures().people),
  listOrgPeople: () =>
    withLatency((): OrgPerson[] =>
      fixtures().people.map((p) => ({ ...p, department_id: null, email: null, is_active: true })),
    ),
  getProfile: () => withLatency(() => fixtures().profile),

  uploadDocument: (vertical, file, meta = {}) =>
    withLatency((): UploadResult => {
      const actor = requireActingPersonId(meta.acting_person_id);
      const name = checkFile(file, nameOf(file, meta.filename));
      if (!canUploadToVertical(MOCK_VERTICALS, vertical)) throw new ApiError(422, `Unknown vertical '${vertical}'.`);
      person(actor);
      if (name.includes("duplicate")) return duplicateOf();
      const doc_id = `DOC-${String(900000 + s.seq + 1).padStart(6, "0")}`;
      const title = meta.title?.trim() || nameOf(file, meta.filename).replace(/\.[^.]+$/, "");
      s.docs.push({
        doc_id,
        title,
        version: "",
        status: "",
        effective_date: null,
        approved_date: null,
        law_as_of: meta.law_as_of ?? null,
        next_review: null,
        review_cycle: null,
        vertical,
        vertical_name: getVertical(MOCK_VERTICALS, vertical)?.name ?? null,
        // Like the backend: no roles at upload, so owner/reviewer are blank stubs until assigned.
        owner: blankPerson(),
        reviewer: blankPerson(),
        approver: null,
        two_signature: true,
        monitored: false,
        doc_type: "Document",
        cited_citations: [],
        doc_number: meta.doc_number?.trim() || null,
        ingest_status: "pending",
        lifecycle_state: "pending",
        // Like the backend: a new upload has no CURRENT version yet; the newest non-retired
        // version is v1, in review, still being ingested.
        has_current_version: false,
        latest_version_no: 1,
        latest_version_status: "in_review",
        latest_ingest_status: "pending",
      });
      const { version_id, job_id, req } = addVersion(doc_id, 1, actor, meta.change_reason ?? null, name.includes("fail") ? "failed" : "succeeded");
      return {
        kind: "created",
        doc_id,
        version_id,
        job_id,
        version_no: 1,
        approval_request_id: req.request_id,
        approval_state: req.state,
        retired_version_ids: [],
      };
    }),

  uploadVersion: (doc_id, file, meta = {}) =>
    withLatency((): UploadResult => {
      const actor = requireActingPersonId(meta.acting_person_id);
      const name = checkFile(file, nameOf(file, meta.filename));
      person(actor);
      const doc = findDoc(doc_id);
      if (!doc) throw new ApiError(404, "document not found");
      if (!s.docs.some((d) => d.doc_id === doc_id)) ensureFixtureVersion(doc);
      if (name.includes("unchanged")) return { kind: "unchanged", message: MOCK_MESSAGES.unchanged };
      if (name.includes("duplicate")) return duplicateOf();
      const mine = s.versions.filter((v) => v.doc_id === doc_id);
      const version_no = Math.max(0, ...mine.map((v) => v.version_no ?? 0)) + 1;
      if (name.includes("retry")) {
        const { version_id, job_id } = addVersion(doc_id, version_no, actor, meta.change_reason ?? null, "failed");
        const j = s.jobs[job_id];
        advance(j);
        advance(j); // straight to failed
        return {
          kind: "retry_available",
          message: `This exact file is already stored as version ${version_no}, whose ingest failed. Retry that ingest instead of uploading it again.`,
          doc_id,
          version_id,
          job_id,
        };
      }
      // A new upload retires stale in-review versions and cancels their open requests (6.2).
      const retired: string[] = [];
      for (const v of mine) {
        if (v.status === "in_review" && !v.is_current) {
          v.status = "retired";
          retired.push(v.version_id);
          for (const r of Object.values(s.requests)) {
            if (r.version_id === v.version_id && r.state === "open") Object.assign(r, { state: "cancelled", completed_at: now() });
          }
        }
      }
      const { version_id, job_id, req } = addVersion(doc_id, version_no, actor, meta.change_reason ?? null, name.includes("fail") ? "failed" : "succeeded");
      return {
        kind: "created",
        doc_id,
        version_id,
        job_id,
        version_no,
        approval_request_id: req.request_id,
        approval_state: req.state,
        retired_version_ids: retired,
      };
    }),

  listVersions: (doc_id) =>
    withLatency(() => {
      const doc = findDoc(doc_id);
      if (!doc) return null;
      if (!s.docs.some((d) => d.doc_id === doc_id)) ensureFixtureVersion(doc);
      const mine = s.versions
        .filter((v) => v.doc_id === doc_id)
        .sort((a, b) => (b.version_no ?? 0) - (a.version_no ?? 0))
        .map(versionView);
      return { doc_id, current_version_id: mine.find((v) => v.is_current)?.version_id ?? null, versions: mine };
    }),

  /** Each poll advances the job one state (queued -> running -> terminal) and returns the new state. */
  getIngestJob: (job_id) =>
    withLatency((): IngestJob | null => {
      const j = s.jobs[job_id];
      if (!j) return null;
      advance(j);
      return clone({ job: j.job, stats: j.stats });
    }),

  retryIngestJob: (job_id) =>
    withLatency(() => {
      const j = s.jobs[job_id];
      if (!j) throw new ApiError(404, "ingest job not found");
      if (j.job.state !== "failed") throw new ApiError(409, `job is ${j.job.state}, not failed`);
      Object.assign(j.job, { state: "queued", error: null, started_at: null, finished_at: null });
      j.outcome = "succeeded";
      const v = s.versions.find((x) => x.version_id === j.job.version_id);
      if (v) v.ingest_status = "pending";
      return { job_id, doc_id: j.job.doc_id, version_id: j.job.version_id, state: "queued" as const };
    }),

  getApprovalRequest: (request_id) => withLatency(() => (s.requests[request_id] ? clone(s.requests[request_id]) : null)),

  decideApprovalStep: (request_id, step_no, decision, opts) =>
    withLatency(() => {
      const actor = requireActingPersonId(opts?.acting_person_id);
      person(actor);
      const req = s.requests[request_id];
      if (!req) throw new ApiError(404, "approval request not found");
      if (req.state !== "open") throw new ApiError(409, `approval request is ${req.state}, not open`);
      const step = req.steps.find((x) => x.step_no === step_no);
      if (!step) throw new ApiError(404, "step not found");
      if (step.decision) throw new ApiError(409, "step already decided");
      const earlier = req.steps.filter((x) => x.step_no < step_no && !x.decision).map((x) => x.step_no);
      if (earlier.length) throw new ApiError(409, `earlier step(s) [${earlier.join(", ")}] not yet decided`);
      if (step.assignee_person_id) {
        if (step.assignee_person_id !== actor) throw new ApiError(403, `step ${step_no} is assigned to ${step.assignee_person_id}`);
      } else if (!req.doc_id || !holdsRole(req.doc_id, step.required_role, actor)) {
        throw new ApiError(403, `${actor} does not hold role '${step.required_role}' on ${req.doc_id}`);
      }
      if (decision === "approved") {
        const job = Object.values(s.jobs).filter((j) => j.job.version_id === req.version_id).at(-1);
        if (job && job.job.state !== "succeeded") {
          throw new ApiError(409, "cannot approve: the version's ingest job has not succeeded");
        }
      }
      Object.assign(step, { decision, decided_at: now(), note: opts?.note?.trim() || null, assignee_person_id: actor });
      if (decision === "rejected") Object.assign(req, { state: "rejected", completed_at: now() });
      else if (req.steps.every((x) => x.decision === "approved")) {
        Object.assign(req, { state: "approved", completed_at: now(), version_status: "effective" });
        promote(req.version_id);
      }
      return { ...clone(req), decided_step: step_no, decided_by: actor, request_state: req.state };
    }),

  cancelApprovalRequest: (request_id, opts) =>
    withLatency(() => {
      const actor = requireActingPersonId(opts?.acting_person_id);
      person(actor);
      const req = s.requests[request_id];
      if (!req) throw new ApiError(404, "approval request not found");
      if (req.state !== "open") throw new ApiError(409, `approval request is ${req.state}, not open`);
      Object.assign(req, { state: "cancelled", completed_at: now(), version_status: "retired" });
      const v = s.versions.find((x) => x.version_id === req.version_id);
      if (v && !v.is_current) v.status = "retired";
      if (v && !s.versions.some((o) => o.doc_id === v.doc_id && o.status !== "retired")) {
        setDoc(v.doc_id, { lifecycle_state: "retired" });
      }
      return clone(req);
    }),

  listDocumentRoles: (doc_id) => withLatency(() => clone(s.roles.filter((r) => r.doc_id === doc_id))),

  assignDocumentRole: (doc_id, person_id, role: DocumentRole, opts) =>
    withLatency(() => {
      const actor = requireActingPersonId(opts?.acting_person_id);
      person(actor);
      const p = person(person_id);
      if (!findDoc(doc_id)) throw new ApiError(404, "document not found");
      s.roles = s.roles.filter((r) => !(r.doc_id === doc_id && r.person_id === person_id && r.role === role));
      s.roles.push({ doc_id, person_id, role, assigned_at: now(), name: p.name, title: p.title });
      if (role === "approver") setDoc(doc_id, { approver: { ...p }, two_signature: false });
      else setDoc(doc_id, { [role]: { ...p } } as Partial<DocumentMeta>);
      const legacy = { owner: "owner_id", reviewer: "reviewer_id", approver: "approver_id" }[role];
      return { doc_id, person_id, role, legacy_column: legacy, legacy_value: person_id };
    }),
};

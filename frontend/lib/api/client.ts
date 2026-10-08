import { httpApi } from "./http";
import { mockApi } from "./mock";
import type {
  Agency,
  Candidate,
  ChangeRecord,
  Clause,
  CodeSection,
  CompanyProfile,
  DocRollup,
  DocumentMeta,
  EditableSection,
  Finding,
  LineDiff,
  MatrixCell,
  Annotation,
  Person,
  RadarItem,
  RegulatoryAction,
  Run,
  Scenario,
  ScoreReport,
  SectionS1Text,
  VersionEntry,
} from "./schemas";

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  limit: number;
}

export interface Reader {
  doc: DocumentMeta;
  clauses: Clause[];
  annotations: Annotation[];
}

export interface Matrix {
  docs: DocumentMeta[];
  changes: ChangeRecord[];
  cells: MatrixCell[];
}

export interface KbApi {
  listAgencies(): Promise<Agency[]>;
  getAgency(slug: string): Promise<Agency | null>;
  listSections(q: {
    agency?: string;
    source_system?: string;
    status?: "approved" | "repealed";
    search?: string;
    page?: number;
    limit?: number;
  }): Promise<Page<CodeSection>>;
  getSection(source_system: string, citation: string): Promise<CodeSection | null>;
  listActions(q: {
    agency?: string;
    source_system?: string;
    status?: string;
    action_type?: string;
    stream?: string;
    date_from?: string;
    date_to?: string;
    search?: string;
    page?: number;
    limit?: number;
  }): Promise<Page<RegulatoryAction>>;
  getAction(source_system: string, source_id: string): Promise<RegulatoryAction | null>;
  /** Modeled on GET /diff/{source_system}/{citation} (version history). */
  getVersionHistory(source_system: string, citation: string): Promise<VersionEntry[]>;
  /** Modeled on GET /diff/{source_system}/{citation}/compare. */
  compare(source_system: string, citation: string, date_a?: string, date_b?: string): Promise<LineDiff>;
}

export interface EngineApi {
  listRuns(): Promise<Run[]>;
  /** Polled every 2s by the UI while status === "running". */
  getRun(run_id: string): Promise<Run | null>;
  listChanges(run_id: string): Promise<ChangeRecord[]>;
  getChange(run_id: string, change_id: string): Promise<ChangeRecord | null>;
  listCandidates(run_id: string, q?: { change_id?: string; doc_id?: string }): Promise<Candidate[]>;
  listFindings(run_id: string, q?: { doc_id?: string; change_id?: string }): Promise<Finding[]>;
  getFinding(finding_id: string): Promise<Finding | null>;
  listRollups(run_id: string): Promise<DocRollup[]>;
  getReader(doc_id: string, run_id: string): Promise<Reader | null>;
  getMatrix(run_id: string, opts?: { include_noise?: boolean }): Promise<Matrix>;
  listRadar(run_id: string): Promise<RadarItem[]>;
  listScenarios(): Promise<Scenario[]>;
  saveScenario(s: Omit<Scenario, "scenario_id" | "is_preset" | "last_run_id"> & { scenario_id?: string }): Promise<Scenario>;
  /** Presets finish instantly; custom scenarios advance through the five stages (~8–10 s). */
  startWhatIf(scenario_id: string): Promise<Run>;
/** null when the run has no score report (what-if runs are never scored). */
  getScore(run_id: string): Promise<ScoreReport | null>;
  /** person_id defaults to the finding's routed reviewer when omitted. */
  submitReview(finding_id: string, decision: "accept" | "reject", note?: string, person_id?: string): Promise<Finding>;
  /** Sections cited by at least one company clause: the what-if section picker. */
  listEditableSections(): Promise<EditableSection[]>;
  /** The S1 (baseline) text of a section, the starting point of a what-if edit. */
  getSectionS1Text(source_system: string, citation: string): Promise<SectionS1Text | null>;
}

export interface CompanyApi {
  listDocuments(): Promise<DocumentMeta[]>;
  getDocument(doc_id: string): Promise<DocumentMeta | null>;
  listClauses(doc_id: string): Promise<Clause[]>;
  listPeople(): Promise<Person[]>;
  getProfile(): Promise<CompanyProfile>;
}

export interface StrataApi {
  kb: KbApi;
  engine: EngineApi;
  company: CompanyApi;
}

/** The single place that picks the StrataApi implementation. */
export const api: StrataApi = process.env.NEXT_PUBLIC_STRATA_DATA === "http" ? httpApi : mockApi;

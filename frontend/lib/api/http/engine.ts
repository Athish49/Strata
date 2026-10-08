// HTTP adapter for EngineApi. Contract: development_docs/ui_wiring_contract.md section 3. No fixtures.
import { z } from "zod";
import type { EngineApi, Matrix, Reader } from "../client";
import {
  annotationSchema,
  candidateSchema,
  changeRecordSchema,
  docRollupSchema,
  editableSectionSchema,
  findingSchema,
  matrixCellSchema,
  radarItemSchema,
  runSchema,
  scenarioSchema,
  scoreReportSchema,
  sectionS1TextSchema,
  type EditableSection,
  type Run,
  type Scenario,
} from "../schemas";
import { companyHttp } from "./company";
import { getJson, postJson, qs, seg, sleep } from "./shared";

const R = (run_id: string) => `/engine/ui/runs/${seg(run_id)}`;

const emptyList = { on404: [] as never[], on409: [] as never[] };

const matrixSchema = z.object({ changes: z.array(changeRecordSchema), cells: z.array(matrixCellSchema) });

const editableSectionWithIdSchema = editableSectionSchema.extend({ s1_section_id: z.union([z.string(), z.number()]) });

const createdScenarioSchema = z.object({ scenario_id: z.string(), run_id: z.string() });
const startedRunSchema = z.object({ run_id: z.string() });

// ---- what-if section id map (3.11) -----------------------------------------------------------
const sectionKey = (source_system: string, citation: string) => `${source_system}|${citation}`;
const sectionIds = new Map<string, string>();
const sectionIdByCitation = new Map<string, string>();

async function fetchEditableSections(): Promise<EditableSection[]> {
  const rows = await getJson("/engine/ui/whatif/sections", z.array(editableSectionWithIdSchema), emptyList);
  sectionIds.clear();
  sectionIdByCitation.clear();
  return rows.map(({ s1_section_id, ...section }) => {
    sectionIds.set(sectionKey(section.source_system, section.citation), String(s1_section_id));
    if (!sectionIdByCitation.has(section.citation)) sectionIdByCitation.set(section.citation, String(s1_section_id));
    return section;
  });
}

async function resolveSectionId(citation: string, source_system?: string): Promise<string | undefined> {
  const lookup = () =>
    (source_system ? sectionIds.get(sectionKey(source_system, citation)) : undefined) ?? sectionIdByCitation.get(citation);
  let id = lookup();
  if (!id) {
    await fetchEditableSections();
    id = lookup();
  }
  return id;
}

// ---- local scenario drafts (3.12) ------------------------------------------------------------
const drafts = new Map<string, Scenario>();
const isDraftId = (id: string) => id.startsWith("draft-");
const newDraftId = () => `draft-${globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`}`;

// ---- what-if run start (3.13) ----------------------------------------------------------------
const POLL_INTERVAL_MS = 400;
const POLL_ATTEMPTS = 30; // ~12 s

async function waitForRun(run_id: string): Promise<Run> {
  for (let i = 0; i < POLL_ATTEMPTS; i++) {
    const run = await getJson(R(run_id), runSchema, { on404: null as Run | null });
    if (run) return run;
    await sleep(POLL_INTERVAL_MS);
  }
  throw new Error("Run did not start");
}

async function backendScenarios(): Promise<Scenario[]> {
  return getJson("/engine/ui/scenarios", z.array(scenarioSchema));
}

const getFindingOrNull = (finding_id: string) =>
  getJson(`/engine/ui/findings/${seg(finding_id)}`, findingSchema.nullable(), { on404: null, on409: null });

export const engineHttp: EngineApi = {
  listRuns: () => getJson("/engine/ui/runs?collapse=true", z.array(runSchema)),

  getRun: (run_id) => getJson(R(run_id), runSchema.nullable(), { on404: null }),

  listChanges: (run_id) => getJson(`${R(run_id)}/changes`, z.array(changeRecordSchema), emptyList),

  getChange: (run_id, change_id) =>
    getJson(`${R(run_id)}/changes/${seg(change_id)}`, changeRecordSchema.nullable(), { on404: null, on409: null }),

  listCandidates: (run_id, q) =>
    getJson(`${R(run_id)}/candidates${qs({ change_id: q?.change_id, doc_id: q?.doc_id })}`, z.array(candidateSchema), emptyList),

  listFindings: (run_id, q) =>
    getJson(`${R(run_id)}/findings${qs({ doc_id: q?.doc_id, change_id: q?.change_id })}`, z.array(findingSchema), emptyList),

  getFinding: (finding_id) => getFindingOrNull(finding_id),

  listRollups: (run_id) => getJson(`${R(run_id)}/rollups`, z.array(docRollupSchema), emptyList),

  async getReader(doc_id, run_id): Promise<Reader | null> {
    const [doc, clauses, annotations] = await Promise.all([
      companyHttp.getDocument(doc_id),
      companyHttp.listClauses(doc_id),
      getJson(`${R(run_id)}/documents/${seg(doc_id)}/annotations`, z.array(annotationSchema), emptyList),
    ]);
    if (!doc) return null;
    return { doc, clauses, annotations };
  },

  async getMatrix(run_id, opts): Promise<Matrix> {
    const [documents, result] = await Promise.all([
      companyHttp.listDocuments(),
      getJson(`${R(run_id)}/matrix${qs({ include_noise: opts?.include_noise ? "true" : "false" })}`, matrixSchema.nullable(), {
        on404: null,
        on409: null,
      }),
    ]);
    if (!result) return { docs: [], changes: [], cells: [] };
    const docs = documents.filter((d) => d.monitored).sort((a, b) => (a.doc_id < b.doc_id ? -1 : a.doc_id > b.doc_id ? 1 : 0));
    return { docs, changes: result.changes, cells: result.cells };
  },

  listRadar: (run_id) => getJson(`${R(run_id)}/radar`, z.array(radarItemSchema), emptyList),

  async listScenarios() {
    const rows = await backendScenarios();
    return [...rows, ...drafts.values()];
  },

  async saveScenario(s) {
    if (s.edit_kind === "text_edit" && !(s.edited_text ?? "").trim()) {
      throw new Error("Edited text is required for a text edit");
    }
    const id = await resolveSectionId(s.citation, s.source_system);
    if (!id) throw new Error("Section is not cited by any RPL clause");
    const scenario_id = s.scenario_id && isDraftId(s.scenario_id) ? s.scenario_id : newDraftId();
    const draft: Scenario = {
      ...s,
      scenario_id,
      edited_text: s.edit_kind === "repeal" ? null : s.edited_text,
      is_preset: false,
      last_run_id: null,
    };
    drafts.set(scenario_id, draft);
    return draft;
  },

  async startWhatIf(scenario_id) {
    const draft = drafts.get(scenario_id);
    if (draft) {
      const s1_section_id = await resolveSectionId(draft.citation, draft.source_system);
      if (!s1_section_id) throw new Error("Section is not cited by any RPL clause");
      const created = await postJson(
        "/engine/whatif/scenarios",
        {
          s1_section_id,
          edit_kind: draft.edit_kind,
          edited_text: draft.edit_kind === "repeal" ? null : (draft.edited_text ?? null),
          title: draft.title,
        },
        createdScenarioSchema,
      );
      drafts.delete(scenario_id);
      return waitForRun(created.run_id);
    }

    const scenario = (await backendScenarios()).find((s) => s.scenario_id === scenario_id);
    if (!scenario) throw new Error("Scenario not found");
    if (scenario.is_preset && scenario.last_run_id) {
      const last = await getJson(R(scenario.last_run_id), runSchema.nullable(), { on404: null });
      if (last && last.status === "succeeded") return last;
    }
    const started = await postJson(`/engine/whatif/scenarios/${seg(scenario_id)}/run`, {}, startedRunSchema);
    return waitForRun(started.run_id);
  },

  getScore: (run_id) => getJson(`${R(run_id)}/score`, scoreReportSchema.nullable(), { on404: null, on409: null }),

  async submitReview(finding_id, decision, note, person_id) {
    if (decision === "reject" && !(note ?? "").trim()) throw new Error("A note is required to reject");
    let reviewer = person_id;
    if (!reviewer) {
      const finding = await getFindingOrNull(finding_id);
      if (!finding) throw new Error("Finding not found");
      reviewer = finding.route.reviewer?.person_id ?? finding.route.owner.person_id;
    }
    await postJson(`/engine/findings/${seg(finding_id)}/reviews`, { action: decision, note: note ?? null, person_id: reviewer }, z.unknown());
    const updated = await getFindingOrNull(finding_id);
    if (!updated) throw new Error("Finding not found");
    return updated;
  },

  listEditableSections: () => fetchEditableSections(),

  async getSectionS1Text(source_system, citation) {
    const id = await resolveSectionId(citation, source_system);
    if (!id) return null;
    return getJson(`/engine/ui/whatif/sections/${seg(id)}`, sectionS1TextSchema.nullable(), { on404: null, on409: null });
  },
};

// Static fixture imports, validated once with zod and cached.
import { z } from "zod";
import {
  agencySchema,
  candidateSchema,
  changeRecordSchema,
  clauseSchema,
  codeSectionSchema,
  companyProfileSchema,
  docRollupSchema,
  documentMetaSchema,
  findingSchema,
  personSchema,
  radarItemSchema,
  regulatoryActionSchema,
  runSchema,
  scenarioSchema,
  scoreReportSchema,
  versionEntrySchema,
  type Candidate,
  type ChangeRecord,
  type Clause,
  type DocRollup,
  type Finding,
  type RadarItem,
  type VersionEntry,
} from "../schemas";

import documentsJson from "../../../fixtures/company/documents.json";
import peopleJson from "../../../fixtures/company/people.json";
import profileJson from "../../../fixtures/company/profile.json";
import agenciesJson from "../../../fixtures/kb/agencies.json";
import sectionsJson from "../../../fixtures/kb/sections.json";
import actionsJson from "../../../fixtures/kb/actions.json";
import versionsJson from "../../../fixtures/kb/versions.json";
import runsJson from "../../../fixtures/engine/runs.json";
import scenariosJson from "../../../fixtures/engine/scenarios.json";
import scoreJson from "../../../fixtures/engine/score.json";

import kbChanges from "../../../fixtures/engine/run_kb_real/changes.json";
import kbCandidates from "../../../fixtures/engine/run_kb_real/candidates.json";
import kbFindings from "../../../fixtures/engine/run_kb_real/findings.json";
import kbRollups from "../../../fixtures/engine/run_kb_real/rollups.json";
import kbRadar from "../../../fixtures/engine/run_kb_real/radar.json";
import baseChanges from "../../../fixtures/engine/run_baseline/changes.json";
import baseCandidates from "../../../fixtures/engine/run_baseline/candidates.json";
import baseFindings from "../../../fixtures/engine/run_baseline/findings.json";
import baseRollups from "../../../fixtures/engine/run_baseline/rollups.json";
import baseRadar from "../../../fixtures/engine/run_baseline/radar.json";
import paChanges from "../../../fixtures/engine/run_whatif_preset_a/changes.json";
import paCandidates from "../../../fixtures/engine/run_whatif_preset_a/candidates.json";
import paFindings from "../../../fixtures/engine/run_whatif_preset_a/findings.json";
import paRollups from "../../../fixtures/engine/run_whatif_preset_a/rollups.json";
import paRadar from "../../../fixtures/engine/run_whatif_preset_a/radar.json";
import pbChanges from "../../../fixtures/engine/run_whatif_preset_b/changes.json";
import pbCandidates from "../../../fixtures/engine/run_whatif_preset_b/candidates.json";
import pbFindings from "../../../fixtures/engine/run_whatif_preset_b/findings.json";
import pbRollups from "../../../fixtures/engine/run_whatif_preset_b/rollups.json";
import pbRadar from "../../../fixtures/engine/run_whatif_preset_b/radar.json";

export interface RunData {
  changes: ChangeRecord[];
  candidates: Candidate[];
  findings: Finding[];
  rollups: DocRollup[];
  radar: RadarItem[];
}

export const PRESET_A_RUN_ID = "run_whatif_preset_a";

const list = <T extends z.ZodType>(schema: T, json: unknown) => z.array(schema).parse(json);

function runData(c: unknown, ca: unknown, f: unknown, r: unknown, ra: unknown): RunData {
  return {
    changes: list(changeRecordSchema, c),
    candidates: list(candidateSchema, ca),
    findings: list(findingSchema, f),
    rollups: list(docRollupSchema, r),
    radar: list(radarItemSchema, ra),
  };
}

type Fixtures = ReturnType<typeof build>;
let cache: Fixtures | null = null;

function build() {
  return {
    documents: list(documentMetaSchema, documentsJson),
    people: list(personSchema, peopleJson),
    profile: companyProfileSchema.parse(profileJson),
    agencies: list(agencySchema, agenciesJson),
    sections: list(codeSectionSchema, sectionsJson),
    actions: list(regulatoryActionSchema, actionsJson),
    versions: z.record(z.string(), z.array(versionEntrySchema)).parse(versionsJson) as Record<string, VersionEntry[]>,
    runs: list(runSchema, runsJson),
    scenarios: list(scenarioSchema, scenariosJson),
    score: scoreReportSchema.parse(scoreJson),
    runData: {
      run_kb_real: runData(kbChanges, kbCandidates, kbFindings, kbRollups, kbRadar),
      run_baseline: runData(baseChanges, baseCandidates, baseFindings, baseRollups, baseRadar),
      run_whatif_preset_a: runData(paChanges, paCandidates, paFindings, paRollups, paRadar),
      run_whatif_preset_b: runData(pbChanges, pbCandidates, pbFindings, pbRollups, pbRadar),
    } as Record<string, RunData>,
  };
}

export function fixtures(): Fixtures {
  if (!cache) cache = build();
  return cache;
}

const clauseCache = new Map<string, Clause[]>();

/** Clause files are loaded lazily per document (they are the largest fixtures). */
export async function loadClauses(doc_id: string): Promise<Clause[]> {
  const hit = clauseCache.get(doc_id);
  if (hit) return hit;
  let raw: unknown = [];
  try {
    const mod = await import(`../../../fixtures/company/clauses/${doc_id}.json`);
    raw = (mod as { default?: unknown }).default ?? mod;
  } catch {
    raw = [];
  }
  const parsed = list(clauseSchema, raw).sort((a, b) => a.ordinal - b.ordinal);
  clauseCache.set(doc_id, parsed);
  return parsed;
}

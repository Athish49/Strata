/**
 * Engine fixture builder for the two what-if presets (spec §6.4).
 * Run manually: `pnpm exec tsx scripts/build-engine-preset-fixtures.ts`.
 *
 * Reads only committed fixtures (kb/versions.json, company/*) and writes
 * fixtures/engine/run_whatif_preset_{a,b}/*.json plus fixtures/engine/scenarios.json.
 * Findings are INVENTED scenarios. Quote spans are computed with indexOf so that
 * substring(span) === text always holds; diff_segments come from jsdiff.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { diffWords } from "diff";
import {
  candidateSchema,
  changeRecordSchema,
  docRollupSchema,
  findingSchema,
  runSchema,
  scenarioSchema,
  type Candidate,
  type ChangeRecord,
  type DocRollup,
  type Finding,
  type PathNode,
  type Run,
} from "../lib/api/schemas/engine";
import type { Clause, DocumentMeta } from "../lib/api/schemas/company";
import type { MatchPath, Verdict } from "../lib/api/schemas/common";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FX = path.resolve(HERE, "../fixtures");
const readJson = <T>(p: string): T => JSON.parse(readFileSync(path.join(FX, p), "utf8")) as T;

const documents = readJson<DocumentMeta[]>("company/documents.json");
const docById = new Map(documents.map((d) => [d.doc_id, d]));
const clauseCache = new Map<string, Map<string, Clause>>();
function clauseOf(clauseId: string): Clause {
  const docId = clauseId.split(":")[0];
  if (!clauseCache.has(docId)) {
    const list = readJson<Clause[]>(`company/clauses/${docId}.json`);
    clauseCache.set(docId, new Map(list.map((c) => [c.clause_id, c])));
  }
  const c = clauseCache.get(docId)!.get(clauseId);
  if (!c) throw new Error(`Unknown clause ${clauseId}`);
  return c;
}

const versions = readJson<Record<string, { snapshot: string; snapshot_date: string; text: string }[]>>("kb/versions.json");
const S1_DATE = "2024-12-31";
const S2_DATE = "2025-12-31";
const PUBLISHED = "2025-02-20";

/* ------------------------------------------------------------------ types */

interface FSpec {
  clause: string;
  verdict: Verdict;
  severity: "high" | "medium" | "low";
  type: string;
  by: "rule" | "ai";
  conf: number;
  match: MatchPath;
  path?: PathNode[]; // overrides the default path
  from: string;
  to: string;
  s1q: string;
  s2q: string;
  /** exact substring of clause.text_raw; null = quote could not be located (unverified) */
  cq: string | null;
  /** text shown for an unverified quote (not found in the clause) */
  cqLoose?: string;
  verified?: boolean;
  propagatedFrom?: number; // 1-based index into the spec list
  rationale: string;
}
interface CSpec {
  clause: string;
  match: MatchPath;
  path?: PathNode[];
  skip: string;
  rationale: string;
  ai?: boolean;
}
interface PresetDef {
  letter: "a" | "b";
  runId: string;
  scenarioId: string;
  title: string;
  citation: string;
  editKind: "text_edit" | "repeal";
  s1: string;
  s2: string;
  heading: string;
  changeClass: "substantive" | "repealed";
  characterization: NonNullable<ChangeRecord["characterization"]>;
  disposition: string;
  dispositionReason: string;
  startedAt: string;
  finishedAt: string;
  findings: FSpec[];
  cleared: CSpec[];
  clearedReasons: Record<string, string>;
}

/* ---------------------------------------------------------------- helpers */

const sec = (ref: string, label = ref): PathNode => ({ kind: "section", ref, label });
const rule = (ref: string, label = ref): PathNode => ({ kind: "rule", ref, label });

function localId(clauseId: string): string {
  return clauseId.split(":")[1];
}
function nodeFor(clauseId: string): PathNode {
  const c = clauseOf(clauseId);
  const doc = c.doc_id;
  const local = localId(clauseId);
  switch (c.unit_kind) {
    case "register_row":
      return { kind: "register_row", ref: clauseId, label: `${doc} row ${local}` };
    case "form_field":
      return { kind: "form_field", ref: clauseId, label: `${doc} field ${local.replace(/^App-/, "")}` };
    case "tariff_subrule":
      return { kind: "tariff_rule", ref: clauseId, label: `${doc} rule ${local}` };
    case "table_row":
      return { kind: "clause", ref: clauseId, label: `${doc} table ${local}` };
    default:
      return { kind: "clause", ref: clauseId, label: `${doc} §${local}` };
  }
}
function defaultPath(match: MatchPath, clauseId: string, citationRef: string, ruleKey: string, echoLabel?: string): PathNode[] {
  switch (match) {
    case "direct_rule":
      return [rule(ruleKey), nodeFor(clauseId)];
    case "value_echo":
      return [sec(citationRef, echoLabel ?? citationRef), nodeFor(clauseId)];
    default:
      return [sec(citationRef), nodeFor(clauseId)];
  }
}
function locate(text: string, q: string, what: string): [number, number] {
  const i = text.indexOf(q);
  if (i < 0) throw new Error(`${what}: quote not found: ${q}`);
  return [i, i + q.length];
}
function route(docId: string) {
  const d = docById.get(docId);
  if (!d) throw new Error(`Unknown doc ${docId}`);
  return { owner: d.owner, reviewer: d.reviewer, approver: d.two_signature ? null : (d.approver ?? null) };
}
const count = <T>(items: T[], key: (t: T) => string): Record<string, number> => {
  const out: Record<string, number> = {};
  for (const i of items) out[key(i)] = (out[key(i)] ?? 0) + 1;
  return out;
};
const pad = (n: number) => String(n).padStart(3, "0");

/* ------------------------------------------------------------ builder core */

function build(def: PresetDef) {
  const L = def.letter;
  const changeId = `chg_whatif_${L}_001`;
  const ruleKey = "170 IAC 4-1";

  const diff_segments = diffWords(def.s1, def.s2).map((p) => ({
    op: p.added ? ("insert" as const) : p.removed ? ("delete" as const) : ("equal" as const),
    text: p.value,
  }));

  const findingIds = def.findings.map((_, i) => `f_${L}_${pad(i + 1)}`);

  const findings: Finding[] = def.findings.map((f, i) => {
    const c = clauseOf(f.clause);
    const doc = docById.get(c.doc_id)!;
    const cqText = f.cq ?? f.cqLoose ?? "";
    const verified = f.verified ?? f.cq !== null;
    const clauseQuote = f.cq !== null ? { text: f.cq, span: locate(c.text_raw, f.cq, f.clause) } : { text: cqText, span: null };
    const nodes = f.path ?? defaultPath(f.match, f.clause, def.citation, ruleKey);
    return findingSchema.parse({
      finding_id: findingIds[i],
      run_id: def.runId,
      change_id: changeId,
      clause_id: f.clause,
      doc_id: c.doc_id,
      citation: def.citation,
      finding_type: f.type,
      verdict: f.verdict,
      severity: f.severity,
      confidence: f.conf,
      decided_by: f.by,
      required_change: { from_text: f.from, to_text: f.to },
      quotes: {
        s1: { text: f.s1q, span: locate(def.s1, f.s1q, `${f.clause} s1`) },
        s2: { text: f.s2q, span: locate(def.s2, f.s2q, `${f.clause} s2`) },
        clause: clauseQuote,
      },
      quotes_verified: verified,
      rationale: f.rationale,
      match_path: f.match,
      path_detail: nodes,
      propagated_from: f.propagatedFrom ? findingIds[f.propagatedFrom - 1] : null,
      stale_at_approval: doc.approved_date != null && PUBLISHED < doc.approved_date,
      doc_approved_date: doc.approved_date ?? null,
      rule_published_date: PUBLISHED,
      route: route(c.doc_id),
      reviews: [],
    });
  });

  const candidates: Candidate[] = [];
  findings.forEach((f, i) => {
    candidates.push(
      candidateSchema.parse({
        candidate_id: `cand_${L}_${pad(candidates.length + 1)}`,
        run_id: def.runId,
        change_id: changeId,
        clause_id: f.clause_id,
        doc_id: f.doc_id,
        match_path: f.match_path,
        path_detail: f.path_detail,
        outcome: "affected",
        skip_reason: null,
        rationale: f.rationale,
        finding_id: f.finding_id,
      }),
    );
    void i;
  });
  let aiCleared = 0;
  for (const cs of def.cleared) {
    const c = clauseOf(cs.clause);
    if (cs.ai) aiCleared++;
    candidates.push(
      candidateSchema.parse({
        candidate_id: `cand_${L}_${pad(candidates.length + 1)}`,
        run_id: def.runId,
        change_id: changeId,
        clause_id: cs.clause,
        doc_id: c.doc_id,
        match_path: cs.match,
        path_detail: cs.path ?? defaultPath(cs.match, cs.clause, def.citation, ruleKey),
        outcome: "cleared",
        skip_reason: cs.skip,
        rationale: cs.rationale,
        finding_id: null,
      }),
    );
  }

  const change: ChangeRecord = changeRecordSchema.parse({
    change_id: changeId,
    citation: def.citation,
    heading: def.heading,
    source_system: "iac",
    rule_key: ruleKey,
    agency_id: "iurc",
    title_number: "170",
    change_class: def.changeClass,
    diff_segments,
    s1_text: def.s1,
    s2_text: def.s2,
    published_date: PUBLISHED,
    date_basis: "What-if assumption: edit treated as effective on this date",
    din: null,
    s1_snapshot: S1_DATE,
    s2_snapshot: S2_DATE,
    in_footprint: true,
    cited_clause_count: candidates.length,
    characterization: def.characterization,
    disposition: "obligation_changed",
    disposition_reason: def.dispositionReason,
    placeholder: true,
  });

  const docIds = [...new Set(candidates.map((c) => c.doc_id))];
  const rollups: DocRollup[] = docIds.map((docId) => {
    const fs = findings.filter((f) => f.doc_id === docId);
    return docRollupSchema.parse({
      run_id: def.runId,
      doc_id: docId,
      status: fs.length ? "flagged" : "cleared",
      counts_by_verdict: count(fs, (f) => f.verdict),
      changes_considered: 1,
      considered_by_class: { [def.changeClass]: 1 },
      cleared_reason: fs.length ? null : (def.clearedReasons[docId] ?? "No clause conflicts with the change"),
    });
  });

  const clearedN = candidates.filter((c) => c.outcome === "cleared").length;
  const aiFindings = findings.filter((f) => f.decided_by === "ai").length;
  const stats = {
    changes_raw: 1,
    by_class: { [def.changeClass]: 1 },
    substantive: 1,
    noise: 0,
    in_footprint: 1,
    obligation_changed: 1,
    candidates_by_path: count(candidates, (c) => c.match_path),
    findings_by_verdict: count(findings, (f) => f.verdict),
    clauses_cleared: clearedN,
    docs_flagged: rollups.filter((r) => r.status === "flagged").length,
    docs_cleared: rollups.filter((r) => r.status === "cleared").length,
    radar: { applicable: 0, screened_out: 0, unclear: 0 },
    decided_by: { rule: findings.length - aiFindings, ai: aiFindings },
    llm_calls: 1 + aiFindings + aiCleared,
  };

  const run: Run = runSchema.parse({
    run_id: def.runId,
    kind: "whatif",
    title: def.title,
    status: "succeeded",
    started_at: def.startedAt,
    finished_at: def.finishedAt,
    scenario_id: def.scenarioId,
    progress: null,
    stats,
  });

  return { change, candidates, findings, rollups, run };
}

function writeJson(rel: string, data: unknown) {
  const p = path.join(FX, rel);
  mkdirSync(path.dirname(p), { recursive: true });
  writeFileSync(p, JSON.stringify(data, null, 2) + "\n");
}

/* =================================================================== A === */

const S1_16 = versions["iac|170 IAC 4-1-16"].find((v) => v.snapshot === "S1")!.text;
const S2_A = S1_16.replace("at least fourteen (14) days before", "at least twenty (20) days before");
if (S2_A === S1_16) throw new Error("Preset A edit did not apply");

const OBL = "RPL-CMP-REG-001:OBL-2024-0036";
const P4 = "RPL-CS-PRO-004";
const CITE_E = "170 IAC 4-1-16(e)";

const presetA: PresetDef = {
  letter: "a",
  runId: "run_whatif_preset_a",
  scenarioId: "scn_preset_a",
  title: "170 IAC 4-1-16: notice period 14 → 20 days",
  citation: "170 IAC 4-1-16",
  editKind: "text_edit",
  s1: S1_16,
  s2: S2_A,
  heading: "Disconnection; prohibited disconnections; reconnection",
  changeClass: "substantive",
  characterization: {
    obligation_changed: true,
    direction: "tightened",
    summary:
      "The minimum written notice before a residential disconnection for nonpayment is lengthened from fourteen (14) days to twenty (20) days. Every other subsection is unchanged.",
    value_changes: [{ label: "Residential disconnection notice period", old: "14", new: "20", unit: "days" }],
  },
  disposition: "obligation_changed",
  dispositionReason:
    "Subsection (e) now requires twenty (20) days of written notice. Clauses that state, schedule, audit or print the 14-day period need review.",
  startedAt: "2026-10-07T14:02:11Z",
  finishedAt: "2026-10-07T14:02:12Z",
  clearedReasons: {
    "RPL-DO-PLN-002": "The only 14-day figures are vegetation-work notices governed by a different rule.",
  },
  findings: [
    {
      clause: OBL,
      verdict: "review",
      severity: "medium",
      type: "register_control_update",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "advance notice to customer",
      to: "advance notice to customer (20 days)",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "advance notice to customer",
      rationale:
        "The register row obliges RPL to give advance notice under 170 IAC 4-1-16 and names the Disconnection Procedure as its implementation. The notice period it monitors is now 20 days, so the control description and monitoring method should state the new period.",
    },
    {
      clause: `${P4}:8.2`,
      verdict: "action_required",
      severity: "high",
      type: "value_mismatch",
      by: "rule",
      conf: 1,
      match: "register_hop",
      path: [sec("170 IAC 4-1-16", CITE_E), { kind: "register_row", ref: OBL, label: "OBL-2024-0036" }, nodeFor(`${P4}:8.2`)],
      propagatedFrom: 1,
      from: "fourteen (14) days prior written notice",
      to: "twenty (20) days prior written notice",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "fourteen (14) days prior written notice",
      rationale:
        "Section 8.2 is the procedure's statement of the residential notice period and it still says 14 days. Reached from register row OBL-2024-0036; fixing this sentence resolves the register finding's implementation gap.",
    },
    {
      clause: `${P4}:3.7`,
      verdict: "action_required",
      severity: "medium",
      type: "value_mismatch",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "at least fourteen (14) days before the proposed disconnection date",
      to: "at least twenty (20) days before the proposed disconnection date",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "at least fourteen (14) days before the proposed disconnection date",
      rationale:
        "The definition of the disconnect notice hard-codes 14 days and cites 170 IAC 4-1-16(e) directly. It must match the rule's new minimum.",
    },
    {
      clause: `${P4}:T6-3`,
      verdict: "action_required",
      severity: "medium",
      type: "value_mismatch",
      by: "rule",
      conf: 0.97,
      match: "direct_section",
      from: "14-day notice period begins",
      to: "20-day notice period begins",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "14-day notice period begins (170 IAC 4-1-16(e))",
      rationale:
        "The collection-cycle table says the notice generated on Day 18 starts a 14-day period. With a 20-day minimum the CIS batch logic and this table need to change together.",
    },
    {
      clause: `${P4}:T7-1`,
      verdict: "review",
      severity: "medium",
      type: "value_mismatch",
      by: "rule",
      conf: 0.95,
      match: "direct_section",
      from: "proper 14-day notice mailed",
      to: "proper 20-day notice mailed",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "proper 14-day notice mailed",
      rationale:
        "The eligibility decision table allows disconnection when a proper 14-day notice was mailed. Confirm whether the system rule that evaluates this row also needs the new period.",
    },
    {
      clause: `${P4}:T6-5`,
      verdict: "review",
      severity: "medium",
      type: "restated_value",
      by: "ai",
      conf: 0.71,
      match: "value_echo",
      path: [sec("170 IAC 4-1-16", "Restated value: 14 days"), nodeFor(`${P4}:T6-5`)],
      verified: false,
      from: "Day 32 (Day 18 + 14 days notice)",
      to: "Day 38 (Day 18 + 20 days notice)",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: null,
      cqLoose: "Day 18 + 14-day notice",
      rationale:
        "This row never cites the rule, but its day count (Day 18 + 14 days) restates the old notice period. The wording the model quoted could not be matched exactly in the clause, so confirm the evidence before acting.",
    },
    {
      clause: `${P4}:16.3`,
      verdict: "action_required",
      severity: "medium",
      type: "restated_value",
      by: "ai",
      conf: 0.88,
      match: "value_echo",
      path: [sec("170 IAC 4-1-16", "Restated value: 14 days"), nodeFor(`${P4}:16.3`)],
      from: "at least 14 days before disconnect date",
      to: "at least 20 days before disconnect date",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "at least 14 days before disconnect date",
      rationale:
        "The monthly audit tests whether the notice went out at least 14 days before disconnection. Left unchanged, the audit would pass notices that are now too short.",
    },
    {
      clause: `${P4}:App-A.F6`,
      verdict: "review",
      severity: "medium",
      type: "form_content",
      by: "ai",
      conf: 0.82,
      match: "register_hop",
      path: [
        sec("170 IAC 4-1-16", CITE_E),
        { kind: "register_row", ref: OBL, label: "OBL-2024-0036" },
        nodeFor(`${P4}:8.2`),
        { kind: "form_field", ref: `${P4}:App-A.F6`, label: "Notice letter field App-A.F6" },
      ],
      propagatedFrom: 2,
      from: "Proposed Disconnection Date (notice date + 14 days)",
      to: "Proposed Disconnection Date (notice date + 20 days)",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "A.F6 — Proposed Disconnection Date",
      rationale:
        "The Proposed Disconnection Date printed on notice letter CS-F-012 is computed from the notice date plus the notice period (section 8.2). Once 8.2 changes, the date this field shows must move out by six more days.",
    },
    {
      clause: `${P4}:T4-4`,
      verdict: "update_citation",
      severity: "low",
      type: "stale_reference",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "170 IAC 4-1-16",
      to: "170 IAC 4-1-16 (as amended)",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "170 IAC 4-1-16",
      rationale:
        "The Regulatory Basis table lists the rule as the authority for notice content and timing. Update the entry and the document's law-as-of marker when the section text is revised.",
    },
    {
      clause: `${P4}:2.3`,
      verdict: "info",
      severity: "low",
      type: "restated_value",
      by: "rule",
      conf: 0.95,
      match: "direct_section",
      from: "The 14-day prior written notice requirement",
      to: "The 20-day prior written notice requirement",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "The 14-day prior written notice requirement at 170 IAC 4-1-16(e)",
      rationale:
        "The scope note names the 14-day residential requirement only to exclude non-residential accounts. Behaviour does not change, but the figure should be corrected for consistency.",
    },
    {
      clause: `${P4}:8.11`,
      verdict: "info",
      severity: "low",
      type: "restated_value",
      by: "rule",
      conf: 0.95,
      match: "direct_section",
      from: "the 14-day residential notice",
      to: "the 20-day residential notice",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "do not receive the 14-day residential notice required by 170 IAC 4-1-16(e)",
      rationale:
        "Non-residential accounts remain on the tariff timeline, so the process is unchanged. The sentence quotes the old residential period and should be updated.",
    },
    {
      clause: "RPL-REG-CAL-2025:EVT-2025-0041",
      verdict: "review",
      severity: "medium",
      type: "monitoring_update",
      by: "rule",
      conf: 0.95,
      match: "direct_section",
      from: "required notice timelines and procedures",
      to: "required notice timelines (20 days) and procedures",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "required notice timelines and procedures",
      rationale:
        "The monthly monitoring event checks compliance with the notice timelines in 170 IAC 4-1-16. The checklist behind it should be updated to test for 20 days. This calendar was approved after the rule's publication date, so it was already out of date when approved.",
    },
    {
      clause: "RPL-REG-CAL-2025:EVT-2025-0031",
      verdict: "info",
      severity: "low",
      type: "scope_note",
      by: "rule",
      conf: 0.9,
      match: "direct_rule",
      from: "all 170 IAC Articles 1 and 4 obligations",
      to: "all 170 IAC Articles 1 and 4 obligations (including the 20-day disconnection notice)",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "covering all 170 IAC Articles 1 and 4 obligations",
      rationale:
        "The annual self-assessment covers every obligation under 170 IAC 4-1, which now includes the longer disconnection notice. No wording must change, but the assessor should add it to the checklist.",
    },
    {
      clause: "RPL-TAR-GRR-012:R13.3",
      verdict: "action_required",
      severity: "high",
      type: "value_mismatch",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "without fourteen (14) days prior written notice",
      to: "without twenty (20) days prior written notice",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "without fourteen (14) days prior written notice",
      rationale:
        "The filed tariff states the 14-day residential notice and cites 170 IAC 4-1-16(e). A tariff revision would have to be filed with the commission, so this needs the longest lead time of any finding.",
    },
    {
      clause: "RPL-CS-PRO-011:8.5",
      verdict: "action_required",
      severity: "medium",
      type: "value_mismatch",
      by: "rule",
      conf: 0.95,
      match: "direct_section",
      from: "a 14-day written notice was sent",
      to: "a 20-day written notice was sent",
      s1q: "at least fourteen (14) days before the proposed discontinuance date",
      s2q: "at least twenty (20) days before the proposed discontinuance date",
      cq: "a 14-day written notice was sent to residential customers",
      rationale:
        "The complaint specialist's checklist for disconnection complaints verifies that a 14-day notice was sent and cites 170 IAC 4-1-16(e). The check must use 20 days. This procedure was approved after the rule's publication date.",
    },
  ],
  cleared: [
    { clause: `${P4}:8.3`, match: "direct_section", skip: "no_period_stated", rationale: "Delivery method (first-class mail or personal delivery) is unchanged; no day count appears in this clause." },
    { clause: `${P4}:8.4`, match: "direct_section", skip: "no_period_stated", rationale: "Language and format requirements for the notice are unchanged by the edit." },
    { clause: `${P4}:8.5`, match: "direct_section", skip: "no_period_stated", rationale: "Content element (proposed disconnection date) is unchanged. The date itself is governed by section 8.2 and the notice-letter field, which are flagged." },
    { clause: `${P4}:9.5`, match: "direct_section", skip: "different_subsection", rationale: "Cites subsection (c) (10-day medical postponement). The edit changes only subsection (e).", ai: true },
    { clause: `${P4}:9.6`, match: "direct_section", skip: "different_subsection", rationale: "Cites subsection (c) (renewal of the 10-day postponement). Not touched by the edit.", ai: true },
    { clause: `${P4}:12.6`, match: "direct_section", skip: "different_subsection", rationale: "Cites subsection (d) (time-of-day limits). Not touched by the edit." },
    { clause: `${P4}:13.3`, match: "direct_section", skip: "different_subsection", rationale: "Cites subsection (g) (reconnection timing). Not touched by the edit." },
    {
      clause: `${P4}:App-A.F5`,
      match: "register_hop",
      path: [sec("170 IAC 4-1-16", CITE_E), { kind: "register_row", ref: OBL, label: "OBL-2024-0036" }, nodeFor(`${P4}:8.2`), nodeFor(`${P4}:App-A.F5`)],
      skip: "label_only",
      rationale: "The Notice Date field is the date the letter is generated. Only the Proposed Disconnection Date (A.F6) depends on the notice period.",
    },
    { clause: `${P4}:App-A.F13`, match: "value_echo", skip: "different_period", rationale: "States a ten (10) day medical postponement, which comes from subsection (c), not the notice period.", ai: true },
    { clause: `${P4}:T7-4`, match: "direct_section", skip: "different_subsection", rationale: "Decision-table row for the 10-day medical postponement under subsection (c)." },
    { clause: "RPL-CMP-REG-001:A.1.tbl1.r4", match: "direct_section", skip: "no_period_stated", rationale: "Top-20 excerpt lists the obligation by citation only and states no period. The underlying row OBL-2024-0036 carries the flag." },
    { clause: "RPL-CMP-REG-001:11.2.tbl1.r2", match: "direct_rule", skip: "range_reference", rationale: "Maps the procedure to a range of rules (4-1-11 through 4-1-16) without stating any period." },
    { clause: "RPL-REG-CAL-2025:EVT-2025-0006", match: "direct_section", skip: "completed_event", rationale: "Q1 review that was completed on 2025-02-28; a historical record that does not need to change." },
    { clause: "RPL-TAR-GRR-012:R13.1", match: "direct_section", skip: "different_subsection", rationale: "Cites subsection (a) (customer-requested disconnection, three days)." },
    { clause: "RPL-TAR-GRR-012:R13.2", match: "direct_section", skip: "different_subsection", rationale: "Cites subsection (b) (disconnection without notice for hazards or fraud)." },
    { clause: "RPL-TAR-GRR-012:R13.4", match: "direct_section", skip: "different_subsection", rationale: "Cites subsection (d) (permitted hours and days)." },
    { clause: "RPL-TAR-GRR-012:R13.7", match: "direct_section", skip: "different_subsection", rationale: "Cites subsection (c) (ten-day medical postponement)." },
    {
      clause: "RPL-CS-PRO-011:T4-4",
      match: "direct_section",
      skip: "no_period_stated",
      rationale: "Regulatory-basis row describing complaint handling for service-off cases; states no notice period.",
    },
    { clause: "RPL-CS-PRO-011:11.6", match: "value_echo", skip: "different_rule_value", rationale: "The 14 days is RPL's response time to Consumer Affairs under 170 IAC 16-1-5(c)(3), an unrelated rule.", ai: true },
    { clause: "RPL-DO-PLN-002:T11.r1", match: "value_echo", skip: "different_rule_value", rationale: "The 14-day figure is the regulatory minimum for vegetation-work notices, not the disconnection notice.", ai: true },
    { clause: "RPL-DO-PLN-002:T19.r4", match: "value_echo", skip: "different_rule_value", rationale: "KPI measures vegetation notice lead time; unrelated to disconnection notice.", ai: true },
  ],
};

/* =================================================================== B === */

const S1_166 = versions["iac|170 IAC 4-1-16.6"].find((v) => v.snapshot === "S1")!.text;
const S2_B = "170 IAC 4-1-16.6 [Repealed]";
const SEC166 = "170 IAC 4-1-16.6";
const TAR = "RPL-TAR-GRR-012";
const B_S1Q = "shall not discontinue residential electric service for nonpayment during the period December 1 through March 15";
const B_S2Q = "[Repealed]";

const presetB: PresetDef = {
  letter: "b",
  runId: "run_whatif_preset_b",
  scenarioId: "scn_preset_b",
  title: "Repeal 170 IAC 4-1-16.6 (winter protection)",
  citation: SEC166,
  editKind: "repeal",
  s1: S1_166,
  s2: S2_B,
  heading: "Home energy assistance; disconnection to recipients",
  changeClass: "repealed",
  characterization: {
    obligation_changed: true,
    direction: "removed",
    summary:
      "The December 1 through March 15 ban on disconnecting energy-assistance recipients is repealed. Clauses that cite this section as their authority now point at a rule that no longer exists.",
    value_changes: [{ label: "Winter disconnection protection period", old: "December 1 – March 15", new: "repealed", unit: null }],
  },
  disposition: "obligation_changed",
  dispositionReason:
    "The section is repealed. Clauses that cite it must drop the citation or restate the protection as company policy.",
  startedAt: "2026-10-07T14:05:40Z",
  finishedAt: "2026-10-07T14:05:41Z",
  clearedReasons: {
    "RPL-CMP-REG-001": "The register row cites the parent rule 170 IAC 4-1-16 and does not mention the repealed section.",
    "RPL-REG-CAL-2025": "The monitoring event cites 170 IAC 4-1-16 and 4-1-17, not the repealed section.",
  },
  findings: [
    {
      clause: `${P4}:10.2`,
      verdict: "action_required",
      severity: "high",
      type: "repealed_authority",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "(170 IAC 4-1-16.6(a))",
      to: "(RPL policy; 170 IAC 4-1-16.6 repealed)",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "(170 IAC 4-1-16.6(a))",
      rationale:
        "Section 10.2 presents the winter protection as a legal requirement and cites the repealed subsection as its basis. RPL must decide whether to keep the protection as company policy and, if so, restate its authority.",
    },
    {
      clause: `${P4}:10.3`,
      verdict: "update_citation",
      severity: "medium",
      type: "repealed_authority",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "(170 IAC 4-1-16.6(b))",
      to: "(RPL policy)",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "(170 IAC 4-1-16.6(b))",
      rationale: "Application-pending protection cites subsection (b) of the repealed section. Remove or replace the citation once the policy decision for 10.2 is made.",
    },
    {
      clause: `${P4}:10.8`,
      verdict: "update_citation",
      severity: "low",
      type: "repealed_authority",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "(170 IAC 4-1-16.6(c))",
      to: "(RPL policy)",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "(170 IAC 4-1-16.6(c))",
      rationale: "The exceptions to winter protection cite subsection (c) of the repealed section.",
    },
    {
      clause: `${P4}:T7-6`,
      verdict: "update_citation",
      severity: "medium",
      type: "repealed_authority",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "170 IAC 4-1-16.6(a)",
      to: "RPL policy",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "170 IAC 4-1-16.6(a)",
      rationale: "The eligibility decision-table row blocks disconnection of energy-assistance recipients and cites the repealed subsection.",
    },
    {
      clause: `${P4}:T7-7`,
      verdict: "update_citation",
      severity: "medium",
      type: "repealed_authority",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "170 IAC 4-1-16.6(b)",
      to: "RPL policy",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "170 IAC 4-1-16.6(b)",
      rationale: "The decision-table row for pending applications cites the repealed subsection (b).",
    },
    {
      clause: `${P4}:T4-5`,
      verdict: "review",
      severity: "low",
      type: "repealed_authority",
      by: "rule",
      conf: 0.95,
      match: "direct_section",
      from: "170 IAC 4-1-16.6 | Home energy assistance; disconnection to recipients",
      to: "Remove from Regulatory Basis, or mark as RPL policy",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "170 IAC 4-1-16.6",
      rationale: "The Regulatory Basis table lists the repealed section as authority for clauses 10.1 through 10.8. Review the table after those clauses are resolved.",
    },
    {
      clause: `${P4}:App-D.F5`,
      verdict: "review",
      severity: "medium",
      type: "form_content",
      by: "ai",
      conf: 0.82,
      match: "register_hop",
      path: [sec(SEC166), nodeFor(`${P4}:10.2`), { kind: "form_field", ref: `${P4}:App-D.F5`, label: "Protection confirmation letter App-D.F5" }],
      propagatedFrom: 1,
      from: "(170 IAC 4-1-16.6)",
      to: "(RPL energy assistance protection policy)",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "(170 IAC 4-1-16.6)",
      rationale: "The customer-facing protection confirmation letter tells the customer that RPL may not disconnect them, citing the repealed section. Wording depends on the decision for clause 10.2.",
    },
    {
      clause: `${TAR}:R13.6`,
      verdict: "review",
      severity: "high",
      type: "repealed_authority",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "Pursuant to 170 IAC 4-1-16.6(a)",
      to: "Pursuant to RPL's filed tariff",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "Pursuant to 170 IAC 4-1-16.6(a)",
      rationale: "The LIHEAP Winter Moratorium tariff rule is authorised by the repealed section. The tariff is on file with the commission, so any change needs a filing and cannot be made by editing the procedure alone.",
    },
    {
      clause: `${TAR}:R01.D25`,
      verdict: "update_citation",
      severity: "low",
      type: "repealed_authority",
      by: "rule",
      conf: 1,
      match: "direct_section",
      from: "Rule 13.6 and 170 IAC 4-1-16.6",
      to: "Rule 13.6",
      s1q: B_S1Q,
      s2q: B_S2Q,
      cq: "Rule 13.6 and 170 IAC 4-1-16.6",
      rationale: "The LIHEAP definition points customers to the repealed section as a source of winter protections.",
    },
  ],
  cleared: [
    { clause: `${P4}:1.2`, match: "direct_section", skip: "scope_statement", rationale: "Scope sentence lists the rules the procedure supports. No requirement depends on it; the citation is covered by the fixes to 10.2 through 10.8." },
    { clause: `${P4}:T4-4`, match: "direct_rule", skip: "different_section", rationale: "Regulatory-basis row for the parent rule 170 IAC 4-1-16, which is not repealed." },
    { clause: `${P4}:3.11`, match: "value_echo", skip: "independent_authority", rationale: "Defines an energy assistance recipient by status under IC 4-4-33, which remains in force.", ai: true },
    { clause: `${P4}:T7-5`, match: "direct_rule", skip: "different_section", rationale: "Decision-table row for second medical certificate under 170 IAC 4-1-16(c)." },
    { clause: "RPL-CMP-REG-001:OBL-2024-0036", match: "direct_rule", skip: "different_section", rationale: "Register row cites 170 IAC 4-1-16 (disconnection rules), not the repealed section. The notes column mentions the winter moratorium but the obligation itself is not affected." },
    { clause: "RPL-CMP-REG-001:A.1.tbl1.r4", match: "direct_rule", skip: "different_section", rationale: "Excerpt row cites 170 IAC 4-1-16 only." },
    { clause: "RPL-REG-CAL-2025:EVT-2025-0041", match: "direct_rule", skip: "different_section", rationale: "Monitoring event cites 170 IAC 4-1-16 and 4-1-17; winter protection is not mentioned." },
    { clause: `${TAR}:R13.2`, match: "direct_rule", skip: "different_section", rationale: "Cites 170 IAC 4-1-16(b) (hazard or fraud disconnection)." },
    { clause: `${TAR}:R13.7`, match: "direct_rule", skip: "different_section", rationale: "Cites 170 IAC 4-1-16(c) (medical postponement)." },
    { clause: "RPL-CS-PRO-011:T4-4", match: "direct_rule", skip: "different_section", rationale: "Regulatory-basis row for complaint handling under 170 IAC 4-1-16; the repealed section is not referenced." },
  ],
};

/* ================================================================ output === */

const defs = [presetA, presetB];
for (const def of defs) {
  const out = build(def);
  const dir = `engine/run_whatif_preset_${def.letter}`;
  writeJson(`${dir}/changes.json`, [out.change]);
  writeJson(`${dir}/candidates.json`, out.candidates);
  writeJson(`${dir}/findings.json`, out.findings);
  writeJson(`${dir}/rollups.json`, out.rollups);
  writeJson(`${dir}/radar.json`, []);
  writeJson(`${dir}/run.json`, out.run);
}

const scenarios = defs.map((def) =>
  scenarioSchema.parse({
    scenario_id: def.scenarioId,
    title: def.title,
    citation: def.citation,
    source_system: "iac",
    edit_kind: def.editKind,
    edited_text: def.editKind === "text_edit" ? def.s2 : null,
    is_preset: true,
    last_run_id: def.runId,
  }),
);
writeJson("engine/scenarios.json", scenarios);
console.log("Wrote preset fixtures for", defs.map((d) => d.runId).join(", "));

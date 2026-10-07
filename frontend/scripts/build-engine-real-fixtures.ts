/**
 * Engine fixture builder for the REAL WAVE run (run_kb_real), the BASELINE run, score.json and runs.json.
 * Run manually: `pnpm exec tsx scripts/build-engine-real-fixtures.ts`. Never wired into build/dev/CI.
 *
 * Inputs: fixtures/kb/{sections,versions}.json, fixtures/company/{documents,profile}.json and clauses/*.json.
 * Output is deterministic. All findings/candidates/radar items are INVENTED demo scenarios.
 * diff_segments are produced with jsdiff (diffWordsWithSpace) from s1_text / s2_text, never by hand.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { diffWordsWithSpace } from "diff";
import {
  candidateSchema,
  changeRecordSchema,
  docRollupSchema,
  radarItemSchema,
  runSchema,
  scoreReportSchema,
  type Candidate,
  type ChangeRecord,
  type DiffSegment,
  type DocRollup,
  type RadarItem,
  type Run,
} from "../lib/api/schemas/engine";
import type { ChangeClass } from "../lib/api/schemas/common";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, "..");
const FX = path.join(FRONTEND, "fixtures");
const RUN_ID = "run_kb_real";
const BASE_ID = "run_baseline";

const readJson = <T>(p: string): T => JSON.parse(readFileSync(path.join(FX, p), "utf8")) as T;

type Section = {
  citation: string;
  source_system: "iac" | "cfr";
  title_number: string;
  rule_key: string;
  heading: string;
  body_text: string;
  status: string;
  owning_agency: string;
  amendment_source: string | null;
};
type Version = { snapshot: string; snapshot_date: string; text: string };
type ClauseRow = {
  clause_id: string;
  doc_id: string;
  unit_kind: string;
  heading_path: string[];
  text_raw: string;
  row_cells: Record<string, string> | null;
};

const sections = readJson<Section[]>("kb/sections.json");
const versions = readJson<Record<string, Version[]>>("kb/versions.json");
const secBy = new Map(sections.map((s) => [s.citation, s]));

/* ------------------------------------------------------------------ helpers */

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
const changeId = (_ss: string, cit: string) => `chg-${slug(cit)}`;

function segments(s1: string, s2: string): DiffSegment[] {
  const out: DiffSegment[] = [];
  for (const p of diffWordsWithSpace(s1, s2)) {
    const op = p.added ? "insert" : p.removed ? "delete" : "equal";
    const last = out[out.length - 1];
    if (last && last.op === op) last.text += p.value;
    else out.push({ op, text: p.value });
  }
  return out;
}

const IAC_FOOTER = (cit: string, extra = "") =>
  `(${cit.startsWith("326") || cit.startsWith("327") ? "Indiana Department of Environmental Management" : "Indiana Utility Regulatory Commission"}; ${cit}; filed Mar 3, 2008, 3:20 p.m.: 31 IR 1722${extra})`;

function iacText(cit: string, heading: string, body: string, extraFooter = ""): string {
  return `${cit} ${heading}\n\n${body}\n\n${IAC_FOOTER(cit, extraFooter)}`;
}

const S = {
  iac: { s1: "2024-12-31", s2: "2025-12-31" },
  cfr: { s1: "2025-01-02", s2: "2026-10-02" },
} as const;

let dinSeq = 100;
const iacDin = (date: string) => `${date.replace(/-/g, "")}-IR-170${date.slice(2, 4)}${String(++dinSeq).padStart(4, "0")}NRA`;

/* ------------------------------------------------------------------ in-footprint changes */

type FootSpec = {
  cit: string;
  cls: ChangeClass;
  pub: string;
  basis: string;
  summary: string;
  reason: string;
  disposition: string;
};

const FOOT: FootSpec[] = [
  {
    cit: "170 IAC 4-1-13",
    cls: "cosmetic",
    pub: "2024-12-18",
    basis: "Indiana Register publication of the readoption notice",
    summary: "Only a readoption stamp line was added to the history note; no operative text changed.",
    reason: "Only the readoption stamp changed. Every citing clause was checked and cleared.",
    disposition: "Cleared — cosmetic",
  },
  {
    cit: "170 IAC 4-1-16",
    cls: "substantive",
    pub: "2025-03-12",
    basis: "Indiana Register publication (IURC-RM-24-11 readoption)",
    summary:
      'Paragraphs (c) and (d) now say "may not" instead of "shall not". The readoption notice states the prohibitions are unchanged, so the legal effect is the same.',
    reason: 'Style-only rewording ("shall not" to "may not"); same legal effect. Every citing clause was checked and cleared.',
    disposition: "Cleared — same legal effect",
  },
  {
    cit: "170 IAC 1-6-3",
    cls: "punctuation_only",
    pub: "2025-02-19",
    basis: "Indiana Register publication of the readoption notice",
    summary: "Commas were added in paragraph (a). No requirement, timing or actor changed.",
    reason: "Punctuation only. Every citing clause was checked and cleared.",
    disposition: "Cleared — punctuation only",
  },
  {
    cit: "170 IAC 1-6-4",
    cls: "cosmetic",
    pub: "2024-12-18",
    basis: "Indiana Register publication of the readoption notice",
    summary: "Only a readoption stamp line was added to the history note; no operative text changed.",
    reason: "Only the readoption stamp changed. Every citing clause was checked and cleared.",
    disposition: "Cleared — cosmetic",
  },
  {
    cit: "170 IAC 1-6-5",
    cls: "cross_ref_only",
    pub: "2025-02-19",
    basis: "Indiana Register publication of the readoption notice",
    summary: 'A cross-reference was made more precise ("170 IAC 1-6-2" became "170 IAC 1-6-2(11)"). The obligation is unchanged.',
    reason: "Cross-reference refinement only. Every citing clause was checked and cleared.",
    disposition: "Cleared — cross-reference only",
  },
  {
    cit: "170 IAC 16-1-4",
    cls: "punctuation_only",
    pub: "2025-04-23",
    basis: "Indiana Register publication of the readoption notice",
    summary: "Serial commas were added in paragraph (b). The ten-day response time is unchanged.",
    reason: "Punctuation only. Every citing clause was checked and cleared.",
    disposition: "Cleared — punctuation only",
  },
  {
    cit: "170 IAC 16-1-5",
    cls: "cosmetic",
    pub: "2024-12-18",
    basis: "Indiana Register publication of the readoption notice",
    summary: "Only a readoption stamp line was added to the history note; no operative text changed.",
    reason: "Only the readoption stamp changed. Every citing clause was checked and cleared.",
    disposition: "Cleared — cosmetic",
  },
  {
    cit: "170 IAC 16-1-7",
    cls: "cross_ref_only",
    pub: "2025-04-23",
    basis: "Indiana Register publication of the readoption notice",
    summary: 'A statute reference was made more precise ("IC 8-1-1-3" became "IC 8-1-1-3(a)"). The reporting duty is unchanged.',
    reason: "Cross-reference refinement only. Every citing clause was checked and cleared.",
    disposition: "Cleared — cross-reference only",
  },
];

/* ------------------------------------------------------------------ out-of-footprint changes */

type Sub = {
  cit: string;
  cls: ChangeClass;
  dir?: "tightened" | "relaxed" | "new_requirement" | "removed" | "clarified";
  intro?: string;
  p1?: string;
  p2?: string;
  label?: string;
  old?: string;
  neu?: string;
  unit?: string;
  summary?: string;
  quote?: string;
  pub?: string;
  basis?: string;
  fromVersions?: boolean;
};

const SUBS: Sub[] = [
  // --- demo anchors (S1/S2 text comes from versions.json)
  {
    cit: "326 IAC 2-8-4",
    cls: "substantive",
    dir: "relaxed",
    fromVersions: true,
    label: "Emergency engine maintenance and testing hours",
    old: "50",
    neu: "100",
    unit: "hours per year",
    summary: "The annual cap on maintenance-check and readiness-test operation of emergency and standby engines rises from 50 to 100 hours.",
    quote: "limit operation for maintenance checks and readiness testing",
    pub: "2025-02-05",
    basis: "Effective date of IDEM-LSA-24-301 (published 2024-11-06)",
  },
  {
    cit: "40 CFR 60.4320",
    cls: "substantive",
    dir: "tightened",
    fromVersions: true,
    label: "NOx limit, natural gas turbines",
    old: "25",
    neu: "15",
    unit: "ppm at 15% O2",
    summary: "The nitrogen oxides limit for new natural-gas-fired stationary combustion turbines falls from 25 ppm to 15 ppm.",
    quote: "in excess of 15 ppm at 15 percent oxygen",
    pub: "2025-06-10",
    basis: "Federal Register publication date (FR 2025-06114)",
  },
  {
    cit: "18 CFR 35.28",
    cls: "substantive",
    dir: "tightened",
    fromVersions: true,
    label: "Market monitor flaw report deadline",
    old: "30",
    neu: "20",
    unit: "days",
    summary: "A market monitoring unit must now report an identified market design flaw within 20 days instead of 30.",
    quote: "within twenty (20) days",
    pub: "2026-06-17",
    basis: "Federal Register publication date (FR 2026-06091)",
  },
  // --- further substantive
  {
    cit: "326 IAC 2-8-9",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) The permittee shall keep records needed to show compliance with the limits in this rule.",
    p1: "(b) Records shall be retained for three (3) years from the date of the entry.",
    p2: "(b) Records shall be retained for five (5) years from the date of the entry.",
    label: "FESOP record retention",
    old: "3",
    neu: "5",
    unit: "years",
    summary: "FESOP compliance records must be kept for five years instead of three.",
    quote: "retained for five (5) years",
    pub: "2025-07-16",
  },
  {
    cit: "326 IAC 5-1-2",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) This section sets the opacity limits for visible emissions from a stack or process.",
    p1: "(b) Visible emissions shall not exceed an average of forty percent (40%) opacity in six (6) consecutive minutes.",
    p2: "(b) Visible emissions shall not exceed an average of thirty percent (30%) opacity in six (6) consecutive minutes.",
    label: "Opacity limit",
    old: "40",
    neu: "30",
    unit: "percent opacity",
    summary: "The six-minute average opacity limit tightens from 40 percent to 30 percent.",
    quote: "thirty percent (30%) opacity",
    pub: "2025-08-27",
  },
  {
    cit: "326 IAC 6-3-2",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) This section limits particulate emissions from manufacturing processes.",
    p1: "(b) Particulate emissions shall not exceed 0.03 grain per dry standard cubic foot of exhaust.",
    p2: "(b) Particulate emissions shall not exceed 0.02 grain per dry standard cubic foot of exhaust.",
    label: "Particulate emission limit",
    old: "0.03",
    neu: "0.02",
    unit: "grain/dscf",
    summary: "The particulate emission limit for manufacturing processes tightens from 0.03 to 0.02 grain per dry standard cubic foot.",
    quote: "0.02 grain per dry standard cubic foot",
    pub: "2025-09-10",
  },
  {
    cit: "326 IAC 10-1-1",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) This rule applies to a source in a county designated for NOx reduction.",
    p1: "(b) A source that emits twenty-five (25) tons or more of NOx per year is subject to this rule.",
    p2: "(b) A source that emits fifteen (15) tons or more of NOx per year is subject to this rule.",
    label: "NOx applicability threshold",
    old: "25",
    neu: "15",
    unit: "tons per year",
    summary: "The NOx rule now applies to sources emitting 15 tons per year or more, down from 25.",
    quote: "fifteen (15) tons or more of NOx per year",
    pub: "2025-10-08",
  },
  {
    cit: "327 IAC 5-4-6",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) This section governs stormwater discharges from construction activity.",
    p1: "(b) A site disturbing one (1) acre or more shall submit a notice of intent before land disturbance begins.",
    p2: "(b) A site disturbing one-half (0.5) acre or more shall submit a notice of intent before land disturbance begins.",
    label: "Construction stormwater notice threshold",
    old: "1",
    neu: "0.5",
    unit: "acres",
    summary: "A notice of intent is now needed for sites disturbing half an acre or more, instead of one acre.",
    quote: "one-half (0.5) acre or more",
    pub: "2026-01-14",
  },
  {
    cit: "327 IAC 15-6-1",
    cls: "substantive",
    dir: "new_requirement",
    intro: "(a) This rule covers stormwater discharges associated with industrial activity.",
    p1: "(b) A permittee shall collect quarterly stormwater samples.",
    p2: "(b) A permittee shall collect quarterly stormwater samples and shall post each result on a public website within thirty (30) days.",
    label: "Public posting of sample results",
    old: "none",
    neu: "30",
    unit: "days",
    summary: "Industrial stormwater permittees must also post each sample result publicly within 30 days.",
    quote: "post each result on a public website",
    pub: "2026-02-04",
  },
  {
    cit: "40 CFR 63.6603",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) This section sets emission limits for existing stationary reciprocating internal combustion engines.",
    p1: "(b) An owner or operator of an emergency engine shall limit carbon monoxide to 23 ppmvd at 15 percent oxygen.",
    p2: "(b) An owner or operator of an emergency engine shall limit carbon monoxide to 20 ppmvd at 15 percent oxygen.",
    label: "CO limit, emergency engines",
    old: "23",
    neu: "20",
    unit: "ppmvd at 15% O2",
    summary: "The carbon monoxide limit for emergency stationary engines tightens from 23 to 20 ppmvd.",
    quote: "limit carbon monoxide to 20 ppmvd",
    pub: "2025-10-21",
    basis: "Federal Register publication date (FR 2025-10190)",
  },
  {
    cit: "40 CFR 60.5520",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) This section sets carbon dioxide standards for affected fossil fuel-fired electric generating units.",
    p1: "(b) An affected unit shall not discharge more than 1,400 lb CO2 per MWh gross output.",
    p2: "(b) An affected unit shall not discharge more than 1,200 lb CO2 per MWh gross output.",
    label: "CO2 output standard",
    old: "1,400",
    neu: "1,200",
    unit: "lb CO2/MWh",
    summary: "The CO2 standard for affected generating units tightens from 1,400 to 1,200 lb per MWh.",
    quote: "more than 1,200 lb CO2 per MWh",
    pub: "2026-05-28",
    basis: "Federal Register publication date (FR 2026-05022)",
  },
  {
    cit: "40 CFR 63.10005",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) This section sets compliance requirements for electric utility steam generating units.",
    p1: "(b) An owner or operator shall demonstrate compliance on a 90-day rolling average basis.",
    p2: "(b) An owner or operator shall demonstrate compliance on a 30-day rolling average basis.",
    label: "Compliance averaging period",
    old: "90",
    neu: "30",
    unit: "days",
    summary: "Compliance for steam generating units is judged on a 30-day rolling average instead of 90 days.",
    quote: "30-day rolling average basis",
    pub: "2026-03-19",
    basis: "Federal Register publication date (FR 2026-00977)",
  },
  {
    cit: "40 CFR 72.90",
    cls: "substantive",
    dir: "relaxed",
    intro: "(a) The designated representative shall submit an annual reconciliation of allowances held and emissions.",
    p1: "(b) The reconciliation is due by March 1 following the compliance year.",
    p2: "(b) The reconciliation is due by March 31 following the compliance year.",
    label: "Annual reconciliation due date",
    old: "March 1",
    neu: "March 31",
    unit: null as unknown as string,
    summary: "The Acid Rain annual reconciliation deadline moves from March 1 to March 31.",
    quote: "due by March 31",
    pub: "2026-04-02",
    basis: "Federal Register publication date (FR 2026-03611)",
  },
  {
    cit: "18 CFR 35.13",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) A public utility that changes a rate schedule shall file the change under this section.",
    p1: "(b) A filing shall be made at least sixty (60) days and not more than one hundred twenty (120) days before the proposed effective date.",
    p2: "(b) A filing shall be made at least sixty (60) days and not more than ninety (90) days before the proposed effective date.",
    label: "Maximum advance filing window",
    old: "120",
    neu: "90",
    unit: "days",
    summary: "A rate schedule change can be filed no earlier than 90 days before its effective date, down from 120.",
    quote: "not more than ninety (90) days",
    pub: "2026-03-05",
    basis: "Federal Register publication date (FR 2026-02755)",
  },
  {
    cit: "18 CFR 35.36",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) A transmission provider shall process generator interconnection requests under this section.",
    p1: "(b) The provider shall complete each system impact study within ninety (90) days of a complete request.",
    p2: "(b) The provider shall complete each system impact study within sixty (60) days of a complete request.",
    label: "System impact study deadline",
    old: "90",
    neu: "60",
    unit: "days",
    summary: "Transmission providers must finish generator system impact studies in 60 days instead of 90.",
    quote: "within sixty (60) days of a complete request",
    pub: "2026-08-20",
    basis: "Federal Register publication date (FR 2026-08812)",
  },
  {
    cit: "18 CFR 37.6",
    cls: "substantive",
    dir: "new_requirement",
    intro: "(a) A transmission provider shall post specified information on its OASIS.",
    p1: "(b) The provider shall post planned outages when they are scheduled.",
    p2: "(b) The provider shall post planned outages when they are scheduled and shall update the posting within one (1) business day of any change.",
    label: "Outage posting update",
    old: "none",
    neu: "1",
    unit: "business day",
    summary: "OASIS outage postings must be updated within one business day of any change.",
    quote: "within one (1) business day of any change",
    pub: "2026-01-29",
    basis: "Federal Register publication date (FR 2026-00412)",
  },
  {
    cit: "170 IAC 2-1-2",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) The commission shall assess a utility fee each year on gross intrastate operating revenues.",
    p1: "(b) The fee rate is one-tenth of one percent (0.10%) of gross intrastate operating revenues.",
    p2: "(b) The fee rate is twelve-hundredths of one percent (0.12%) of gross intrastate operating revenues.",
    label: "Utility fee rate",
    old: "0.10",
    neu: "0.12",
    unit: "percent of revenues",
    summary: "The annual IURC utility fee rate rises from 0.10 to 0.12 percent of gross intrastate revenues.",
    quote: "twelve-hundredths of one percent (0.12%)",
    pub: "2025-09-24",
  },
  {
    cit: "170 IAC 6-1-1",
    cls: "substantive",
    dir: "new_requirement",
    intro: "(a) This rule applies to an electric utility that offers an energy efficiency program.",
    p1: "(b) A utility shall file an annual program report with the commission.",
    p2: "(b) A utility shall file an annual program report with the commission and shall include verified savings by customer class.",
    label: "Verified savings by customer class",
    old: "none",
    neu: "required",
    unit: null as unknown as string,
    summary: "Annual energy efficiency program reports must now break verified savings out by customer class.",
    quote: "verified savings by customer class",
    pub: "2025-11-12",
  },
  {
    cit: "170 IAC 3-1-1",
    cls: "substantive",
    dir: "tightened",
    intro: "(a) This rule applies to a gas utility that operates a pipeline in Indiana.",
    p1: "(b) A leak survey of each distribution main shall be completed every three (3) years.",
    p2: "(b) A leak survey of each distribution main shall be completed every two (2) years.",
    label: "Leak survey interval",
    old: "3",
    neu: "2",
    unit: "years",
    summary: "Gas distribution mains must be leak-surveyed every two years instead of every three.",
    quote: "every two (2) years",
    pub: "2025-05-14",
  },
  {
    cit: "170 IAC 5-1-1",
    cls: "substantive",
    dir: "relaxed",
    intro: "(a) This rule applies to a water or sewage utility regulated by the commission.",
    p1: "(b) A utility shall file a rate case notice sixty (60) days before filing.",
    p2: "(b) A utility shall file a rate case notice thirty (30) days before filing.",
    label: "Rate case notice lead time",
    old: "60",
    neu: "30",
    unit: "days",
    summary: "Water and sewage utilities may give rate case notice 30 days ahead instead of 60.",
    quote: "thirty (30) days before filing",
    pub: "2025-06-25",
  },
  // --- new sections
  {
    cit: "170 IAC 7-1-1",
    cls: "new_section",
    dir: "new_requirement",
    intro: "(a) This rule establishes the process for a customer load of one hundred (100) megawatts or more to interconnect to a utility system.",
    p1: "",
    p2: "(b) A utility shall provide a written interconnection study estimate within sixty (60) days of a complete application.",
    label: "New large load interconnection process",
    old: "none",
    neu: "60",
    unit: "days",
    summary: "New section creating a large load interconnection process with a 60-day study estimate.",
    quote: "within sixty (60) days of a complete application",
    pub: "2026-02-18",
    basis: "Indiana Register publication (IURC-RM-26-01)",
  },
  {
    cit: "326 IAC 12-1-1",
    cls: "new_section",
    dir: "new_requirement",
    intro: "(a) This section incorporates by reference the federal new source performance standards adopted after 2024.",
    p1: "",
    p2: "(b) An owner or operator of an affected facility shall comply with each incorporated standard as of its federal effective date.",
    label: "NSPS incorporation update",
    old: "none",
    neu: "incorporated",
    unit: null as unknown as string,
    summary: "New incorporation section brings recent federal NSPS standards into Indiana air rules.",
    quote: "comply with each incorporated standard",
    pub: "2026-03-26",
    basis: "Indiana Register publication (IDEM-LSA-26-090)",
  },
  {
    cit: "40 CFR 60.4333",
    cls: "new_section",
    dir: "new_requirement",
    intro: "(a) This section sets general compliance requirements for affected stationary combustion turbines.",
    p1: "",
    p2: "(b) The owner or operator shall operate and maintain each turbine and its emission controls in a manner consistent with good air pollution control practice.",
    label: "General turbine compliance duty",
    old: "none",
    neu: "required",
    unit: null as unknown as string,
    summary: "New paragraph set requires turbines and controls to be run per good air pollution control practice.",
    quote: "good air pollution control practice",
    pub: "2025-06-10",
    basis: "Federal Register publication date (FR 2025-06114)",
  },
  // --- repealed
  { cit: "326 IAC 2-3-1", cls: "repealed", dir: "removed", label: "Emission offset (obsolete)", summary: "Obsolete emission offset section repealed.", pub: "2025-04-09" },
  { cit: "326 IAC 1-7-1", cls: "repealed", dir: "removed", label: "Stack height (obsolete)", summary: "Obsolete stack height section repealed.", pub: "2025-04-09" },
  { cit: "327 IAC 16-1-1", cls: "repealed", dir: "removed", label: "Spill prevention (obsolete)", summary: "Obsolete spill prevention section repealed.", pub: "2025-08-13" },
  { cit: "327 IAC 4-1-1", cls: "repealed", dir: "removed", label: "Sludge disposal (obsolete)", summary: "Obsolete sludge disposal section repealed.", pub: "2025-08-13" },
  { cit: "40 CFR 72.95", cls: "repealed", dir: "removed", label: "Excess emissions penalty (obsolete)", summary: "Obsolete excess emissions penalty section removed from the CFR.", pub: "2026-02-10", basis: "Federal Register publication date (FR 2026-02140)" },
  { cit: "40 CFR 73.50", cls: "repealed", dir: "removed", label: "Auctions (obsolete)", summary: "Obsolete allowance auction section removed from the CFR.", pub: "2026-02-10", basis: "Federal Register publication date (FR 2026-02140)" },
  // --- renumbered
  { cit: "327 IAC 15-5-1", cls: "renumbered", dir: "clarified", label: "Construction stormwater renumbered", summary: "Construction stormwater rule moved to a new number; text unchanged.", pub: "2025-11-19" },
];

// noise out of footprint: [citation, class, publication date]
const NOISE: [string, ChangeClass, string][] = [
  ["170 IAC 2-1-1", "cosmetic", "2024-12-18"],
  ["326 IAC 1-1-1", "cosmetic", "2024-12-18"],
  ["326 IAC 1-2-1", "cosmetic", "2024-12-18"],
  ["326 IAC 2-1.1-1", "cosmetic", "2024-12-18"],
  ["326 IAC 4-1-1", "cosmetic", "2024-12-18"],
  ["327 IAC 1-1-1", "cosmetic", "2024-12-18"],
  ["327 IAC 3-1-1", "cosmetic", "2024-12-18"],
  ["40 CFR 60.1", "cosmetic", "2025-04-15"],
  ["18 CFR 35.1", "cosmetic", "2025-04-15"],
  ["326 IAC 1-2-2", "metadata_only", "2025-03-05"],
  ["327 IAC 2-1-6", "metadata_only", "2025-03-05"],
  ["40 CFR 63.2", "metadata_only", "2025-05-20"],
  ["326 IAC 2-5.1-2", "punctuation_only", "2025-06-18"],
  ["327 IAC 5-2-3", "punctuation_only", "2025-06-18"],
  ["40 CFR 60.7", "punctuation_only", "2025-07-08"],
  ["18 CFR 35.2", "punctuation_only", "2025-07-08"],
  ["326 IAC 2-7-1", "cross_ref_only", "2025-08-06"],
  ["327 IAC 5-4-1", "cross_ref_only", "2025-08-06"],
  ["40 CFR 60.8", "cross_ref_only", "2025-09-03"],
  ["18 CFR 37.3", "cross_ref_only", "2025-09-03"],
];

/* ------------------------------------------------------------------ build changes */

function noiseTexts(sec: Section, cls: ChangeClass): { s1: string; s2: string; summary: string } {
  const h = sec.heading.toLowerCase();
  const isIac = sec.source_system === "iac";
  const body = (xref: string, serial: boolean) =>
    `(a) This section applies to each person, facility, ${serial ? "or" : "or"} filing described in ${h}.\n\n` +
    `(b) The responsible person shall maintain records, reports${serial ? "," : ""} and notices required by this section and shall make them available on request.\n\n` +
    `(c) Definitions used in this section are in ${xref} of this ${isIac ? "rule" : "part"}.`;
  const wrap = (b: string, extra = "", meta = "Authority: IC 13-14-8") =>
    isIac ? iacText(sec.citation, sec.heading, `${meta}\n\n${b}`, extra) : `${meta.replace("Authority", "Source")}\n\n${b}`;
  switch (cls) {
    case "cosmetic": {
      const stamp = isIac ? `; readopted filed Dec 12, 2024, 2:05 p.m.: 20241218-IR-170240455RFA` : "";
      const s1 = wrap(body("section 2", true));
      const s2 = isIac ? wrap(body("section 2", true), stamp) : `${s1}\n\n[Editorial: paragraph headings reformatted; no text change.]`;
      return { s1, s2, summary: "Only a readoption or editorial stamp changed." };
    }
    case "punctuation_only":
      return { s1: wrap(body("section 2", false)), s2: wrap(body("section 2", true)), summary: "Serial commas added; no change in meaning." };
    case "cross_ref_only":
      return { s1: wrap(body("section 2", true)), s2: wrap(body("section 2(a)", true)), summary: "A cross-reference was made more precise." };
    default:
      return {
        s1: wrap(body("section 2", true), "", "Authority: IC 13-14-8"),
        s2: wrap(body("section 2", true), "", "Authority: IC 13-14-8; IC 13-15-1"),
        summary: "Only the authority line changed.",
      };
  }
}

const changes: ChangeRecord[] = [];
const quoteFor = new Map<string, string>(); // change_id -> quote in S2

function pushChange(c: Omit<ChangeRecord, "diff_segments" | "placeholder"> & { placeholder?: boolean }) {
  const rec = { ...c, diff_segments: segments(c.s1_text, c.s2_text), placeholder: true };
  changes.push(changeRecordSchema.parse(rec));
}

// in-footprint
const footIds: string[] = [];
for (const f of FOOT) {
  const v = versions[`iac|${f.cit}`];
  const sec = secBy.get(f.cit)!;
  const id = changeId("iac", f.cit);
  footIds.push(id);
  pushChange({
    change_id: id,
    citation: f.cit,
    heading: sec.heading,
    source_system: "iac",
    rule_key: sec.rule_key,
    agency_id: "iurc",
    title_number: sec.title_number,
    change_class: f.cls,
    s1_text: v[0].text,
    s2_text: v[1].text,
    published_date: f.pub,
    date_basis: f.basis,
    din: iacDin(f.pub),
    s1_snapshot: S.iac.s1,
    s2_snapshot: S.iac.s2,
    in_footprint: true,
    cited_clause_count: 0, // filled after candidates are built
    characterization: {
      obligation_changed: false,
      direction: "style_only",
      summary: f.summary,
      value_changes: [],
    },
    disposition: f.disposition,
    disposition_reason: f.reason,
  });
}

// out-of-footprint substantive-type
for (const s of SUBS) {
  const cit = s.cit;
  const sec = secBy.get(cit)!;
  const ss = sec.source_system;
  const id = changeId(ss, s.cit);
  let s1 = "";
  let s2 = "";
  if (s.fromVersions) {
    const v = versions[`${ss}|${cit}`];
    s1 = v[0].text;
    s2 = v[1].text;
  } else if (s.cls === "repealed") {
    const body = sec.body_text;
    s1 = ss === "iac" ? iacText(cit, sec.heading, body) : body;
    s2 = ss === "iac" ? `${cit} ${sec.heading}\n\n[Section repealed.]` : "[Section removed and reserved.]";
  } else if (s.cls === "renumbered") {
    const body = `(a) This rule covers stormwater discharges associated with construction activity.\n\n(b) A permittee shall implement the erosion and sediment controls in its plan.`;
    s1 = iacText("327 IAC 15-5-1.1", sec.heading, body);
    s2 = iacText(cit, sec.heading, body);
  } else {
    const mk = (p: string) => [s.intro!, p, "(c) Records required by this section shall be available for inspection on request."].filter(Boolean).join("\n\n");
    const body1 = mk(s.p1!);
    const body2 = mk(s.p2!);
    s1 = s.cls === "new_section" ? "" : ss === "iac" ? iacText(cit, sec.heading, body1) : body1;
    s2 = ss === "iac" ? iacText(cit, sec.heading, body2) : body2;
  }
  const value_changes =
    s.cls === "substantive" || s.cls === "new_section"
      ? [{ label: s.label!, old: s.old!, new: s.neu!, unit: s.unit ?? null }]
      : [];
  const pub = s.pub ?? "2025-06-01";
  pushChange({
    change_id: id,
    citation: s.cit,
    heading: sec.heading,
    source_system: ss,
    rule_key: sec.rule_key,
    agency_id: sec.owning_agency,
    title_number: sec.title_number,
    change_class: s.cls,
    s1_text: s1,
    s2_text: s2,
    published_date: pub,
    date_basis: s.basis ?? (ss === "iac" ? "Indiana Register publication date" : "Federal Register publication date"),
    din: ss === "iac" ? iacDin(pub) : null,
    s1_snapshot: S[ss].s1,
    s2_snapshot: S[ss].s2,
    in_footprint: false,
    cited_clause_count: 0,
    characterization: {
      obligation_changed: s.cls === "substantive" || s.cls === "new_section" || s.cls === "repealed",
      direction: s.dir ?? "clarified",
      summary: s.summary!,
      value_changes,
    },
    disposition: "Outside footprint",
    disposition_reason:
      s.cls === "renumbered"
        ? "No RPL document cites this section. Renumbering only."
        : "No RPL document cites this section. Screened on the Radar against the company profile.",
  });
  if (s.quote) quoteFor.set(id, s.quote);
}

// out-of-footprint noise
for (const [cit, cls, pub] of NOISE) {
  const sec = secBy.get(cit)!;
  const ss = sec.source_system;
  const t = noiseTexts(sec, cls);
  pushChange({
    change_id: changeId(ss, cit),
    citation: cit,
    heading: sec.heading,
    source_system: ss,
    rule_key: sec.rule_key,
    agency_id: sec.owning_agency,
    title_number: sec.title_number,
    change_class: cls,
    s1_text: t.s1,
    s2_text: t.s2,
    published_date: pub,
    date_basis: ss === "iac" ? "Indiana Register publication of the readoption notice" : "Federal Register publication date",
    din: ss === "iac" ? iacDin(pub) : null,
    s1_snapshot: S[ss].s1,
    s2_snapshot: S[ss].s2,
    in_footprint: false,
    cited_clause_count: 0,
    characterization: null,
    disposition: "Outside footprint",
    disposition_reason: `${t.summary} No RPL document cites this section.`,
  });
}

/* ------------------------------------------------------------------ candidates */

const DOCS = ["RPL-REG-CAL-2025", "RPL-CS-PRO-011", "RPL-CS-PRO-004"];
const clausesByDoc = new Map<string, ClauseRow[]>();
for (const d of DOCS) clausesByDoc.set(d, readJson<ClauseRow[]>(`company/clauses/${d}.json`));
const regRows = readJson<ClauseRow[]>("company/clauses/RPL-CMP-REG-001.json").filter((c) => c.unit_kind === "register_row");
const pool: ClauseRow[] = DOCS.flatMap((d) => clausesByDoc.get(d)!);

type Plan = {
  cit: string;
  n: number;
  rule: string; // sibling-rule regex source
  ruleLabel: string;
  echo?: RegExp;
  rationale: string;
  ruleRationale: string;
  echoRationale: string;
  skip: string;
  ai?: boolean;
};

const STAMP_R = "Only a readoption stamp was added to the history note, so the clause's reliance on {c} is unaffected.";
const PLANS: Plan[] = [
  {
    cit: "170 IAC 1-6-4", n: 4, rule: "170 IAC 1-6-", ruleLabel: "170 IAC 1-6",
    rationale: STAMP_R, ruleRationale: "Cites the 170 IAC 1-6 rule generally; the only change in {c} is a readoption stamp.",
    echoRationale: "Restates content from {c}, which changed only by a readoption stamp.", skip: "cosmetic_noise",
  },
  {
    cit: "170 IAC 1-6-5", n: 6, rule: "170 IAC 1-6-", ruleLabel: "170 IAC 1-6",
    rationale: 'The change only refines a cross-reference to "170 IAC 1-6-2(11)"; the notice obligation this clause relies on is unchanged.',
    ruleRationale: "Cites the 170 IAC 1-6 rule generally; {c} changed only by a more precise cross-reference.",
    echoRationale: "Restates content from {c}; the change is a cross-reference refinement only.", skip: "cross_ref_only_noise",
  },
  {
    cit: "170 IAC 1-6-3", n: 8, rule: "170 IAC 1-6-", ruleLabel: "170 IAC 1-6",
    echo: /thirty \(30\)|30[- ]day/i,
    rationale: "Commas were added to paragraph (a); the 30-day effective period and who acts are unchanged, so this clause stays accurate.",
    ruleRationale: "Cites the 170 IAC 1-6 rule generally; {c} changed only in punctuation.",
    echoRationale: "Echoes the 30-day filing period, which is unchanged between S1 and S2.", skip: "punctuation_only_noise",
  },
  {
    cit: "170 IAC 16-1-5", n: 6, rule: "170 IAC 16-1-", ruleLabel: "170 IAC 16-1",
    rationale: STAMP_R, ruleRationale: "Cites the 170 IAC 16-1 rule generally; the only change in {c} is a readoption stamp.",
    echoRationale: "Restates content from {c}, which changed only by a readoption stamp.", skip: "cosmetic_noise",
  },
  {
    cit: "170 IAC 16-1-7", n: 6, rule: "170 IAC 16-1-", ruleLabel: "170 IAC 16-1",
    rationale: 'The change only adds "(a)" to the IC 8-1-1-3 reference; the complaint-outcome reporting duty this clause relies on is unchanged.',
    ruleRationale: "Cites the 170 IAC 16-1 rule generally; {c} changed only by a more precise statute reference.",
    echoRationale: "Restates content from {c}; the change is a cross-reference refinement only.", skip: "cross_ref_only_noise",
  },
  {
    cit: "170 IAC 16-1-4", n: 10, rule: "170 IAC 16-1-", ruleLabel: "170 IAC 16-1",
    echo: /ten \(10\) days|10[- ]day/i,
    rationale: "Serial commas were added in paragraph (b); the ten-day response time and the items to provide are unchanged.",
    ruleRationale: "Cites the 170 IAC 16-1 rule generally; {c} changed only in punctuation.",
    echoRationale: "Echoes the ten-day response time, which is unchanged between S1 and S2.", skip: "punctuation_only_noise",
  },
  {
    cit: "170 IAC 4-1-16", n: 28, rule: "170 IAC 4-1-", ruleLabel: "170 IAC 4-1",
    echo: /14[- ]day|fourteen \(14\)|14 (calendar |business )?days/i,
    rationale:
      'Paragraphs (c) and (d) changed from "shall not" to "may not". The commission\'s readoption notice states no change in effect, so the prohibition this clause relies on has the same legal effect.',
    ruleRationale: 'Cites the 170 IAC 4-1 rule generally; the "shall not" to "may not" rewording in {c} has the same legal effect.',
    echoRationale: "Echoes the 14-day notice period in 4-1-16(e), which is not edited. The rewording touches only (c) and (d), with the same legal effect.",
    skip: "style_only_same_effect", ai: true,
  },
  {
    cit: "170 IAC 4-1-13", n: 94, rule: "170 IAC 4-1-", ruleLabel: "170 IAC 4-1",
    echo: /deposit/i,
    rationale: STAMP_R,
    ruleRationale: "Cites the 170 IAC 4-1 rule generally; the only change in {c} is a readoption stamp.",
    echoRationale: "Mentions customer deposits, which {c} governs; the section changed only by a readoption stamp.", skip: "cosmetic_noise",
  },
];

const exactRe = (cit: string) => new RegExp(`${cit.replace(/ /g, "\\s")}(?![\\d]|\\.\\d)`);
const used = new Set<string>();
const candidates: Candidate[] = [];
const candByChange = new Map<string, Candidate[]>();
let cn = 0;
const clauseLabel = (c: ClauseRow) => {
  const t = c.heading_path[c.heading_path.length - 1] ?? c.clause_id;
  return `${c.doc_id} · ${t}`.slice(0, 90);
};

for (const plan of PLANS) {
  const sec = secBy.get(plan.cit)!;
  const id = changeId("iac", plan.cit);
  const chosen: { c: ClauseRow; kind: "direct_section" | "register_hop" | "value_echo" | "direct_rule"; hop?: ClauseRow }[] = [];
  const take = (c: ClauseRow, kind: (typeof chosen)[number]["kind"], hop?: ClauseRow) => {
    if (used.has(c.clause_id) || chosen.length >= plan.n) return;
    used.add(c.clause_id);
    chosen.push({ c, kind, hop });
  };
  // balance docs: round-robin over docs for direct_section so every doc is represented
  const exact = exactRe(plan.cit);
  const byDocExact = DOCS.map((d) => clausesByDoc.get(d)!.filter((c) => exact.test(JSON.stringify(c))));
  const cap = Math.ceil(plan.n / 2);
  for (let i = 0; chosen.length < Math.min(plan.n, cap + 6); i++) {
    let any = false;
    for (const list of byDocExact) {
      if (list[i]) {
        take(list[i], "direct_section");
        any = true;
      }
    }
    if (!any) break;
  }
  // register hops: pool clauses naming an obligation id whose register row cites the section
  const rows = regRows.filter((r) => exact.test(JSON.stringify(r)));
  for (const r of rows) {
    const oid = r.row_cells?.obligation_id;
    if (!oid) continue;
    for (const c of pool) if (c.text_raw.includes(oid) && c.clause_id !== r.clause_id) take(c, "register_hop", r);
  }
  // value echoes
  if (plan.echo) for (const c of pool) if (plan.echo.test(c.text_raw) && !exact.test(JSON.stringify(c))) take(c, "value_echo");
  // remaining direct_section beyond the first sweep
  for (const list of byDocExact) for (const c of list) take(c, "direct_section");
  // sibling-rule citations
  const ruleRe = new RegExp(plan.rule.replace(/ /g, "\\s"));
  for (const c of pool) if (ruleRe.test(c.text_raw)) take(c, "direct_rule");
  if (chosen.length !== plan.n) throw new Error(`${plan.cit}: wanted ${plan.n}, got ${chosen.length}`);

  const list: Candidate[] = [];
  for (const entry of chosen) {
    const { c, hop: h0 } = entry;
    let { kind, hop } = { kind: entry.kind, hop: h0 };
    // a calendar event row that cites the section is reached through the obligations register
    if (kind === "direct_section" && c.unit_kind === "register_row" && rows[0]) {
      kind = "register_hop";
      hop = rows[0];
    }
    const secNode = { kind: "section" as const, ref: plan.cit, label: `${plan.cit} · ${sec.heading}` };
    const clauseNode = { kind: "clause" as const, ref: c.clause_id, label: clauseLabel(c) };
    const path_detail =
      kind === "register_hop" && hop
        ? [secNode, { kind: "register_row" as const, ref: hop.clause_id, label: `Register row ${hop.row_cells?.obligation_id ?? hop.clause_id}` }, clauseNode]
        : kind === "direct_rule"
          ? [secNode, { kind: "rule" as const, ref: plan.ruleLabel, label: plan.ruleLabel }, clauseNode]
          : [secNode, clauseNode];
    const rationale = (kind === "direct_rule" ? plan.ruleRationale : kind === "value_echo" ? plan.echoRationale : plan.rationale).replaceAll("{c}", plan.cit);
    cn++;
    list.push(
      candidateSchema.parse({
        candidate_id: `cand-${String(cn).padStart(4, "0")}`,
        run_id: RUN_ID,
        change_id: id,
        clause_id: c.clause_id,
        doc_id: c.doc_id,
        match_path: kind === "register_hop" ? "register_hop" : kind,
        path_detail,
        outcome: "cleared",
        skip_reason: plan.skip,
        rationale,
        finding_id: null,
      }),
    );
  }
  candByChange.set(id, list);
  candidates.push(...list);
}

for (const c of changes) c.cited_clause_count = candByChange.get(c.change_id)?.length ?? 0;
changes.forEach((c) => changeRecordSchema.parse(c));

/* ------------------------------------------------------------------ rollups */

const classLabel = (cls: ChangeClass, direction?: string) =>
  direction === "style_only" && cls === "substantive"
    ? "style-only"
    : ({ cosmetic: "cosmetic", punctuation_only: "punctuation-only", cross_ref_only: "cross-reference-only", metadata_only: "metadata-only" } as Record<string, string>)[cls] ?? cls;
const changeById = new Map(changes.map((c) => [c.change_id, c]));
const ZERO_VERDICTS = { action_required: 0, optional_relaxed: 0, update_citation: 0, review: 0, info: 0 };
const rollups: DocRollup[] = [];
for (const d of DOCS) {
  const ids = [...new Set(candidates.filter((c) => c.doc_id === d).map((c) => c.change_id))];
  const byClass: Record<string, number> = {};
  const labels: Record<string, number> = {};
  for (const id of ids) {
    const ch = changeById.get(id)!;
    byClass[ch.change_class] = (byClass[ch.change_class] ?? 0) + 1;
    const l = classLabel(ch.change_class, ch.characterization?.direction);
    labels[l] = (labels[l] ?? 0) + 1;
  }
  const parts = Object.entries(labels).map(([l, n]) => `${n} ${l}`);
  rollups.push(
    docRollupSchema.parse({
      run_id: RUN_ID,
      doc_id: d,
      status: "cleared",
      counts_by_verdict: { ...ZERO_VERDICTS },
      changes_considered: ids.length,
      considered_by_class: byClass,
      cleared_reason: `${ids.length} change${ids.length === 1 ? "" : "s"} considered: ${parts.join(", ")}`,
    }),
  );
}

/* ------------------------------------------------------------------ radar */

type R = {
  cit: string;
  applicable: "yes" | "no" | "unclear";
  basis: { key: string; value: string | number | boolean }[];
  activity: string;
  reason: string;
  docs?: string[];
};
const RADAR: R[] = [
  { cit: "326 IAC 2-8-4", applicable: "yes", basis: [{ key: "standby_generator_count", value: 3 }, { key: "has_emergency_standby_generators", value: true }],
    activity: "Running RPL's three emergency standby generators for maintenance checks and readiness testing.",
    reason: "RPL operates 3 emergency standby generators, so the annual testing-hours cap in this FESOP section can affect its operating practice and permits.", docs: ["RPL-ENV-PRO-005", "RPL-CMP-REG-001"] },
  { cit: "40 CFR 63.6603", applicable: "yes", basis: [{ key: "has_emergency_standby_generators", value: true }, { key: "standby_generator_count", value: 3 }],
    activity: "Emission limits for stationary reciprocating engines used as emergency generators.",
    reason: "RPL has emergency standby generators, which are stationary reciprocating engines covered by this subpart." },
  { cit: "170 IAC 2-1-2", applicable: "yes", basis: [{ key: "iurc_jurisdictional", value: true }, { key: "jurisdiction", value: "IN" }],
    activity: "Paying the annual IURC utility fee on gross intrastate operating revenues.",
    reason: "RPL is an IURC-jurisdictional Indiana utility, so the higher fee rate applies to its annual fee.", docs: ["RPL-REG-CAL-2025"] },
  { cit: "170 IAC 6-1-1", applicable: "yes", basis: [{ key: "iurc_jurisdictional", value: true }, { key: "utility_type", value: "electric" }],
    activity: "Annual energy efficiency program reporting to the IURC.",
    reason: "RPL is an electric utility under IURC jurisdiction; if it files program reports, the new breakout applies.", docs: ["RPL-CMP-REG-001"] },
  { cit: "170 IAC 7-1-1", applicable: "yes", basis: [{ key: "iurc_jurisdictional", value: true }, { key: "utility_type", value: "electric" }],
    activity: "Handling requests from customer loads of 100 MW or more to interconnect.",
    reason: "A new large load interconnection process applies to IURC-jurisdictional electric utilities such as RPL." },
  { cit: "40 CFR 60.4320", applicable: "no", basis: [{ key: "owns_generating_units", value: false }],
    activity: "Limiting NOx from new natural gas turbines.", reason: "RPL owns no generating units, so a turbine NOx standard does not apply." },
  { cit: "40 CFR 60.5520", applicable: "no", basis: [{ key: "owns_generating_units", value: false }],
    activity: "CO2 output standards for fossil fuel-fired generating units.", reason: "RPL owns no generating units." },
  { cit: "40 CFR 63.10005", applicable: "no", basis: [{ key: "owns_generating_units", value: false }],
    activity: "Compliance averaging for electric utility steam generating units.", reason: "RPL owns no steam generating units." },
  { cit: "326 IAC 6-3-2", applicable: "no", basis: [{ key: "owns_generating_units", value: false }],
    activity: "Particulate limits for manufacturing processes.", reason: "RPL operates no manufacturing process or generating unit that emits particulate." },
  { cit: "18 CFR 35.28", applicable: "no", basis: [{ key: "operates_transmission_above_100kv", value: false }],
    activity: "Open access transmission tariff and market monitor reporting.", reason: "RPL operates no transmission above 100 kV and is not a transmission provider under the tariff." },
  { cit: "18 CFR 35.36", applicable: "no", basis: [{ key: "owns_generating_units", value: false }, { key: "operates_transmission_above_100kv", value: false }],
    activity: "Generator interconnection study deadlines.", reason: "RPL owns no generation and runs no transmission, so it processes no generator interconnection studies under this section." },
  { cit: "170 IAC 3-1-1", applicable: "no", basis: [{ key: "has_gas_operations", value: false }],
    activity: "Gas pipeline leak surveys.", reason: "RPL has no gas operations." },
  { cit: "170 IAC 5-1-1", applicable: "no", basis: [{ key: "has_water_operations", value: false }],
    activity: "Rate case notices for water and sewage utilities.", reason: "RPL has no water or sewage operations." },
  { cit: "327 IAC 5-4-6", applicable: "unclear", basis: [{ key: "has_underground_facilities", value: true }],
    activity: "Notices of intent for construction sites that disturb land.",
    reason: "RPL has underground facilities and does construction work, but whether any site reaches the new half-acre threshold depends on project size.", docs: ["RPL-DO-PLN-002"] },
  { cit: "326 IAC 10-1-1", applicable: "unclear", basis: [{ key: "has_emergency_standby_generators", value: true }],
    activity: "NOx rule applicability by annual tons emitted.",
    reason: "RPL's standby generators emit NOx, but their annual tons relative to the new 15-ton threshold are not in the profile." },
  { cit: "18 CFR 37.6", applicable: "unclear", basis: [{ key: "operates_transmission_above_100kv", value: false }],
    activity: "OASIS outage posting updates.", reason: "RPL has no transmission above 100 kV, but may post outages through its MISO transmission owner." },
];
const radar: RadarItem[] = RADAR.map((r, i) => {
  const ch = changes.find((c) => c.citation === r.cit && !c.in_footprint)!;
  if (!ch) throw new Error(`radar change missing: ${r.cit}`);
  const quote = quoteFor.get(ch.change_id);
  const para = ch.s2_text.split("\n").find((l) => quote && l.includes(quote));
  if (!para) throw new Error(`radar quote missing for ${r.cit}`);
  return radarItemSchema.parse({
    radar_id: `rad-${String(i + 1).padStart(3, "0")}`,
    run_id: RUN_ID,
    change_id: ch.change_id,
    citation: ch.citation,
    heading: ch.heading,
    agency_id: ch.agency_id,
    applicable: r.applicable,
    attribute_basis: r.basis,
    affected_activity: r.activity,
    reason: r.reason,
    quote: para.trim(),
    docs_covering_same_rule: r.docs ?? [],
  });
});

/* ------------------------------------------------------------------ stats / runs / score */

const by_class: Record<string, number> = {
  substantive: 403,
  repealed: 31,
  renumbered: 12,
  new_section: 45,
  cosmetic: 590,
  metadata_only: 9,
  punctuation_only: 14,
  cross_ref_only: 10,
};
const ruleDecided = candidates.filter((c) => c.skip_reason !== "style_only_same_effect").length;
const aiDecided = candidates.length - ruleDecided;
const tally: Record<string, number> = { direct_section: 0, direct_rule: 0, register_hop: 0, value_echo: 0 };
for (const c of candidates) tally[c.match_path]++;

const realStats = {
  changes_raw: 1114,
  by_class,
  substantive: 491,
  noise: 623,
  in_footprint: changes.filter((c) => c.in_footprint).length,
  obligation_changed: changes.filter((c) => c.in_footprint && c.characterization?.obligation_changed).length,
  candidates_by_path: tally,
  findings_by_verdict: { ...ZERO_VERDICTS },
  clauses_cleared: candidates.length,
  docs_flagged: 0,
  docs_cleared: rollups.length,
  // 490 = 491 substantive minus the one in-footprint substantive change (4-1-16)
  radar: { applicable: 5, screened_out: 467, unclear: 18 },
  decided_by: { rule: ruleDecided, ai: aiDecided },
  llm_calls: aiDecided + 1,
};
const zeroStats = {
  changes_raw: 0,
  by_class: Object.fromEntries(Object.keys(by_class).map((k) => [k, 0])),
  substantive: 0,
  noise: 0,
  in_footprint: 0,
  obligation_changed: 0,
  candidates_by_path: { direct_section: 0, direct_rule: 0, register_hop: 0, value_echo: 0 },
  findings_by_verdict: { ...ZERO_VERDICTS },
  clauses_cleared: 0,
  docs_flagged: 0,
  docs_cleared: 0,
  radar: { applicable: 0, screened_out: 0, unclear: 0 },
  decided_by: { rule: 0, ai: 0 },
  llm_calls: 0,
};
const runs: Run[] = [
  runSchema.parse({
    run_id: RUN_ID,
    kind: "kb",
    title: "Real wave · S1→S2",
    status: "succeeded",
    started_at: "2026-10-05T14:02:11Z",
    finished_at: "2026-10-05T14:09:48Z",
    scenario_id: null,
    progress: null,
    stats: realStats,
  }),
  runSchema.parse({
    run_id: BASE_ID,
    kind: "baseline",
    title: "Baseline · S1 vs S1",
    status: "succeeded",
    started_at: "2026-10-05T14:10:30Z",
    finished_at: "2026-10-05T14:10:41Z",
    scenario_id: null,
    progress: null,
    stats: zeroStats,
  }),
];
const score = scoreReportSchema.parse({
  precision: 0.91,
  recall: 0.88,
  fp_rate_must_not_flag: 0,
  routing_accuracy: 0.92,
  targets: { precision: 0.8, recall: 0.83, fp_rate: 0, routing: 0.8 },
  baseline_findings: 0,
  decided_by: { rule: 214, ai: 96 },
  llm_calls: 118,
});

/* ------------------------------------------------------------------ write */

const write = (p: string, data: unknown) => {
  mkdirSync(path.dirname(path.join(FX, p)), { recursive: true });
  writeFileSync(path.join(FX, p), JSON.stringify(data, null, 2) + "\n");
};
write("engine/run_kb_real/changes.json", changes);
write("engine/run_kb_real/candidates.json", candidates);
write("engine/run_kb_real/findings.json", []);
write("engine/run_kb_real/rollups.json", rollups);
write("engine/run_kb_real/radar.json", radar);
for (const f of ["changes", "candidates", "findings", "rollups", "radar"]) write(`engine/run_baseline/${f}.json`, []);
write("engine/runs.json", runs);
write("engine/score.json", score);

console.log(
  `changes ${changes.length} (in footprint ${footIds.length}), candidates ${candidates.length}, rollups ${rollups.length}, radar ${radar.length}`,
);
console.log("key ids:", footIds.join(", "));
console.log("paths", tally, "decided_by", realStats.decided_by);

/**
 * Company fixture builder (spec §6.4). Run manually: `pnpm fixtures:build`.
 *
 * Reads ONLY these corpus files (read-only) from ../backend/app/company/corpus:
 *   _global/document_register.csv, _global/people_directory.csv, _global/company_profile.yaml,
 *   docs/<doc_id>/<doc_id>_v*.md, docs/<doc_id>/data/<register>.csv (three registers only).
 * Writes validated JSON to fixtures/company/. Output is deterministic.
 */
import { mkdirSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { parse as parseYaml } from "yaml";
import { clauseSchema, companyProfileSchema, documentMetaSchema } from "../lib/api/schemas/company";
import { personSchema, type UnitKind } from "../lib/api/schemas/common";
import type { Clause, CompanyAttribute, DocumentMeta } from "../lib/api/schemas/company";
import type { Person } from "../lib/api/schemas/common";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, "..");
const CORPUS = path.resolve(FRONTEND, "../backend/app/company/corpus");
const OUT = path.join(FRONTEND, "fixtures/company");

/* ------------------------------------------------------------------ helpers */

function parseCsv(text: string): Record<string, string>[] {
  const rows: string[][] = [];
  let row: string[] = [];
  let cell = "";
  let inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"';
          i++;
        } else inQuotes = false;
      } else cell += ch;
    } else if (ch === '"') inQuotes = true;
    else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n" || ch === "\r") {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell);
      cell = "";
      if (row.some((c) => c !== "")) rows.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell !== "" || row.length) {
    row.push(cell);
    if (row.some((c) => c !== "")) rows.push(row);
  }
  const [header, ...body] = rows;
  return body.map((r) => Object.fromEntries(header.map((h, i) => [h, (r[i] ?? "").trim()])));
}

const readText = (p: string) => readFileSync(p, "utf8");
const nn = (s: string | undefined) => (s && s.trim() !== "" ? s.trim() : null);

function writeJson(file: string, data: unknown) {
  mkdirSync(path.dirname(file), { recursive: true });
  writeFileSync(file, JSON.stringify(data, null, 2) + "\n");
}

/* ------------------------------------------------------------------ verticals */

/** Backend vertical → frontend slug (spec §5.3). */
const VERTICAL_SLUG: Record<string, string> = {
  "Compliance & Legal": "compliance-legal",
  "Policy & Governance": "policy-governance",
  "Operations & Processes": "operations-processes",
  "Workforce & Safety": "workforce-hr",
  Environmental: "environmental-esg",
};

const VERTICAL_ORDER = [
  "compliance-legal",
  "policy-governance",
  "financial-reporting",
  "revenue-pricing",
  "operations-processes",
  "technology-systems",
  "workforce-hr",
  "environmental-esg",
  "supply-chain-procurement",
  "risk-insurance",
  "strategic-competitive",
  "reputational-stakeholder",
  "contractual-third-party",
  "capital-infrastructure",
];

function docTypeOf(docId: string): string {
  const code = docId.split("-")[2] ?? "";
  if (code === "PRO") return "Procedure";
  if (code === "PLN") return "Plan";
  if (code === "PGM") return "Program Plan";
  if (code === "GRR") return "Tariff";
  return "Register"; // REG, CAL, RRS
}

/* ------------------------------------------------------------------ people */

function loadPeople(): Person[] {
  const rows = parseCsv(readText(path.join(CORPUS, "_global/people_directory.csv")));
  return rows.map((r) =>
    personSchema.parse({
      person_id: r.person_id,
      name: r.name,
      title: r.title,
      department: r.department,
      reports_to_id: nn(r.reports_to_id),
    }),
  );
}

/* ------------------------------------------------------------------ citations */

const IAC_RE = /\b(\d{1,3}) IAC (\d+(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?)/g;
const CFR_RE = /\b(\d{1,3}) CFR (?:[Pp]art )?(\d+(?:\.\d+)?)/g;

function extractCitations(text: string, seed: string[] = []): string[] {
  const out = new Set<string>();
  for (const s of seed) {
    const m = /^(\d{1,3}) IAC (\d+(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?)/.exec(s.trim());
    if (m) out.add(`${m[1]} IAC ${m[2]}`);
  }
  for (const m of text.matchAll(IAC_RE)) out.add(`${m[1]} IAC ${m[2]}`);
  for (const m of text.matchAll(CFR_RE)) out.add(`${m[1]} CFR ${m[2]}`);
  return [...out].sort((a, b) => a.localeCompare(b, "en", { numeric: true }));
}

/* ------------------------------------------------------------------ markdown segmentation */

interface Unit {
  clause_id: string;
  kind: UnitKind;
  heading_path: string[];
  lines: string[];
  row_cells: Record<string, string> | null;
  parent: string | null | undefined; // undefined => resolve from heading/id structure
  hparent?: string | null; // nearest preceding heading-clause at creation time
  isHeading?: boolean;
  explicitText?: string;
  children: number;
}

const stripMd = (s: string) =>
  s
    .replace(/\*\*/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/[ \t]+$/gm, "");

const FIELD_RE = /^\*\*([A-Z])\.(F\d+)\b/;
const BOLD_CAPS_RE = /^\*\*[A-Z][A-Z0-9 &/—–\-:()'.,]{3,}\*\*:?$/;

function splitRow(line: string): string[] {
  let s = line.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|")) s = s.slice(0, -1);
  return s.split(/(?<!\\)\|/).map((c) => c.replace(/\\\|/g, "|").trim());
}

function kindForId(id: string, headingPath: string[]): UnitKind {
  if (/^App-?[A-Z0-9]*\.F\d+$/i.test(id)) return "form_field";
  if (/^App/i.test(id) || /^[A-D]\.\d+$/.test(id)) return "appendix";
  if (/^R\d+\./.test(id)) return "tariff_subrule";
  if (/^(Appendix|App-)/i.test(headingPath[0] ?? "")) return "appendix";
  return "section";
}

function segmentMarkdown(docId: string, body: string): Clause[] {
  const esc = docId.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const clauseRe = new RegExp(`^<!--\\s*(?:clause:\\s*)?${esc}:(\\S+?)\\s*-->$`);
  const tableRe = new RegExp(`^<!--\\s*table:\\s*${esc}:(\\S+?)\\s*-->$`);
  const IGNORED_ANCHORS = new Set(["meta", "front-matter"]);

  const units: Unit[] = [];
  const usedIds = new Set<string>();
  const headings: { level: number; text: string }[] = [];
  let sub: string | null = null; // PART/BRANCH style sub-heading
  let unit: Unit | null = null;
  let lastReal: Unit | null = null;
  let started = false;
  let skipping = false; // inside an ignored (document control) region
  let tableAnchor: string | null = null;
  const synth = new Map<string, number>();
  const headingUnits: { level: number; id: string }[] = [];
  const tableCounter = new Map<string, number>();

  const path_ = () => {
    const p = headings.filter((h) => h.level >= 2).map((h) => h.text);
    if (sub) p.push(sub);
    return p;
  };
  const uniq = (id: string) => {
    if (!usedIds.has(id)) return id;
    let n = 2;
    while (usedIds.has(`${id}~${n}`)) n++;
    return `${id}~${n}`;
  };
  const open = (id: string, kind?: UnitKind, parent?: string | null): Unit => {
    const hp = path_();
    const u: Unit = {
      clause_id: uniq(id),
      kind: kind ?? kindForId(id, hp),
      heading_path: hp,
      lines: [],
      row_cells: null,
      parent,
      children: 0,
      hparent: headingUnits.length ? headingUnits[headingUnits.length - 1].id : null,
    };
    usedIds.add(u.clause_id);
    units.push(u);
    unit = u;
    lastReal = u;
    started = true;
    return u;
  };
  const hasText = (u: Unit) => u.lines.some((l) => l.trim() !== "");
  const ensureUnit = (): Unit | null => {
    if (unit) return unit;
    if (!started || skipping || !lastReal) return null;
    const base = (lastReal as Unit).clause_id.replace(/~.*$/, "");
    const n = (synth.get(base) ?? 0) + 1;
    synth.set(base, n);
    const u = open(`${base}~c${n}`, (lastReal as Unit).kind === "form_field" ? "appendix" : (lastReal as Unit).kind);
    u.parent = base;
    return u;
  };

  const lines = body.split(/\r?\n/);
  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const line = raw.trimEnd();
    const t = line.trim();

    let m = clauseRe.exec(t);
    if (m) {
      const id = m[1];
      if (IGNORED_ANCHORS.has(id)) {
        unit = null;
        skipping = true;
        continue;
      }
      skipping = false;
      sub = /^App/i.test(id) ? sub : null;
      unit = null;
      open(id);
      continue;
    }
    m = tableRe.exec(t);
    if (m) {
      tableAnchor = m[1];
      continue;
    }
    if (t.startsWith("<!--")) continue; // other comments (control block markers, decision table notes)
    if (skipping) {
      // control block: ignore until the next anchor
      if (/^#{1,6}\s/.test(t)) skipping = false;
      else continue;
    }
    if (t === "---" || t === "***") {
      continue;
    }

    const hm = /^(#{1,6})\s+(.*)$/.exec(t);
    if (hm) {
      const level = hm[1].length;
      const text = stripMd(hm[2]).trim();
      while (headings.length && headings[headings.length - 1].level >= level) headings.pop();
      while (headingUnits.length && headingUnits[headingUnits.length - 1].level >= level) headingUnits.pop();
      headings.push({ level, text });
      sub = null;
      if (unit && !hasText(unit) && (unit as Unit).row_cells === null && (unit as Unit).kind !== "form_field") {
        // anchor immediately followed by its heading: heading is the clause text
        (unit as Unit).heading_path = path_();
        (unit as Unit).lines.push(text);
        (unit as Unit).kind = kindForId((unit as Unit).clause_id, path_());
        (unit as Unit).isHeading = true;
        // a heading clause's parent is the enclosing heading clause, not itself
        (unit as Unit).hparent = headingUnits.length ? headingUnits[headingUnits.length - 1].id : null;
        headingUnits.push({ level, id: (unit as Unit).clause_id });
      } else {
        unit = null;
      }
      continue;
    }

    if (BOLD_CAPS_RE.test(t) && !FIELD_RE.test(t)) {
      // PART A / BRANCH B / OPENING style sub-heading
      sub = stripMd(t).replace(/:$/, "").trim();
      unit = unit && !hasText(unit) ? unit : null;
      if (unit) (unit as Unit).heading_path = path_();
      continue;
    }

    // Tables
    if (t.startsWith("|")) {
      const block: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        block.push(lines[i].trim());
        i++;
      }
      i--;
      const rows = block.map(splitRow);
      const isSep = (r: string[]) => r.every((c) => /^:?-{2,}:?$/.test(c) || c === "");
      const sepIdx = rows.findIndex(isSep);
      if (sepIdx < 1) continue;
      const header = rows[sepIdx - 1].map((h, idx, arr) => {
        const base = stripMd(h) || (idx === 1 ? "Value" : `Column ${idx + 1}`);
        return arr.findIndex((x, j) => j < idx && (stripMd(x) || (j === 1 ? "Value" : `Column ${j + 1}`)) === base) >= 0
          ? `${base} ${idx + 1}`
          : base;
      });
      const dataRows = rows.slice(sepIdx + 1).filter((r) => !isSep(r));
      const parent = (unit ?? lastReal) as Unit | null;
      const isFieldTable = dataRows.some((r) => FIELD_RE.test(r[0] ?? ""));
      if (!parent && !tableAnchor && !isFieldTable) {
        tableAnchor = null;
        continue; // preface / document-control table
      }
      const parentId = parent ? parent.clause_id : null;
      let tname = tableAnchor;
      if (!tname && parentId) {
        const k = (tableCounter.get(parentId) ?? 0) + 1;
        tableCounter.set(parentId, k);
        tname = `${parentId}.tbl${k}`;
      }
      let rowNo = 0;
      for (const r of dataRows) {
        rowNo++;
        const cells: Record<string, string> = {};
        header.forEach((h, idx) => {
          cells[h] = stripMd(r[idx] ?? "");
        });
        const fm = FIELD_RE.exec(r[0] ?? "");
        if (fm) {
          const id = `App-${fm[1]}.${fm[2]}`;
          const hp = path_();
          const u: Unit = {
            clause_id: uniq(id),
            kind: "form_field",
            heading_path: hp,
            lines: [r.map(stripMd).filter((c) => c !== "").join(" | ")],
            row_cells: cells,
            parent: undefined,
            children: 0,
          };
          // adopt an empty anchor unit with the same id instead of colliding
          const prev = units[units.length - 1];
          if (prev && prev.clause_id === id && !hasText(prev) && prev.row_cells === null) {
            prev.lines = u.lines;
            prev.row_cells = cells;
            prev.heading_path = hp;
            prev.kind = "form_field";
            unit = null;
            lastReal = prev;
          } else {
            usedIds.add(u.clause_id);
            units.push(u);
            unit = null;
            lastReal = u;
            started = true;
          }
          continue;
        }
        let key: string | null = null;
        if (/^id$/i.test(header[0]) && stripMd(r[0] ?? "")) key = stripMd(r[0]);
        const id = key ? `${key}` : `${tname}.r${rowNo}`;
        const u: Unit = {
          clause_id: uniq(id),
          kind: "table_row",
          heading_path: path_(),
          lines: [r.map(stripMd).filter((c) => c !== "").join(" | ")],
          row_cells: cells,
          parent: parentId,
          children: 0,
        };
        usedIds.add(u.clause_id);
        units.push(u);
        if (parent) parent.children++;
      }
      tableAnchor = null;
      continue;
    }

    if (t === "") {
      if (unit) (unit as Unit).lines.push("");
      continue;
    }

    // Form-field paragraph lines (e.g. "**A.F11 — Pamphlet Reference.** ...")
    const fm = FIELD_RE.exec(t);
    if (fm) {
      const id = `App-${fm[1]}.${fm[2]}`;
      const cur = unit as Unit | null;
      if (cur && cur.clause_id === id && !hasText(cur)) {
        cur.kind = "form_field";
        cur.heading_path = path_();
        cur.lines.push(line);
      } else {
        unit = null;
        const u = open(id, "form_field");
        u.lines.push(line);
      }
      continue;
    }

    const u = ensureUnit();
    if (u) u.lines.push(line);
  }

  // finalise: drop empties, assign text
  const finalUnits = units.filter((u) => {
    const txt = stripMd(u.lines.join("\n")).trim();
    if (txt) return true;
    return u.children > 0 || units.some((v) => v.parent === u.clause_id);
  });
  const ids = new Set(finalUnits.map((u) => u.clause_id));

  const resolveParent = (u: Unit): string | null => {
    if (u.parent !== undefined) return u.parent && ids.has(u.parent) ? u.parent : null;
    const id = u.clause_id;
    if (u.hparent && ids.has(u.hparent) && u.hparent !== id) return u.hparent;
    if (id.includes("~")) {
      const b = id.replace(/~.*$/, "");
      if (b !== id && ids.has(b)) return b;
    }
    const fm = /^(App-?[A-Z0-9]*)\.F\d+$/i.exec(id);
    if (fm) {
      for (const c of [`${fm[1]}.1`, fm[1]]) if (ids.has(c)) return c;
      return null;
    }
    let cur = id;
    while (cur.includes(".")) {
      cur = cur.slice(0, cur.lastIndexOf("."));
      if (ids.has(cur)) return cur;
    }
    return null;
  };

  return finalUnits.map((u, idx) => {
    let text = stripMd(u.lines.join("\n")).replace(/\n{3,}/g, "\n\n").trim();
    if (!text) text = u.heading_path[u.heading_path.length - 1] ?? u.clause_id;
    return clauseSchema.parse({
      clause_id: `${docId}:${u.clause_id}`,
      doc_id: docId,
      ordinal: idx + 1,
      heading_path: u.heading_path,
      unit_kind: u.kind,
      text_raw: text,
      row_cells: u.row_cells,
      parent_clause_id: (() => {
        const p = resolveParent(u);
        return p ? `${docId}:${p}` : null;
      })(),
    });
  });
}

/* ------------------------------------------------------------------ register rows */

interface RegisterSpec {
  csv: string;
  key: string;
  heading: string;
  text: (r: Record<string, string>) => string;
  citations: (r: Record<string, string>) => string[];
}

const REGISTERS: Record<string, RegisterSpec> = {
  "RPL-CMP-REG-001": {
    csv: "compliance_register_2024-12-31.csv",
    key: "obligation_id",
    heading: "Compliance obligations",
    text: (r) => `${r.citation} — ${r.title}. ${r.description}`,
    citations: (r) => [r.citation],
  },
  "RPL-REG-CAL-2025": {
    csv: "calendar_events_2025.csv",
    key: "event_id",
    heading: "Regulatory calendar events",
    text: (r) => `${r.title} (due ${r.due_date}). ${r.description}`,
    citations: (r) => r.citation.split(";"),
  },
  "RPL-LEG-RRS-001": {
    csv: "retention_schedule_2024-12-31.csv",
    key: "rrs_id",
    heading: "Record series",
    text: (r) => `${r.record_series_name}. ${r.description} Retention: ${r.retention_period}.`,
    citations: (r) => r.regulatory_authority.split(";"),
  },
};

function registerClauses(docId: string, startOrdinal: number): { clauses: Clause[]; citationText: string } {
  const spec = REGISTERS[docId];
  const rows = parseCsv(readText(path.join(CORPUS, "docs", docId, "data", spec.csv)));
  let citationText = "";
  const clauses = rows.map((r, i) => {
    citationText += " " + spec.citations(r).join(" ; ");
    return clauseSchema.parse({
      clause_id: `${docId}:${r[spec.key]}`,
      doc_id: docId,
      ordinal: startOrdinal + i,
      heading_path: [spec.heading],
      unit_kind: "register_row",
      text_raw: spec.text(r),
      row_cells: r,
      parent_clause_id: null,
    });
  });
  return { clauses, citationText };
}

/* ------------------------------------------------------------------ samples */

interface Sample {
  id: string;
  title: string;
  vertical: string;
  type: string;
  owner: string;
  reviewer: string;
  approver: string | null;
  version: string;
  effective: string;
  cycle: string;
}

const SAMPLES: Sample[] = [
  // Financial & Reporting
  { id: "RPL-FIN-PRO-101", title: "FERC Form 1 Preparation Procedure", vertical: "financial-reporting", type: "Procedure", owner: "P06", reviewer: "P05", approver: "P04", version: "3.1", effective: "2024-03-01", cycle: "Annual" },
  { id: "RPL-FIN-PRO-102", title: "IURC Annual Financial Report Filing Procedure", vertical: "financial-reporting", type: "Procedure", owner: "P09", reviewer: "P08", approver: "P07", version: "2.4", effective: "2024-04-15", cycle: "Annual" },
  { id: "RPL-FIN-POL-103", title: "Regulatory Asset & Deferral Accounting Policy", vertical: "financial-reporting", type: "Policy", owner: "P05", reviewer: "P04", approver: "P01", version: "1.6", effective: "2023-09-01", cycle: "Biennial" },
  // Revenue & Pricing
  { id: "RPL-REV-PRO-101", title: "Rate Case Preparation Procedure", vertical: "revenue-pricing", type: "Procedure", owner: "P11", reviewer: "P10", approver: "P07", version: "2.0", effective: "2024-01-22", cycle: "Annual" },
  { id: "RPL-REV-PRO-102", title: "Rider & Tracker Adjustment Filing Procedure", vertical: "revenue-pricing", type: "Procedure", owner: "P10", reviewer: "P08", approver: "P07", version: "4.2", effective: "2024-06-10", cycle: "Annual" },
  { id: "RPL-REV-POL-103", title: "Customer Billing Adjustment & Refund Policy", vertical: "revenue-pricing", type: "Policy", owner: "P14", reviewer: "P13", approver: "P03", version: "1.3", effective: "2023-11-20", cycle: "Biennial" },
  // Technology & Systems
  { id: "RPL-TEC-POL-101", title: "Customer Data Privacy & Security Policy", vertical: "technology-systems", type: "Policy", owner: "P03", reviewer: "P02", approver: "P01", version: "3.0", effective: "2024-02-05", cycle: "Annual" },
  { id: "RPL-TEC-PRO-102", title: "AMI Head-End System Change Management Procedure", vertical: "technology-systems", type: "Procedure", owner: "P20", reviewer: "P19", approver: "P16", version: "2.2", effective: "2024-05-13", cycle: "Annual" },
  { id: "RPL-TEC-PLN-103", title: "Operational Technology Cybersecurity Incident Response Plan", vertical: "technology-systems", type: "Plan", owner: "P23", reviewer: "P21", approver: "P16", version: "1.8", effective: "2024-08-01", cycle: "Annual" },
  // Supply Chain & Procurement
  { id: "RPL-SCM-PRO-101", title: "Supplier Qualification Procedure", vertical: "supply-chain-procurement", type: "Procedure", owner: "P19", reviewer: "P20", approver: "P16", version: "2.5", effective: "2024-03-18", cycle: "Annual" },
  { id: "RPL-SCM-PRO-102", title: "Contractor Safety Prequalification Procedure", vertical: "supply-chain-procurement", type: "Procedure", owner: "P27", reviewer: "P24", approver: "P16", version: "3.3", effective: "2024-07-08", cycle: "Annual" },
  { id: "RPL-SCM-STD-103", title: "Transformer & Meter Inventory Management Standard", vertical: "supply-chain-procurement", type: "Standard", owner: "P22", reviewer: "P21", approver: null, version: "1.4", effective: "2023-12-04", cycle: "Biennial" },
  // Risk & Insurance
  { id: "RPL-RSK-PLN-101", title: "Enterprise Risk Management Framework", vertical: "risk-insurance", type: "Plan", owner: "P04", reviewer: "P02", approver: "P01", version: "2.1", effective: "2024-01-08", cycle: "Annual" },
  { id: "RPL-RSK-PRO-102", title: "Insurance Claims Management Procedure", vertical: "risk-insurance", type: "Procedure", owner: "P12", reviewer: "P03", approver: "P02", version: "1.9", effective: "2024-04-29", cycle: "Biennial" },
  { id: "RPL-RSK-PLN-103", title: "Business Continuity & Storm Restoration Plan", vertical: "risk-insurance", type: "Plan", owner: "P23", reviewer: "P21", approver: "P16", version: "5.0", effective: "2024-09-16", cycle: "Annual" },
  // Strategic & Competitive
  { id: "RPL-STR-PLN-101", title: "Integrated Distribution System Planning Process", vertical: "strategic-competitive", type: "Plan", owner: "P21", reviewer: "P20", approver: "P16", version: "1.2", effective: "2024-02-26", cycle: "Annual" },
  { id: "RPL-STR-PRO-102", title: "Regulatory Intervention & Docket Monitoring Procedure", vertical: "strategic-competitive", type: "Procedure", owner: "P08", reviewer: "P07", approver: "P02", version: "2.0", effective: "2024-06-24", cycle: "Annual" },
  { id: "RPL-STR-POL-103", title: "Distributed Energy Resource Interconnection Strategy", vertical: "strategic-competitive", type: "Policy", owner: "P20", reviewer: "P21", approver: "P16", version: "1.1", effective: "2024-10-07", cycle: "Biennial" },
  // Reputational & Stakeholder
  { id: "RPL-COM-PRO-101", title: "Crisis Communications Procedure", vertical: "reputational-stakeholder", type: "Procedure", owner: "P17", reviewer: "P13", approver: "P01", version: "3.2", effective: "2024-03-11", cycle: "Annual" },
  { id: "RPL-COM-PRO-102", title: "Public Meeting & Community Notification Procedure", vertical: "reputational-stakeholder", type: "Procedure", owner: "P22", reviewer: "P21", approver: "P07", version: "1.5", effective: "2023-10-23", cycle: "Biennial" },
  { id: "RPL-COM-POL-103", title: "Media & Social Media Policy", vertical: "reputational-stakeholder", type: "Policy", owner: "P13", reviewer: "P03", approver: "P01", version: "2.3", effective: "2024-05-20", cycle: "Annual" },
  // Contractual & Third-Party Obligations
  { id: "RPL-CON-PRO-101", title: "Pole Attachment Agreement Administration Procedure", vertical: "contractual-third-party", type: "Procedure", owner: "P12", reviewer: "P10", approver: "P03", version: "2.7", effective: "2024-02-12", cycle: "Annual" },
  { id: "RPL-CON-PRO-102", title: "Wholesale Power Agreement Compliance Procedure", vertical: "contractual-third-party", type: "Procedure", owner: "P09", reviewer: "P08", approver: "P07", version: "1.6", effective: "2024-07-29", cycle: "Annual" },
  { id: "RPL-CON-STD-103", title: "Vegetation Contractor Agreement Management Standard", vertical: "contractual-third-party", type: "Standard", owner: "P22", reviewer: "P21", approver: null, version: "1.2", effective: "2024-01-15", cycle: "Biennial" },
  // Capital & Infrastructure
  { id: "RPL-CAP-STD-101", title: "Substation Capital Project Approval Standard", vertical: "capital-infrastructure", type: "Standard", owner: "P21", reviewer: "P20", approver: "P16", version: "3.4", effective: "2024-04-08", cycle: "Annual" },
  { id: "RPL-CAP-PRO-102", title: "Capital Budget Planning Procedure", vertical: "capital-infrastructure", type: "Procedure", owner: "P16", reviewer: "P05", approver: "P01", version: "2.8", effective: "2024-08-19", cycle: "Annual" },
  { id: "RPL-CAP-PLN-103", title: "Distribution Asset Replacement Plan", vertical: "capital-infrastructure", type: "Plan", owner: "P22", reviewer: "P21", approver: "P16", version: "2025.1", effective: "2025-01-13", cycle: "Annual" },
];

function addYears(iso: string, years: number): string {
  const [y, m, d] = iso.split("-");
  return `${Number(y) + years}-${m}-${d}`;
}

/* ------------------------------------------------------------------ main */

function main() {
  const people = loadPeople();
  const byId = new Map(people.map((p) => [p.person_id, p]));
  const person = (id: string): Person => {
    const p = byId.get(id);
    if (!p) throw new Error(`unknown person ${id}`);
    return p;
  };

  // --- documents
  const register = parseCsv(readText(path.join(CORPUS, "_global/document_register.csv"))).filter(
    (r) => !r.doc_id.startsWith("RPL-INF-"),
  );
  const docs: DocumentMeta[] = [];
  const clausesByDoc = new Map<string, Clause[]>();

  for (const r of register) {
    const docId = r.doc_id;
    const slug = VERTICAL_SLUG[r.vertical];
    if (!slug) throw new Error(`no vertical slug for ${r.vertical}`);
    const mdDir = path.join(CORPUS, "docs", docId);
    const mdName = readdirSync(mdDir).find((f) => f.startsWith(`${docId}_v`) && f.endsWith(".md"));
    if (!mdName) throw new Error(`no markdown for ${docId}`);
    let md = readText(path.join(mdDir, mdName));

    let basis: string[] = [];
    const fmMatch = /^---\r?\n([\s\S]*?)\r?\n---\r?\n/.exec(md);
    if (fmMatch) {
      const fm = parseYaml(fmMatch[1]) as { regulatory_basis?: string[] };
      basis = fm.regulatory_basis ?? [];
      md = md.slice(fmMatch[0].length);
    }

    let clauses = segmentMarkdown(docId, md);
    let extraText = "";
    if (REGISTERS[docId]) {
      const reg = registerClauses(docId, clauses.length + 1);
      clauses = [...clauses, ...reg.clauses];
      extraText = reg.citationText;
    }
    clausesByDoc.set(docId, clauses);

    const twoSignature = !r.approver_id;
    const cited = extractCitations(md + "\n" + extraText, basis);

    docs.push(
      documentMetaSchema.parse({
        doc_id: docId,
        title: r.title,
        version: r.version,
        status: r.status,
        effective_date: nn(r.effective_date),
        approved_date: nn(r.approved_date),
        law_as_of: nn(r.law_as_of),
        next_review: nn(r.next_review_date),
        review_cycle: nn(r.review_cycle),
        vertical: slug,
        owner: person(r.owner_id),
        reviewer: person(r.reviewer_id),
        approver: twoSignature ? null : person(r.approver_id),
        two_signature: twoSignature,
        monitored: true,
        doc_type: docTypeOf(docId),
        cited_citations: cited,
      }),
    );
  }

  for (const s of SAMPLES) {
    docs.push(
      documentMetaSchema.parse({
        doc_id: s.id,
        title: s.title,
        version: s.version,
        status: "Not monitored",
        effective_date: s.effective,
        approved_date: s.effective,
        law_as_of: null,
        next_review: addYears(s.effective, s.cycle === "Annual" ? 1 : 2),
        review_cycle: s.cycle,
        vertical: s.vertical,
        owner: person(s.owner),
        reviewer: person(s.reviewer),
        approver: s.approver ? person(s.approver) : null,
        two_signature: false,
        monitored: false,
        doc_type: s.type,
        cited_citations: [],
      }),
    );
  }

  docs.sort((a, b) => {
    const va = VERTICAL_ORDER.indexOf(a.vertical) - VERTICAL_ORDER.indexOf(b.vertical);
    if (va) return va;
    if (a.monitored !== b.monitored) return a.monitored ? -1 : 1;
    return a.doc_id.localeCompare(b.doc_id);
  });

  // --- validation of clause ids
  for (const [docId, cl] of clausesByDoc) {
    const seen = new Set<string>();
    for (const c of cl) {
      if (seen.has(c.clause_id)) throw new Error(`duplicate clause id ${c.clause_id}`);
      seen.add(c.clause_id);
    }
    for (const c of cl) {
      if (c.parent_clause_id && !seen.has(c.parent_clause_id))
        throw new Error(`${docId}: dangling parent ${c.parent_clause_id} on ${c.clause_id}`);
    }
  }

  // --- profile
  const prof = parseYaml(readText(path.join(CORPUS, "_global/company_profile.yaml"))) as {
    company: { legal_name: string; regulator: string };
    business_model: { grid_membership: string };
    customers: { total: number };
    applicability_attributes: Record<string, string | number | boolean>;
  };
  const SRC = "company_profile.yaml";
  const attributes: CompanyAttribute[] = Object.entries(prof.applicability_attributes).map(([key, value]) => ({
    key,
    value,
    source: SRC,
  }));
  attributes.push({ key: "grid_membership", value: prof.business_model.grid_membership, source: SRC });
  const profile = companyProfileSchema.parse({
    name: prof.company.legal_name,
    type: "Investor-owned electric distribution utility",
    state: "Indiana",
    customers: prof.customers.total,
    regulator: prof.company.regulator,
    attributes,
  });

  // --- write
  rmSync(path.join(OUT, "clauses"), { recursive: true, force: true });
  writeJson(path.join(OUT, "documents.json"), docs);
  writeJson(path.join(OUT, "people.json"), people);
  writeJson(path.join(OUT, "profile.json"), profile);
  for (const [docId, cl] of [...clausesByDoc].sort((a, b) => a[0].localeCompare(b[0]))) {
    writeJson(path.join(OUT, "clauses", `${docId}.json`), cl);
  }

  for (const [docId, cl] of [...clausesByDoc].sort((a, b) => a[0].localeCompare(b[0]))) {
    const kinds: Record<string, number> = {};
    for (const c of cl) kinds[c.unit_kind] = (kinds[c.unit_kind] ?? 0) + 1;
    console.log(`${docId.padEnd(18)} ${String(cl.length).padStart(5)}  ${JSON.stringify(kinds)}`);
  }
  console.log(`documents: ${docs.length} (${docs.filter((d) => d.monitored).length} monitored), people: ${people.length}`);
}

main();

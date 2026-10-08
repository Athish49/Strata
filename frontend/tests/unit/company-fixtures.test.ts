import { readFileSync, readdirSync, existsSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { personSchema } from "@/lib/api/schemas/common";
import { clauseSchema, companyProfileSchema, documentMetaSchema } from "@/lib/api/schemas/company";

const DIR = path.resolve(__dirname, "../../fixtures/company");
const load = (f: string) => JSON.parse(readFileSync(path.join(DIR, f), "utf8"));

const VERTICALS = [
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
const EMPTY_VERTICALS = [
  "financial-reporting",
  "revenue-pricing",
  "technology-systems",
  "supply-chain-procurement",
  "risk-insurance",
  "strategic-competitive",
  "reputational-stakeholder",
  "contractual-third-party",
  "capital-infrastructure",
];

const people = (load("people.json") as unknown[]).map((p) => personSchema.parse(p));
const docs = (load("documents.json") as unknown[]).map((d) => documentMetaSchema.parse(d));
const profile = companyProfileSchema.parse(load("profile.json"));
const clauseFiles = readdirSync(path.join(DIR, "clauses")).filter((f) => f.endsWith(".json"));
const clausesByDoc = new Map(
  clauseFiles.map((f) => [
    f.replace(/\.json$/, ""),
    (load(`clauses/${f}`) as unknown[]).map((c) => clauseSchema.parse(c)),
  ]),
);

describe("company fixtures", () => {
  it("has 27 people P01-P27", () => {
    expect(people).toHaveLength(27);
    expect(people.map((p) => p.person_id)).toEqual(
      Array.from({ length: 27 }, (_, i) => `P${String(i + 1).padStart(2, "0")}`),
    );
    const ids = new Set(people.map((p) => p.person_id));
    for (const p of people) if (p.reports_to_id) expect(ids.has(p.reports_to_id)).toBe(true);
  });

  it("has 12 monitored docs, each with a clauses file", () => {
    const monitored = docs.filter((d) => d.monitored);
    expect(monitored).toHaveLength(12);
    for (const d of monitored) {
      expect(clausesByDoc.has(d.doc_id)).toBe(true);
      expect(clausesByDoc.get(d.doc_id)!.length).toBeGreaterThan(0);
    }
    expect(new Set(docs.map((d) => d.doc_id)).size).toBe(docs.length);
  });

  it("only monitored docs have clause files", () => {
    const monitored = new Set(docs.filter((d) => d.monitored).map((d) => d.doc_id));
    for (const id of clausesByDoc.keys()) expect(monitored.has(id)).toBe(true);
    for (const d of docs.filter((d) => !d.monitored)) {
      expect(existsSync(path.join(DIR, "clauses", `${d.doc_id}.json`))).toBe(false);
    }
  });

  it("uses only the 14 vertical slugs; the 9 empty verticals hold 2-3 unmonitored samples", () => {
    for (const d of docs) expect(VERTICALS).toContain(d.vertical);
    for (const v of EMPTY_VERTICALS) {
      const inV = docs.filter((d) => d.vertical === v);
      expect(inV.length).toBeGreaterThanOrEqual(2);
      expect(inV.length).toBeLessThanOrEqual(3);
      for (const d of inV) {
        expect(d.monitored).toBe(false);
        expect(d.cited_citations).toEqual([]);
        expect(d.two_signature).toBe(false);
      }
    }
    for (const v of ["compliance-legal", "policy-governance", "operations-processes", "workforce-hr", "environmental-esg"]) {
      expect(docs.some((d) => d.vertical === v && d.monitored)).toBe(true);
    }
  });

  it("two-signature docs have no approver; all others do or are samples", () => {
    for (const d of docs.filter((d) => d.two_signature)) {
      expect(["RPL-CS-PRO-007", "RPL-CS-PRO-011"]).toContain(d.doc_id);
      expect(d.approver).toBeNull();
    }
    for (const id of ["RPL-CS-PRO-007", "RPL-CS-PRO-011"]) {
      const d = docs.find((x) => x.doc_id === id)!;
      expect(d.two_signature).toBe(true);
      expect(d.approver).toBeNull();
    }
    for (const d of docs.filter((d) => d.monitored && !d.two_signature)) expect(d.approver).not.toBeNull();
  });

  it("owners, reviewers and approvers are drawn from the people directory", () => {
    const byId = new Map(people.map((p) => [p.person_id, p]));
    for (const d of docs) {
      for (const p of [d.owner, d.reviewer, d.approver]) {
        if (p) expect(byId.get(p.person_id)).toEqual(p);
      }
    }
  });

  it("clause ids are unique, belong to their doc, and parents resolve", () => {
    const all = new Set<string>();
    for (const [docId, clauses] of clausesByDoc) {
      const local = new Set(clauses.map((c) => c.clause_id));
      expect(local.size).toBe(clauses.length);
      clauses.forEach((c, i) => {
        expect(c.doc_id).toBe(docId);
        expect(c.clause_id.startsWith(`${docId}:`)).toBe(true);
        expect(c.ordinal).toBe(i + 1);
        expect(all.has(c.clause_id)).toBe(false);
        all.add(c.clause_id);
        if (c.parent_clause_id) {
          expect(local.has(c.parent_clause_id)).toBe(true);
          expect(c.parent_clause_id).not.toBe(c.clause_id);
        }
        if (c.unit_kind === "table_row" || c.unit_kind === "register_row") expect(c.row_cells).toBeTruthy();
      });
    }
    const docIds = new Set(docs.map((d) => d.doc_id));
    for (const c of [...clausesByDoc.values()].flat()) expect(docIds.has(c.doc_id)).toBe(true);
  });

  it("registers produce register_row clauses; key clause ids exist", () => {
    const count = (id: string) => clausesByDoc.get(id)!.filter((c) => c.unit_kind === "register_row").length;
    expect(count("RPL-CMP-REG-001")).toBe(70);
    expect(count("RPL-REG-CAL-2025")).toBe(48);
    expect(count("RPL-LEG-RRS-001")).toBe(86);
    const ids = new Set([...clausesByDoc.values()].flat().map((c) => c.clause_id));
    for (const id of ["RPL-CS-PRO-004:8.2", "RPL-CMP-REG-001:OBL-2024-0047", "RPL-CS-PRO-004:App-A.F6"]) {
      expect(ids.has(id)).toBe(true);
    }
    expect(clausesByDoc.get("RPL-TAR-GRR-012")!.some((c) => c.unit_kind === "tariff_subrule")).toBe(true);
    expect(clausesByDoc.get("RPL-CS-PRO-004")!.some((c) => c.unit_kind === "form_field")).toBe(true);
  });

  it("profile carries the applicability attributes", () => {
    expect(profile.state).toBe("Indiana");
    expect(profile.customers).toBeGreaterThan(400000);
    const attr = (k: string) => profile.attributes.find((a) => a.key === k);
    expect(attr("owns_generating_units")?.value).toBe(false);
    expect(attr("has_gas_operations")?.value).toBe(false);
    expect(attr("standby_generator_count")?.value).toBe(3);
    for (const a of profile.attributes) expect(a.source).toBe("company_profile.yaml");
  });
});

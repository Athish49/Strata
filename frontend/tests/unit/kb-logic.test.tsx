import { describe, expect, it } from "vitest";
import { actionHref, agencyHref, decodeCatchAll, encodePathValue, safeDecode, sectionHref, sourceSystemOfCitation } from "@/components/kb/links";
import { buildTree, filterSections, paginate, type TreeSection } from "@/components/kb/tree";
import { amendmentTarget, citedByDocuments, crossRefs } from "@/components/kb/section-utils";
import { actionDisplayTitle, stripMarkup } from "@/components/kb/bits";
import { buildBlocks, wordSegments } from "@/components/kb/LineDiffView";
import { toParagraphs } from "@/components/kb/SectionBody";
import { groupAgencies, isCodebookOnly } from "@/components/kb/agencies";
import { attributeLabel, attributeValue, docsByPerson, groupByDepartment, reportingRows } from "@/components/company/people";
import type { Agency, DocumentMeta, Person } from "@/lib/api/schemas";

describe("KB links", () => {
  it("encodes spaces and keeps slashes as segment separators", () => {
    expect(sectionHref("iac", "170 IAC 4-1-16")).toBe("/app/regulations/sections/iac/170%20IAC%204-1-16");
    expect(actionHref("federal_register", "2025/02 101")).toBe("/app/regulations/actions/federal_register/2025/02%20101");
    expect(agencyHref("iurc", "activity")).toBe("/app/regulations/iurc?tab=activity");
    expect(encodePathValue("a b/c#d")).toBe("a%20b/c%23d");
  });
  it("round-trips through a catch-all param, decoded or not", () => {
    expect(decodeCatchAll(["2025", "02%20101"])).toBe("2025/02 101");
    expect(decodeCatchAll("170%20IAC%204-1-16")).toBe("170 IAC 4-1-16");
    expect(decodeCatchAll(["170 IAC 4-1-16"])).toBe("170 IAC 4-1-16");
    expect(decodeCatchAll(undefined)).toBe("");
    expect(safeDecode("%E0%A4%A")).toBe("%E0%A4%A"); // malformed escape does not throw
  });
  it("guesses the source system of a cross-reference", () => {
    expect(sourceSystemOfCitation("18 CFR 35.28")).toBe("cfr");
    expect(sourceSystemOfCitation("326 IAC 1-1-1")).toBe("iac");
  });
});

const sec = (citation: string, title: string, part: string, rule: string, status: "approved" | "repealed" = "approved", heading = "H"): TreeSection => ({
  citation,
  source_system: "iac",
  title_number: title,
  part_or_article: part,
  rule_key: rule,
  heading,
  status,
  section_number: "1",
});

describe("section tree", () => {
  const all = [
    sec("326 IAC 10-1-1", "326", "10", "326 IAC 10-1"),
    sec("326 IAC 2-1-1", "326", "2", "326 IAC 2-1"),
    sec("326 IAC 2-1-9", "326", "2", "326 IAC 2-1", "repealed", "Old rule"),
    sec("327 IAC 1-1-1", "327", "1", "327 IAC 1-1", "approved", "Water things"),
  ];
  it("groups Title > Part > Rule with natural sorting", () => {
    const t = buildTree(all);
    expect(t.map((x) => x.label)).toEqual(["326 IAC", "327 IAC"]);
    expect(t[0].parts.map((p) => p.label)).toEqual(["Article 2", "Article 10"]);
    expect(t[0].count).toBe(3);
    expect(t[0].parts[0].rules[0].sections.map((s) => s.citation)).toEqual(["326 IAC 2-1-1", "326 IAC 2-1-9"]);
  });
  it("hides repealed unless asked and filters by citation or heading", () => {
    expect(filterSections(all, "", false)).toHaveLength(3);
    expect(filterSections(all, "", true)).toHaveLength(4);
    expect(filterSections(all, "water", false).map((s) => s.citation)).toEqual(["327 IAC 1-1-1"]);
    expect(filterSections(all, "2-1-9", true)).toHaveLength(1);
    expect(filterSections(all, "2-1-9", false)).toHaveLength(0);
  });
  it("paginates with a clamped page", () => {
    const items = Array.from({ length: 120 }, (_, i) => i);
    expect(paginate(items, 3, 50)).toMatchObject({ page: 3, pages: 3 });
    expect(paginate(items, 3, 50).items).toHaveLength(20);
    expect(paginate(items, 99, 50).page).toBe(3);
    expect(paginate([], 1, 50)).toMatchObject({ page: 1, pages: 1, items: [] });
  });
});

describe("section helpers", () => {
  it("drops self references and duplicates in cross-references", () => {
    const refs = crossRefs({ citation: "326 IAC 1-1-1", iac_cross_refs: ["326 IAC 1-1-1", "326 IAC 1-1-3", "326 IAC 1-1-3"], federal_refs: ["40 CFR 60.1"] });
    expect(refs.map((r) => r.citation)).toEqual(["326 IAC 1-1-3", "40 CFR 60.1"]);
    expect(refs[1].href).toBe("/app/regulations/sections/cfr/40%20CFR%2060.1");
  });
  it("links CFR amendments to the Federal Register action, leaves IAC ids as text", () => {
    expect(amendmentTarget({ source_system: "cfr", amendment_source: "2025-06941" })).toEqual({
      label: "2025-06941",
      href: "/app/regulations/actions/federal_register/2025-06941",
    });
    expect(amendmentTarget({ source_system: "iac", amendment_source: "RM-21-04" })).toEqual({ label: "RM-21-04", href: null });
    expect(amendmentTarget({ source_system: "iac", amendment_source: null })).toBeNull();
  });
  it("groups citing documents by vertical in fixed order", () => {
    const d = (doc_id: string, vertical: string, cited: string[]) => ({ doc_id, vertical, cited_citations: cited, title: doc_id }) as unknown as DocumentMeta;
    const g = citedByDocuments(
      [d("B", "policy-governance", ["x"]), d("A", "compliance-legal", ["x"]), d("C", "compliance-legal", ["y"])],
      "x",
    );
    expect(g.map((x) => x.name)).toEqual(["Compliance & Legal", "Policy & Governance Documents"]);
    expect(g[0].docs.map((x) => x.doc_id)).toEqual(["A"]);
  });
});

describe("action text", () => {
  it("strips inline markup and replaces meaningless titles", () => {
    expect(stripMarkup("PM<INF>2.5</INF> standard")).toBe("PM2.5 standard");
    expect(actionDisplayTitle({ title: "PDF", action_type: "order", source_id: "GAO-2019-02" })).toBe("Order GAO-2019-02");
    expect(actionDisplayTitle({ title: "", action_type: "rulemaking", source_id: "LSA-26-1" })).toBe("Rulemaking LSA-26-1");
    expect(actionDisplayTitle({ title: "A real title here", action_type: "order", source_id: "1" })).toBe("A real title here");
  });
});

describe("line diff", () => {
  it("marks word-level changes inside a paired line", () => {
    const segs = wordSegments("shall notify within 10 days", "shall notify within 15 days");
    expect(segs.filter((s) => s.op === "delete").map((s) => s.text.trim())).toEqual(["10"]);
    expect(segs.filter((s) => s.op === "insert").map((s) => s.text.trim())).toEqual(["15"]);
  });
  it("collapses long unchanged runs but keeps context", () => {
    const equal = (n: number) => Array.from({ length: n }, (_, i) => ({ op: "equal" as const, line: `l${i}` }));
    const blocks = buildBlocks([...equal(10), { op: "delete", line: "a" }, { op: "insert", line: "b" }, ...equal(10)]);
    expect(blocks.map((b) => b.kind)).toEqual(["skip", "equal", "change", "equal", "skip"]);
    expect(blocks[0]).toEqual({ kind: "skip", count: 8 });
    expect(buildBlocks([{ op: "equal", line: "x" }])).toEqual([{ kind: "equal", lines: ["x"] }]);
  });
  it("splits very long text into readable paragraphs without losing words", () => {
    const text = Array.from({ length: 200 }, (_, i) => `Sentence number ${i} says something.`).join(" ");
    const paras = toParagraphs(text);
    expect(paras.length).toBeGreaterThan(3);
    expect(paras.join(" ").replace(/\s+/g, " ")).toBe(text);
  });
});

describe("agencies", () => {
  const a = (slug: string, level: "federal" | "state", feed: boolean) => ({ slug, level, has_activity_feed: feed }) as unknown as Agency;
  it("groups by level and flags codebook-only agencies", () => {
    const g = groupAgencies([a("ferc", "federal", true), a("iurc", "state", true), a("idol", "state", false)]);
    expect(g.federal.map((x) => x.slug)).toEqual(["ferc"]);
    expect(g.state.map((x) => x.slug)).toEqual(["iurc", "idol"]);
    expect(isCodebookOnly(g.state[1])).toBe(true);
  });
});

describe("company people", () => {
  const p = (person_id: string, department: string, reports_to_id: string | null): Person => ({ person_id, name: person_id, title: "t", department, reports_to_id });
  const people = [p("P02", "Legal", "P01"), p("P01", "Executive", null), p("P03", "Legal", "P02"), p("P09", "X", "P99")];
  it("groups by department and builds the reporting tree", () => {
    expect(groupByDepartment(people).map((g) => g.department)).toEqual(["Executive", "Legal", "X"]);
    expect(reportingRows(people).map((r) => `${r.person.person_id}:${r.depth}`)).toEqual(["P01:0", "P02:1", "P03:2", "P09:0"]);
  });
  it("survives a reporting cycle", () => {
    const rows = reportingRows([p("A", "d", "B"), p("B", "d", "A")]);
    expect(rows.length).toBeLessThanOrEqual(2);
  });
  it("lists the documents each person owns, reviews or approves", () => {
    const doc = { doc_id: "D1", owner: p("P01", "", null), reviewer: p("P02", "", null), approver: null } as unknown as DocumentMeta;
    const m = docsByPerson([doc]);
    expect(m.get("P01")?.[0].role).toBe("Owner");
    expect(m.get("P02")?.[0].role).toBe("Reviewer");
    expect(m.has("P03")).toBe(false);
  });
  it("formats attribute keys and values", () => {
    expect(attributeLabel("owns_generating_units")).toBe("Owns generating units");
    expect(attributeLabel("has_spcc_plans")).toBe("Has SPCC plans");
    expect(attributeValue(true)).toBe("Yes");
    expect(attributeValue(false)).toBe("No");
    expect(attributeValue(407491)).toBe("407,491");
    expect(attributeValue("investor_owned")).toBe("investor owned");
    expect(attributeValue("")).toBe("Not set");
  });
});

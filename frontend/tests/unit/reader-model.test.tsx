import { describe, expect, it } from "vitest";
import type { Annotation, Clause } from "@/lib/api/schemas";
import { parseBlocks, isBlankText } from "@/components/documents/reader/markdown";
import {
  buildReaderModel,
  cellOffset,
  cleanCells,
  clearedClauses,
  notesByClause,
  orderedKeys,
  prettyHeading,
  railFindings,
} from "@/components/documents/reader/model";

const clause = (id: string, ordinal: number, over: Partial<Clause> = {}): Clause => ({
  clause_id: `D:${id}`,
  doc_id: "D",
  ordinal,
  heading_path: ["1. Purpose"],
  unit_kind: "section",
  text_raw: `**${id}** Some text.`,
  row_cells: null,
  parent_clause_id: null,
  ...over,
});

const ann = (clause_id: string, over: Partial<Annotation> = {}): Annotation => ({
  clause_id,
  kind: "cleared",
  verdict: null,
  finding_id: null,
  change_id: "ch1",
  citation: "170 IAC 1-1",
  quote_span: null,
  reason: "Checked: no impact.",
  ...over,
});

describe("markdown block parser", () => {
  it("keeps raw offsets for paragraphs, tables and list items", () => {
    const raw = "**1.1** Intro line.\n\n| Field | |\n|---|---|\n| **A.F1 — Name** | ____ |\n\n- first\n- second";
    const blocks = parseBlocks(raw);
    expect(blocks.map((b) => b.type)).toEqual(["p", "table", "list"]);
    const p = blocks[0];
    if (p.type !== "p") throw new Error("p");
    expect(raw.slice(p.lines[0].start, p.lines[0].start + 6)).toBe("**1.1*");
    const t = blocks[1];
    if (t.type !== "table") throw new Error("table");
    expect(t.header?.map((c) => c.text)).toEqual(["Field", ""]);
    expect(t.rows).toHaveLength(1);
    const cell = t.rows[0][0];
    expect(raw.slice(cell.start, cell.start + cell.text.length)).toBe(cell.text);
    const l = blocks[2];
    if (l.type !== "list") throw new Error("list");
    expect(l.items.map((i) => raw.slice(i.start, i.start + i.text.length))).toEqual(["first", "second"]);
  });

  it("treats rules-only and blank-form text as blank", () => {
    expect(isBlankText("\n\n---\n")).toBe(true);
    expect(isBlankText("")).toBe(true);
    expect(isBlankText("Hello")).toBe(false);
  });
});

describe("annotation grouping", () => {
  it("aggregates cleared annotations per clause and keeps findings individual", () => {
    const m = notesByClause([
      ann("D:1"),
      ann("D:1", { change_id: "ch2" }),
      ann("D:1", { change_id: "ch3" }),
      ann("D:2", { kind: "finding", verdict: "action_required", finding_id: "f1" }),
    ]);
    expect(m.get("D:1")?.cleared).toHaveLength(3);
    expect(m.get("D:1")?.findings).toHaveLength(0);
    expect(m.get("D:2")?.findings).toHaveLength(1);
  });

  it("lists findings in document order, worst verdict first, and cleared clauses once each", () => {
    const clauses = [clause("1", 1), clause("2", 2), clause("3", 3)];
    const annotations = [
      ann("D:3", { kind: "finding", verdict: "info", finding_id: "f3" }),
      ann("D:2", { kind: "finding", verdict: "review", finding_id: "f2" }),
      ann("D:2", { kind: "finding", verdict: "action_required", finding_id: "f2b" }),
      ann("D:1"),
      ann("D:1", { change_id: "x" }),
    ];
    expect(railFindings(clauses, annotations).map((f) => f.findingId)).toEqual(["f2b", "f2", "f3"]);
    const cl = clearedClauses(clauses, notesByClause(annotations));
    expect(cl).toHaveLength(1);
    expect(cl[0].reasons).toHaveLength(2);
  });
});

describe("reader model", () => {
  it("de-duplicates consecutive headings, hides the doc id heading and prettifies snake_case", () => {
    const clauses = [
      clause("1", 1, { heading_path: ["1. Purpose"] }),
      clause("2", 2, { heading_path: ["1. Purpose"] }),
      clause("3", 3, { heading_path: ["D", "compliance_register_2024-12-31"] }),
    ];
    const m = buildReaderModel(clauses, new Map(), "D");
    const heads = m.items.filter((i) => i.kind === "heading").map((i) => (i.kind === "heading" ? i.text : ""));
    expect(heads).toEqual(["1. Purpose", "Compliance register 2024-12-31"]);
    expect(prettyHeading("Plain heading")).toBe("Plain heading");
  });

  it("folds empty TOC clauses into headings and maps them to the next visible item", () => {
    const clauses = [
      clause("1", 1, { heading_path: ["Table of Contents"], text_raw: "" }),
      clause("2", 2, { heading_path: ["1. Purpose"], text_raw: "" }),
      clause("3", 3, { heading_path: ["1. Purpose"] }),
    ];
    const m = buildReaderModel(clauses, new Map());
    expect(m.items.map((i) => i.kind)).toEqual(["heading", "heading", "clause"]);
    expect(m.indexByClause.get("D:1")).toBe(1);
    expect(m.indexByClause.get("D:3")).toBe(2);
  });

  it("keeps an empty clause that carries an annotation", () => {
    const clauses = [clause("1", 1, { text_raw: "" })];
    const m = buildReaderModel(clauses, notesByClause([ann("D:1")]));
    expect(m.items.some((i) => i.kind === "clause")).toBe(true);
  });

  it("groups register rows into one table with a header and drops junk cell keys", () => {
    const row = (id: string, o: number, cells: Record<string, unknown> | null) =>
      clause(id, o, {
        unit_kind: "register_row",
        heading_path: ["Register"],
        text_raw: Object.entries(cells ?? {})
          .filter(([, v]) => typeof v === "string")
          .map(([k, v]) => `${k}: ${v}`)
          .join("\n"),
        row_cells: cells as Record<string, string> | null,
      });
    const clauses = [
      clause("1", 1),
      row("R1", 2, { id: "R1", citation: "170 IAC 1-1", null: ["x"] }),
      row("R2", 3, { id: "R2", citation: "170 IAC 1-2" }),
      row("R3", 4, null),
    ];
    const m = buildReaderModel(clauses, new Map());
    const kinds = m.items.map((i) => i.kind);
    expect(kinds.filter((k) => k === "table-head")).toHaveLength(1);
    expect(kinds.filter((k) => k === "table-row")).toHaveLength(2);
    const head = m.items.find((i) => i.kind === "table-head");
    if (head?.kind !== "table-head") throw new Error("head");
    expect(head.group.columns).toEqual(["id", "citation"]);
    expect(cleanCells(clauses[1])).toEqual({ id: "R1", citation: "170 IAC 1-1" });
  });

  it("collapses wide registers to a few columns and locates cell offsets in text_raw", () => {
    const cells: Record<string, string> = {};
    for (let i = 0; i < 12; i++) cells[`col_${i}`] = `value ${i}`;
    cells.status = "compliant";
    const c = clause("W", 1, {
      unit_kind: "register_row",
      heading_path: ["Reg"],
      row_cells: cells,
      text_raw: Object.entries(cells)
        .map(([k, v]) => `${k}: ${v}`)
        .join("\n"),
    });
    const m = buildReaderModel([c], new Map());
    const head = m.items.find((i) => i.kind === "table-head");
    if (head?.kind !== "table-head") throw new Error("head");
    expect(head.group.visible).toHaveLength(5);
    expect(head.group.visible).toContain("status");
    expect(head.group.columns).toHaveLength(13);
    expect(orderedKeys(c, cells)[0]).toBe("col_0");
    const off = cellOffset(c, "col_1", "value 1");
    expect(off).not.toBeNull();
    expect(c.text_raw.slice(off as number, (off as number) + 7)).toBe("value 1");
  });
});

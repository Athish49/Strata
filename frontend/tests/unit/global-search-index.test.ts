import { describe, expect, it } from "vitest";
import { normalizeStatus } from "@/components/documents/board/logic";
import { idRank, matchesAll, searchClauses, snippet, toClauseEntry } from "@/components/shell/search-index";

const clause = (clause_id: string, text_raw: string, heading_path: string[] = []) =>
  ({ clause_id, doc_id: "RPL-X-1", ordinal: 1, heading_path, unit_kind: "section", text_raw, row_cells: null }) as never;

describe("normalizeStatus", () => {
  it("accepts keys and the aliases other pages link with", () => {
    expect(normalizeStatus("flagged")).toBe("action_needed");
    expect(normalizeStatus("action_needed")).toBe("action_needed");
    expect(normalizeStatus("cleared")).toBe("cleared");
    expect(normalizeStatus("bogus")).toBeNull();
    expect(normalizeStatus(null)).toBeNull();
  });
});

describe("global search index", () => {
  it("ranks ids exact < prefix < contains", () => {
    expect(idRank("170 IAC 4-1-16", "170 iac 4-1-16")).toBe(0);
    expect(idRank("170 IAC 4-1-16", "170 IAC 4-1")).toBe(1);
    expect(idRank("170 IAC 4-1-16", "4-1-16")).toBe(2);
    expect(idRank("170 IAC 4-1-16", "zzz")).toBeNull();
  });
  it("matches every token", () => {
    expect(matchesAll("disconnection of service", "service disconn")).toBe(true);
    expect(matchesAll("disconnection of service", "service tariff")).toBe(false);
  });
  it("finds clauses by id prefix first, then text, and strips markdown", () => {
    const entries = [
      clause("RPL-X-1:1.1", "The **noncontroversial** filing rule."),
      clause("RPL-X-1:8.1", "Other text"),
      clause("RPL-X-1:8.2", "More text"),
    ].map(toClauseEntry);
    expect(searchClauses(entries, "noncontroversial").map((e) => e.localId)).toEqual(["1.1"]);
    expect(searchClauses(entries, "RPL-X-1:8").map((e) => e.localId)).toEqual(["8.1", "8.2"]);
    expect(searchClauses(entries, "x")).toEqual([]);
    expect(entries[0].text).not.toContain("*");
  });
  it("builds a snippet around the hit", () => {
    const text = `${"a ".repeat(100)}needle ${"b ".repeat(100)}`;
    const s = snippet(text, "needle");
    expect(s).toContain("needle");
    expect(s.startsWith("…")).toBe(true);
  });
});

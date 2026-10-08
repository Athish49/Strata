import { afterEach, describe, expect, it, vi } from "vitest";
import { kbHttp } from "@/lib/api/http/kb";

function stub(handler: (url: string) => { status?: number; body?: unknown }) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const { status = 200, body = null } = handler(url);
      return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
    }),
  );
  return calls;
}

const rawAction = {
  source_system: "iurc_gaos",
  source_id: "GAO 2024/1",
  agency: "iurc",
  action_type: "gao",
  status: "active",
  title: "T",
  source_url: "http://x",
  date_published: null,
  cfr_references: null,
};

afterEach(() => vi.unstubAllGlobals());

describe("kbHttp", () => {
  it("maps listSections query params and drops empties", async () => {
    const calls = stub(() => ({ body: { items: [], total: 0, page: 2, limit: 10 } }));
    await kbHttp.listSections({ agency: "iurc", source_system: "iac", search: "", page: 2, limit: 10 });
    expect(calls[0]).toMatch(/\/engine\/ui\/kb\/sections\?agency=iurc&source_system=iac&page=2&limit=10$/);
  });

  it("encodes citation segments and returns null on 404", async () => {
    const calls = stub(() => ({ status: 404, body: { detail: "nope" } }));
    expect(await kbHttp.getSection("iac", "170 IAC 4-1-16")).toBeNull();
    expect(calls[0]).toMatch(/\/engine\/ui\/kb\/sections\/iac\/170%20IAC%204-1-16$/);
    expect(await kbHttp.getAgency("zzz")).toBeNull();
    expect(await kbHttp.getVersionHistory("cfr", "18 CFR 35.19")).toEqual([]);
    expect(calls[2]).toMatch(/\/sections\/cfr\/18%20CFR%2035\.19\/versions$/);
  });

  it("listActions maps stream to source_system and adapts rows", async () => {
    const calls = stub(() => ({ body: { items: [rawAction], total: 1, page: 1, limit: 50 } }));
    const page = await kbHttp.listActions({ stream: "iurc_gaos", agency: "iurc", date_from: "2024-01-01" });
    expect(calls[0]).toMatch(/\/actions\?agency=iurc&source_system=iurc_gaos&date_from=2024-01-01$/);
    expect(page.items[0]).toMatchObject({
      stream: "iurc_gaos",
      abstract: "",
      cfr_references: [],
      legal_refs: [],
      din: null,
      related: [],
      date_published: null,
    });
  });

  it("listActions returns empty page for conflicting stream/source_system without fetching", async () => {
    const calls = stub(() => ({}));
    const page = await kbHttp.listActions({ stream: "a", source_system: "b" });
    expect(page.items).toEqual([]);
    expect(calls).toHaveLength(0);
  });

  it("getAction encodes each segment of ids containing slashes and maps related", async () => {
    const calls = stub(() => ({
      body: {
        ...rawAction,
        abstract: "abs",
        related_actions_resolved: [
          { relationship_type: "supersedes", action: { source_id: "A" } },
          { relationship_type: "weird", action: { source_id: "B" } },
        ],
      },
    }));
    const a = await kbHttp.getAction("iurc_gaos", "GAO 2024/1");
    expect(calls[0]).toMatch(/\/actions\/iurc_gaos\/GAO%202024\/1$/);
    expect(a?.abstract).toBe("abs");
    expect(a?.related).toEqual([
      { source_id: "A", relationship_type: "supersedes" },
      { source_id: "B", relationship_type: "related_to" },
    ]);
  });

  it("getAction returns null on 404", async () => {
    stub(() => ({ status: 404, body: { detail: "x" } }));
    expect(await kbHttp.getAction("s", "i")).toBeNull();
  });

  it("compare diffs first vs last version by default and by date", async () => {
    const versions = [
      { snapshot: "S1", snapshot_date: "2024-12-31", text: "a\nb\nc" },
      { snapshot: "S2", snapshot_date: "2025-12-31", text: "a\nB\nc" },
    ];
    stub(() => ({ body: versions }));
    const d = await kbHttp.compare("iac", "170 IAC 1-1");
    expect(d).toEqual([
      { op: "equal", line: "a" },
      { op: "delete", line: "b" },
      { op: "insert", line: "B" },
      { op: "equal", line: "c" },
    ]);
    const same = await kbHttp.compare("iac", "170 IAC 1-1", "2024-12-31", "2024-12-31");
    expect(same.every((l) => l.op === "equal")).toBe(true);
  });

  it("compare returns [] when no versions", async () => {
    stub(() => ({ status: 404, body: {} }));
    expect(await kbHttp.compare("iac", "x")).toEqual([]);
  });
});

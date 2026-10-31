import { afterEach, describe, expect, it, vi } from "vitest";
import { companyHttp } from "@/lib/api/http/company";

const person = { person_id: "P01", name: "N", title: "T", department: "D", reports_to_id: null };
const doc = (doc_id: string, vertical: string) => ({
  doc_id,
  title: "t",
  version: "1",
  status: "Approved",
  effective_date: null,
  approved_date: null,
  law_as_of: null,
  next_review: null,
  review_cycle: null,
  vertical,
  owner: person,
  reviewer: person,
  approver: null,
  two_signature: true,
  monitored: true,
  doc_type: "Procedure",
  cited_citations: [],
});

function stub(handler: (url: string) => { status?: number; body?: unknown }) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      calls.push(url);
      const { status = 200, body = null } = handler(url);
      return new Response(JSON.stringify(body), { status });
    }),
  );
  return calls;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("companyHttp", () => {
  it("keeps unclassified documents and maps unknown verticals to unclassified (warns only for unknown)", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const calls = stub(() => ({ body: [doc("A", "compliance-legal"), doc("B", "unclassified"), doc("C", "nope")] }));
    const docs = await companyHttp.listDocuments();
    expect(docs.map((d) => [d.doc_id, d.vertical])).toEqual([
      ["A", "compliance-legal"],
      ["B", "unclassified"],
      ["C", "unclassified"],
    ]);
    expect(calls[0]).toMatch(/\/company\/documents$/);
    expect(warn).toHaveBeenCalledOnce();
  });

  it("getDocument: encodes id, null on 404, unknown vertical becomes unclassified", async () => {
    vi.spyOn(console, "warn").mockImplementation(() => {});
    let n = 0;
    const calls = stub(() => (n++ === 0 ? { status: 404, body: { detail: "x" } } : { body: doc("B", "nope") }));
    expect(await companyHttp.getDocument("RPL CS/1")).toBeNull();
    expect(calls[0]).toMatch(/\/company\/documents\/RPL%20CS%2F1$/);
    expect((await companyHttp.getDocument("B"))?.vertical).toBe("unclassified");
  });

  it("documentMetaSchema accepts the new optional fields and extra keys", async () => {
    stub(() => ({
      body: [{ ...doc("D", "workforce-hr"), doc_number: "HR-1", vertical_name: "Workforce & Safety", ingest_status: "pending", lifecycle_state: "pending", brand_new_key: 1 }],
    }));
    const [d] = await companyHttp.listDocuments();
    expect(d).toMatchObject({ doc_number: "HR-1", ingest_status: "pending", lifecycle_state: "pending", vertical_name: "Workforce & Safety" });
  });

  it("listClauses returns [] on 404 and parses rows", async () => {
    stub(() => ({ status: 404, body: {} }));
    expect(await companyHttp.listClauses("X")).toEqual([]);
    const calls = stub(() => ({
      body: [{ clause_id: "X:1", doc_id: "X", ordinal: 1, heading_path: [], unit_kind: "section", text_raw: "", row_cells: null }],
    }));
    expect(await companyHttp.listClauses("X")).toHaveLength(1);
    expect(calls[0]).toMatch(/\/company\/documents\/X\/clauses$/);
  });

  it("listPeople and getProfile hit the right paths", async () => {
    let calls = stub(() => ({ body: [person] }));
    expect(await companyHttp.listPeople()).toHaveLength(1);
    expect(calls[0]).toMatch(/\/company\/people$/);
    calls = stub(() => ({
      body: { name: "R", type: "t", state: "s", customers: 1, regulator: "r", attributes: [{ key: "k", value: true, source: "y" }] },
    }));
    expect((await companyHttp.getProfile()).name).toBe("R");
    expect(calls[0]).toMatch(/\/company\/profile$/);
  });
});

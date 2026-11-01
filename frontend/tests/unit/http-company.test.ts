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
  it("keeps unclassified documents as-is; the backend already normalises `vertical` (task 3.7)", async () => {
    // app/api/company/routes.py's vertical_slug() always returns a real slug or "unclassified"
    // before the response leaves the server, against the same company.verticals table
    // GET /company/verticals reads -- so there is no "unknown slug" case to defend against
    // here any more; normalizeDocument only catches a genuinely empty/missing value.
    const calls = stub(() => ({ body: [doc("A", "compliance-ethics"), doc("B", "unclassified")] }));
    const docs = await companyHttp.listDocuments();
    expect(docs.map((d) => [d.doc_id, d.vertical])).toEqual([
      ["A", "compliance-ethics"],
      ["B", "unclassified"],
    ]);
    expect(calls[0]).toMatch(/\/company\/documents$/);
  });

  it("listDocuments/getDocument: an empty vertical becomes unclassified", async () => {
    const calls = stub(() => ({ body: [doc("A", "")] }));
    expect((await companyHttp.listDocuments())[0].vertical).toBe("unclassified");
    expect(calls[0]).toMatch(/\/company\/documents$/);
  });

  it("getDocument: encodes id, null on 404", async () => {
    let n = 0;
    const calls = stub(() => (n++ === 0 ? { status: 404, body: { detail: "x" } } : { body: doc("B", "compliance-ethics") }));
    expect(await companyHttp.getDocument("RPL CS/1")).toBeNull();
    expect(calls[0]).toMatch(/\/company\/documents\/RPL%20CS%2F1$/);
    expect((await companyHttp.getDocument("B"))?.vertical).toBe("compliance-ethics");
  });

  it("documentMetaSchema accepts the new optional fields and extra keys", async () => {
    stub(() => ({
      body: [{ ...doc("D", "workforce-employment"), doc_number: "HR-1", vertical_name: "Workforce & Employment", ingest_status: "pending", lifecycle_state: "pending", brand_new_key: 1 }],
    }));
    const [d] = await companyHttp.listDocuments();
    expect(d).toMatchObject({ doc_number: "HR-1", ingest_status: "pending", lifecycle_state: "pending", vertical_name: "Workforce & Employment" });
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

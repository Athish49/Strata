import type { CompanyApi } from "@/lib/api/client";
import { fixtures, loadClauses } from "./fixtures";
import { withLatency } from "./config";

export const companyApi: CompanyApi = {
  listDocuments: () => withLatency(() => fixtures().documents),
  getDocument: (doc_id) => withLatency(() => fixtures().documents.find((d) => d.doc_id === doc_id) ?? null),
  listClauses: (doc_id) => withLatency(() => loadClauses(doc_id)),
  listPeople: () => withLatency(() => fixtures().people),
  getProfile: () => withLatency(() => fixtures().profile),
};

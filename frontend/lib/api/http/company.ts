// CompanyApi over HTTP. See development_docs/ui_wiring_contract.md section 5. No fixtures.
import { z } from "zod";
import type { CompanyApi } from "../client";
import { clauseSchema, companyProfileSchema, documentMetaSchema } from "../schemas/company";
import type { DocumentMeta } from "../schemas/company";
import { personSchema } from "../schemas/common";
import { isVerticalSlug } from "../../verticals";
import { getJson, seg } from "./shared";

function keep(doc: DocumentMeta): boolean {
  if (isVerticalSlug(doc.vertical)) return true;
  console.warn(`Dropping document ${doc.doc_id}: unknown vertical "${doc.vertical}"`);
  return false;
}

export const companyHttp: CompanyApi = {
  async listDocuments() {
    return (await getJson("/company/documents", z.array(documentMetaSchema))).filter(keep);
  },

  async getDocument(doc_id) {
    const doc = await getJson(`/company/documents/${seg(doc_id)}`, documentMetaSchema.nullable(), { on404: null });
    return doc && keep(doc) ? doc : null;
  },

  listClauses: (doc_id) => getJson(`/company/documents/${seg(doc_id)}/clauses`, z.array(clauseSchema), { on404: [] }),

  listPeople: () => getJson("/company/people", z.array(personSchema)),

  getProfile: () => getJson("/company/profile", companyProfileSchema),
};

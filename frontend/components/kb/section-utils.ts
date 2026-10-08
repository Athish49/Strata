import type { CodeSection, DocumentMeta } from "@/lib/api/schemas";
import { compareVerticals, verticalName } from "@/lib/verticals";
import { actionHref, sectionHref, sourceSystemOfCitation } from "./links";

/** Cross-reference citations other than the section itself, de-duplicated, order kept. */
export function crossRefs(section: Pick<CodeSection, "citation" | "federal_refs" | "iac_cross_refs">): { citation: string; href: string }[] {
  const seen = new Set<string>([section.citation]);
  const out: { citation: string; href: string }[] = [];
  for (const c of [...(section.iac_cross_refs ?? []), ...(section.federal_refs ?? [])]) {
    const cit = (c ?? "").trim();
    if (!cit || seen.has(cit)) continue;
    seen.add(cit);
    out.push({ citation: cit, href: sectionHref(sourceSystemOfCitation(cit), cit) });
  }
  return out;
}

/** Where an amendment_source points: Federal Register document numbers link to the action; other ids stay text. */
export function amendmentTarget(section: Pick<CodeSection, "source_system" | "amendment_source">): { label: string; href: string | null } | null {
  const id = (section.amendment_source ?? "").trim();
  if (!id) return null;
  return { label: id, href: section.source_system === "cfr" ? actionHref("federal_register", id) : null };
}

/** Documents citing this section (exact citation match), grouped by vertical in the fixed vertical order. */
export function citedByDocuments(docs: DocumentMeta[], citation: string): { vertical: string; name: string; docs: DocumentMeta[] }[] {
  const by = new Map<string, DocumentMeta[]>();
  for (const d of docs) {
    if (!(d.cited_citations ?? []).includes(citation)) continue;
    by.set(d.vertical, [...(by.get(d.vertical) ?? []), d]);
  }
  return [...by.entries()]
    .sort(([a], [b]) => compareVerticals(a, b))
    .map(([vertical, list]) => ({ vertical, name: verticalName(vertical), docs: list.sort((x, y) => x.doc_id.localeCompare(y.doc_id)) }));
}

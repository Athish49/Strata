// URL helpers for KB routes. Citations and source ids can contain spaces and "/", so they live in
// catch-all segments: each "/"-separated piece is encoded on its own and decoded again on the page.

/** Decode one URL segment, tolerating malformed or already-decoded input. */
export function safeDecode(s: string): string {
  try {
    return decodeURIComponent(s);
  } catch {
    return s;
  }
}

/** "170 IAC 4-1-16" -> "170%20IAC%204-1-16"; "a/b c" -> "a/b%20c". */
export function encodePathValue(value: string): string {
  return value.split("/").map(encodeURIComponent).join("/");
}

/** Catch-all params (array or single string) -> the original value. */
export function decodeCatchAll(param: string | string[] | undefined): string {
  if (param === undefined) return "";
  const parts = Array.isArray(param) ? param : [param];
  return parts.map(safeDecode).join("/");
}

export const regulationsHref = () => "/app/regulations";
export const agencyHref = (slug: string, tab?: "rules" | "activity") =>
  `/app/regulations/${encodeURIComponent(slug)}${tab ? `?tab=${tab}` : ""}`;
export const sectionHref = (sourceSystem: string, citation: string) =>
  `/app/regulations/sections/${encodeURIComponent(sourceSystem)}/${encodePathValue(citation)}`;
export const actionHref = (sourceSystem: string, sourceId: string) =>
  `/app/regulations/actions/${encodeURIComponent(sourceSystem)}/${encodePathValue(sourceId)}`;

/** Source system of a citation string: "18 CFR 35.28" -> cfr, anything else -> iac. */
export function sourceSystemOfCitation(citation: string): "cfr" | "iac" {
  return /\bCFR\b/i.test(citation) ? "cfr" : "iac";
}

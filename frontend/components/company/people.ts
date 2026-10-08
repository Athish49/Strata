import type { DocumentMeta, Person } from "@/lib/api/schemas";

export type DocRole = "Owner" | "Reviewer" | "Approver";
export interface PersonDoc {
  doc: DocumentMeta;
  role: DocRole;
}

/** Documents each person owns, reviews or approves (keyed by person_id). */
export function docsByPerson(docs: DocumentMeta[]): Map<string, PersonDoc[]> {
  const m = new Map<string, PersonDoc[]>();
  const add = (id: string | undefined, doc: DocumentMeta, role: DocRole) => {
    if (!id) return;
    m.set(id, [...(m.get(id) ?? []), { doc, role }]);
  };
  for (const d of docs) {
    add(d.owner.person_id, d, "Owner");
    add(d.reviewer.person_id, d, "Reviewer");
    add(d.approver?.person_id, d, "Approver");
  }
  return m;
}

/** Departments in order of first appearance of their most senior member (lowest person_id), people sorted by id. */
export function groupByDepartment(people: Person[]): { department: string; people: Person[] }[] {
  const sorted = [...people].sort((a, b) => a.person_id.localeCompare(b.person_id, "en", { numeric: true }));
  const by = new Map<string, Person[]>();
  for (const p of sorted) by.set(p.department || "Other", [...(by.get(p.department || "Other") ?? []), p]);
  return [...by.entries()].map(([department, list]) => ({ department, people: list }));
}

export interface TreeNode {
  person: Person;
  depth: number;
}

/** Depth-first reporting tree flattened to rows. Roots are people with no (or an unknown) manager; cycles are cut. */
export function reportingRows(people: Person[]): TreeNode[] {
  const ids = new Set(people.map((p) => p.person_id));
  const kids = new Map<string, Person[]>();
  const roots: Person[] = [];
  const order = (a: Person, b: Person) => a.person_id.localeCompare(b.person_id, "en", { numeric: true });
  for (const p of [...people].sort(order)) {
    if (p.reports_to_id && ids.has(p.reports_to_id) && p.reports_to_id !== p.person_id) {
      kids.set(p.reports_to_id, [...(kids.get(p.reports_to_id) ?? []), p]);
    } else roots.push(p);
  }
  const out: TreeNode[] = [];
  const seen = new Set<string>();
  const walk = (p: Person, depth: number) => {
    if (seen.has(p.person_id)) return;
    seen.add(p.person_id);
    out.push({ person: p, depth });
    for (const c of kids.get(p.person_id) ?? []) walk(c, depth + 1);
  };
  roots.forEach((r) => walk(r, 0));
  return out;
}

const ACRONYMS = new Set(["pcb", "spcc", "osha", "iosha", "iurc", "kv", "ferc", "epa", "idem"]);

/** "owns_generating_units" -> "Owns generating units"; known acronyms stay upper-case ("has_spcc_plans" -> "Has SPCC plans"). */
export function attributeLabel(key: string): string {
  const words = key.split("_").filter(Boolean).map((w) => (ACRONYMS.has(w.toLowerCase()) ? w.toUpperCase() : w));
  if (words.length === 0) return key;
  const first = words[0];
  words[0] = first === first.toUpperCase() && first.length > 1 ? first : first.charAt(0).toUpperCase() + first.slice(1);
  return words.join(" ");
}

/** Display of an attribute value: booleans read Yes / No, numbers get separators, empty reads as not set. */
export function attributeValue(v: string | number | boolean | null | undefined): string {
  if (v === true) return "Yes";
  if (v === false) return "No";
  if (v === null || v === undefined || v === "") return "Not set";
  if (typeof v === "number") return new Intl.NumberFormat("en-US").format(v);
  return String(v).replace(/_/g, " ");
}

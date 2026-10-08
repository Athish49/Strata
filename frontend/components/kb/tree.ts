import type { CodeSection } from "@/lib/api/schemas";

export type TreeSection = Pick<
  CodeSection,
  "citation" | "source_system" | "title_number" | "part_or_article" | "rule_key" | "heading" | "status" | "section_number"
>;

export interface RuleNode<S extends TreeSection = TreeSection> {
  key: string;
  label: string;
  sections: S[];
}
export interface PartNode<S extends TreeSection = TreeSection> {
  key: string;
  label: string;
  rules: RuleNode<S>[];
  count: number;
}
export interface TitleNode<S extends TreeSection = TreeSection> {
  key: string;
  label: string;
  parts: PartNode<S>[];
  count: number;
}

const collator = new Intl.Collator("en", { numeric: true, sensitivity: "base" });

/** Case-insensitive match on citation or heading; hides repealed sections unless asked. */
export function filterSections<S extends TreeSection>(sections: S[], query: string, includeRepealed: boolean): S[] {
  const q = query.trim().toLowerCase();
  return sections.filter((s) => {
    if (!includeRepealed && s.status === "repealed") return false;
    if (!q) return true;
    return s.citation.toLowerCase().includes(q) || s.heading.toLowerCase().includes(q);
  });
}

/** Title -> Part/Article -> Rule -> Section, all sorted naturally (so "10" follows "9"). */
export function buildTree<S extends TreeSection>(sections: S[]): TitleNode<S>[] {
  const titles = new Map<string, Map<string, Map<string, S[]>>>();
  const sys = new Map<string, string>();
  for (const s of sections) {
    sys.set(s.title_number, s.source_system);
    const parts = titles.get(s.title_number) ?? new Map();
    const rules: Map<string, S[]> = parts.get(s.part_or_article) ?? new Map();
    const list = rules.get(s.rule_key) ?? [];
    list.push(s);
    rules.set(s.rule_key, list);
    parts.set(s.part_or_article, rules);
    titles.set(s.title_number, parts);
  }
  return [...titles.entries()]
    .sort(([a], [b]) => collator.compare(a, b))
    .map(([title, parts]) => {
      const isCfr = sys.get(title) === "cfr";
      const partNodes = [...parts.entries()]
        .sort(([a], [b]) => collator.compare(a, b))
        .map(([part, rules]): PartNode<S> => {
          const ruleNodes = [...rules.entries()]
            .sort(([a], [b]) => collator.compare(a, b))
            .map(([rule, list]): RuleNode<S> => ({
              key: rule,
              label: rule,
              sections: [...list].sort((x, y) => collator.compare(x.citation, y.citation)),
            }));
          return {
            key: `${title}|${part}`,
            label: part ? `${isCfr ? "Part" : "Article"} ${part}` : "Other",
            rules: ruleNodes,
            count: ruleNodes.reduce((n, r) => n + r.sections.length, 0),
          };
        });
      return {
        key: title,
        label: `${title} ${isCfr ? "CFR" : "IAC"}`,
        parts: partNodes,
        count: partNodes.reduce((n, p) => n + p.count, 0),
      };
    });
}

/** 1-based page slice with clamped page number. */
export function paginate<T>(items: T[], page: number, size: number): { items: T[]; page: number; pages: number } {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const p = Math.min(Math.max(1, page), pages);
  return { items: items.slice((p - 1) * size, p * size), page: p, pages };
}

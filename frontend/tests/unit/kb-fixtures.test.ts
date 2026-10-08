import { describe, expect, it } from "vitest";
import actionsJson from "../../fixtures/kb/actions.json";
import agenciesJson from "../../fixtures/kb/agencies.json";
import sectionsJson from "../../fixtures/kb/sections.json";
import versionsJson from "../../fixtures/kb/versions.json";
import {
  agencySchema,
  codeSectionSchema,
  regulatoryActionSchema,
  versionEntrySchema,
} from "../../lib/api/schemas/kb";

const agencies = agencySchema.array().parse(agenciesJson);
const sections = codeSectionSchema.array().parse(sectionsJson);
const actions = regulatoryActionSchema.array().parse(actionsJson);
const versions = Object.fromEntries(
  Object.entries(versionsJson as Record<string, unknown>).map(([k, v]) => [
    k,
    versionEntrySchema.array().parse(v),
  ]),
);

const sectionKeys = new Set(sections.map((s) => `${s.source_system}|${s.citation}`));
const cites = new Set(sections.map((s) => s.citation));
const resolves = (ref: string) => cites.has(ref) || [...cites].some((c) => c.startsWith(ref + "-") || c.startsWith(ref + "."));
const byAgency = (slug: string) => agencies.find((a) => a.slug === slug)!;

describe("kb fixtures", () => {
  it("has unique section citations and action ids", () => {
    expect(sectionKeys.size).toBe(sections.length);
    const ids = actions.map((a) => `${a.source_system}|${a.source_id}`);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("has the agency counts and snapshot dates from the audit", () => {
    expect(byAgency("iurc").section_count).toBe(647);
    expect(byAgency("ferc").action_count + byAgency("epa").action_count).toBe(990);
    expect(byAgency("iurc").action_count).toBe(42 + 138 + 19);
    expect(byAgency("idem").action_count).toBe(17);
    expect(byAgency("iurc").streams).toEqual(["iurc_gaos", "iurc_investigations", "iurc_rulemakings"]);
    expect(byAgency("iurc").s1_snapshot).toBe("2024-12-31");
    expect(byAgency("iurc").s2_snapshot).toBe("2025-12-31");
    expect(byAgency("ferc").s1_snapshot).toBe("2025-01-02");
    expect(byAgency("epa").s2_snapshot).toBe("2026-10-02");
  });

  it("marks 610/675 codebook-only", () => {
    for (const slug of ["iac-610", "iac-675"]) {
      const a = byAgency(slug);
      expect(a.agency_id).toBeNull();
      expect(a.has_activity_feed).toBe(false);
      expect(a.streams).toEqual([]);
      expect(actions.filter((x) => x.agency === slug)).toHaveLength(0);
    }
  });

  it("has depth and some repealed sections per codebook title", () => {
    for (const t of ["170", "326", "327", "610", "675", "18", "40"]) {
      const rows = sections.filter((s) => s.title_number === t);
      expect(rows.length).toBeGreaterThanOrEqual(19);
    }
    expect(sections.some((s) => s.status === "repealed")).toBe(true);
    for (const s of sections) {
      expect(s.placeholder).toBe(true);
      expect(s.citation.startsWith(`${s.title_number} ${s.source_system === "iac" ? "IAC" : "CFR"}`)).toBe(true);
      expect(s.rule_key.startsWith(`${s.title_number} `)).toBe(true);
    }
  });

  it("agency codebook titles cover section titles", () => {
    for (const s of sections) {
      const label = `${s.title_number} ${s.source_system === "iac" ? "IAC" : "CFR"}`;
      const ok = agencies.some((a) => a.codebook_titles.some((t) => t === label || t.startsWith(label + " ")));
      expect(ok, s.citation).toBe(true);
    }
  });

  it("resolves action references internally", () => {
    for (const a of actions) {
      for (const r of [...a.cfr_references, ...a.legal_refs]) expect(resolves(r), `${a.source_id} -> ${r}`).toBe(true);
    }
    for (const s of sections) {
      if (s.amendment_source) expect(actions.some((a) => a.source_id === s.amendment_source), s.citation).toBe(true);
      for (const r of s.iac_cross_refs) expect(resolves(r), `${s.citation} -> ${r}`).toBe(true);
      for (const r of s.federal_refs) expect(resolves(r), `${s.citation} -> ${r}`).toBe(true);
    }
  });

  it("has valid related[] chains per stream", () => {
    const rel = actions.flatMap((a) => a.related.map((r) => ({ a, r })));
    for (const { a, r } of rel) {
      const t = actions.find((x) => x.source_id === r.source_id && x.source_system === a.source_system);
      expect(t, `${a.source_id} -> ${r.source_id}`).toBeDefined();
      expect(r.source_id).not.toBe(a.source_id);
    }
    for (const key of new Set(actions.map((a) => `${a.agency}|${a.stream}`))) {
      const n = actions.filter((a) => `${a.agency}|${a.stream}` === key).length;
      expect(n, key).toBeGreaterThanOrEqual(8);
      expect(n, key).toBeLessThanOrEqual(15);
    }
    expect(rel.some(({ r }) => r.relationship_type === "supersedes")).toBe(true);
    expect(rel.some(({ r }) => r.relationship_type === "corrects")).toBe(true);
  });

  it("has a proposed-rule or advance-notice action for FERC, EPA, IURC", () => {
    for (const ag of ["ferc", "epa", "iurc"]) {
      expect(actions.some((a) => a.agency === ag && ["proposed_rule", "advance_notice"].includes(a.action_type)), ag).toBe(true);
    }
    for (const a of actions) expect(byAgency(a.agency)).toBeDefined();
  });

  it("has consistent S1/S2 version pairs", () => {
    expect(Object.keys(versions).length).toBeGreaterThanOrEqual(10);
    for (const [key, v] of Object.entries(versions)) {
      expect(sectionKeys.has(key), key).toBe(true);
      expect(v.map((e) => e.snapshot)).toEqual(["S1", "S2"]);
      const sec = sections.find((s) => `${s.source_system}|${s.citation}` === key)!;
      expect(v[1].text).toBe(sec.body_text);
      expect(v[1].snapshot_date).toBe(sec.snapshot_date);
    }
    // the preset-A section is long and the real wave includes a style rewording
    const a = versions["iac|170 IAC 4-1-16"];
    expect(a[0].text.split("\n\n").length).toBeGreaterThanOrEqual(6);
    expect(a[0].text).toContain("shall not");
    expect(a[1].text).toContain("may not");
  });
});

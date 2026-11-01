import { describe, expect, it } from "vitest";
import {
  UNCLASSIFIED_SLUG,
  canUploadToVertical,
  compareVerticals,
  isKnownVerticalSlug,
  normalizeVerticalSlug,
  getVertical,
  isVerticalSlug,
  verticalGroups,
  verticalName,
  type Vertical,
} from "@/lib/verticals";

// Fixture standing in for a GET /company/verticals response (task 3.7): every function in
// lib/verticals.ts now takes this as an explicit argument instead of reading a hardcoded
// module-level array, so the live/mock data is the only source of truth.
const VERTICALS: Vertical[] = [
  { sort_order: 1, slug: "corporate-governance-board", name: "Corporate Governance & Board", description: "Board structure, bylaws, charters, fiduciary duties, shareholder rights, entity management, annual filings, regulatory disclosure obligations." },
  { sort_order: 2, slug: "compliance-ethics", name: "Compliance & Ethics", description: "Code of conduct, anti-corruption (FCPA), anti-bribery, whistleblower protections, compliance training, conflicts of interest, FTC consumer/advertising compliance." },
  { sort_order: 3, slug: "legal-contractual", name: "Legal & Contractual", description: "Contract governance, litigation holds, IP protection, licensing, entity structure, NDAs, antitrust compliance." },
  { sort_order: 4, slug: "financial-compliance-reporting", name: "Financial Compliance & Reporting", description: "SOX/ICFR, GAAP/IFRS, financial disclosures, audit requirements, internal controls, revenue recognition, pricing regulations, fee disclosures." },
  { sort_order: 5, slug: "tax-trade-compliance", name: "Tax & Trade Compliance", description: "Corporate tax, payroll tax, sales tax, international tax (FATCA), transfer pricing, export controls, customs, OFAC sanctions, tariffs." },
  { sort_order: 6, slug: "workforce-employment", name: "Workforce & Employment", description: "Labor laws, wage & hour, FMLA, ADA, anti-discrimination, benefits (ERISA), immigration/work authorization, DEI policies." },
  { sort_order: 7, slug: "health-safety", name: "Health & Safety", description: "Workplace safety, emergency preparedness, hazard communication, PPE, incident reporting, product/consumer safety." },
  { sort_order: 8, slug: "data-privacy-cybersecurity", name: "Data Privacy & Cybersecurity", description: "GDPR, CCPA/CPRA, state privacy laws, data breach notification, cybersecurity frameworks, data retention, information security." },
  { sort_order: 9, slug: "environmental-sustainability", name: "Environmental & Sustainability", description: "EPA regulations, emissions, waste management, environmental permits, GHG reporting, ESG disclosures, climate risk, energy management." },
  { sort_order: 10, slug: "operations-quality", name: "Operations & Quality", description: "Quality management, process compliance, GMP, FDA product regulations, CAPA, operational standards, business process documentation." },
  { sort_order: 11, slug: "information-technology-records", name: "Information Technology & Records", description: "IT policies, system access controls, change management, records retention, digital accessibility (ADA/WCAG), AI governance and responsible use." },
  { sort_order: 12, slug: "supply-chain-third-party-risk", name: "Supply Chain & Third-Party Risk", description: "Vendor compliance, third-party risk, supplier due diligence, modern slavery/forced labor, supply chain transparency, conflict minerals." },
  { sort_order: 13, slug: "policy-training-management", name: "Policy & Training Management", description: "Policy lifecycle, document control, version management, compliance training programs, employee acknowledgments." },
  { sort_order: 14, slug: "risk-resilience", name: "Risk & Resilience", description: "Enterprise risk management, insurance requirements, business continuity, disaster recovery, operational resilience." },
];

describe("verticals", () => {
  it("has 14 in fixed order with unique slugs", () => {
    expect(VERTICALS).toHaveLength(14);
    expect(VERTICALS.map((v) => v.sort_order)).toEqual(Array.from({ length: 14 }, (_, i) => i + 1));
    expect(new Set(VERTICALS.map((v) => v.slug)).size).toBe(14);
    expect(VERTICALS[0].slug).toBe("corporate-governance-board");
    expect(VERTICALS[13].slug).toBe("risk-resilience");
  });
  it("every vertical has a non-empty description", () => {
    for (const v of VERTICALS) {
      expect(v.description.length).toBeGreaterThan(20);
    }
  });
  it("helpers", () => {
    expect(verticalName(VERTICALS, "tax-trade-compliance")).toBe("Tax & Trade Compliance");
    expect(verticalName(VERTICALS, "unknown")).toBe("unknown");
    expect(getVertical(VERTICALS, "information-technology-records")?.name).toBe("Information Technology & Records");
    expect(isVerticalSlug(VERTICALS, "workforce-employment")).toBe(true);
    expect(isVerticalSlug(VERTICALS, "x")).toBe(false);
    expect(["risk-resilience", "compliance-ethics"].sort((a, b) => compareVerticals(VERTICALS, a, b))).toEqual([
      "compliance-ethics",
      "risk-resilience",
    ]);
  });
  it("unclassified fallback group", () => {
    expect(VERTICALS.map((v) => v.slug)).not.toContain(UNCLASSIFIED_SLUG);
    const groups = verticalGroups(VERTICALS);
    expect(groups).toHaveLength(15);
    expect(groups.at(-1)?.slug).toBe("unclassified");
    expect(getVertical(VERTICALS, "unclassified")?.name).toBe("Unclassified");
    expect(verticalName(VERTICALS, "unclassified")).toBe("Unclassified");
    expect(isVerticalSlug(VERTICALS, "unclassified")).toBe(false);
    expect(isKnownVerticalSlug(VERTICALS, "unclassified")).toBe(true);
    expect(normalizeVerticalSlug(VERTICALS, "nope")).toBe("unclassified");
    expect(normalizeVerticalSlug(VERTICALS, null)).toBe("unclassified");
    expect(normalizeVerticalSlug(VERTICALS, "workforce-employment")).toBe("workforce-employment");
    expect(
      ["unclassified", "risk-resilience", "zzz"].sort((a, b) => compareVerticals(VERTICALS, a, b)),
    ).toEqual(["risk-resilience", "unclassified", "zzz"]);
  });
  it("every one of the 14 verticals accepts uploads, and unclassified never does", () => {
    // The backend maps all 14 (it once mapped only the 5 the synthetic corpus used, so uploads
    // into the other 9 returned 422). `unclassified` is a fallback group, not an upload target.
    expect(
      verticalGroups(VERTICALS).filter((v) => canUploadToVertical(VERTICALS, v.slug)).map((v) => v.slug),
    ).toEqual(VERTICALS.map((v) => v.slug));
    expect(VERTICALS).toHaveLength(14);
    expect(canUploadToVertical(VERTICALS, "unclassified")).toBe(false);
    expect(canUploadToVertical(VERTICALS, "tax-trade-compliance")).toBe(true);
    expect(canUploadToVertical(VERTICALS, "not-a-vertical")).toBe(false);
  });
});

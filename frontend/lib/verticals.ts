// The 14 verticals in fixed order (spec §5.3).
export interface Vertical {
  /** 1-based fixed position. */
  order: number;
  slug: string;
  name: string;
  /** Backend vertical name this maps to, or null when the vertical only has sample documents. */
  backendVertical: string | null;
  /** One factual sentence for the page header. */
  description: string;
}

export const VERTICALS: readonly Vertical[] = [
  { order: 1, slug: "corporate-governance-board", name: "Corporate Governance & Board", backendVertical: null, description: "Board structure, bylaws, charters, fiduciary duties, shareholder rights, entity management, annual filings, regulatory disclosure obligations." },
  { order: 2, slug: "compliance-ethics", name: "Compliance & Ethics", backendVertical: "Compliance & Ethics", description: "Code of conduct, anti-corruption (FCPA), anti-bribery, whistleblower protections, compliance training, conflicts of interest, FTC consumer/advertising compliance." },
  { order: 3, slug: "legal-contractual", name: "Legal & Contractual", backendVertical: null, description: "Contract governance, litigation holds, IP protection, licensing, entity structure, NDAs, antitrust compliance." },
  { order: 4, slug: "financial-compliance-reporting", name: "Financial Compliance & Reporting", backendVertical: "Financial Compliance & Reporting", description: "SOX/ICFR, GAAP/IFRS, financial disclosures, audit requirements, internal controls, revenue recognition, pricing regulations, fee disclosures." },
  { order: 5, slug: "tax-trade-compliance", name: "Tax & Trade Compliance", backendVertical: null, description: "Corporate tax, payroll tax, sales tax, international tax (FATCA), transfer pricing, export controls, customs, OFAC sanctions, tariffs." },
  { order: 6, slug: "workforce-employment", name: "Workforce & Employment", backendVertical: null, description: "Labor laws, wage & hour, FMLA, ADA, anti-discrimination, benefits (ERISA), immigration/work authorization, DEI policies." },
  { order: 7, slug: "health-safety", name: "Health & Safety", backendVertical: "Health & Safety", description: "Workplace safety, emergency preparedness, hazard communication, PPE, incident reporting, product/consumer safety." },
  { order: 8, slug: "data-privacy-cybersecurity", name: "Data Privacy & Cybersecurity", backendVertical: null, description: "GDPR, CCPA/CPRA, state privacy laws, data breach notification, cybersecurity frameworks, data retention, information security." },
  { order: 9, slug: "environmental-sustainability", name: "Environmental & Sustainability", backendVertical: "Environmental & Sustainability", description: "EPA regulations, emissions, waste management, environmental permits, GHG reporting, ESG disclosures, climate risk, energy management." },
  { order: 10, slug: "operations-quality", name: "Operations & Quality", backendVertical: "Operations & Quality", description: "Quality management, process compliance, GMP, FDA product regulations, CAPA, operational standards, business process documentation." },
  { order: 11, slug: "information-technology-records", name: "Information Technology & Records", backendVertical: "Information Technology & Records", description: "IT policies, system access controls, change management, records retention, digital accessibility (ADA/WCAG), AI governance and responsible use." },
  { order: 12, slug: "supply-chain-third-party-risk", name: "Supply Chain & Third-Party Risk", backendVertical: null, description: "Vendor compliance, third-party risk, supplier due diligence, modern slavery/forced labor, supply chain transparency, conflict minerals." },
  { order: 13, slug: "policy-training-management", name: "Policy & Training Management", backendVertical: null, description: "Policy lifecycle, document control, version management, compliance training programs, employee acknowledgments." },
  { order: 14, slug: "risk-resilience", name: "Risk & Resilience", backendVertical: null, description: "Enterprise risk management, insurance requirements, business continuity, disaster recovery, operational resilience." },
];

export const VERTICAL_SLUGS: readonly string[] = VERTICALS.map((v) => v.slug);

export function isVerticalSlug(slug: string): boolean {
  return VERTICAL_SLUGS.includes(slug);
}

/**
 * Fallback group for documents whose vertical is not one of the 14: the backend sends the
 * literal slug "unclassified" for a NULL or unmapped vertical. Deliberately NOT in VERTICALS
 * (it is not a navigable vertical page, and the upload endpoint rejects it with 422).
 */
export const UNCLASSIFIED_SLUG = "unclassified";
export const UNCLASSIFIED_VERTICAL: Vertical = {
  order: VERTICALS.length + 1,
  slug: UNCLASSIFIED_SLUG,
  name: "Unclassified",
  backendVertical: null,
  description: "Documents whose vertical is missing or not one of the fourteen recognised verticals.",
};

/** The 14 verticals followed by the unclassified fallback: use this to group documents so none are hidden. */
export const VERTICAL_GROUPS: readonly Vertical[] = [...VERTICALS, UNCLASSIFIED_VERTICAL];

/** True for the 14 slugs and "unclassified" (every value a document's `vertical` can hold after normalising). */
export function isKnownVerticalSlug(slug: string): boolean {
  return slug === UNCLASSIFIED_SLUG || isVerticalSlug(slug);
}

/** A document's vertical slug, or "unclassified" when it is not one of the 14. */
export function normalizeVerticalSlug(slug: string | null | undefined): string {
  return slug && isVerticalSlug(slug) ? slug : UNCLASSIFIED_SLUG;
}

/**
 * True when POST /company/documents accepts this vertical: any of the 14, never `unclassified`.
 * (This used to require a `backendVertical`, i.e. only the 5 verticals the synthetic corpus used;
 * the backend now maps all 14, so a customer can upload into any of them.)
 */
export function canUploadToVertical(slug: string): boolean {
  return isVerticalSlug(slug);
}

/** Resolves the 14 slugs and "unclassified". */
export function getVertical(slug: string): Vertical | undefined {
  if (slug === UNCLASSIFIED_SLUG) return UNCLASSIFIED_VERTICAL;
  return VERTICALS.find((v) => v.slug === slug);
}

/** Display name for a slug; falls back to the slug itself. */
export function verticalName(slug: string): string {
  return getVertical(slug)?.name ?? slug;
}

/** Find the vertical mapped to a backend vertical name (case-insensitive). */
export function verticalFromBackend(backendName: string): Vertical | undefined {
  const n = backendName.trim().toLowerCase();
  return VERTICALS.find((v) => v.backendVertical?.toLowerCase() === n);
}

/** Verticals with real backend documents. */
export function realVerticals(): Vertical[] {
  return VERTICALS.filter((v) => v.backendVertical !== null);
}

/** Sort comparator by fixed order; "unclassified" sorts after the 14, unknown slugs last. */
export function compareVerticals(a: string, b: string): number {
  return (getVertical(a)?.order ?? 99) - (getVertical(b)?.order ?? 99);
}

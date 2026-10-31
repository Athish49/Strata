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
  { order: 1, slug: "compliance-legal", name: "Compliance & Legal", backendVertical: "Compliance & Legal", description: "Documents that set out legal and regulatory compliance obligations, such as ethics, reporting and recordkeeping requirements." },
  { order: 2, slug: "policy-governance", name: "Policy & Governance Documents", backendVertical: "Policy & Governance", description: "Corporate policies and governance standards that define how the company is directed and controlled." },
  { order: 3, slug: "financial-reporting", name: "Financial & Reporting", backendVertical: null, description: "Procedures for financial statements, regulatory filings and rate reporting to commissions and agencies." },
  { order: 4, slug: "revenue-pricing", name: "Revenue & Pricing", backendVertical: null, description: "Tariffs, rate schedules and billing practices that determine what customers are charged." },
  { order: 5, slug: "operations-processes", name: "Operations & Processes", backendVertical: "Operations & Processes", description: "Operating procedures for running the distribution system, including service, outage and metering processes." },
  { order: 6, slug: "technology-systems", name: "Technology & Systems", backendVertical: null, description: "Policies for information systems, cybersecurity and the handling of customer data." },
  { order: 7, slug: "workforce-hr", name: "Workforce & HR", backendVertical: "Workforce & Safety", description: "Workforce, training and safety documents covering employees and contractors." },
  { order: 8, slug: "environmental-esg", name: "Environmental & ESG", backendVertical: "Environmental", description: "Environmental permits, emissions and waste procedures, and sustainability reporting." },
  { order: 9, slug: "supply-chain-procurement", name: "Supply Chain & Procurement", backendVertical: null, description: "Procedures for qualifying suppliers and purchasing materials, equipment and services." },
  { order: 10, slug: "risk-insurance", name: "Risk & Insurance", backendVertical: null, description: "Enterprise risk, insurance coverage and business continuity documents." },
  { order: 11, slug: "strategic-competitive", name: "Strategic & Competitive", backendVertical: null, description: "Long-range plans and market positioning documents, including resource and growth planning." },
  { order: 12, slug: "reputational-stakeholder", name: "Reputational & Stakeholder", backendVertical: null, description: "Customer, community and media communication standards, and stakeholder engagement practices." },
  { order: 13, slug: "contractual-third-party", name: "Contractual & Third-Party Obligations", backendVertical: null, description: "Obligations the company owes under contracts, interconnection agreements and third-party arrangements." },
  { order: 14, slug: "capital-infrastructure", name: "Capital & Infrastructure", backendVertical: null, description: "Capital project approval and infrastructure standards for substations, lines and facilities." },
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

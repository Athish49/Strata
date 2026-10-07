// Future-capability registry (spec §18). Disabled affordances; each id is defined exactly once.
export type FutureVariant =
  | "button"
  | "toolbar"
  | "inline-add"
  | "card"
  | "nav"
  | "icon"
  | "chip"
  | "menu-item";

export interface FutureFeature {
  id: string;
  label: string;
  tooltip: string;
  /** lucide-react icon export name, e.g. "Bell". Resolved by <FutureCue/>. */
  icon: string;
  variant: FutureVariant;
}

/** Set to false to hide every cue at once (no-cues demo). */
export const SHOW_FUTURE_CUES = true;

export const TOOLTIP_MAX_LENGTH = 90;

const defs: FutureFeature[] = [
  { id: "notifications", label: "Alerts", tooltip: "Get alerted the moment a rule your documents depend on changes.", icon: "Bell", variant: "icon" },
  { id: "assistant", label: "Assistant", tooltip: "Ask questions across regulations and your documents, with cited answers.", icon: "Sparkles", variant: "nav" },
  { id: "agents", label: "Agents", tooltip: "Automate recurring work, like monthly obligation reviews or filing prep.", icon: "Bot", variant: "nav" },
  { id: "integrations", label: "Integrations", tooltip: "Connect SharePoint, Google Drive, Box, Jira and ServiceNow.", icon: "Plug", variant: "nav" },
  { id: "workspace-switcher", label: "Switch company", tooltip: "Monitor several operating companies and affiliates from one workspace.", icon: "ChevronsUpDown", variant: "icon" },
  { id: "search-ask", label: "Ask Strata \"‹query›\"", tooltip: "Get a cited answer instead of a list of results.", icon: "Sparkles", variant: "menu-item" },
  { id: "schedule-briefing", label: "Schedule briefing", tooltip: "Email a one-page summary of every regulatory wave to leadership.", icon: "CalendarClock", variant: "button" },
  { id: "export-report", label: "Export report", tooltip: "Download a board-ready PDF of this wave's impact.", icon: "FileDown", variant: "button" },
  { id: "continuous-monitoring", label: "Continuous monitoring", tooltip: "Analyze changes the day they're published, not snapshot to snapshot.", icon: "Radio", variant: "menu-item" },
  { id: "proposed-rules", label: "Proposed rules", tooltip: "See which clauses a proposed rule would affect before it becomes final.", icon: "ScrollText", variant: "chip" },
  { id: "watch", label: "Watch", tooltip: "Follow this section and get alerted on any future change.", icon: "Eye", variant: "button" },
  { id: "impact-memo", label: "Draft impact memo", tooltip: "Generate a counsel-ready memo of this change and every clause it touches.", icon: "FileText", variant: "button" },
  { id: "connect-source", label: "Connect source", tooltip: "Keep documents in sync from SharePoint, Google Drive, Box or iManage.", icon: "Cable", variant: "button" },
  { id: "upload-document", label: "Upload", tooltip: "Add a document; Strata splits it into clauses and files it in the right vertical.", icon: "Upload", variant: "button" },
  { id: "coverage-gaps", label: "Find coverage gaps", tooltip: "Find rules RPL is subject to that no document covers yet.", icon: "ScanSearch", variant: "toolbar" },
  { id: "invite-team", label: "Invite team", tooltip: "Give this department's owners and reviewers their own view.", icon: "UserPlus", variant: "button" },
  { id: "start-monitoring", label: "Start monitoring", tooltip: "Check this document against every future regulatory change.", icon: "Activity", variant: "inline-add" },
  { id: "ask-document", label: "Ask", tooltip: "Ask about this document and get answers cited to its clauses.", icon: "MessageSquare", variant: "toolbar" },
  { id: "export-redline", label: "Export redline", tooltip: "Send suggested updates to Word as tracked changes for the owner.", icon: "FileDiff", variant: "toolbar" },
  { id: "view-original", label: "Original file", tooltip: "View the source PDF or Word file beside its clauses.", icon: "FileSearch", variant: "toolbar" },
  { id: "version-history", label: "Version history", tooltip: "Compare this document with its earlier versions.", icon: "History", variant: "icon" },
  { id: "draft-rewrite", label: "Draft full rewrite", tooltip: "Draft a complete replacement clause that satisfies the new rule.", icon: "PenLine", variant: "inline-add" },
  { id: "create-task", label: "Create task", tooltip: "Open a tracked task in Jira or ServiceNow for the owner.", icon: "ListChecks", variant: "button" },
  { id: "request-signoff", label: "Request sign-off", tooltip: "Collect owner, reviewer and approver sign-off with an audit trail.", icon: "BadgeCheck", variant: "button" },
  { id: "ai-column", label: "Add column", tooltip: "Ask one question of every document and see each answer in its row.", icon: "Columns3", variant: "toolbar" },
  { id: "export-matrix", label: "Export", tooltip: "Download this matrix as a spreadsheet.", icon: "Download", variant: "toolbar" },
  { id: "map-document", label: "Map to document", tooltip: "Link this rule to the document that should cover it.", icon: "Link2", variant: "inline-add" },
  { id: "assign-review", label: "Assign", tooltip: "Ask a colleague to confirm whether this applies to RPL.", icon: "UserCheck", variant: "inline-add" },
  { id: "from-proposed-rule", label: "Start from a proposed rule", tooltip: "Load an open IURC or Federal Register proposal as a scenario.", icon: "Plus", variant: "card" },
  { id: "compare-scenarios", label: "Compare", tooltip: "Put two scenarios side by side.", icon: "GitCompare", variant: "button" },
  { id: "evidence-pack", label: "Export evidence pack", tooltip: "Package every decision, quote and review for auditors or regulators.", icon: "Package", variant: "button" },
  { id: "review-sampling", label: "Set up review sampling", tooltip: "Route a random sample of AI decisions to a human reviewer each wave.", icon: "Shuffle", variant: "inline-add" },
  { id: "add-agency-federal", label: "Add agency", tooltip: "Track another federal agency's rules and actions for RPL.", icon: "Plus", variant: "card" },
  { id: "add-agency-state", label: "Add agency", tooltip: "Track another Indiana agency's rules and actions for RPL.", icon: "Plus", variant: "card" },
  { id: "add-jurisdiction", label: "Add jurisdiction", tooltip: "Monitor another state, such as Ohio, Illinois or Michigan.", icon: "MapPin", variant: "button" },
  { id: "more-sources", label: "More source types", tooltip: "Track bills, MISO tariff changes and court decisions that affect your rules.", icon: "Plus", variant: "card" },
  { id: "track-docket", label: "Track docket", tooltip: "Follow an IURC cause or FERC docket and see every new filing.", icon: "Flag", variant: "toolbar" },
  { id: "add-data-source", label: "Add data source", tooltip: "Add another feed for this agency, such as guidance or FAQs.", icon: "Database", variant: "button" },
  { id: "add-note", label: "Add note", tooltip: "Leave an internal interpretation note for your team.", icon: "StickyNote", variant: "button" },
  { id: "comment-letter", label: "Draft comment letter", tooltip: "Draft comments on an open rulemaking, grounded in RPL's documents.", icon: "FilePen", variant: "button" },
  { id: "edit-profile", label: "Edit profile", tooltip: "Correct an attribute and Radar re-screens every change automatically.", icon: "Pencil", variant: "button" },
  { id: "sync-directory", label: "Sync directory", tooltip: "Keep people and roles in sync with Workday or Okta.", icon: "RefreshCw", variant: "inline-add" },
];

export const FUTURE_FEATURES: Record<string, FutureFeature> = Object.fromEntries(
  defs.map((f) => [f.id, f]),
);

/** The three small cards under "More source types" on the Regulations overview. */
export const MORE_SOURCES_ITEMS: ReadonlyArray<{ title: string; tooltip: string }> = [
  { title: "Indiana General Assembly", tooltip: "Track bills before they amend the Indiana Code." },
  { title: "MISO tariff & manuals", tooltip: "Track MISO tariff and business-practice changes." },
  { title: "Court & commission decisions", tooltip: "Track decisions that reinterpret your rules." },
];

/** Cues rendered in the app shell on every page; excluded from the per-page limit. */
export const SHELL_CUES: readonly string[] = [
  "notifications",
  "assistant",
  "agents",
  "integrations",
  "workspace-switcher",
  "search-ask",
];

/** Page key -> cue ids in placement order (shell cues excluded). */
export const PAGE_CUES: Record<string, readonly string[]> = {
  overview: ["schedule-briefing", "export-report", "continuous-monitoring"],
  changes: ["proposed-rules", "watch", "impact-memo"],
  documents: ["connect-source", "upload-document", "coverage-gaps"],
  vertical: ["invite-team", "upload-document", "start-monitoring"],
  reader: ["ask-document", "export-redline", "view-original"],
  evidence: ["draft-rewrite", "create-task", "request-signoff"],
  matrix: ["ai-column", "export-matrix"],
  radar: ["map-document", "assign-review"],
  "what-if": ["from-proposed-rule", "compare-scenarios"],
  trust: ["evidence-pack", "review-sampling"],
  regulations: ["add-agency-federal", "add-agency-state", "add-jurisdiction", "more-sources"],
  agency: ["track-docket", "add-data-source"],
  "regulation-section": ["watch", "add-note"],
  "regulatory-action": ["comment-letter", "track-docket"],
  company: ["edit-profile", "sync-directory"],
};

/**
 * Cues allowed on a page beyond the 3-cue limit. The version-history chevron counts toward the
 * limit only if the reader toolbar is crowded, so it is kept out of the main list.
 */
export const OPTIONAL_PAGE_CUES: Record<string, readonly string[]> = {
  reader: ["version-history"],
};

/** Cues that count as a single cue for the per-page limit. */
const CLUSTERS: ReadonlyArray<readonly string[]> = [["add-agency-federal", "add-agency-state"]];

/** Number of cues a page counts against the 3-per-page limit. */
export function countPageCues(page: string): number {
  const ids = PAGE_CUES[page] ?? [];
  const seen = new Set<string>();
  for (const id of ids) {
    const cluster = CLUSTERS.find((c) => c.includes(id));
    seen.add(cluster ? cluster.join("+") : id);
  }
  return seen.size;
}

export function getFutureFeature(id: string): FutureFeature | undefined {
  return FUTURE_FEATURES[id];
}

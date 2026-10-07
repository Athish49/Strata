// Sentence builders (spec §11.4). Each has a structured variant (segments) so key values can be bold.
import type { Candidate, ChangeRecord, Clause, DocRollup, Finding, UnitKind } from "@/lib/api/schemas";
import { CHANGE_CLASS_LABELS, DIRECTION_LABELS } from "@/lib/labels";
import { formatCount } from "@/lib/format";

export interface Segment {
  text: string;
  strong?: boolean;
}

export const segmentsToString = (segs: Segment[]): string => segs.map((s) => s.text).join("");

const t = (text: string): Segment => ({ text });
const b = (text: string): Segment => ({ text, strong: true });

type ClauseLike = Pick<Clause, "clause_id" | "unit_kind"> &
  Partial<Pick<Clause, "doc_id" | "heading_path" | "row_cells">>;

/** Strip "<doc_id>:" / "<doc_id>/" style prefixes to get the id local to the document. */
export function localClauseId(clause: Pick<Clause, "clause_id"> & Partial<Pick<Clause, "doc_id">>): string {
  const id = clause.clause_id;
  if (clause.doc_id && id.startsWith(clause.doc_id)) {
    const rest = id.slice(clause.doc_id.length).replace(/^[:/#._-]+/, "");
    if (rest) return rest;
  }
  return id;
}

const KIND_PREFIX: Record<UnitKind, string> = {
  section: "§",
  appendix: "§",
  table_row: "row ",
  register_row: "row ",
  form_field: "field ",
  tariff_subrule: "rule ",
};

/** "§4.2" / "row R-12" / "field Meter class" / "rule 3.1". */
export function clauseLabel(clause: ClauseLike): string {
  const local = localClauseId(clause);
  if (clause.unit_kind === "form_field") {
    const label = clause.heading_path?.[clause.heading_path.length - 1] || local;
    return `field ${label}`;
  }
  return `${KIND_PREFIX[clause.unit_kind]}${local.replace(/^§/, "")}`;
}

type FindingLike = Pick<Finding, "verdict" | "citation" | "finding_type" | "rationale" | "required_change">;
type ChangeLike = Partial<Pick<ChangeRecord, "change_class" | "characterization">>;

/** Structured finding sentence. `label` is clauseLabel(...). */
export function findingSentenceSegments(
  finding: FindingLike,
  label: string,
  change?: ChangeLike,
): Segment[] {
  const { from_text, to_text } = finding.required_change;
  const repealed = change?.change_class === "repealed" || /repeal/i.test(finding.finding_type);
  if (repealed) {
    return [b(label), t(" relies on "), b(finding.citation), t(", which was repealed.")];
  }
  if (finding.verdict === "update_citation" && from_text && to_text) {
    return [b(label), t(" cites "), b(from_text), t("; the rule is now "), b(to_text), t(".")];
  }
  if (from_text && to_text) {
    return [
      b(label),
      t(" states "),
      b(from_text),
      t("; "),
      b(finding.citation),
      t(" now requires "),
      b(to_text),
      t("."),
    ];
  }
  return [t(change?.characterization?.summary || finding.rationale)];
}

export function findingSentence(finding: FindingLike, label: string, change?: ChangeLike): string {
  return segmentsToString(findingSentenceSegments(finding, label, change));
}

type CandidateLike = Partial<Pick<Candidate, "skip_reason" | "rationale">>;

/** Structured cleared reason. Backend skip_reason / rationale win when present. */
export function clearedReasonSegments(
  candidate: CandidateLike,
  change: Pick<ChangeRecord, "change_class" | "citation">,
): Segment[] {
  const backend = candidate.skip_reason?.trim() || candidate.rationale?.trim();
  if (backend) return [t(backend)];
  return [
    t("Checked: no impact — "),
    b(CHANGE_CLASS_LABELS[change.change_class].toLowerCase()),
    t(" change to "),
    b(change.citation),
    t("."),
  ];
}

export function clearedReason(
  candidate: CandidateLike,
  change: Pick<ChangeRecord, "change_class" | "citation">,
): string {
  return segmentsToString(clearedReasonSegments(candidate, change));
}

const CLASS_PHRASES: Record<string, string> = {
  style_only: "style-only",
  cross_ref_only: "cross-reference-only",
  metadata_only: "metadata-only",
  punctuation_only: "punctuation-only",
};

function classPhrase(key: string): string {
  if (CLASS_PHRASES[key]) return CLASS_PHRASES[key];
  const label =
    (CHANGE_CLASS_LABELS as Record<string, string>)[key] ??
    (DIRECTION_LABELS as Record<string, string>)[key] ??
    key.replace(/_/g, " ");
  return label.toLowerCase();
}

/** "12 changes considered: 7 cosmetic, 5 style-only" from a rollup. */
export function docClearedLineSegments(rollup: Pick<DocRollup, "changes_considered" | "considered_by_class">): Segment[] {
  const n = rollup.changes_considered;
  if (n === 0) return [t("No cited section changed")];
  const parts = Object.entries(rollup.considered_by_class ?? {})
    .filter(([, k]) => k > 0)
    .sort((a, c) => c[1] - a[1])
    .map(([key, k]) => `${formatCount(k)} ${classPhrase(key)}`);
  const head = `${formatCount(n)} ${n === 1 ? "change" : "changes"} considered`;
  return parts.length ? [b(head), t(`: ${parts.join(", ")}`)] : [b(head)];
}

export function docClearedLine(rollup: Pick<DocRollup, "changes_considered" | "considered_by_class">): string {
  return segmentsToString(docClearedLineSegments(rollup));
}

"""Engine data contracts: stage inputs/outputs (engine_spec.md) and API DTOs (api_ui.md)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, model_validator

# ---- Enums (data_model.md section 5) ----
ChangeClass = Literal[
    "repealed", "renumbered", "new_section", "cosmetic",
    "metadata_only", "punctuation_only", "cross_ref_only", "substantive",
]
Direction = Literal[
    "tightened", "relaxed", "new_requirement", "removed_requirement",
    "clarified", "style_only", "mixed",
]
Disposition = Literal[
    "findings_emitted", "no_affected_clauses", "excluded_noise",
    "not_in_footprint", "needs_review",
]
MatchPath = Literal["direct_section", "direct_rule", "register_hop", "value_echo"]
FindingType = Literal[
    "parameter_change", "required_content_change", "conflict", "stale_citation",
    "new_requirement_gap", "stale_at_approval", "informational",
]
Verdict = Literal["action_required", "optional_relaxed", "update_citation", "review", "info"]
Severity = Literal["high", "medium", "low"]
Origin = Literal["kb", "whatif"]
RunKind = Literal["kb", "baseline", "whatif"]
Applicable = Literal["yes", "no", "unclear"]

CHANGE_CLASSES = get_args(ChangeClass)
DIRECTIONS = get_args(Direction)
DISPOSITIONS = get_args(Disposition)
MATCH_PATHS = get_args(MatchPath)  # priority order
FINDING_TYPES = get_args(FindingType)
VERDICTS = get_args(Verdict)
NOISE_CLASSES = ("cosmetic", "metadata_only", "punctuation_only", "cross_ref_only")


# ---- Stage inputs / outputs ----
class ChangeInput(BaseModel):
    origin: Origin
    source_system: str
    citation: str
    s1_section_id: int | None = None
    s2_section_id: int | None = None
    s1_text: str | None = None
    s2_text: str | None = None
    s1_status: str | None = None
    s2_status: str | None = None
    heading: str | None = None
    amendment_source: str | None = None


class ValueChange(BaseModel):
    kind: Literal["period", "deadline", "amount", "threshold", "frequency", "number", "other"]
    unit: str | None = None
    day_type: str | None = None  # 'calendar'|'business'|None
    old_value_text: str
    new_value_text: str
    old_value_num: float | None = None
    new_value_num: float | None = None
    subject: str


class Characterization(BaseModel):
    obligation_changed: bool
    direction: Direction
    summary: str
    value_changes: list[ValueChange]
    added_requirements: list[str]
    removed_requirements: list[str]
    quotes: dict


class JudgeResult(BaseModel):
    affected: bool
    finding_type: FindingType
    severity: Severity
    required_change: dict | None = None
    quotes: dict
    rationale: str
    confidence: float


class RadarResult(BaseModel):
    obligation_changed: bool
    applicable: Applicable
    attribute_basis: list[str]
    affected_activity: str
    reason: str
    quote_s2: str | None = None


# ---- API DTOs (api_ui.md section 1) ----
class _DTO(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RunCreate(BaseModel):
    kind: Literal["kb", "baseline"]


class RunCreated(BaseModel):
    run_id: str


class RunSummary(_DTO):
    run_id: str
    kind: RunKind
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    scenario_title: str | None = None


class FunnelStats(_DTO):
    """runs.stats (the funnel); extra keys are kept for forward compatibility."""
    model_config = ConfigDict(extra="allow")


class RunDetail(_DTO):
    run: RunSummary
    stats: dict[str, Any]


class Person(_DTO):
    person_id: str
    name: str
    title: str | None = None


class DocumentRollup(_DTO):
    run_id: str | None = None
    doc_id: str
    title: str | None = None
    vertical: str | None = None
    owner_name: str | None = None
    approved_date: date | None = None
    status: Literal["flagged", "cleared"]
    counts: dict[str, int] = {}
    changes_considered: list[dict[str, Any]] = []
    reason: str | None = None
    reviewed: int = 0


class FindingItem(_DTO):
    finding_id: str
    clause_id: str
    heading_path: str | list[str] | None = None
    citation: str
    finding_type: FindingType
    verdict: Verdict
    severity: Severity
    short_rationale: str


class ClearedItem(_DTO):
    clause_id: str
    citation: str | None = None
    skip_reason: str | None = None
    rationale: str | None = None
    change_class: ChangeClass | None = None


class DocumentGroups(_DTO):
    action_required: list[FindingItem] = []
    optional_relaxed: list[FindingItem] = []
    update_citation: list[FindingItem] = []
    review: list[FindingItem] = []
    info: list[FindingItem] = []


class DocumentDetail(_DTO):
    doc: dict[str, Any]
    rollup: DocumentRollup | dict[str, Any]
    groups: DocumentGroups
    cleared: list[ClearedItem] = []


class RouteInfo(_DTO):
    owner: Person | dict[str, Any] | None = None
    reviewer: Person | dict[str, Any] | None = None
    approver: Person | dict[str, Any] | None = None


class ReviewRecord(_DTO):
    action: str
    note: str | None = None
    person_id: str
    created_at: datetime | None = None


class EvidenceFinding(_DTO):
    finding_id: str
    clause_id: str
    doc_id: str
    citation: str
    finding_type: FindingType
    verdict: Verdict
    severity: Severity
    needs_review: bool
    required_change: dict | None = None
    rationale: str
    confidence: float | None = None
    decided_by: Literal["rule", "llm"]
    match_path: MatchPath
    quotes_verified: bool
    route: RouteInfo
    reviews: list[ReviewRecord] = []


class EvidenceChange(_DTO):
    change_id: str
    citation: str
    heading: str | None = None
    change_class: ChangeClass
    summary: str | None = None
    direction: Direction | None = None
    value_changes: list[ValueChange] | None = None
    published_date: date | None = None
    date_basis: str | None = None
    din: str | None = None
    amendment_source: str | None = None
    origin: Origin
    diff_segments: list[dict[str, str]] | None = None
    s1_quote_span: tuple[int, int] | None = None
    s2_quote_span: tuple[int, int] | None = None


class EvidenceClause(_DTO):
    clause_id: str
    doc_title: str | None = None
    heading_path: str | list[str] | None = None
    text_raw: str
    quote_span: tuple[int, int] | None = None


class PathStep(_DTO):
    path: MatchPath
    via_clause_id: str | None = None
    link_type: str | None = None
    value: Any = None


class AlsoAffected(_DTO):
    finding_id: str
    doc_id: str
    clause_id: str
    verdict: Verdict


class PropagatedFrom(_DTO):
    finding_id: str
    clause_id: str


class EvidenceCard(_DTO):
    finding: EvidenceFinding
    change: EvidenceChange
    clause: EvidenceClause
    path: list[PathStep]
    also_affected: list[AlsoAffected] = []
    propagated_from: PropagatedFrom | None = None


class LedgerRow(_DTO):
    change_id: str
    citation: str
    heading: str | None = None
    change_class: ChangeClass
    in_footprint: bool
    cited_clause_count: int
    disposition: Disposition | None = None
    disposition_reason: str | None = None
    published_date: date | None = None
    n_findings: int = 0
    n_cleared: int = 0


class CandidateDetail(_DTO):
    candidate_id: str | None = None
    clause_id: str
    doc_id: str | None = None
    cited_citation: str | None = None
    match_path: MatchPath
    path_detail: list[PathStep] = []
    judged_by: Literal["rule", "llm"] | None = None
    skip_reason: str | None = None
    affected: bool | None = None
    rationale: str | None = None
    finding_id: str | None = None
    verdict: Verdict | None = None


class ChangeDetail(_DTO):
    change_id: str
    citation: str | None = None
    heading: str | None = None
    change_class: ChangeClass | None = None
    diff_segments: list[dict[str, str]] | None = None
    summary: str | None = None
    value_changes: list[ValueChange] | None = None
    candidates: list[CandidateDetail] = []


class RadarItem(_DTO):
    change_id: str
    citation: str | None = None
    heading: str | None = None
    agency: str | None = None
    obligation_changed: bool
    applicable: Applicable
    attribute_basis: list[str] = []
    affected_activity: str = ""
    reason: str = ""
    quote_s2: str | None = None
    rule_covered_by_docs: list[str] = []


class WhatIfSection(_DTO):
    citation: str
    s1_section_id: int
    heading: str | None = None
    cited_clause_count: int


class WhatIfSectionText(_DTO):
    citation: str
    heading: str | None = None
    s1_text: str


class WhatIfScenarioCreate(BaseModel):
    s1_section_id: int
    edit_kind: Literal["text_edit", "repeal"]
    edited_text: str | None = None
    title: str


class WhatIfScenarioCreated(BaseModel):
    scenario_id: str
    run_id: str


class WhatIfScenario(_DTO):
    scenario_id: str
    title: str
    s1_section_id: int | None = None
    edit_kind: Literal["text_edit", "repeal"] | None = None
    is_preset: bool = False
    last_run_id: str | None = None
    status: str | None = None


class ReviewRequest(BaseModel):
    action: str
    note: str | None = None
    person_id: str

    @model_validator(mode="after")
    def _reject_requires_note(self) -> "ReviewRequest":
        if self.action == "reject" and not (self.note and self.note.strip()):
            raise ValueError("note is required when action is 'reject'")
        return self


class ScoreMetrics(_DTO):
    """engine.score_reports.metrics; scoring.py's keys pass through unchanged."""
    model_config = ConfigDict(extra="allow")


class Scorecard(_DTO):
    run_id: str | None = None
    metrics: dict[str, Any] | None = None
    baseline: dict[str, Any] | None = None

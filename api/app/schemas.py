from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Stage = Literal[
    "identified",
    "reviewed",
    "invited",
    "booked",
    "attended",
    "follow_up",
    "closed",
]
Disposition = Literal[
    "active",
    "completed",
    "declined",
    "deferred",
    "unreachable",
    "clinically_closed_other",
]
Pathway = Literal["child_wcv", "adult_screening"]
Role = Literal["coordinator", "clinical_reviewer", "population_analyst"]
ActionId = Literal[
    "record_contact_preference",
    "approve_pathway",
    "send_invitation",
    "record_decline",
    "record_unreachable",
    "book_appointment",
    "record_attendance",
    "record_referral_outcome",
    "reassign_owner",
    "defer_with_recall",
    "close_as_completed",
    "close_other",
    "reopen",
]


class StructuredError(BaseModel):
    code: str
    message: str
    field_errors: dict[str, str] = Field(default_factory=dict)
    request_id: str | None = None


class ContactPreference(BaseModel):
    channel: str
    language: str
    preferred_time: str


class CompletionEvidence(BaseModel):
    evidence_type: str
    evidence_reference: str


class SourceFact(BaseModel):
    label: str
    value: str
    source: str
    observed_time: str
    verified: bool = True


class MissingItem(BaseModel):
    label: str
    consequence: str


class EventOut(BaseModel):
    id: str
    case_id: str
    timestamp: str
    actor_role: str
    action: str
    prior_state: str | None = None
    new_state: str | None = None
    reason: str | None = None
    evidence_reference: str | None = None
    request_id: str | None = None


class CaseRow(BaseModel):
    id: str
    care_gap_id: str
    patient_id: str | None = None
    patient_label: str
    age_band: str
    pathway: Pathway
    rule_id_version: str
    flag_status: Literal["gap", "needs_review"]
    stage: Stage
    disposition: Disposition
    owner: str
    next_action: str
    due_time: str | None
    overdue: bool
    revision: int


class CaseDetail(BaseModel):
    explanation: str
    factors: list[SourceFact]
    missing: list[MissingItem]
    suggested_review_action: str
    events: list[EventOut]
    contact_preference: ContactPreference | None = None
    recall_date: str | None = None
    completion_evidence: CompletionEvidence | None = None
    referral_outcome: Literal["pending", "accepted", "rejected"] | None = None
    caregiver_authority: Literal[
        "verified_caregiver", "self", "unknown", "not_supplied"
    ] | None = None
    caregiver_relationship: str | None = None


class CaseDocumentOut(BaseModel):
    id: str
    version: int
    document_date: str
    patient_id: str
    case_id: str | None = None


class CaseOut(CaseRow):
    detail: CaseDetail


class ActionRequest(BaseModel):
    action: ActionId
    expected_revision: int
    request_id: str
    data: dict[str, Any] = Field(default_factory=dict)


class ActionResponse(BaseModel):
    case: CaseOut
    event: EventOut


class DemoSessionOut(BaseModel):
    session_id: str
    role: Role
    synthetic: bool = True
    notice: str = "SYNTHETIC DEMO DATA — NOT FOR CLINICAL USE"


class DemoResetOut(BaseModel):
    session_id: str
    cases_restored: int
    notice: str = "Guest session reset to seed fixtures"


class MetricCell(BaseModel):
    label: str
    numerator: int | None = None
    denominator: int | None = None
    value: float | None = None
    suppressed: bool = False
    reason: str | None = None
    threshold: int | None = None


class PathwayMetrics(BaseModel):
    pathway: Pathway
    eligible: MetricCell
    invited: MetricCell
    booked: MetricCell
    attended: MetricCell
    follow_up: MetricCell
    completed: MetricCell
    declined: MetricCell
    unreachable: MetricCell


class AnalyticsOverview(BaseModel):
    synthetic: bool = True
    as_of: str
    threshold: int
    pathways: list[PathwayMetrics]
    notice: str = "All figures are synthetic demo data"


class EvaluationRequest(BaseModel):
    pathway: Pathway | None = None


class EvaluationResult(BaseModel):
    patient_id: str
    pathway: Pathway
    rule_id_version: str
    flag_status: Literal["gap", "needs_review", "no_gap", "not_eligible"]
    factors: list[SourceFact]
    missing: list[MissingItem]
    uncertainty: str
    suggested_review_action: str
    case: CaseOut | None = None
    evaluation_id: str
    # Alfred lossless handoff (I6) — persist alongside any legacy flag
    rule_evaluation: dict | None = None
    legacy_flag_status: str | None = None
    api_compatibility: str | None = None
    notice: str = (
        "Canonical rule_evaluation must be retained; legacy_flag_status may be lossy."
    )


class HealthOut(BaseModel):
    status: str
    service: str = "namaa-api"
    synthetic: bool = True
    version: str
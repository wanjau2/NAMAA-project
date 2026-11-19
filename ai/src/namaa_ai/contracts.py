"""JSON contracts: Pydantic 2, compatible with the existing FastAPI backend."""
from __future__ import annotations

from datetime import date
import re
from typing import Annotated, Any, Literal

from pydantic import AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, StrictBool, model_validator


def _explicit_date(value):
    # Pydantic's default date codec also accepts timestamps and midnight datetimes.
    # Neither is an explicit event date copied from a clinical source.
    if type(value) is date:
        return value
    if isinstance(value, str) and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        return date.fromisoformat(value)
    raise ValueError("An explicit YYYY-MM-DD date is required")


ExplicitDate = Annotated[date, BeforeValidator(_explicit_date)]

Text = Annotated[str, Field(min_length=1, max_length=6000, pattern=r"\S")]
Version = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9.-]+$")]
LogicalId = Version
PatientRef = Annotated[str, Field(pattern=r"^Patient/[A-Za-z0-9.-]{1,64}$")]
ReviewerRef = Annotated[str, Field(pattern=r"^Practitioner(Role)?/[A-Za-z0-9.-]{1,64}$")]
ResourceRef = Annotated[str, Field(pattern=r"^[A-Z][A-Za-z]+/[A-Za-z0-9.-]{1,64}$")]
Concept = Literal["last_wcv", "last_adult_screening", "caregiver_concern", "tobacco_use", "family_condition", "documented_condition"]
Assertion = Literal["present", "absent", "uncertain", "historical"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class ExtractionRequest(Contract):
    request_id: LogicalId
    workspace_id: LogicalId
    patient_reference: PatientRef
    source_id: LogicalId
    source_version: Version
    source_date: ExplicitDate
    language: Literal["en"] = "en"
    note_text: Text


class ProposedFact(Contract):
    concept: Concept
    value_text: Text  # original statement, verbatim; never a model paraphrase
    subject: Literal["patient", "family_member"]
    assertion: Assertion
    effective_date: ExplicitDate | None  # explicit full ISO date only in this slice
    excerpt: Text
    proposed_resource_type: Literal["Observation", "Condition", "FamilyMemberHistory"]
    relationship: Literal["mother", "father", "sister", "brother", "sibling", "grandmother", "grandfather"] | None


class ModelOutput(Contract):
    facts: tuple[ProposedFact, ...] = Field(max_length=30)


class ModelIdentity(Contract):
    model_id: Literal["google/medgemma-1.5-4b-it"] = "google/medgemma-1.5-4b-it"
    model_revision: Text
    prompt_version: Literal["extract-v1.0.1"] = "extract-v1.0.1"
    simulated: StrictBool


class EndpointResponse(Contract):
    protocol: Literal["namaa-extraction-v1"]
    model_id: Literal["google/medgemma-1.5-4b-it"]
    model_revision: Text
    prompt_version: Literal["extract-v1.0.1"]
    output: ModelOutput


class ValidationIssue(Contract):
    code: str
    severity: Literal["block", "review"]
    message: str


class ExtractionProposal(Contract):
    id: LogicalId
    version: int = Field(default=1, ge=1, strict=True)
    state: Literal["proposed"] = "proposed"
    workspace_id: LogicalId
    patient_reference: PatientRef
    source_document_id: LogicalId
    source_document_version: Version
    source_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    fact: ProposedFact
    offset_start: int | None
    offset_end: int | None
    offset_unit: Literal["unicode_code_points"] = "unicode_code_points"
    issues: tuple[ValidationIssue, ...]
    model: ModelIdentity


class ExtractionResult(Contract):
    status: Literal["success", "no_supported_facts", "invalid_output", "transport_failure"]
    model: ModelIdentity
    proposals: tuple[ExtractionProposal, ...] = ()
    error_code: str | None = None
    latency_ms: float = Field(ge=0)
    attempts: int = Field(ge=1, le=3)
    schema_valid: StrictBool


class ReviewCommand(Contract):
    request_id: LogicalId
    proposal_id: LogicalId
    expected_proposal_version: int = Field(ge=1, strict=True)
    action: Literal["accept", "correct", "reject"]
    reviewer_reference: ReviewerRef
    reason: Text
    correction: ProposedFact | None = None
    acknowledged_issues: tuple[str, ...] = ()

    @model_validator(mode="after")
    def correction_matches_action(self):
        if (self.action == "correct") != (self.correction is not None):
            raise ValueError("Only correct requires a complete replacement fact")
        return self


class ReviewedFact(Contract):
    proposal: ExtractionProposal
    fact: ProposedFact
    review: ReviewCommand
    reviewed_at: AwareDatetime
    source_date: date
    offset_start: int = Field(ge=0)
    offset_end: int = Field(ge=1)
    offset_unit: Literal["unicode_code_points"] = "unicode_code_points"

    @model_validator(mode="after")
    def accepted_only(self):
        if self.review.action == "reject":
            raise ValueError("A rejected proposal cannot become a reviewed fact")
        if self.review.proposal_id != self.proposal.id or self.review.expected_proposal_version != self.proposal.version:
            raise ValueError("Review must address this exact proposal version")
        expected = self.review.correction if self.review.action == "correct" else self.proposal.fact
        if self.fact != expected:
            raise ValueError("Reviewed content must equal the explicit review selection")
        if self.offset_end <= self.offset_start or self.offset_end - self.offset_start != len(self.fact.excerpt):
            raise ValueError("Reviewed source offsets must be a non-empty Unicode code-point span matching the excerpt")
        return self


class ReviewDecision(Contract):
    command: ReviewCommand
    resulting_proposal_version: int
    state: Literal["accepted", "corrected", "rejected"]
    fact: ReviewedFact | None


class ResourceVersion(Contract):
    reference: ResourceRef
    version: Version


class VerifiedResource(Contract):
    """Internal backend assertion, NEVER a client- or model-controlled request."""
    resource: dict[str, Any]
    review_reference: Text
    reviewed: StrictBool


class RuleSnapshot(Contract):
    workspace_id: LogicalId
    patient_reference: PatientRef
    as_of: date
    authority: Literal["hapi_fhir", "simulated_fhir"]
    authorized: StrictBool
    complete_for_rule: StrictBool
    resources: tuple[VerifiedResource, ...]


class RuleEvaluation(Contract):
    patient_reference: PatientRef
    as_of: date
    rule_id: Literal["DEMO_WCV_01", "DEMO_ADULT_01"]
    rule_version: Literal["synthetic-1.0.0"] = "synthetic-1.0.0"
    outcome: Literal["gap_identified", "no_gap_identified_in_available_data", "needs_review", "not_eligible"]
    input_versions: tuple[ResourceVersion, ...]
    contributing_factors: tuple[str, ...]
    missing_information: tuple[str, ...]
    due_date: date | None
    simulated: StrictBool
    synthetic_rule: Literal[True] = True


class RuleEvaluationHandoff(Contract):
    """Lossless Alfred-to-backend handoff; not a direct API EvaluationResult."""
    evaluation: RuleEvaluation
    legacy_flag_status: Literal["gap", "needs_review", "no_gap"] | None
    api_compatibility: Literal["current_api_outcome_supported", "api_outcome_extension_required"]

    @model_validator(mode="after")
    def projection_matches_evaluation(self):
        expected = {
            "gap_identified": "gap",
            "no_gap_identified_in_available_data": "no_gap",
            "needs_review": "needs_review",
            "not_eligible": None,
        }[self.evaluation.outcome]
        if self.legacy_flag_status != expected:
            raise ValueError("Legacy flag must be an explicit projection of the canonical outcome")
        status = "api_outcome_extension_required" if expected is None else "current_api_outcome_supported"
        if self.api_compatibility != status:
            raise ValueError("API compatibility marker does not match projected outcome")
        return self


class ContextRecord(Contract):
    source: ResourceVersion
    patient_reference: PatientRef
    source_last_updated: AwareDatetime
    verified_at: AwareDatetime
    authorized: StrictBool
    source_verified: StrictBool
    text: Text
    reviewed: StrictBool = False
    offset_start: int | None = Field(default=None, ge=0)
    offset_end: int | None = Field(default=None, ge=1)
    offset_unit: Literal["unicode_code_points"] = "unicode_code_points"

    @model_validator(mode="after")
    def paired_offsets(self):
        if (self.offset_start is None) != (self.offset_end is None):
            raise ValueError("Context source offsets must both be present or both be null")
        if self.offset_start is not None and self.offset_end <= self.offset_start:
            raise ValueError("Context source offsets must be a non-empty half-open span")
        if self.offset_start is not None and self.offset_end - self.offset_start != len(self.text):
            raise ValueError("Context excerpt length must match its Unicode code-point offsets")
        return self


class VerifiedContext(Contract):
    workspace_id: LogicalId
    patient_reference: PatientRef
    generation_id: LogicalId
    mapping_version: Version
    permission_revision: Version
    built_at: AwareDatetime
    verified_at: AwareDatetime
    expires_at: AwareDatetime
    state: Literal["current", "stale", "dirty", "unavailable"]
    authorized: StrictBool
    source_verified: StrictBool
    completeness: Literal["complete_in_checked_scope", "partial", "unknown"]
    checked_scope: Text
    records: tuple[ContextRecord, ...]


class ContextItem(Contract):
    """One authorized FHIR resource/passsage; resource boundaries never merge."""
    item_id: LogicalId
    source: ResourceVersion
    patient_reference: PatientRef
    tier: Literal["structured", "longitudinal", "relational"]
    source_last_updated: AwareDatetime
    verified_at: AwareDatetime
    permission_revision: Version
    generation_id: LogicalId
    authorized: StrictBool
    source_verified: StrictBool
    reviewed: StrictBool
    text: Text
    offset_start: int | None = Field(default=None, ge=0)
    offset_end: int | None = Field(default=None, ge=1)
    offset_unit: Literal["unicode_code_points"] = "unicode_code_points"

    @model_validator(mode="after")
    def paired_offsets(self):
        if (self.offset_start is None) != (self.offset_end is None):
            raise ValueError("Context source offsets must both be present or both be null")
        if self.offset_start is not None and self.offset_end <= self.offset_start:
            raise ValueError("Context source offsets must be a non-empty half-open span")
        if self.offset_start is not None and self.offset_end - self.offset_start != len(self.text):
            raise ValueError("Context excerpt length must match its Unicode code-point offsets")
        return self


class ContextQuery(Contract):
    """Internal query over an already backend-authorized context envelope."""
    query: Text
    max_items: int = Field(default=12, ge=1, le=30)
    max_context_characters: int = Field(default=12000, ge=256, le=24000)
    requested_resource_types: tuple[str, ...] = ()


class AssembledContext(Contract):
    query: Text
    workspace_id: LogicalId
    patient_reference: PatientRef
    generation_id: LogicalId
    permission_revision: Version
    state: Literal["assembled", "empty_unknown"]
    completeness: Literal["complete_in_checked_scope", "partial", "unknown"]
    items: tuple[ContextItem, ...]
    character_count: int = Field(ge=0)
    exhaustive: Literal[False] = False
    absence_claims_allowed: Literal[False] = False
    notice: str = "Context is limited to current authorized sources in the backend checked scope."


class RelateCandidate(Contract):
    """Untrusted graph hint: references only, never a permission or clinical fact."""
    patient_reference: PatientRef
    supporting_references: tuple[ResourceRef, ...] = Field(min_length=1, max_length=8)
    candidate_kind: Literal["family_history", "care_plan_link", "provider_handoff"]


class RelateCandidateBatch(Contract):
    """Metadata returned by the fixed backend Relate operation."""
    workspace_id: LogicalId
    patient_reference: PatientRef
    generation_id: LogicalId
    permission_revision: Version
    state: Literal["current", "stale", "unavailable"]
    candidates: tuple[RelateCandidate, ...] = Field(max_length=100)


class LayoutBlock(Contract):
    block_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    page_number: int = Field(ge=1)
    order: int = Field(ge=0)
    kind: Literal["heading", "paragraph", "table_cell", "form_field"]
    section: str | None = Field(default=None, max_length=120)
    text: str = Field(min_length=1, max_length=6000)


class ParsedDocument(Contract):
    """Parser output still requires backend source verification/authorization."""
    source: ResourceRef
    source_version: Version
    media_type: Literal["text/plain", "application/pdf", "image/tiff", "image/png", "image/jpeg"]
    parser_id: str = Field(min_length=1, max_length=80)
    parser_revision: Version
    extraction_method: Literal["native_text", "ocr"]
    simulated: StrictBool
    blocks: tuple[LayoutBlock, ...] = Field(max_length=500)


class EngagementTemplate(Contract):
    template_id: LogicalId
    channel: Literal["sms", "whatsapp", "portal"]
    language: Literal["en"]
    purpose: Literal["prevention_reminder", "follow_up_choice"]
    text: Text
    review_status: Literal["human_review_required_before_demo"]
    simulated_only: Literal[True] = True


class MetricDefinition(Contract):
    metric_id: LogicalId
    version: Version
    name: Text
    unit_of_analysis: Literal["patient_pathway", "case", "task", "event"]
    aggregation: Literal["rate", "median", "count"]
    numerator: Text
    denominator: Text
    exclusions: tuple[str, ...]
    reporting_period: Literal["point_in_time", "calendar_month", "cohort_followup"]
    suppression_threshold: int = Field(default=10, ge=10)
    complementary_suppression_required: StrictBool = True
    synthetic_only: StrictBool = True

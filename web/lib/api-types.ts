/**
 * Types mirroring the Namaa API (api/app/schemas.py).
 *
 * The API is the source of truth for these shapes. Keep this file in step with
 * `api/app/schemas.py`; `GET /api/v1/meta/actions` publishes the action and
 * error contract at runtime so drift is detectable.
 */

export const STAGES = [
  "identified",
  "reviewed",
  "invited",
  "booked",
  "attended",
  "follow_up",
  "closed",
] as const;
export type Stage = (typeof STAGES)[number];

export const DISPOSITIONS = [
  "active",
  "completed",
  "declined",
  "deferred",
  "unreachable",
  "clinically_closed_other",
] as const;
export type Disposition = (typeof DISPOSITIONS)[number];

export const PATHWAYS = ["child_wcv", "adult_screening"] as const;
export type Pathway = (typeof PATHWAYS)[number];

export type Role = "coordinator" | "clinical_reviewer" | "population_analyst";

export type ActionId =
  | "record_contact_preference"
  | "approve_pathway"
  | "send_invitation"
  | "record_decline"
  | "record_unreachable"
  | "book_appointment"
  | "record_attendance"
  | "record_referral_outcome"
  | "reassign_owner"
  | "defer_with_recall"
  | "close_as_completed"
  | "close_other"
  | "reopen";

export type StructuredError = {
  code: string;
  message: string;
  field_errors: Record<string, string>;
  request_id: string | null;
};

export type ContactPreference = {
  channel: string;
  language: string;
  preferred_time: string;
};

export type CompletionEvidence = {
  evidence_type: string;
  evidence_reference: string;
};

export type SourceFact = {
  label: string;
  value: string;
  source: string;
  observed_time: string;
  verified: boolean;
};

export type MissingItem = { label: string; consequence: string };

export type Booking = {
  appointment_time: string;
  location: string;
};

export type EventOut = {
  booking?: Booking | null;
  id: string;
  case_id: string;
  timestamp: string;
  actor_role: string;
  action: string;
  prior_state: string | null;
  new_state: string | null;
  reason: string | null;
  evidence_reference: string | null;
  request_id: string | null;
  outcome: string | null;
};

export type CaseRow = {
  id: string;
  care_gap_id: string;
  patient_id: string | null;
  patient_label: string;
  age_band: string;
  pathway: Pathway;
  rule_id_version: string;
  flag_status: "gap" | "needs_review";
  stage: Stage;
  disposition: Disposition;
  owner: string;
  next_action: string;
  due_time: string | null;
  overdue: boolean;
  revision: number;
  completion_status?: string | null;
};

export type CaregiverAuthority =
  | "verified_caregiver"
  | "self"
  | "unknown"
  | "not_supplied";

export type CaseDetail = {
  booking?: Booking | null;
  explanation: string;
  factors: SourceFact[];
  missing: MissingItem[];
  suggested_review_action: string;
  events: EventOut[];
  contact_preference: ContactPreference | null;
  recall_date: string | null;
  completion_evidence: CompletionEvidence | null;
  referral_outcome: "pending" | "accepted" | "rejected" | null;
  caregiver_authority?: CaregiverAuthority | null;
  caregiver_relationship?: string | null;
};

export type AvailableAction = {
  id: ActionId;
  permitted_role: Role;
  blocked_reason: string | null;
};

export type CaseOut = CaseRow & {
  detail: CaseDetail;
  available_actions: AvailableAction[];
};

/** The mutation envelope. Every field is required by the server. */
export type ActionRequest = {
  action: ActionId;
  expected_revision: number;
  request_id: string;
  data: Record<string, string | boolean | number>;
};

export type ActionResponse = { case: CaseOut; event: EventOut };

export type DemoSessionOut = {
  session_id: string;
  role: Role;
  synthetic: boolean;
  notice: string;
};

export type DemoResetOut = {
  session_id: string;
  cases_restored: number;
  notice: string;
};

export type MetricCell = {
  label: string;
  numerator: number | null;
  denominator: number | null;
  value: number | null;
  suppressed: boolean;
  reason: string | null;
  threshold: number | null;
};

export type ApiPathwayMetrics = {
  pathway: Pathway;
  eligible: MetricCell;
  invited: MetricCell;
  booked: MetricCell;
  attended: MetricCell;
  follow_up: MetricCell;
  completed: MetricCell;
  declined: MetricCell;
  unreachable: MetricCell;
};

export type AnalyticsOverview = {
  synthetic: boolean;
  as_of: string;
  threshold: number;
  pathways: ApiPathwayMetrics[];
  notice: string;
};

export const DISPOSITION_LABELS: Record<Disposition, string> = {
  active: "Active",
  completed: "Preventive action completed",
  declined: "Declined",
  deferred: "Deferred",
  unreachable: "Unreachable",
  clinically_closed_other: "Clinically closed — other reason",
};

export const STAGE_LABELS: Record<Stage, string> = {
  identified: "Identified",
  reviewed: "Reviewed",
  invited: "Invited",
  booked: "Booked",
  attended: "Attended",
  follow_up: "Follow-up",
  closed: "Closed",
};

export const PATHWAY_LABELS: Record<Pathway, string> = {
  child_wcv: "Child Well-Child",
  adult_screening: "Adult Screening",
};

/* ---------------------------------------------------------------------------
   Extraction and proposals (D004). Mirrors api/app/schemas_extraction.py and
   the proposal projection in api/app/services/extractions.py.
   --------------------------------------------------------------------------- */

export type ExtractionState =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "timed_out";

export type ReviewState = "proposed" | "accepted" | "corrected" | "rejected";
export type Assertion = "present" | "absent" | "uncertain" | "historical";
export type ProposalSubject = "patient" | "family_member";

export type NestedProposalFact = {
  concept: string;
  value_text: string;
  subject: ProposalSubject;
  assertion: Assertion;
  effective_date: string | null;
  excerpt: string;
  proposed_resource_type: string;
  relationship: string | null;
};

export type NestedProposalModel = {
  model_id: string;
  model_revision: string;
  prompt_version: string;
  simulated: boolean;
};

export type NestedProposalIssue = {
  code: string;
  severity: "block" | "review";
  message: string;
};

/**
 * Extraction and GET-fact wire shape (Alfred nested contract, Ismail I4).
 * Review state on GET is `review_state`; extraction snapshots stay `proposed`.
 */
export type ApiProposal = {
  id: string;
  version: number;
  state: "proposed" | ReviewState;
  workspace_id?: string;
  patient_reference?: string;
  source_document_id: string;
  source_document_version: string;
  source_sha256: string;
  fact: NestedProposalFact;
  /**
   * Exact supporting excerpt lives on `fact`. Offsets are Unicode CODE POINTS
   * (ai/docs/CONTRACTS.md), not JavaScript string indices — compare them with
   * lib/text-offsets.ts. Null means the source match failed or was ambiguous,
   * and nothing may be highlighted.
   */
  offset_start: number | null;
  offset_end: number | null;
  offset_unit: "unicode_code_points";
  issues: NestedProposalIssue[];
  model: NestedProposalModel;
  review_state?: ReviewState;
  reviewer_reference?: string | null;
  review_reason?: string | null;
  reviewed_at?: string | null;
  notice?: string | null;
};

export type ExtractionAccepted = {
  job_id: string;
  state: ExtractionState;
  events_url: string;
  status_url: string;
  notice: string;
};

export type ExtractionJobOut = {
  event?: string | null;
  job_id: string;
  document_id: string;
  document_version: number;
  state: ExtractionState;
  progress_percent: number;
  message: string;
  elapsed_ms: number;
  timeout_ms: number;
  model_revision: string;
  prompt_version: string;
  error_code: string | null;
  error_message: string | null;
  synthetic: boolean;
  /** "offline_fixture" today — must never be presented as live inference. */
  inference_mode: string;
  proposals: ApiProposal[];
};

export type DocumentOut = {
  id: string;
  version: number;
  document_date: string;
  patient_id: string | null;
  case_id: string | null;
  text: string;
  policy_adapter: string;
  production_authorization: boolean;
};

/** GET /api/v1/cases/{id}/documents — listing has no note text. */
export type CaseDocumentOut = {
  id: string;
  version: number;
  document_date: string;
  patient_id: string;
  case_id: string | null;
};

export const CAREGIVER_AUTHORITY_LABELS: Record<CaregiverAuthority, string> = {
  verified_caregiver: "Verified caregiver (synthetic record)",
  self: "Self — no caregiver required",
  unknown: "Unknown — not established",
  not_supplied: "Not supplied",
};

/* ---------------------------------------------------------------------------
   Canonical evaluations (D006) and verified context (Relate + records).
   --------------------------------------------------------------------------- */

export type ResourceVersionRef = {
  reference: string;
  version: string;
};

export type CanonicalRuleEvaluation = {
  patient_reference: string;
  as_of: string;
  rule_id: string;
  rule_version: string;
  outcome: string;
  input_versions: ResourceVersionRef[];
  contributing_factors: string[];
  missing_information: string[];
  due_date: string | null;
  simulated: boolean;
  synthetic_rule: boolean;
};

export type EvaluationResult = {
  patient_id: string;
  pathway: Pathway;
  rule_id_version: string;
  flag_status: string;
  factors: SourceFact[];
  missing: MissingItem[];
  uncertainty?: string;
  suggested_review_action?: string;
  /** Present on POST; omitted on GET latest. Explicit null means no case opened. */
  case?: CaseOut | null;
  evaluation_id: string;
  created_at?: string;
  rule_evaluation: CanonicalRuleEvaluation | null;
  legacy_flag_status: string | null;
  api_compatibility: string | null;
  notice?: string;
  input_snapshot?: Record<string, unknown>;
};

export type EvaluationRequest = {
  pathway?: Pathway | null;
};

export type RelateCandidate = {
  patient_reference: string;
  supporting_references: string[];
  candidate_kind: string;
};

export type RelateBatch = {
  state: string;
  workspace_id: string;
  patient_reference: string;
  permission_revision: string;
  generation_id: string;
  candidates: RelateCandidate[];
};

export type RelateHint = {
  resource_type: string;
  logical_id: string;
};

export type VerifiedContextRecord = {
  source: ResourceVersionRef;
  patient_reference: string;
  source_last_updated: string;
  verified_at: string;
  authorized: boolean;
  source_verified: boolean;
  reviewed: boolean;
  text: string;
};

export type VerifiedContext = {
  workspace_id: string;
  patient_reference: string;
  generation_id: string;
  mapping_version: string;
  permission_revision: string;
  built_at: string;
  verified_at: string;
  expires_at: string;
  state: string;
  authorized: boolean;
  source_verified: boolean;
  completeness: string;
  checked_scope: string;
  records: VerifiedContextRecord[];
  exhaustive: boolean;
  absence_claims_allowed: boolean;
  source_versions: Record<string, string>;
  policy_adapter: string;
  production_authorization: boolean;
  notice: string;
};

export const ASSERTION_LABELS: Record<Assertion, string> = {
  present: "Present",
  absent: "Absent",
  uncertain: "Uncertain",
  historical: "Historical",
};

export const SUBJECT_LABELS: Record<ProposalSubject, string> = {
  patient: "Patient",
  family_member: "Family member",
};

/* Traceability now lives in lib/text-offsets.ts, which compares by Unicode
   code point rather than UTF-16 code unit. */


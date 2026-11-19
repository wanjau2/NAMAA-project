from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    role: Mapped[str] = mapped_column(String(32), default="coordinator")

    commands: Mapped[list[Command]] = relationship(back_populates="workspace")


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("workspace_id", "id", name="uq_patient_ws"),)

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    label: Mapped[str] = mapped_column(String(128))
    age_band: Mapped[str] = mapped_column(String(64))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    language: Mapped[str] = mapped_column(String(16), default="en")
    channel_preference: Mapped[str | None] = mapped_column(String(32), nullable=True)
    preferred_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    caregiver_authority: Mapped[str] = mapped_column(String(64), default="unknown")


class Observation(Base):
    __tablename__ = "observations"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    type: Mapped[str] = mapped_column(String(128))
    value: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(128))
    observed_time: Mapped[str] = mapped_column(String(64))
    missing_or_conflict: Mapped[bool] = mapped_column(Boolean, default=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=True)


class CareGap(Base):
    __tablename__ = "care_gaps"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    pathway: Mapped[str] = mapped_column(String(64))
    rule_id_version: Mapped[str] = mapped_column(String(64))
    flag_status: Mapped[str] = mapped_column(String(32))
    factors_json: Mapped[str] = mapped_column(Text, default="[]")
    missing_json: Mapped[str] = mapped_column(Text, default="[]")
    uncertainty: Mapped[str] = mapped_column(Text, default="")
    explanation: Mapped[str] = mapped_column(Text, default="")
    suggested_review_action: Mapped[str] = mapped_column(Text, default="")


class Case(Base):
    __tablename__ = "cases"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    care_gap_id: Mapped[str] = mapped_column(String(64), index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    patient_label: Mapped[str] = mapped_column(String(128))
    age_band: Mapped[str] = mapped_column(String(64))
    pathway: Mapped[str] = mapped_column(String(64))
    rule_id_version: Mapped[str] = mapped_column(String(64))
    flag_status: Mapped[str] = mapped_column(String(32))
    stage: Mapped[str] = mapped_column(String(32))
    disposition: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(128))
    next_action: Mapped[str] = mapped_column(Text)
    due_time: Mapped[str | None] = mapped_column(String(64), nullable=True)
    overdue: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    referral_outcome: Mapped[str | None] = mapped_column(String(32), nullable=True)
    recall_date: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_channel: Mapped[str | None] = mapped_column(String(32), nullable=True)
    contact_language: Mapped[str | None] = mapped_column(String(16), nullable=True)
    contact_preferred_time: Mapped[str | None] = mapped_column(String(32), nullable=True)
    evidence_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean, default=True)


class Event(Base):
    __tablename__ = "events"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[str] = mapped_column(String(64))
    actor_role: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(64))
    prior_state: Mapped[str] = mapped_column(String(64))
    new_state: Mapped[str] = mapped_column(String(64))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Command(Base):
    """Idempotent action journal + optional FHIR saga linkage (D004)."""

    __tablename__ = "commands"
    __table_args__ = (
        UniqueConstraint("workspace_id", "request_id", name="uq_command_request"),
    )

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64))
    case_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    payload_hash: Mapped[str] = mapped_column(String(128))
    response_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64))
    # Saga state for dual-store boundary (application DB ↔ FHIR)
    saga_state: Mapped[str] = mapped_column(String(32), default="app_committed")
    outbox_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    workspace: Mapped[Workspace] = relationship(back_populates="commands")


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint("workspace_id", "id", "version", name="uq_document_ws_ver"),
    )

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    document_date: Mapped[str] = mapped_column(String(64))
    text: Mapped[str] = mapped_column(Text)
    case_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


class ExtractionJob(Base):
    __tablename__ = "extraction_jobs"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    document_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version: Mapped[int] = mapped_column(Integer)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # queued | running | succeeded | failed | cancelled | timed_out
    state: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model_revision: Mapped[str] = mapped_column(String(128), default="offline-fixture-v1")
    prompt_version: Mapped[str] = mapped_column(String(64), default="extract-v0.3")
    progress_percent: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[str] = mapped_column(String(256), default="Queued")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    finished_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timeout_ms: Mapped[int] = mapped_column(Integer, default=90_000)
    # Preserved initiating principal for re-authorization (D005)
    initiating_user_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    initiating_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    initiating_purpose: Mapped[str | None] = mapped_column(String(64), nullable=True)
    initiating_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    principal_snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class Proposal(Base):
    """Proposed facts — outside the clinical store until human review (design §5)."""

    __tablename__ = "proposals"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    job_id: Mapped[str] = mapped_column(String(64), index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    document_id: Mapped[str] = mapped_column(String(64), index=True)
    document_version: Mapped[int] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_sha256: Mapped[str] = mapped_column(String(64), default="")
    concept: Mapped[str] = mapped_column(String(128))
    value_text: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(32))
    assertion: Mapped[str] = mapped_column(String(32))
    effective_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    proposed_resource_type: Mapped[str] = mapped_column(String(64))
    relationship: Mapped[str | None] = mapped_column(String(32), nullable=True)
    excerpt: Mapped[str] = mapped_column(Text)
    offset_start: Mapped[int] = mapped_column(Integer)
    offset_end: Mapped[int] = mapped_column(Integer)
    issues_json: Mapped[str] = mapped_column(Text, default="[]")
    model_id: Mapped[str] = mapped_column(String(128), default="google/medgemma-1.5-4b-it")
    model_revision: Mapped[str] = mapped_column(String(128), default="offline-fixture-v1")
    prompt_version: Mapped[str] = mapped_column(String(64), default="extract-v1.0.1")
    model_simulated: Mapped[bool] = mapped_column(Boolean, default=True)
    # proposed | accepted | corrected | rejected
    review_state: Mapped[str] = mapped_column(String(32), default="proposed")
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_reference: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ReviewCommandJournal(Base):
    """Idempotent human-review journal (outside FHIR until commit)."""

    __tablename__ = "review_commands"
    __table_args__ = (
        UniqueConstraint("workspace_id", "request_id", name="uq_review_request"),
    )

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64))
    proposal_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32))
    payload_hash: Mapped[str] = mapped_column(String(128))
    response_json: Mapped[str] = mapped_column(Text)
    reviewer_reference: Mapped[str] = mapped_column(String(128))
    created_at: Mapped[str] = mapped_column(String(64))
    outbox_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PrincipalRevocation(Base):
    """Simple revocation list for guest/service principals (synthetic prototype)."""

    __tablename__ = "principal_revocations"
    __table_args__ = (
        UniqueConstraint("workspace_id", "principal_id", name="uq_revocation"),
    )

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    principal_id: Mapped[str] = mapped_column(String(128), index=True)
    reason_code: Mapped[str] = mapped_column(String(64), default="revoked")
    revoked_at: Mapped[str] = mapped_column(String(64))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class OutboxEntry(Base):
    """Transactional outbox for application DB → FHIR gateway (D004)."""

    __tablename__ = "outbox_entries"
    __table_args__ = (
        UniqueConstraint("workspace_id", "request_id", name="uq_outbox_request"),
    )

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(64))
    case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    # pending | processing | committed | compensating | compensated | dead_lettered
    state: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    intended_bundle_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[str | None] = mapped_column(String(64), nullable=True)
    next_attempt_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[str] = mapped_column(String(64))
    dead_lettered_at: Mapped[str | None] = mapped_column(String(64), nullable=True)
    compensation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class FhirResource(Base):
    """In-process FHIR gateway stub store (replace with HAPI later)."""

    __tablename__ = "fhir_resources"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "resource_type",
            "logical_id",
            name="uq_fhir_logical",
        ),
    )

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(64))
    logical_id: Mapped[str] = mapped_column(String(64))
    version_id: Mapped[int] = mapped_column(Integer, default=1)
    body_json: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    updated_at: Mapped[str] = mapped_column(String(64))


class RuleEvaluation(Base):
    __tablename__ = "rule_evaluations"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    patient_id: Mapped[str] = mapped_column(String(64), index=True)
    pathway: Mapped[str] = mapped_column(String(64))
    rule_id_version: Mapped[str] = mapped_column(String(64))
    input_snapshot_json: Mapped[str] = mapped_column(Text)
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(64))


class AuditEvent(Base):
    """Protected audit sink rows — no note text, tokens, or full prompts (D005)."""

    __tablename__ = "audit_events"

    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str] = mapped_column(String(64), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id"), index=True)
    timestamp: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64))
    request_id: Mapped[str] = mapped_column(String(64), index=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(128))
    service_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    purpose_of_use: Mapped[str] = mapped_column(String(64))
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    patient_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decision_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_revision: Mapped[str] = mapped_column(String(64))
    permission_revision: Mapped[str] = mapped_column(String(64))
    policy_adapter: Mapped[str] = mapped_column(String(64))
    production_authorization: Mapped[bool] = mapped_column(Boolean, default=False)
    source_versions_json: Mapped[str] = mapped_column(Text, default="{}")
    model_revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewer_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    reason_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    safe_detail_json: Mapped[str] = mapped_column(Text, default="{}")

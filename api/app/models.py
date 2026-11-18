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

    workspace: Mapped[Workspace] = relationship(back_populates="commands")


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

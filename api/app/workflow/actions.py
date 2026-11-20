"""Action registry mirrors web/lib/case-actions.ts — server is authoritative."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.models import Case

Role = str


@dataclass(frozen=True)
class FieldSpec:
    name: str
    required: bool = False
    kind: str = "text"


@dataclass
class ActionSpec:
    id: str
    role: Role
    applies: Callable[[Case], bool]
    fields: list[FieldSpec]
    precondition: Callable[[Case], str | None] | None = None


def _open(c: Case) -> bool:
    return c.stage != "closed"


def _paused(c: Case) -> bool:
    return c.stage != "closed" and c.disposition in {"deferred", "unreachable"}


def _rejected_referral_blocks_completion(c: Case) -> str | None:
    # Reassignment clears overdue (the open escalation). The rejected outcome
    # stays on the case; it must not keep blocking after that handoff.
    if c.stage == "follow_up" and c.referral_outcome == "rejected" and c.overdue:
        return (
            "The referral was rejected and is still open. Reassign it before "
            "closing, or close with another reason."
        )
    return None


ACTIONS: dict[str, ActionSpec] = {
    "record_contact_preference": ActionSpec(
        id="record_contact_preference",
        role="coordinator",
        applies=_open,
        fields=[
            FieldSpec("channel", True, "select"),
            FieldSpec("language", True, "select"),
            FieldSpec("preferred_time", True, "select"),
        ],
    ),
    "approve_pathway": ActionSpec(
        id="approve_pathway",
        role="clinical_reviewer",
        applies=lambda c: c.stage == "identified",
        precondition=lambda c: (
            "Information is missing or unverified. Resolve it in source review and let the rule re-evaluate before approving — unknown is not the same as up to date."
            if c.flag_status == "needs_review"
            else None
        ),
        fields=[
            FieldSpec("attestation", True, "checkbox"),
            FieldSpec("reason", False, "textarea"),
        ],
    ),
    "send_invitation": ActionSpec(
        id="send_invitation",
        role="coordinator",
        applies=lambda c: c.stage == "reviewed",
        precondition=lambda c: (
            "Record a contact preference first, so the invitation uses a channel the person actually chose."
            if not c.contact_channel
            else None
        ),
        fields=[FieldSpec("template", True, "select")],
    ),
    "record_decline": ActionSpec(
        id="record_decline",
        role="coordinator",
        applies=lambda c: c.stage in {"invited", "booked"},
        fields=[FieldSpec("reason", True, "textarea")],
    ),
    "record_unreachable": ActionSpec(
        id="record_unreachable",
        role="coordinator",
        applies=lambda c: c.stage in {"reviewed", "invited"},
        fields=[
            FieldSpec("attempts", True, "number"),
            FieldSpec("reason", True, "textarea"),
        ],
    ),
    "book_appointment": ActionSpec(
        id="book_appointment",
        role="coordinator",
        # Deferred/unreachable stay invited but paused; resume_pathway first.
        applies=lambda c: c.stage == "invited" and c.disposition == "active",
        fields=[
            FieldSpec("appointment_time", True, "date"),
            FieldSpec("location", True, "text"),
        ],
    ),
    "record_attendance": ActionSpec(
        id="record_attendance",
        role="coordinator",
        applies=lambda c: c.stage == "booked",
        fields=[
            FieldSpec("attended", True, "select"),
            FieldSpec("reason", False, "textarea"),
        ],
    ),
    "record_referral_outcome": ActionSpec(
        id="record_referral_outcome",
        role="coordinator",
        applies=lambda c: c.stage in {"attended", "follow_up"},
        fields=[
            FieldSpec("outcome", True, "select"),
            FieldSpec("reason", True, "textarea"),
        ],
    ),
    "reassign_owner": ActionSpec(
        id="reassign_owner",
        role="coordinator",
        applies=_open,
        fields=[
            FieldSpec("owner", True, "text"),
            FieldSpec("reason", True, "textarea"),
        ],
    ),
    "defer_with_recall": ActionSpec(
        id="defer_with_recall",
        role="coordinator",
        applies=_open,
        fields=[
            FieldSpec("recall_date", True, "date"),
            FieldSpec("reason", True, "textarea"),
        ],
    ),
    "resume_pathway": ActionSpec(
        id="resume_pathway",
        role="coordinator",
        applies=_paused,
        fields=[FieldSpec("reason", True, "textarea")],
    ),
    "close_as_completed": ActionSpec(
        id="close_as_completed",
        role="clinical_reviewer",
        applies=lambda c: c.stage in {"attended", "follow_up"},
        precondition=_rejected_referral_blocks_completion,
        fields=[
            FieldSpec("evidence_type", True, "select"),
            FieldSpec("evidence_reference", True, "text"),
            FieldSpec("attestation", True, "checkbox"),
        ],
    ),
    "close_other": ActionSpec(
        id="close_other",
        role="clinical_reviewer",
        applies=_open,
        fields=[FieldSpec("reason", True, "textarea")],
    ),
    "reopen": ActionSpec(
        id="reopen",
        role="clinical_reviewer",
        applies=lambda c: c.stage == "closed",
        fields=[FieldSpec("reason", True, "textarea")],
    ),
}


ACTION_ROLES: dict[str, str] = {k: v.role for k, v in ACTIONS.items()}
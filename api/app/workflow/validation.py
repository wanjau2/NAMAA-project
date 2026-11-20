"""Typed, bounded action payloads shared by every workflow entry point."""
from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AfterValidator, BaseModel, ConfigDict, Field, StrictBool,
    StringConstraints, ValidationError, field_validator,
)

from app.errors import AppError

Text = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=2000)]
ShortText = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=128)]
OptionalNote = Annotated[str, StringConstraints(strict=True, strip_whitespace=True, max_length=2000)]


def calendar_date(value: str) -> str:
    # fromisoformat alone also accepts compact dates and ISO week dates.
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        raise ValueError("Use YYYY-MM-DD.")
    if date.fromisoformat(value).isoformat() != value:
        raise ValueError("Use YYYY-MM-DD.")
    return value

CalendarDate = Annotated[
    str, StringConstraints(strict=True, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    AfterValidator(calendar_date), Field(json_schema_extra={"format": "date"}),
]


class ActionData(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ContactData(ActionData):
    channel: Literal["sms", "phone", "email"]
    language: Literal["en", "ar"]
    preferred_time: Literal["morning", "afternoon", "evening"]


class ConfirmedData(ActionData):
    attestation: StrictBool

    @field_validator("attestation")
    @classmethod
    def confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("This confirmation is required.")
        return value


class ApprovalData(ConfirmedData):
    reason: OptionalNote | None = None


class InvitationData(ActionData):
    template: Literal["wcv_invite_v1", "screening_invite_v1"]


class ReasonData(ActionData):
    reason: Text


class UnreachableData(ReasonData):
    attempts: Annotated[int, Field(strict=True, ge=1, le=1000)]


class BookingData(ActionData):
    appointment_time: CalendarDate
    location: ShortText


class AttendanceData(ActionData):
    attended: Literal["attended", "did_not_attend"]
    reason: OptionalNote | None = None


class ReferralData(ReasonData):
    outcome: Literal["pending", "accepted", "rejected"]


class OwnerData(ReasonData):
    owner: ShortText


class RecallData(ReasonData):
    recall_date: CalendarDate


class CompletionData(ConfirmedData):
    evidence_type: Literal["Encounter", "Procedure", "DiagnosticReport"]
    evidence_reference: ShortText


ACTION_DATA = {
    "record_contact_preference": ContactData,
    "approve_pathway": ApprovalData,
    "send_invitation": InvitationData,
    "record_decline": ReasonData,
    "record_unreachable": UnreachableData,
    "book_appointment": BookingData,
    "record_attendance": AttendanceData,
    "record_referral_outcome": ReferralData,
    "reassign_owner": OwnerData,
    "defer_with_recall": RecallData,
    "close_as_completed": CompletionData,
    "close_other": ReasonData,
    "reopen": ReasonData,
}


def validate_action_data(action: str, data: dict, request_id: str) -> dict:
    try:
        return ACTION_DATA[action].model_validate(data).model_dump(exclude_none=True)
    except ValidationError as exc:
        raise AppError(
            code="validation_failed", status_code=422,
            message="Correct the invalid action fields.", request_id=request_id,
            field_errors={str(e["loc"][0]): e["msg"] for e in exc.errors()},
        ) from exc

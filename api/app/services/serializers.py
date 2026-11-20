from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import AppointmentBooking, CareGap, Case, Command, Event, OutboxEntry, Patient
from app.schemas import (
    BookingOut,
    CaseDetail,
    CaseOut,
    CompletionEvidence,
    ContactPreference,
    EventOut,
    MissingItem,
    SourceFact,
)


def booking_to_out(booking: AppointmentBooking | None) -> BookingOut | None:
    if booking is None:
        return None
    return BookingOut(appointment_time=booking.appointment_time, location=booking.location)


def event_to_out(event: Event, *, booking: AppointmentBooking | None = None) -> EventOut:
    return EventOut(
        booking=booking_to_out(booking),
        id=event.id,
        case_id=event.case_id,
        timestamp=event.timestamp,
        actor_role=event.actor_role,
        action=event.action,
        prior_state=event.prior_state,
        new_state=event.new_state,
        reason=event.reason,
        evidence_reference=event.evidence_reference,
        request_id=event.request_id,
        outcome=event.outcome,
    )


def case_to_out(db: Session, case: Case) -> CaseOut:
    gap = (
        db.query(CareGap)
        .filter(
            CareGap.workspace_id == case.workspace_id,
            CareGap.id == case.care_gap_id,
        )
        .one_or_none()
    )
    events = (
        db.query(Event)
        .filter(Event.workspace_id == case.workspace_id, Event.case_id == case.id)
        .order_by(Event.timestamp.asc(), Event.pk.asc())
        .all()
    )

    factors = [SourceFact.model_validate(x) for x in json.loads(gap.factors_json)] if gap else []
    missing = [MissingItem.model_validate(x) for x in json.loads(gap.missing_json)] if gap else []

    contact = None
    if case.contact_channel and case.contact_language and case.contact_preferred_time:
        contact = ContactPreference(
            channel=case.contact_channel,
            language=case.contact_language,
            preferred_time=case.contact_preferred_time,
        )

    evidence = None
    if case.evidence_type and case.evidence_reference:
        evidence = CompletionEvidence(
            evidence_type=case.evidence_type,
            evidence_reference=case.evidence_reference,
        )

    patient = (
        db.query(Patient)
        .filter(Patient.workspace_id == case.workspace_id, Patient.id == case.patient_id)
        .one_or_none()
    )
    authority = patient.caregiver_authority if patient else "unknown"
    if authority not in {"verified_caregiver", "self", "unknown", "not_supplied"}:
        authority = "unknown"

    bookings = db.query(AppointmentBooking).filter_by(
        workspace_id=case.workspace_id, case_id=case.id
    ).order_by(AppointmentBooking.pk.asc()).all()
    by_event = {booking.event_id: booking for booking in bookings}

    detail = CaseDetail(
        explanation=gap.explanation if gap else "",
        factors=factors,
        missing=missing,
        suggested_review_action=gap.suggested_review_action if gap else "",
        events=[event_to_out(e, booking=by_event.get(e.id)) for e in events],
        booking=booking_to_out(bookings[-1] if bookings else None),
        contact_preference=contact,
        recall_date=case.recall_date,
        completion_evidence=evidence,
        referral_outcome=case.referral_outcome,  # type: ignore[arg-type]
        caregiver_authority=authority,  # type: ignore[arg-type]
        caregiver_relationship=None,
    )

    completion_status = None
    next_action = case.next_action
    latest = db.query(Command, OutboxEntry).join(
        OutboxEntry, Command.outbox_id == OutboxEntry.id
    ).filter(Command.workspace_id == case.workspace_id, Command.case_id == case.id,
             OutboxEntry.workspace_id == case.workspace_id,
             Command.action == "close_as_completed").order_by(Command.pk.desc()).first()
    if latest:
        command, entry = latest
        snapshot = json.loads(command.response_json)["case"]
        if snapshot["revision"] == case.revision:
            completion_status = entry.state
            if entry.state in {"dead_lettered", "compensated"}:
                next_action = "Completion was not persisted — review evidence or retry the failed write"
        elif case.disposition == "completed" and entry.state == "committed":
            completion_status = "committed"

    return CaseOut(
        id=case.id,
        care_gap_id=case.care_gap_id,
        patient_id=case.patient_id,
        patient_label=case.patient_label,
        age_band=case.age_band,
        pathway=case.pathway,  # type: ignore[arg-type]
        rule_id_version=case.rule_id_version,
        flag_status=case.flag_status,  # type: ignore[arg-type]
        stage=case.stage,  # type: ignore[arg-type]
        disposition=case.disposition,  # type: ignore[arg-type]
        owner=case.owner,
        next_action=next_action,
        completion_status=completion_status,
        due_time=case.due_time,
        overdue=case.overdue,
        revision=case.revision,
        detail=detail,
        available_actions=_available_actions(db, case),
    )


def _available_actions(db: Session, case: Case):
    from app.workflow.availability import available_actions_for

    return available_actions_for(db, case)
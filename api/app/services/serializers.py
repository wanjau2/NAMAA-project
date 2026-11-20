from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import CareGap, Case, Event, Patient
from app.schemas import (
    CaseDetail,
    CaseOut,
    CompletionEvidence,
    ContactPreference,
    EventOut,
    MissingItem,
    SourceFact,
)


def event_to_out(event: Event) -> EventOut:
    return EventOut(
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

    detail = CaseDetail(
        explanation=gap.explanation if gap else "",
        factors=factors,
        missing=missing,
        suggested_review_action=gap.suggested_review_action if gap else "",
        events=[event_to_out(e) for e in events],
        contact_preference=contact,
        recall_date=case.recall_date,
        completion_evidence=evidence,
        referral_outcome=case.referral_outcome,  # type: ignore[arg-type]
        caregiver_authority=authority,  # type: ignore[arg-type]
        caregiver_relationship=None,
    )

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
        next_action=case.next_action,
        due_time=case.due_time,
        overdue=case.overdue,
        revision=case.revision,
        detail=detail,
    )
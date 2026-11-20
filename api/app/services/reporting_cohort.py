"""Labelled synthetic reporting cohort generated from cases and events.

The six journey cases are too small to publish under whole-release suppression
(n < 10, including complements). This cohort is counted in analytics and kept
off the coordinator worklist.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.models import CareGap, Case, Event, FhirResource, Patient

PATHWAYS = (
    ("child_wcv", "c", "0–1 years", "DEMO_WCV_01", "Reporting child"),
    ("adult_screening", "a", "45–49 years", "DEMO_ADULT_01", "Reporting adult"),
)
PER_PATHWAY = 40
STAMP = "2026-11-01T09:00:00Z"


def _factors(pathway: str, rule_id: str) -> str:
    return json.dumps(
        [
            {
                "label": "Last recorded preventive visit",
                "value": "2024-01-15",
                "source": f"Rule/{rule_id}",
                "observed_time": "2024-01-15T00:00:00Z",
                "verified": True,
            }
        ]
    )


def _event(
    *,
    event_id: str,
    workspace_id: str,
    case_id: str,
    action: str,
    prior_state: str,
    new_state: str,
    actor_role: str = "coordinator",
    outcome: str | None = None,
    evidence_reference: str | None = None,
) -> Event:
    return Event(
        id=event_id,
        workspace_id=workspace_id,
        case_id=case_id,
        timestamp=STAMP,
        actor_role=actor_role,
        action=action,
        prior_state=prior_state,
        new_state=new_state,
        outcome=outcome,
        evidence_reference=evidence_reference,
        request_id=None,
        reason="Synthetic reporting cohort",
    )


def load_reporting_cohort(db: Session, workspace_id: str) -> int:
    added = 0
    for pathway, prefix, age_band, rule_id, label in PATHWAYS:
        for index in range(PER_PATHWAY):
            token = f"{prefix}{index:02d}"
            patient_id = f"pat-rpt-{token}"
            gap_id = f"gap-rpt-{token}"
            case_id = f"rpt-{token}"
            db.add(
                Patient(
                    id=patient_id,
                    workspace_id=workspace_id,
                    label=f"{label} {index:02d} (synthetic)",
                    age_band=age_band,
                    synthetic=True,
                    language="en",
                    caregiver_authority="unknown",
                )
            )
            db.add(
                CareGap(
                    id=gap_id,
                    workspace_id=workspace_id,
                    patient_id=patient_id,
                    pathway=pathway,
                    rule_id_version=rule_id,
                    flag_status="gap",
                    factors_json=_factors(pathway, rule_id),
                    missing_json="[]",
                    explanation="Synthetic reporting cohort — not shown on the worklist.",
                    suggested_review_action="None — reporting fixture",
                )
            )
            bucket = index // 10
            kwargs: dict = dict(
                id=case_id,
                workspace_id=workspace_id,
                care_gap_id=gap_id,
                patient_id=patient_id,
                patient_label=f"{label} {index:02d} (synthetic)",
                age_band=age_band,
                pathway=pathway,
                rule_id_version=rule_id,
                flag_status="gap",
                owner="Reporting cohort",
                revision=1,
                eligible=True,
                worklist=False,
                overdue=False,
            )
            if bucket == 0:
                db.add(
                    Case(
                        **kwargs,
                        stage="identified",
                        disposition="active",
                        next_action="Reporting cohort — identified, not invited",
                    )
                )
            elif bucket == 1:
                db.add(
                    Case(
                        **kwargs,
                        stage="reviewed",
                        disposition="unreachable",
                        next_action="Reporting cohort — unreachable before invitation",
                    )
                )
                db.add(
                    _event(
                        event_id=f"evt-rpt-{token}-unr",
                        workspace_id=workspace_id,
                        case_id=case_id,
                        action="record_unreachable",
                        prior_state="reviewed/active",
                        new_state="reviewed/unreachable",
                    )
                )
            elif bucket == 2:
                db.add(
                    Case(
                        **kwargs,
                        stage="invited",
                        disposition="declined",
                        next_action="Reporting cohort — declined after invitation",
                        contact_channel="sms",
                        contact_language="en",
                        contact_preferred_time="morning",
                    )
                )
                db.add(
                    _event(
                        event_id=f"evt-rpt-{token}-inv",
                        workspace_id=workspace_id,
                        case_id=case_id,
                        action="send_invitation",
                        prior_state="reviewed/active",
                        new_state="invited/active",
                    )
                )
                db.add(
                    _event(
                        event_id=f"evt-rpt-{token}-dcl",
                        workspace_id=workspace_id,
                        case_id=case_id,
                        action="record_decline",
                        prior_state="invited/active",
                        new_state="invited/declined",
                    )
                )
            else:
                evidence_id = f"enc-rpt-{token}"
                evidence_ref = f"Encounter/{evidence_id}"
                db.add(
                    Case(
                        **kwargs,
                        stage="closed",
                        disposition="completed",
                        next_action="None — closed with evidence",
                        contact_channel="sms",
                        contact_language="en",
                        contact_preferred_time="morning",
                        evidence_type="Encounter",
                        evidence_reference=evidence_ref,
                        referral_outcome="accepted",
                    )
                )
                db.add(
                    FhirResource(
                        workspace_id=workspace_id,
                        resource_type="Encounter",
                        logical_id=evidence_id,
                        version_id=1,
                        request_id="reporting-cohort",
                        updated_at=STAMP,
                        body_json=json.dumps(
                            {
                                "resourceType": "Encounter",
                                "id": evidence_id,
                                "status": "finished",
                                "class": {
                                    "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                                    "code": "AMB",
                                },
                                "subject": {"reference": f"Patient/{patient_id}"},
                                "meta": {
                                    "tag": [
                                        {
                                            "system": "https://namaa.example/fhir",
                                            "code": "synthetic",
                                        }
                                    ]
                                },
                            }
                        ),
                    )
                )
                db.add(
                    _event(
                        event_id=f"evt-rpt-{token}-inv",
                        workspace_id=workspace_id,
                        case_id=case_id,
                        action="send_invitation",
                        prior_state="reviewed/active",
                        new_state="invited/active",
                    )
                )
                db.add(
                    _event(
                        event_id=f"evt-rpt-{token}-book",
                        workspace_id=workspace_id,
                        case_id=case_id,
                        action="book_appointment",
                        prior_state="invited/active",
                        new_state="booked/active",
                    )
                )
                db.add(
                    _event(
                        event_id=f"evt-rpt-{token}-att",
                        workspace_id=workspace_id,
                        case_id=case_id,
                        action="record_attendance",
                        prior_state="booked/active",
                        new_state="attended/active",
                        outcome="attended",
                    )
                )
                db.add(
                    _event(
                        event_id=f"evt-rpt-{token}-fu",
                        workspace_id=workspace_id,
                        case_id=case_id,
                        action="record_referral_outcome",
                        prior_state="attended/active",
                        new_state="follow_up/active",
                    )
                )
            added += 1
    return added

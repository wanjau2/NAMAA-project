from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import Case, Command, Event
from app.schemas import ActionRequest, ActionResponse
from app.services.outbox import build_evidence_bundle, enqueue_outbox
from app.services.serializers import case_to_out, event_to_out
from app.workflow.actions import ACTIONS

# Actions that cross the application DB ↔ FHIR boundary (D004 outbox).
FHIR_OUTBOX_ACTIONS = {"close_as_completed", "approve_pathway"}


def _state_label(case: Case) -> str:
    return f"{case.stage}/{case.disposition}"


def _payload_hash(request: ActionRequest, *, case_id: str) -> str:
    blob = json.dumps(
        {
            "case_id": case_id,
            "action": request.action,
            "expected_revision": request.expected_revision,
            "data": request.data,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _validate_fields(spec, data: dict[str, Any], request_id: str) -> None:
    field_errors: dict[str, str] = {}
    for field in spec.fields:
        if not field.required:
            continue
        value = data.get(field.name)
        if field.kind == "checkbox":
            if value is not True:
                field_errors[field.name] = "This confirmation is required."
        elif value is None or (isinstance(value, str) and not value.strip()):
            field_errors[field.name] = "This field is required."
    if field_errors:
        raise AppError(
            code="validation_failed",
            message="Some required information is missing.",
            status_code=422,
            field_errors=field_errors,
            request_id=request_id,
        )


def _apply_transition(case: Case, action: str, data: dict[str, Any]) -> None:
    if action == "record_contact_preference":
        case.contact_channel = str(data["channel"])
        case.contact_language = str(data["language"])
        case.contact_preferred_time = str(data["preferred_time"])
        case.next_action = "Invite using the recorded preference"
    elif action == "approve_pathway":
        case.stage = "reviewed"
        case.disposition = "active"
        case.next_action = "Record contact preference and invite"
    elif action == "send_invitation":
        case.stage = "invited"
        case.next_action = "Await response, then book"
    elif action == "record_decline":
        case.disposition = "declined"
        case.next_action = "No further contact. Remains in the eligible denominator."
        case.due_time = None
        case.overdue = False
    elif action == "record_unreachable":
        case.disposition = "unreachable"
        case.next_action = "Offer phone-assisted support"
    elif action == "book_appointment":
        case.stage = "booked"
        case.next_action = "Confirm attendance after the appointment"
    elif action == "record_attendance":
        if data.get("attended") == "attended":
            case.stage = "attended"
            case.next_action = "Record follow-up or close with evidence"
        else:
            case.next_action = "Did not attend — re-contact and rebook"
    elif action == "record_referral_outcome":
        outcome = str(data["outcome"])
        case.stage = "follow_up"
        case.referral_outcome = outcome
        if outcome == "rejected":
            case.next_action = "Referral rejected — reassign owner"
            case.overdue = True
        elif outcome == "accepted":
            case.next_action = "Await referral appointment and attendance"
        else:
            case.next_action = "Chase receiving service"
    elif action == "reassign_owner":
        case.owner = str(data["owner"])
        case.next_action = "New owner to progress the case"
        case.overdue = False
    elif action == "defer_with_recall":
        recall = str(data["recall_date"])
        case.disposition = "deferred"
        case.recall_date = recall
        case.due_time = f"{recall}T09:00:00Z"
        case.next_action = f"Recall on {recall}"
    elif action == "close_as_completed":
        evidence_type = str(data["evidence_type"])
        if evidence_type not in {"Encounter", "Procedure", "DiagnosticReport"}:
            raise AppError(
                code="validation_failed",
                message="Completion requires Encounter, Procedure, or DiagnosticReport evidence.",
                status_code=422,
                field_errors={"evidence_type": "not_completion_evidence"},
            )
        case.stage = "closed"
        case.disposition = "completed"
        case.evidence_type = evidence_type
        case.evidence_reference = str(data["evidence_reference"])
        case.next_action = "None — closed with evidence"
        case.due_time = None
        case.overdue = False
    elif action == "close_other":
        case.stage = "closed"
        case.disposition = "clinically_closed_other"
        case.next_action = "None — closed for another clinical reason"
        case.due_time = None
        case.overdue = False
    elif action == "reopen":
        case.stage = "follow_up"
        case.disposition = "active"
        case.next_action = "Reopened — determine next step"
    else:
        raise AppError(
            code="unknown_action",
            message=f"Unsupported action '{action}'.",
            status_code=422,
        )


def apply_action(
    db: Session,
    *,
    workspace_id: str,
    case: Case,
    request: ActionRequest,
    role: str,
) -> ActionResponse:
    settings = get_settings()
    now = settings.demo_now
    payload_hash = _payload_hash(request, case_id=case.id)

    existing = (
        db.query(Command)
        .filter(
            Command.workspace_id == workspace_id,
            Command.request_id == request.request_id,
        )
        .one_or_none()
    )
    if existing is not None:
        if existing.payload_hash != payload_hash or existing.case_id != case.id:
            raise AppError(
                code="idempotency_conflict",
                message="This request_id was already used with a different payload or target.",
                status_code=409,
                request_id=request.request_id,
            )
        spec = ACTIONS.get(request.action)
        if spec is None or role != spec.role:
            raise AppError(
                code="forbidden_role",
                message="Replay is not authorized for this role.",
                status_code=403,
                request_id=request.request_id,
            )
        return ActionResponse.model_validate_json(existing.response_json)

    spec = ACTIONS.get(request.action)
    if spec is None:
        raise AppError(
            code="unknown_action",
            message=f"Unsupported action '{request.action}'.",
            status_code=422,
            request_id=request.request_id,
        )

    if role != spec.role:
        raise AppError(
            code="forbidden_role",
            message=f"This action requires the {spec.role.replace('_', ' ')} role.",
            status_code=403,
            request_id=request.request_id,
        )

    if request.expected_revision != case.revision:
        raise AppError(
            code="stale_revision",
            message=(
                f"This case changed since the form was opened "
                f"(expected revision {request.expected_revision}, current {case.revision}). "
                "Reload the latest state — your entries are preserved."
            ),
            status_code=409,
            request_id=request.request_id,
        )

    if not spec.applies(case):
        raise AppError(
            code="invalid_transition",
            message=f'"{request.action}" is not a valid action from {_state_label(case)}.',
            status_code=422,
            request_id=request.request_id,
        )

    blocked = spec.precondition(case) if spec.precondition else None
    if blocked:
        raise AppError(
            code="precondition_failed",
            message=blocked,
            status_code=422,
            request_id=request.request_id,
        )

    _validate_fields(spec, request.data, request.request_id)

    prior = _state_label(case)
    _apply_transition(case, request.action, request.data)
    case.revision += 1
    new_state = _state_label(case)

    reason = request.data.get("reason")
    reason_str = reason.strip() if isinstance(reason, str) and reason.strip() else None
    evidence_ref = request.data.get("evidence_reference")
    evidence_str = (
        evidence_ref.strip()
        if isinstance(evidence_ref, str) and evidence_ref.strip()
        else case.evidence_reference
    )

    event = Event(
        id=f"evt-{uuid.uuid4().hex[:12]}",
        workspace_id=workspace_id,
        case_id=case.id,
        timestamp=now,
        actor_role=role,
        action=request.action,
        prior_state=prior,
        new_state=new_state,
        reason=reason_str,
        evidence_reference=evidence_str,
        request_id=request.request_id,
    )
    db.add(event)
    db.flush()

    response = ActionResponse(case=case_to_out(db, case), event=event_to_out(event))

    outbox_id = None
    saga_state = "app_committed"
    if request.action in FHIR_OUTBOX_ACTIONS:
        if request.action == "close_as_completed":
            bundle = build_evidence_bundle(
                case_id=case.id,
                patient_id=case.patient_id,
                evidence_type=str(request.data.get("evidence_type") or case.evidence_type),
                evidence_reference=str(
                    request.data.get("evidence_reference") or case.evidence_reference
                ),
                disposition="completed",
            )
        else:
            bundle = {
                "resourceType": "Bundle",
                "type": "transaction",
                "entry": [
                    {
                        "request": {
                            "method": "PUT",
                            "url": f"CarePlan/cp-{case.id}",
                        },
                        "resource": {
                            "resourceType": "CarePlan",
                            "id": f"cp-{case.id}",
                            "status": "active",
                            "intent": "plan",
                            "subject": {"reference": f"Patient/{case.patient_id}"},
                            "meta": {
                                "tag": [
                                    {
                                        "system": "https://namaa.example/fhir",
                                        "code": "synthetic",
                                    }
                                ]
                            },
                        },
                    }
                ],
            }
        outbox = enqueue_outbox(
            db,
            workspace_id=workspace_id,
            request_id=f"case.{case.id}.{request.request_id}"[:64],
            action=request.action,
            bundle=bundle,
            case_id=case.id,
            now=now,
        )
        outbox_id = outbox.id
        saga_state = "fhir_pending"

    db.add(
        Command(
            workspace_id=workspace_id,
            request_id=request.request_id,
            case_id=case.id,
            action=request.action,
            payload_hash=payload_hash,
            response_json=response.model_dump_json(),
            created_at=now,
            saga_state=saga_state,
            outbox_id=outbox_id,
        )
    )
    db.commit()
    db.refresh(case)
    return response
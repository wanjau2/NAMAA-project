"""Authenticated human review — proposals stay outside FHIR until stub commit (I5)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Document, Proposal, ReviewCommandJournal
from app.security.audit import emit_audit
from app.security.context import TrustedRequestContext
from app.security.enforce import authorize
from app.services.outbox import enqueue_outbox
from app.services.proposals import proposal_to_alfred, source_sha256


def _iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _payload_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(body, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def apply_review(
    db: Session,
    ctx: TrustedRequestContext,
    *,
    proposal_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    request_id = str(body.get("request_id") or "")
    if not request_id:
        raise AppError(
            code="validation_failed",
            message="request_id is required.",
            status_code=422,
            field_errors={"request_id": "required"},
            request_id=ctx.request_id,
        )

    existing = (
        db.query(ReviewCommandJournal)
        .filter(
            ReviewCommandJournal.workspace_id == ctx.workspace_id,
            ReviewCommandJournal.request_id == request_id,
        )
        .one_or_none()
    )
    digest = _payload_hash(body)
    if existing is not None:
        if existing.payload_hash != digest:
            raise AppError(
                code="idempotency_conflict",
                message="request_id was reused with a different payload.",
                status_code=409,
                request_id=request_id,
            )
        return json.loads(existing.response_json)

    proposal = (
        db.query(Proposal)
        .filter(Proposal.workspace_id == ctx.workspace_id, Proposal.id == proposal_id)
        .one_or_none()
    )
    if proposal is None:
        raise AppError(code="not_found", message="Proposal not found.", status_code=404)

    authorize(
        db,
        ctx,
        action="review.apply",
        resource_type="Proposal",
        resource_id=proposal_id,
        patient_id=proposal.patient_id,
        extra_context={"initiating_role": ctx.membership_role},
    )

    if body.get("proposal_id") and body["proposal_id"] != proposal_id:
        raise AppError(
            code="validation_failed",
            message="proposal_id mismatch.",
            status_code=422,
            request_id=request_id,
        )

    expected = int(body.get("expected_proposal_version") or 0)
    if expected != proposal.version:
        raise AppError(
            code="stale_revision",
            message=(
                f"Proposal version conflict (expected {expected}, current {proposal.version})."
            ),
            status_code=409,
            request_id=request_id,
        )

    action = body.get("action")
    if action not in {"accept", "correct", "reject"}:
        raise AppError(
            code="validation_failed",
            message="action must be accept, correct, or reject.",
            status_code=422,
            request_id=request_id,
        )

    reason = (body.get("reason") or "").strip()
    if not reason:
        raise AppError(
            code="validation_failed",
            message="A reason is required so the change is auditable.",
            status_code=422,
            field_errors={"reason": "required"},
            request_id=request_id,
        )

    reviewer = body.get("reviewer_reference") or f"Practitioner/{ctx.user_id}"
    if ctx.membership_role != "clinical_reviewer":
        raise AppError(
            code="forbidden",
            message="Only the clinical_reviewer role may apply review.",
            status_code=403,
            request_id=request_id,
        )

    # Source version binding
    doc = (
        db.query(Document)
        .filter(
            Document.workspace_id == ctx.workspace_id,
            Document.id == proposal.document_id,
            Document.version == proposal.document_version,
        )
        .one_or_none()
    )
    if doc is None or source_sha256(doc.text) != proposal.source_sha256:
        raise AppError(
            code="stale_revision",
            message="Source version mismatch; re-extract before review.",
            status_code=409,
            request_id=request_id,
        )

    issues = json.loads(proposal.issues_json or "[]")
    ack = set(body.get("acknowledged_issues") or [])
    review_codes = {i["code"] for i in issues if i.get("severity") == "review"}
    if action != "reject" and not review_codes.issubset(ack):
        raise AppError(
            code="validation_failed",
            message="Review-level issues must be acknowledged.",
            status_code=422,
            field_errors={"acknowledged_issues": "incomplete"},
            request_id=request_id,
        )

    now = _iso()
    outbox_id = None
    if action == "reject":
        proposal.review_state = "rejected"
        proposal.review_reason = reason
        proposal.reviewer_reference = reviewer
        proposal.reviewed_at = now
        proposal.version += 1
        state = "rejected"
        fact = None
    elif action == "accept":
        proposal.review_state = "accepted"
        proposal.review_reason = reason
        proposal.reviewer_reference = reviewer
        proposal.reviewed_at = now
        proposal.version += 1
        state = "accepted"
        fact = proposal_to_alfred(proposal)["fact"]
        outbox_id = _enqueue_review_transaction(db, ctx, proposal, request_id, now)
    else:  # correct
        correction = body.get("correction")
        if not isinstance(correction, dict):
            raise AppError(
                code="validation_failed",
                message="correct requires a complete replacement fact.",
                status_code=422,
                request_id=request_id,
            )
        proposal.concept = str(correction.get("concept") or proposal.concept)
        proposal.value_text = str(correction.get("value_text") or "")
        proposal.subject = str(correction.get("subject") or proposal.subject)
        proposal.assertion = str(correction.get("assertion") or proposal.assertion)
        proposal.effective_date = correction.get("effective_date")
        proposal.excerpt = str(correction.get("excerpt") or proposal.excerpt)
        proposal.proposed_resource_type = str(
            correction.get("proposed_resource_type") or proposal.proposed_resource_type
        )
        proposal.relationship = correction.get("relationship")
        proposal.review_state = "corrected"
        proposal.review_reason = reason
        proposal.reviewer_reference = reviewer
        proposal.reviewed_at = now
        proposal.version += 1
        state = "corrected"
        fact = proposal_to_alfred(proposal)["fact"]
        outbox_id = _enqueue_review_transaction(db, ctx, proposal, request_id, now)

    response = {
        "command": {
            "request_id": request_id,
            "proposal_id": proposal.id,
            "expected_proposal_version": expected,
            "action": action,
            "reviewer_reference": reviewer,
            "reason": reason,
            "acknowledged_issues": list(ack),
        },
        "resulting_proposal_version": proposal.version,
        "state": state,
        "fact": (
            {
                "proposal": proposal_to_alfred(proposal),
                "fact": fact,
                "reviewed_at": now,
                "source_date": doc.document_date[:10],
                "offset_start": proposal.offset_start,
                "offset_end": proposal.offset_end,
            }
            if fact is not None
            else None
        ),
        "fhir_gateway": "stub",
        "outbox_id": outbox_id,
        "notice": (
            "SYNTHETIC DEMO — review journaled in application DB; "
            "FHIR commit uses gateway stub until HAPI is connected (I5)."
        ),
    }

    db.add(
        ReviewCommandJournal(
            workspace_id=ctx.workspace_id,
            request_id=request_id,
            proposal_id=proposal.id,
            action=action,
            payload_hash=digest,
            response_json=json.dumps(response),
            reviewer_reference=reviewer,
            created_at=now,
            outbox_id=outbox_id,
        )
    )
    emit_audit(
        db,
        event_type="review.applied",
        ctx=ctx,
        action="review.apply",
        resource_type="Proposal",
        resource_id=proposal.id,
        patient_id=proposal.patient_id,
        reviewer_id=reviewer,
        reason_code=state,
        source_versions={
            f"DocumentReference/{proposal.document_id}": str(proposal.document_version)
        },
        extra={"review_action": action, "outbox_id": outbox_id},
    )
    db.commit()
    return response


def _enqueue_review_transaction(
    db: Session,
    ctx: TrustedRequestContext,
    proposal: Proposal,
    request_id: str,
    now: str,
) -> str:
    logical = f"rvw-{proposal.id[:12]}"
    resource_type = proposal.proposed_resource_type
    bundle = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "request": {"method": "PUT", "url": f"{resource_type}/{logical}"},
                "resource": {
                    "resourceType": resource_type,
                    "id": logical,
                    "status": "final" if resource_type == "Observation" else "partial",
                    "subject": {"reference": f"Patient/{proposal.patient_id}"},
                    "meta": {
                        "tag": [
                            {"system": "https://namaa.example/fhir", "code": "synthetic"},
                            {"system": "https://namaa.example/fhir", "code": "human_reviewed"},
                        ]
                    },
                    "note": [{"text": proposal.value_text[:500]}],
                },
            }
        ],
    }
    entry = enqueue_outbox(
        db,
        workspace_id=ctx.workspace_id,
        request_id=request_id,
        action=f"review_{proposal.review_state}",
        bundle=bundle,
        case_id=None,
        now=now,
    )
    return entry.id

"""Human review — Alfred apply_review + propose_transaction; stub FHIR, not HAPI."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.ai_runtime import ensure_namaa_ai
from app.errors import AppError
from app.fhir.gateway import apply_transaction_bundle
from app.models import Document, Proposal, ReviewCommandJournal
from app.security.audit import emit_audit
from app.security.context import TrustedRequestContext
from app.security.enforce import authorize
from app.services.outbox import enqueue_outbox
from app.services.proposals import proposal_to_alfred, source_sha256

ensure_namaa_ai()

from namaa_ai.contracts import ExtractionProposal, ExtractionRequest, ReviewCommand  # noqa: E402
from namaa_ai.fhir import propose_transaction  # noqa: E402
from namaa_ai.review import ReviewError, apply_review as alfred_apply_review  # noqa: E402

SYNTHETIC_REVIEWER = "Practitioner/demo-reviewer"
_REVIEW_ERRORS = {
    "stale_proposal_version": ("stale_revision", 409),
    "source_version_mismatch": ("stale_revision", 409),
    "source_validation_blocked": ("validation_failed", 422),
    "review_issues_not_acknowledged": ("validation_failed", 422),
}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _payload_hash(*, proposal_id: str, body: dict[str, Any]) -> str:
    material = {
        "proposal_id": proposal_id,
        "action": body.get("action"),
        "expected_proposal_version": body.get("expected_proposal_version"),
        "reason": body.get("reason"),
        "correction": body.get("correction"),
        "acknowledged_issues": body.get("acknowledged_issues") or [],
        "reviewer_reference": body.get("reviewer_reference"),
    }
    return hashlib.sha256(
        json.dumps(material, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def review_outbox_request_id(request_id: str) -> str:
    """64-char FHIR/outbox key that stays unique for distinct review request_ids.

    Prefixing then truncating (`review.{id}`[:64]) collapsed any two 64-char ids
    that shared the first 57 characters onto one transaction, so the second
    accept replayed the first stub write.
    """
    digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()[:57]
    return f"review.{digest}"


def _bound_reviewer(ctx: TrustedRequestContext, supplied: str | None) -> str:
    if ctx.membership_role != "clinical_reviewer":
        raise AppError(
            code="forbidden",
            message="Only the clinical_reviewer role may apply review.",
            status_code=403,
            request_id=ctx.request_id,
        )
    bound = SYNTHETIC_REVIEWER
    if supplied and supplied != bound:
        raise AppError(
            code="forbidden",
            message="reviewer_reference does not match the trusted reviewer binding.",
            status_code=403,
            field_errors={"reviewer_reference": "mismatch"},
            request_id=ctx.request_id,
        )
    return bound


def _field_errors(exc: ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ()) if part != "body")
        errors[loc or "body"] = err.get("msg", "invalid")
    return errors


def _extraction_request(doc: Document, proposal: Proposal, request_id: str) -> ExtractionRequest:
    return ExtractionRequest(
        request_id=request_id[:64],
        workspace_id=proposal.workspace_id,
        patient_reference=f"Patient/{proposal.patient_id}",
        source_id=doc.id,
        source_version=str(doc.version),
        source_date=doc.document_date[:10],
        note_text=doc.text,
    )


class _PermitBoundReviewer:
    def __init__(self, reviewer: str) -> None:
        self.reviewer = reviewer

    def require_review(self, command: ReviewCommand, proposal: ExtractionProposal) -> None:
        if command.reviewer_reference != self.reviewer:
            raise PermissionError("reviewer_reference does not match the trusted reviewer binding")
        if command.proposal_id != proposal.id:
            raise PermissionError("proposal_id mismatch")


def _replay_if_present(
    db: Session,
    ctx: TrustedRequestContext,
    *,
    request_id: str,
    digest: str,
    proposal_id: str,
    supplied_reviewer: str | None,
) -> dict[str, Any] | None:
    existing = (
        db.query(ReviewCommandJournal)
        .filter(
            ReviewCommandJournal.workspace_id == ctx.workspace_id,
            ReviewCommandJournal.request_id == request_id,
        )
        .one_or_none()
    )
    if existing is None:
        return None
    if existing.payload_hash != digest or existing.proposal_id != proposal_id:
        raise AppError(
            code="idempotency_conflict",
            message="request_id was reused with a different payload or target.",
            status_code=409,
            request_id=request_id,
        )
    proposal = (
        db.query(Proposal)
        .filter(
            Proposal.workspace_id == ctx.workspace_id,
            Proposal.id == existing.proposal_id,
        )
        .one_or_none()
    )
    if proposal is None:
        raise AppError(code="not_found", message="Proposal not found.", status_code=404)
    _bound_reviewer(ctx, supplied_reviewer)
    authorize(
        db,
        ctx,
        action="review.apply",
        resource_type="Proposal",
        resource_id=existing.proposal_id,
        patient_id=proposal.patient_id,
        extra_context={"initiating_role": ctx.membership_role},
    )
    db.commit()
    return json.loads(existing.response_json)


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
    if body.get("proposal_id") and body["proposal_id"] != proposal_id:
        raise AppError(
            code="validation_failed",
            message="proposal_id mismatch.",
            status_code=422,
            request_id=request_id,
        )

    digest = _payload_hash(proposal_id=proposal_id, body=body)
    replayed = _replay_if_present(
        db,
        ctx,
        request_id=request_id,
        digest=digest,
        proposal_id=proposal_id,
        supplied_reviewer=body.get("reviewer_reference"),
    )
    if replayed is not None:
        return replayed

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

    reviewer = _bound_reviewer(ctx, body.get("reviewer_reference"))
    expected = int(body.get("expected_proposal_version") or 0)
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

    try:
        request = _extraction_request(doc, proposal, request_id)
        original = ExtractionProposal.model_validate(
            proposal_to_alfred(proposal, version=proposal.version)
        )
        command = ReviewCommand.model_validate(
            {
                "request_id": request_id,
                "proposal_id": proposal.id,
                "expected_proposal_version": expected,
                "action": body.get("action"),
                "reviewer_reference": reviewer,
                "reason": body.get("reason") or "",
                "correction": body.get("correction"),
                "acknowledged_issues": list(body.get("acknowledged_issues") or []),
            }
        )
        now = datetime.now(timezone.utc)
        decision = alfred_apply_review(
            request,
            original,
            command,
            current_version=proposal.version,
            reviewed_at=now,
            authorizer=_PermitBoundReviewer(reviewer),
        )
    except ValidationError as exc:
        raise AppError(
            code="validation_failed",
            message="Review command failed contract validation.",
            status_code=422,
            field_errors=_field_errors(exc),
            request_id=request_id,
        ) from exc
    except ReviewError as exc:
        code, status = _REVIEW_ERRORS.get(str(exc), ("validation_failed", 422))
        raise AppError(
            code=code,
            message=str(exc),
            status_code=status,
            request_id=request_id,
        ) from exc
    except PermissionError as exc:
        raise AppError(
            code="forbidden",
            message=str(exc),
            status_code=403,
            request_id=request_id,
        ) from exc

    now_s = _iso(now)
    updates: dict[str, Any] = {
        "review_state": decision.state,
        "review_reason": command.reason,
        "reviewer_reference": reviewer,
        "reviewed_at": now_s,
        "version": decision.resulting_proposal_version,
    }
    if decision.fact is not None:
        fact = decision.fact.fact
        updates.update(
            concept=fact.concept,
            value_text=fact.value_text,
            subject=fact.subject,
            assertion=fact.assertion,
            effective_date=None if fact.effective_date is None else fact.effective_date.isoformat(),
            excerpt=fact.excerpt,
            proposed_resource_type=fact.proposed_resource_type,
            relationship=fact.relationship,
            offset_start=decision.fact.offset_start,
            offset_end=decision.fact.offset_end,
        )

    claimed = (
        db.query(Proposal)
        .filter(
            Proposal.workspace_id == ctx.workspace_id,
            Proposal.id == proposal.id,
            Proposal.version == expected,
            Proposal.review_state == "proposed",
        )
        .update(updates, synchronize_session="fetch")
    )
    if claimed != 1:
        replayed = _replay_if_present(
            db,
            ctx,
            request_id=request_id,
            digest=digest,
            proposal_id=proposal_id,
            supplied_reviewer=body.get("reviewer_reference"),
        )
        if replayed is not None:
            return replayed
        raise AppError(
            code="stale_revision",
            message=(
                f"Proposal version conflict (expected {expected}, current {proposal.version})."
            ),
            status_code=409,
            request_id=request_id,
        )
    db.refresh(proposal)

    outbox_id = None
    if decision.fact is not None:
        transaction = propose_transaction(decision.fact)
        outbox_request_id = review_outbox_request_id(request_id)
        entry = enqueue_outbox(
            db,
            workspace_id=ctx.workspace_id,
            request_id=outbox_request_id,
            action=f"review_{decision.state}",
            bundle=transaction.bundle,
            case_id=None,
            now=now_s,
        )
        applied = apply_transaction_bundle(
            db,
            workspace_id=ctx.workspace_id,
            request_id=outbox_request_id,
            bundle=transaction.bundle,
            now=now_s,
        )
        entry.state = "committed"
        entry.result_json = json.dumps(
            {"status": applied.status, "resource_refs": applied.resource_refs}
        )
        outbox_id = entry.id

    response = decision.model_dump(mode="json")
    response.update(
        {
            "fhir_gateway": "stub",
            "outbox_id": outbox_id,
            "notice": (
                "SYNTHETIC DEMO — review journaled in application DB; "
                "FHIR commit uses gateway stub until HAPI is connected (I5)."
            ),
        }
    )

    db.add(
        ReviewCommandJournal(
            workspace_id=ctx.workspace_id,
            request_id=request_id,
            proposal_id=proposal.id,
            action=command.action,
            payload_hash=digest,
            response_json=json.dumps(response),
            reviewer_reference=reviewer,
            created_at=now_s,
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
        reason_code=decision.state,
        source_versions={
            f"DocumentReference/{proposal.document_id}": str(proposal.document_version)
        },
        extra={"review_action": command.action, "outbox_id": outbox_id},
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        replayed = _replay_if_present(
            db,
            ctx,
            request_id=request_id,
            digest=digest,
            proposal_id=proposal_id,
            supplied_reviewer=body.get("reviewer_reference"),
        )
        if replayed is not None:
            return replayed
        raise AppError(
            code="idempotency_conflict",
            message="request_id collided with another command.",
            status_code=409,
            request_id=request_id,
        ) from None
    return response

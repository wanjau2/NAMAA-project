from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import Proposal
from app.security.context import TrustedRequestContext
from app.security.deps import get_trusted_context
from app.security.enforce import authorize
from app.services.proposals import proposal_to_alfred
from app.services.review import apply_review

router = APIRouter(prefix="/api/v1/facts", tags=["facts"])


class ReviewBody(BaseModel):
    request_id: str
    proposal_id: str | None = None
    expected_proposal_version: int
    action: str
    reviewer_reference: str | None = None
    reason: str
    correction: dict[str, Any] | None = None
    acknowledged_issues: list[str] = Field(default_factory=list)


@router.get("/{proposal_id}")
def get_proposal(
    proposal_id: str,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
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
        action="proposal.disclose",
        resource_type="Proposal",
        resource_id=proposal_id,
        patient_id=proposal.patient_id,
    )
    db.commit()
    payload = proposal_to_alfred(proposal)
    payload["review_state"] = proposal.review_state
    payload["reviewer_reference"] = proposal.reviewer_reference
    payload["review_reason"] = proposal.review_reason
    payload["reviewed_at"] = proposal.reviewed_at
    payload["notice"] = (
        "SYNTHETIC DEMO — proposal is journaled in the application store; "
        "review commit uses the FHIR gateway stub until HAPI is connected."
    )
    return payload


@router.post("/{proposal_id}/review")
def review_proposal(
    proposal_id: str,
    body: ReviewBody,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """I5 — authenticated human review; journals command; stub FHIR outbox on accept/correct."""
    return apply_review(db, ctx, proposal_id=proposal_id, body=body.model_dump())

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import AuditEvent
from app.security.audit import emit_audit
from app.security.context import TrustedRequestContext
from app.security.deps import get_trusted_context
from app.security.pdp import evaluate_access
from app.models import PrincipalRevocation
from app.security.verified_context import build_verified_context
from app.services.relate_index import care_plan_candidates, family_history_candidates
from datetime import datetime, timezone

router = APIRouter(prefix="/api/v1", tags=["security"])


class AuthZenSubject(BaseModel):
    type: str = "user"
    id: str | None = None


class AuthZenResource(BaseModel):
    type: str
    id: str
    workspace_id: str | None = None
    patient_id: str | None = None


class AuthZenAction(BaseModel):
    name: str


class AuthZenEvaluationRequest(BaseModel):
    subject: AuthZenSubject | None = None
    resource: AuthZenResource
    action: AuthZenAction
    context: dict[str, Any] = Field(default_factory=dict)


class AuthZenBatchRequest(BaseModel):
    evaluations: list[AuthZenEvaluationRequest]


class AuditEventIn(BaseModel):
    event_type: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    patient_id: str | None = None
    job_id: str | None = None
    decision: str | None = None
    decision_id: str | None = None
    source_versions: dict[str, str] = Field(default_factory=dict)
    model_revision: str | None = None
    prompt_version: str | None = None
    reviewer_id: str | None = None
    reason_code: str | None = None
    # Safe metadata only — note_text / token / prompt keys are stripped server-side
    detail: dict[str, Any] = Field(default_factory=dict)


class VerifiedContextRequest(BaseModel):
    patient_id: str
    generation_id: str | None = None
    relate_hints: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/security/context")
def security_context(
    ctx: TrustedRequestContext = Depends(get_trusted_context),
) -> dict[str, Any]:
    """Trusted request context — minted by the API, never from the body."""
    return ctx.to_public_dict()


@router.post("/authz/evaluation")
def authz_evaluation(
    body: AuthZenEvaluationRequest,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """AuthZEN 1.0 access-evaluation endpoint (synthetic guest PDP)."""
    decision = evaluate_access(
        ctx,
        subject=body.subject.model_dump() if body.subject else None,
        resource=body.resource.model_dump(),
        action=body.action.model_dump(),
        context=body.context,
    )
    emit_audit(
        db,
        event_type="access.evaluation",
        ctx=ctx,
        action=body.action.name,
        decision=decision,
        resource_type=body.resource.type,
        resource_id=body.resource.id,
        patient_id=body.resource.patient_id or body.context.get("patient_id"),
    )
    db.commit()
    return decision.to_authzen()


@router.post("/authz/evaluations")
def authz_evaluations_batch(
    body: AuthZenBatchRequest,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    results = []
    for item in body.evaluations:
        decision = evaluate_access(
            ctx,
            subject=item.subject.model_dump() if item.subject else None,
            resource=item.resource.model_dump(),
            action=item.action.model_dump(),
            context=item.context,
        )
        emit_audit(
            db,
            event_type="access.evaluation",
            ctx=ctx,
            action=item.action.name,
            decision=decision,
            resource_type=item.resource.type,
            resource_id=item.resource.id,
            patient_id=item.resource.patient_id,
        )
        results.append(decision.to_authzen())
    db.commit()
    return {"evaluations": results}


@router.post("/audit/events", status_code=201)
def post_audit_event(
    body: AuditEventIn,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Protected audit sink. Service or session auth. No note/prompt/token storage."""
    if ctx.membership_role not in {
        "service",
        "clinical_reviewer",
        "coordinator",
        "population_analyst",
    }:
        raise AppError(code="forbidden", message="Not permitted to write audit events.", status_code=403)

    # Reject obvious forbidden keys even before sanitize
    forbidden = {"note_text", "token", "prompt", "full_prompt", "authorization"}
    if forbidden.intersection(body.detail):
        raise AppError(
            code="validation_failed",
            message="Audit detail must not include note text, tokens, or prompts.",
            status_code=422,
            field_errors={"detail": "forbidden_keys"},
            request_id=ctx.request_id,
        )

    event = emit_audit(
        db,
        event_type=body.event_type,
        ctx=ctx,
        action=body.action,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        patient_id=body.patient_id,
        job_id=body.job_id,
        source_versions=body.source_versions,
        model_revision=body.model_revision,
        prompt_version=body.prompt_version,
        reviewer_id=body.reviewer_id,
        reason_code=body.reason_code or body.decision,
        extra={
            **body.detail,
            "client_decision": body.decision,
            "client_decision_id": body.decision_id,
        },
    )
    db.commit()
    return {
        "id": event.id,
        "timestamp": event.timestamp,
        "policy_adapter": event.policy_adapter,
        "production_authorization": event.production_authorization,
    }


@router.get("/audit/events")
def list_audit_events(
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> list[dict[str, Any]]:
    rows = (
        db.query(AuditEvent)
        .filter(AuditEvent.workspace_id == ctx.workspace_id)
        .order_by(AuditEvent.pk.desc())
        .limit(min(limit, 200))
        .all()
    )
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp,
            "event_type": r.event_type,
            "request_id": r.request_id,
            "job_id": r.job_id,
            "user_id": r.user_id,
            "service_id": r.service_id,
            "action": r.action,
            "purpose_of_use": r.purpose_of_use,
            "resource_type": r.resource_type,
            "resource_id": r.resource_id,
            "patient_id": r.patient_id,
            "decision": r.decision,
            "decision_id": r.decision_id,
            "policy_revision": r.policy_revision,
            "permission_revision": r.permission_revision,
            "policy_adapter": r.policy_adapter,
            "production_authorization": r.production_authorization,
            "reason_code": r.reason_code,
            "model_revision": r.model_revision,
            "prompt_version": r.prompt_version,
            "reviewer_id": r.reviewer_id,
        }
        for r in rows
    ]


@router.post("/security/verified-context")
def verified_context(
    body: VerifiedContextRequest,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Current patient scope + source versions. Relate hints never grant access."""
    result = build_verified_context(
        db,
        ctx,
        patient_id=body.patient_id,
        generation_id=body.generation_id,
        relate_hints=body.relate_hints,
    )
    db.commit()
    return result


@router.get("/relate/family-history")
def relate_family_history(
    patient_id: str,
    limit: int = 20,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """I7 — fixed Relate operation; does not authorize access."""
    if patient_id not in ctx.patient_ids:
        raise AppError(
            code="forbidden",
            message="Patient outside trusted assignment.",
            status_code=403,
        )
    return family_history_candidates(
        db, workspace_id=ctx.workspace_id, patient_id=patient_id, limit=limit
    )


@router.get("/relate/care-plans")
def relate_care_plans(
    patient_id: str,
    limit: int = 20,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if patient_id not in ctx.patient_ids:
        raise AppError(
            code="forbidden",
            message="Patient outside trusted assignment.",
            status_code=403,
        )
    return care_plan_candidates(
        db, workspace_id=ctx.workspace_id, patient_id=patient_id, limit=limit
    )


class RevokeBody(BaseModel):
    principal_id: str
    reason_code: str = "revoked"


@router.post("/security/revocations", status_code=201)
def revoke_principal(
    body: RevokeBody,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Synthetic revocation — blocks future job claim/disclosure for the principal."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing = (
        db.query(PrincipalRevocation)
        .filter(
            PrincipalRevocation.workspace_id == ctx.workspace_id,
            PrincipalRevocation.principal_id == body.principal_id,
        )
        .one_or_none()
    )
    if existing:
        existing.active = True
        existing.reason_code = body.reason_code
        existing.revoked_at = now
    else:
        db.add(
            PrincipalRevocation(
                workspace_id=ctx.workspace_id,
                principal_id=body.principal_id,
                reason_code=body.reason_code,
                revoked_at=now,
                active=True,
            )
        )
    emit_audit(
        db,
        event_type="principal.revoked",
        ctx=ctx,
        action="audit.write",
        resource_type="Principal",
        resource_id=body.principal_id,
        reason_code=body.reason_code,
    )
    db.commit()
    return {"principal_id": body.principal_id, "active": True, "revoked_at": now}

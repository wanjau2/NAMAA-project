from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.errors import AppError
from app.security.audit import emit_audit
from app.security.context import TrustedRequestContext
from app.security.pdp import AccessDecision, evaluate_access


class AuthorizationDenied(AppError):
    def __init__(self, decision: AccessDecision, *, request_id: str | None = None) -> None:
        super().__init__(
            code="forbidden",
            message=f"Access denied ({decision.reason_code}).",
            status_code=403,
            request_id=request_id or decision.context.get("request_id"),
            field_errors={"reason_code": decision.reason_code},
        )
        self.decision = decision


def authorize(
    db: Session,
    ctx: TrustedRequestContext,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    patient_id: str | None = None,
    extra_context: dict[str, Any] | None = None,
    audit: bool = True,
) -> AccessDecision:
    """Fresh PDP check. Missing/indeterminate/false → deny + optional audit."""
    decision = evaluate_access(
        ctx,
        subject={"type": "user", "id": ctx.user_id},
        resource={
            "type": resource_type,
            "id": resource_id,
            "workspace_id": ctx.workspace_id,
            "patient_id": patient_id,
        },
        action={"name": action},
        context={
            "purpose_of_use": ctx.purpose_of_use,
            "model_destination": ctx.approved_model_destination,
            "request_id": ctx.request_id,
            **(extra_context or {}),
        },
    )
    if audit:
        emit_audit(
            db,
            event_type="access.evaluation",
            ctx=ctx,
            action=action,
            decision=decision,
            resource_type=resource_type,
            resource_id=resource_id,
            patient_id=patient_id,
        )
    if not decision.decision or decision.decision_value != "Permit":
        if audit:
            # Persist the deny independently of the failed clinical transaction (I11).
            db.commit()
        raise AuthorizationDenied(decision, request_id=ctx.request_id)
    return decision


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex[:16]}"

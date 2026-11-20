from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent
from app.security.context import TrustedRequestContext
from app.security.pdp import AccessDecision


FORBIDDEN_PAYLOAD_KEYS = {
    "note_text",
    "note",
    "prompt",
    "full_prompt",
    "token",
    "access_token",
    "authorization",
    "raw_model_output",
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _sanitize(extra: Any) -> Any:
    if extra is None:
        return {}
    if isinstance(extra, dict):
        clean: dict[str, Any] = {}
        for key, value in extra.items():
            if str(key).lower() in FORBIDDEN_PAYLOAD_KEYS:
                continue
            clean[str(key)] = _sanitize(value)
        return clean
    if isinstance(extra, list):
        return [_sanitize(item) for item in extra]
    if isinstance(extra, str) and len(extra) > 512:
        return extra[:512] + "…"
    return extra


def emit_audit(
    db: Session,
    *,
    event_type: str,
    ctx: TrustedRequestContext,
    action: str,
    decision: AccessDecision | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    patient_id: str | None = None,
    job_id: str | None = None,
    source_versions: dict[str, str] | None = None,
    model_revision: str | None = None,
    prompt_version: str | None = None,
    reviewer_id: str | None = None,
    reason_code: str | None = None,
    extra: dict[str, Any] | None = None,
) -> AuditEvent:
    """Protected audit write — never stores note text, tokens, or full prompts."""
    event = AuditEvent(
        id=f"aud-{uuid.uuid4().hex[:16]}",
        workspace_id=ctx.workspace_id,
        timestamp=_utcnow(),
        event_type=event_type,
        request_id=ctx.request_id,
        job_id=job_id,
        user_id=ctx.user_id,
        service_id=ctx.service_id,
        action=action,
        purpose_of_use=ctx.purpose_of_use,
        resource_type=resource_type,
        resource_id=resource_id,
        patient_id=patient_id,
        decision=None if decision is None else ("Permit" if decision.decision else "Deny"),
        decision_id=None if decision is None else decision.decision_id,
        policy_revision=ctx.policy_revision,
        permission_revision=ctx.permission_revision,
        policy_adapter=ctx.policy_adapter,
        production_authorization=ctx.production_authorization,
        source_versions_json=json.dumps(source_versions or {}),
        model_revision=model_revision,
        prompt_version=prompt_version,
        reviewer_id=reviewer_id,
        reason_code=reason_code or (decision.reason_code if decision else None),
        safe_detail_json=json.dumps(_sanitize(extra) if extra is not None else {}),
    )
    db.add(event)
    db.flush()
    return event

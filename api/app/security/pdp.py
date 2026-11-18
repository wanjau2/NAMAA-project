"""AuthZEN 1.0-shaped access evaluation (synthetic guest PDP)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from app.security.constants import ACTIONS, POLICY_ADAPTER, POLICY_REVISION, PRODUCTION_AUTHORIZATION
from app.security.context import TrustedRequestContext


DecisionValue = Literal["Permit", "Deny", "Indeterminate"]


@dataclass(frozen=True)
class AccessDecision:
    decision: bool
    decision_value: DecisionValue
    decision_id: str
    policy_revision: str
    permission_revision: str
    policy_adapter: str
    production_authorization: bool
    reason_code: str
    context: dict[str, Any]

    def to_authzen(self) -> dict[str, Any]:
        """OpenID AuthZEN access evaluation response shape."""
        return {
            "decision": self.decision,
            "context": {
                "decision_id": self.decision_id,
                "decision_value": self.decision_value,
                "policy_revision": self.policy_revision,
                "permission_revision": self.permission_revision,
                "policy_adapter": self.policy_adapter,
                "production_authorization": self.production_authorization,
                "reason_code": self.reason_code,
                **self.context,
            },
        }


def _deny(
    *,
    reason_code: str,
    ctx: TrustedRequestContext,
    extra: dict[str, Any] | None = None,
) -> AccessDecision:
    return AccessDecision(
        decision=False,
        decision_value="Deny",
        decision_id=f"dec-{uuid.uuid4().hex[:16]}",
        policy_revision=POLICY_REVISION,
        permission_revision=ctx.permission_revision,
        policy_adapter=POLICY_ADAPTER,
        production_authorization=PRODUCTION_AUTHORIZATION,
        reason_code=reason_code,
        context=extra or {},
    )


def _permit(
    *,
    reason_code: str,
    ctx: TrustedRequestContext,
    extra: dict[str, Any] | None = None,
) -> AccessDecision:
    return AccessDecision(
        decision=True,
        decision_value="Permit",
        decision_id=f"dec-{uuid.uuid4().hex[:16]}",
        policy_revision=POLICY_REVISION,
        permission_revision=ctx.permission_revision,
        policy_adapter=POLICY_ADAPTER,
        production_authorization=PRODUCTION_AUTHORIZATION,
        reason_code=reason_code,
        context=extra or {},
    )


def evaluate_access(
    ctx: TrustedRequestContext,
    *,
    subject: dict[str, Any] | None,
    resource: dict[str, Any],
    action: dict[str, Any],
    context: dict[str, Any] | None = None,
) -> AccessDecision:
    """Default-deny AuthZEN evaluation against trusted context only.

    `subject` / body context cannot elevate privileges. Subject id must match
    the trusted principal when provided.
    """
    action_name = (action or {}).get("name") or (action or {}).get("id")
    if not action_name or action_name not in ACTIONS:
        return _deny(reason_code="unknown_or_missing_action", ctx=ctx)

    if not ctx.membership_active:
        return _deny(reason_code="inactive_membership", ctx=ctx)

    if subject:
        sid = subject.get("id")
        if sid and sid != ctx.user_id:
            return _deny(reason_code="subject_principal_mismatch", ctx=ctx)

    resource_type = (resource or {}).get("type") or (resource or {}).get("resource_type")
    resource_id = (resource or {}).get("id")
    patient_id = (resource or {}).get("patient_id") or (context or {}).get("patient_id")

    # Workspace isolation
    res_workspace = (resource or {}).get("workspace_id") or (context or {}).get("workspace_id")
    if res_workspace and res_workspace != ctx.workspace_id:
        return _deny(reason_code="workspace_mismatch", ctx=ctx)

    if patient_id and patient_id not in ctx.patient_ids:
        return _deny(reason_code="patient_not_in_assignment", ctx=ctx)

    # Role matrix (synthetic demo)
    role = ctx.membership_role
    if action_name in {"review.apply"} and role not in {"clinical_reviewer", "service"}:
        # Service may re-check on behalf of preserved initiating reviewer only when
        # context carries initiating_role — still require clinical_reviewer initiator.
        initiating = (context or {}).get("initiating_role")
        if role == "service" and initiating == "clinical_reviewer":
            pass
        else:
            return _deny(reason_code="role_forbidden", ctx=ctx)

    if action_name == "model.dispatch":
        dest = (context or {}).get("model_destination") or ctx.approved_model_destination
        if dest != ctx.approved_model_destination:
            return _deny(reason_code="model_destination_not_approved", ctx=ctx)

    if action_name in {"excerpt.export"} and ctx.resource_sensitivity != "synthetic_demo":
        return _deny(reason_code="export_sensitivity_blocked", ctx=ctx)

    if action_name == "audit.write" and role not in {
        "service",
        "clinical_reviewer",
        "coordinator",
        "population_analyst",
    }:
        return _deny(reason_code="audit_writer_forbidden", ctx=ctx)

    # Caregiver authority: child notes may require verified_caregiver for disclose
    if (
        action_name in {"note.retrieve", "proposal.disclose", "excerpt.display"}
        and patient_id
        and patient_id.startswith("pat-synthetic-1")  # child band in seed
    ):
        auth = ctx.caregiver_authority.get(patient_id, "unknown")
        if auth not in {"verified_caregiver", "self"} and role != "clinical_reviewer":
            return _deny(reason_code="caregiver_authority_unverified", ctx=ctx)

    return _permit(
        reason_code="synthetic_policy_permit",
        ctx=ctx,
        extra={
            "action": action_name,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "patient_id": patient_id,
            "purpose_of_use": ctx.purpose_of_use,
        },
    )

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Case, Workspace
from app.security.constants import (
    APPROVED_MODEL_DESTINATIONS,
    PERMISSION_REVISION,
    POLICY_ADAPTER,
    POLICY_REVISION,
    PRODUCTION_AUTHORIZATION,
    PURPOSE_OF_USE,
    SERVICE_NAME,
)


Role = Literal["coordinator", "clinical_reviewer", "population_analyst", "service"]


@dataclass(frozen=True)
class TrustedRequestContext:
    """Backend-minted authority. Never accept these fields from a client body."""

    request_id: str
    user_id: str
    user_type: Literal["guest", "team", "service"]
    service_id: str
    workspace_id: str
    membership_role: Role
    membership_active: bool
    patient_ids: tuple[str, ...]
    care_relationships: tuple[dict[str, str], ...]
    caregiver_authority: dict[str, str]  # patient_id -> status
    purpose_of_use: str
    resource_sensitivity: str
    restrictions: tuple[str, ...]
    approved_model_destination: str
    policy_adapter: str
    policy_revision: str
    permission_revision: str
    production_authorization: bool
    decision_binding: str  # opaque binding for audit correlation

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["notice"] = (
            "SYNTHETIC DEMO AUTHORIZATION — NOT PRODUCTION. "
            "Values are minted by the API; do not accept client copies as authority."
        )
        return data


def _purpose_for_role(role: str) -> str:
    if role == "clinical_reviewer":
        return "demo_clinical_review"
    if role == "population_analyst":
        return "demo_population_analytics"
    if role == "service":
        return "demo_model_extraction"
    return "demo_care_coordination"


def build_trusted_context(
    db: Session,
    *,
    workspace: Workspace,
    role: str,
    request_id: str,
    user_id: str | None = None,
    user_type: Literal["guest", "team", "service"] = "guest",
    purpose_of_use: str | None = None,
    patient_id: str | None = None,
) -> TrustedRequestContext:
    settings = get_settings()
    membership_role: Role = role if role in {
        "coordinator",
        "clinical_reviewer",
        "population_analyst",
        "service",
    } else "coordinator"

    cases = db.query(Case).filter(Case.workspace_id == workspace.id).all()
    patient_ids = tuple(sorted({c.patient_id for c in cases}))
    if patient_id and patient_id not in patient_ids:
        # Explicit request for a patient outside workspace seed → empty assignment.
        # PDP will deny patient-scoped actions.
        assigned = ()
    else:
        assigned = (patient_id,) if patient_id else patient_ids

    relationships = tuple(
        {
            "patient_id": c.patient_id,
            "case_id": c.id,
            "relationship": "case_owner" if c.owner else "workspace_member",
            "owner": c.owner,
        }
        for c in cases
        if not patient_id or c.patient_id == patient_id
    )

    # Caregiver authority from patient seed (string status only).
    from app.models import Patient

    caregiver: dict[str, str] = {}
    for p in (
        db.query(Patient)
        .filter(Patient.workspace_id == workspace.id)
        .all()
    ):
        caregiver[p.id] = p.caregiver_authority

    purpose = purpose_of_use or _purpose_for_role(membership_role)
    if purpose not in PURPOSE_OF_USE:
        purpose = "demo_care_coordination"

    model_dest = (
        "offline_fixture"
        if settings.extraction_mode == "offline_fixture"
        else "medgemma_hf_endpoint"
    )
    if model_dest not in APPROVED_MODEL_DESTINATIONS:
        model_dest = "offline_fixture"

    principal = user_id or (
        f"service:{SERVICE_NAME}" if user_type == "service" else f"guest:{workspace.id}"
    )

    return TrustedRequestContext(
        request_id=request_id,
        user_id=principal,
        user_type=user_type,
        service_id=SERVICE_NAME,
        workspace_id=workspace.id,
        membership_role=membership_role,
        membership_active=True,
        patient_ids=assigned if assigned else patient_ids,
        care_relationships=relationships,
        caregiver_authority=caregiver,
        purpose_of_use=purpose,
        resource_sensitivity="synthetic_demo",
        restrictions=(
            "no_real_phi",
            "synthetic_only",
            "guest_session_isolated",
            "not_production_authorization",
        ),
        approved_model_destination=model_dest,
        policy_adapter=POLICY_ADAPTER,
        policy_revision=POLICY_REVISION,
        permission_revision=PERMISSION_REVISION,
        production_authorization=PRODUCTION_AUTHORIZATION,
        decision_binding=f"bind:{workspace.id}:{request_id}",
    )

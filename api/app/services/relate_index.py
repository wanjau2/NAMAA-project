"""Fixed, parameterized Relate candidate lookups (disposable discovery index)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import FhirResource, Observation


def family_history_candidates(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    limit: int = 20,
) -> dict[str, Any]:
    refs: list[dict[str, Any]] = []
    for row in (
        db.query(FhirResource)
        .filter(
            FhirResource.workspace_id == workspace_id,
            FhirResource.resource_type == "FamilyMemberHistory",
        )
        .limit(limit)
        .all()
    ):
        if f"Patient/{patient_id}" not in row.body_json:
            continue
        refs.append(
            {
                "candidate_id": f"rel-fmh-{row.logical_id}",
                "patient_reference": f"Patient/{patient_id}",
                "supporting_references": [f"FamilyMemberHistory/{row.logical_id}"],
                "label": "family_history",
            }
        )
    # Seed observations tagged as family-related text are not FMH resources —
    # still expose Observation refs only when type hints family (none in seed).
    return {
        "state": "current",
        "workspace_id": workspace_id,
        "patient_reference": f"Patient/{patient_id}",
        "permission_revision": "permissions-v1",
        "generation_id": f"rel-gen-{patient_id}",
        "operation": "family_history_candidates",
        "candidates": refs[:limit],
        "notice": (
            "Relate is a disposable discovery index. Candidates never grant access; "
            "call POST /api/v1/security/verified-context to authorize and verify."
        ),
    }


def care_plan_candidates(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    limit: int = 20,
) -> dict[str, Any]:
    refs: list[dict[str, Any]] = []
    for row in (
        db.query(FhirResource)
        .filter(
            FhirResource.workspace_id == workspace_id,
            FhirResource.resource_type == "CarePlan",
        )
        .limit(limit)
        .all()
    ):
        if f"Patient/{patient_id}" not in row.body_json:
            continue
        refs.append(
            {
                "candidate_id": f"rel-cp-{row.logical_id}",
                "patient_reference": f"Patient/{patient_id}",
                "supporting_references": [f"CarePlan/{row.logical_id}"],
                "label": "care_plan",
            }
        )
    # Application observations in scope (discovery only)
    for obs in (
        db.query(Observation)
        .filter(
            Observation.workspace_id == workspace_id,
            Observation.patient_id == patient_id,
            Observation.verified.is_(True),
        )
        .limit(limit)
        .all()
    ):
        refs.append(
            {
                "candidate_id": f"rel-obs-{obs.id}",
                "patient_reference": f"Patient/{patient_id}",
                "supporting_references": [f"Observation/{obs.id}"],
                "label": "observation_seed",
            }
        )
    return {
        "state": "current",
        "workspace_id": workspace_id,
        "patient_reference": f"Patient/{patient_id}",
        "permission_revision": "permissions-v1",
        "generation_id": f"rel-gen-{patient_id}",
        "operation": "care_plan_candidates",
        "candidates": refs[:limit],
        "notice": (
            "Relate is a disposable discovery index. Candidates never grant access; "
            "call POST /api/v1/security/verified-context to authorize and verify."
        ),
    }

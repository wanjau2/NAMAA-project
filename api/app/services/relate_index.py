"""Fixed, parameterized Relate candidate lookups (disposable discovery index)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import FhirResource
from app.services.rule_snapshots import _compensated_or_revoked


def _patient_linked(row: FhirResource, patient_id: str) -> bool:
    try:
        body = json.loads(row.body_json)
    except (TypeError, ValueError):
        return False
    if not isinstance(body, dict):
        return False
    link_field = "patient" if row.resource_type == "FamilyMemberHistory" else "subject"
    link = body.get(link_field)
    if not (isinstance(link, dict) and link.get("reference") == f"Patient/{patient_id}"):
        return False
    return not _compensated_or_revoked(body)


def _batch(
    *,
    workspace_id: str,
    patient_id: str,
    candidates: list[dict[str, Any]],
    permission_revision: str = "permissions-v1",
    generation_id: str | None = None,
) -> dict[str, Any]:
    return {
        "state": "current",
        "workspace_id": workspace_id,
        "patient_reference": f"Patient/{patient_id}",
        "permission_revision": permission_revision,
        "generation_id": generation_id or f"rel-gen-{patient_id}",
        "candidates": candidates,
    }


def family_history_candidates(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    limit: int = 20,
    permission_revision: str = "permissions-v1",
    generation_id: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))
    refs: list[dict[str, Any]] = []
    rows = (
        db.query(FhirResource)
        .filter(
            FhirResource.workspace_id == workspace_id,
            FhirResource.resource_type == "FamilyMemberHistory",
        )
        .all()
    )
    for row in rows:
        if not _patient_linked(row, patient_id):
            continue
        refs.append(
            {
                "patient_reference": f"Patient/{patient_id}",
                "supporting_references": [f"FamilyMemberHistory/{row.logical_id}"],
                "candidate_kind": "family_history",
            }
        )
        if len(refs) >= limit:
            break
    return _batch(
        workspace_id=workspace_id,
        patient_id=patient_id,
        candidates=refs,
        permission_revision=permission_revision,
        generation_id=generation_id,
    )


def care_plan_candidates(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    limit: int = 20,
    permission_revision: str = "permissions-v1",
    generation_id: str | None = None,
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 100))
    refs: list[dict[str, Any]] = []
    rows = (
        db.query(FhirResource)
        .filter(
            FhirResource.workspace_id == workspace_id,
            FhirResource.resource_type == "CarePlan",
        )
        .all()
    )
    for row in rows:
        if not _patient_linked(row, patient_id):
            continue
        refs.append(
            {
                "patient_reference": f"Patient/{patient_id}",
                "supporting_references": [f"CarePlan/{row.logical_id}"],
                "candidate_kind": "care_plan_link",
            }
        )
        if len(refs) >= limit:
            break
    return _batch(
        workspace_id=workspace_id,
        patient_id=patient_id,
        candidates=refs,
        permission_revision=permission_revision,
        generation_id=generation_id,
    )

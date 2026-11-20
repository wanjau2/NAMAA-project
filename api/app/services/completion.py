"""Validate persisted evidence; closing a case must never manufacture clinical facts."""
import json
import re

from typing import NoReturn

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import FhirResource

COMPLETION_STATUSES = {
    "Encounter": {"finished"},
    "Procedure": {"completed"},
    "DiagnosticReport": {"final", "amended", "corrected"},
}


def validate_completion_evidence(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    evidence_type: str | None,
    evidence_reference: str | None,
) -> FhirResource:
    def reject(reason: str) -> NoReturn:
        raise AppError(
            code="validation_failed",
            status_code=422,
            message="Completion requires existing, completed evidence for this patient.",
            field_errors={"evidence_reference": reason},
        )

    if not isinstance(evidence_type, str) or evidence_type not in COMPLETION_STATUSES:
        reject("invalid_resource_type")
    if not isinstance(evidence_reference, str) or not re.fullmatch(
        rf"{evidence_type}/[A-Za-z0-9\-.]{{1,64}}", evidence_reference
    ):
        reject("reference_type_mismatch_or_invalid")
    logical_id = evidence_reference.split("/")[1]
    row = db.query(FhirResource).filter_by(
        workspace_id=workspace_id, resource_type=evidence_type, logical_id=logical_id
    ).one_or_none()
    if row is None:
        reject("evidence_not_found")
    body = json.loads(row.body_json)
    if body.get("resourceType") != evidence_type or body.get("id") != logical_id:
        reject("resource_identity_mismatch")
    if (body.get("subject") or {}).get("reference") != f"Patient/{patient_id}":
        reject("patient_mismatch")
    if body.get("status") not in COMPLETION_STATUSES[evidence_type]:
        reject("evidence_not_completed")
    return row

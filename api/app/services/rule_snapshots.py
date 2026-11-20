"""Build Alfred RuleSnapshot objects from the stub store — never from unreviewed proposals."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.ai_runtime import ensure_namaa_ai
from app.models import FhirResource, Observation, Patient, Proposal

ensure_namaa_ai()

from namaa_ai.contracts import RuleSnapshot, VerifiedResource  # noqa: E402
from namaa_ai.fhir import CONCEPT_TEXT  # noqa: E402

CHILD_AGE_BANDS = {"0–1 years", "2–4 years", "5–9 years"}
ELIGIBILITY_CODE = {
    "child_wcv": "Demo WCV eligibility",
    "adult_screening": "Demo adult eligibility",
}
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def infer_pathway(age_band: str, requested: str | None = None) -> str:
    if requested in {"child_wcv", "adult_screening"}:
        return requested
    return "child_wcv" if age_band in CHILD_AGE_BANDS else "adult_screening"


def pathway_rule_id(pathway: str) -> str:
    return "DEMO_WCV_01" if pathway == "child_wcv" else "DEMO_ADULT_01"


def _compensated_or_revoked(body: dict[str, Any]) -> bool:
    status = str(body.get("status") or "")
    if status in {"entered-in-error", "revoked", "cancelled"}:
        return True
    tags = (body.get("meta") or {}).get("tag") or []
    return any(isinstance(tag, dict) and tag.get("code") == "compensated" for tag in tags)


def _patient_link(body: dict[str, Any]) -> str | None:
    link = body.get("patient") if body.get("resourceType") == "FamilyMemberHistory" else body.get("subject")
    if isinstance(link, dict):
        return link.get("reference")
    return None


def _observation_resource(obs: Observation, *, pathway: str, patient_id: str) -> dict[str, Any] | None:
    if not obs.verified or obs.missing_or_conflict:
        return None
    subject = {"reference": f"Patient/{patient_id}"}
    meta = {"versionId": "app-1"}
    if obs.type == "demo_eligibility":
        raw = obs.value.strip().lower()
        if raw not in {"true", "false", "1", "0", "yes", "no"}:
            return None
        return {
            "resourceType": "Observation",
            "id": obs.id,
            "meta": meta,
            "status": "final",
            "code": {"text": ELIGIBILITY_CODE[pathway]},
            "subject": subject,
            "valueBoolean": raw in {"true", "1", "yes"},
        }
    history_type = None
    if obs.type in {"last_wcv", "last_adult_screening"}:
        history_type = obs.type
    elif obs.type == "screening_window":
        history_type = "last_adult_screening"
    if history_type not in CONCEPT_TEXT:
        return None
    if not _DATE.match(obs.value.strip()):
        return None
    return {
        "resourceType": "Observation",
        "id": obs.id,
        "meta": meta,
        "status": "final",
        "code": {"text": CONCEPT_TEXT[history_type]},
        "subject": subject,
        "valueString": obs.value.strip(),
        "effectiveDateTime": obs.value.strip(),
        "component": [
            {
                "code": {"text": "Source assertion"},
                "valueCodeableConcept": {"text": "present"},
            }
        ],
    }


def build_rule_snapshot(
    db: Session,
    *,
    workspace_id: str,
    patient: Patient,
    pathway: str,
    as_of: date,
    authorized: bool,
) -> RuleSnapshot:
    patient_ref = f"Patient/{patient.id}"
    resources: list[VerifiedResource] = [
        VerifiedResource(
            resource={
                "resourceType": "Patient",
                "id": patient.id,
                "meta": {"versionId": "app-1"},
                "name": [{"text": patient.label}],
            },
            review_reference=f"seed:Patient/{patient.id}",
            reviewed=True,
        )
    ]
    seen: set[str] = {f"Patient/{patient.id}"}

    for row in (
        db.query(FhirResource)
        .filter(FhirResource.workspace_id == workspace_id)
        .all()
    ):
        try:
            body = json.loads(row.body_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(body, dict):
            continue
        kind = body.get("resourceType")
        if kind not in {"Observation", "Condition", "FamilyMemberHistory"}:
            continue
        if _compensated_or_revoked(body):
            continue
        if _patient_link(body) != patient_ref:
            continue
        body = {
            **body,
            "id": row.logical_id,
            "meta": {**(body.get("meta") or {}), "versionId": str(row.version_id)},
        }
        key = f"{kind}/{row.logical_id}"
        if key in seen:
            continue
        seen.add(key)
        resources.append(
            VerifiedResource(
                resource=body,
                review_reference=f"stub:{key}/_history/{row.version_id}",
                reviewed=True,
            )
        )

    for obs in (
        db.query(Observation)
        .filter(
            Observation.workspace_id == workspace_id,
            Observation.patient_id == patient.id,
        )
        .all()
    ):
        mapped = _observation_resource(obs, pathway=pathway, patient_id=patient.id)
        if mapped is None:
            continue
        key = f"Observation/{obs.id}"
        if key in seen:
            continue
        seen.add(key)
        resources.append(
            VerifiedResource(
                resource=mapped,
                review_reference=f"seed:Observation/{obs.id}",
                reviewed=True,
            )
        )

    pending = (
        db.query(Proposal)
        .filter(
            Proposal.workspace_id == workspace_id,
            Proposal.patient_id == patient.id,
            Proposal.review_state == "proposed",
        )
        .count()
    )
    return RuleSnapshot(
        workspace_id=workspace_id,
        patient_reference=patient_ref,
        as_of=as_of,
        authority="simulated_fhir",
        authorized=authorized,
        complete_for_rule=pending == 0,
        resources=tuple(resources),
    )

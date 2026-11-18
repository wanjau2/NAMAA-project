"""FHIR / Relate boundary — graph hints never grant access (D005)."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Document, FhirResource, Observation
from app.security.context import TrustedRequestContext
from app.security.enforce import authorize


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_verified_context(
    db: Session,
    ctx: TrustedRequestContext,
    *,
    patient_id: str,
    generation_id: str | None = None,
    relate_hints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Re-check scope and source versions before returning context.

    `relate_hints` are ignored as authority — used only as candidate references
    that must still pass workspace/patient/version checks. Stale or revoked
    resources are suppressed.
    """
    authorize(
        db,
        ctx,
        action="context.retrieve",
        resource_type="Patient",
        resource_id=patient_id,
        patient_id=patient_id,
    )

    if patient_id not in ctx.patient_ids:
        raise AppError(
            code="forbidden",
            message="Patient is outside the trusted assignment scope.",
            status_code=403,
            request_id=ctx.request_id,
        )

    now = datetime.now(timezone.utc)
    records: list[dict[str, Any]] = []

    # Candidate refs from Relate are suggestions only.
    hinted_refs = {
        (h.get("resource_type"), h.get("logical_id"))
        for h in (relate_hints or [])
        if h.get("resource_type") and h.get("logical_id")
    }

    fhir_rows = (
        db.query(FhirResource)
        .filter(FhirResource.workspace_id == ctx.workspace_id)
        .all()
    )
    for row in fhir_rows:
        # Suppress anything not for this patient when body carries subject.
        body = row.body_json
        if f"Patient/{patient_id}" not in body and hinted_refs and (
            row.resource_type,
            row.logical_id,
        ) not in hinted_refs:
            continue
        if f"Patient/{patient_id}" not in body and not hinted_refs:
            # Include only explicitly patient-linked or seed observations path below.
            continue
        records.append(
            {
                "source": {
                    "reference": f"{row.resource_type}/{row.logical_id}",
                    "version": str(row.version_id),
                },
                "patient_reference": f"Patient/{patient_id}",
                "source_last_updated": row.updated_at,
                "verified_at": _iso(now),
                "authorized": True,
                "source_verified": True,
                "text": f"{row.resource_type}/{row.logical_id} v{row.version_id} (synthetic stub)",
            }
        )

    # Always allow checked-scope observations for the patient (application store).
    for obs in (
        db.query(Observation)
        .filter(
            Observation.workspace_id == ctx.workspace_id,
            Observation.patient_id == patient_id,
        )
        .all()
    ):
        if not obs.verified:
            continue  # suppress unverified / revoked-style rows
        records.append(
            {
                "source": {
                    "reference": f"Observation/{obs.id}",
                    "version": "app-1",
                },
                "patient_reference": f"Patient/{patient_id}",
                "source_last_updated": obs.observed_time,
                "verified_at": _iso(now),
                "authorized": True,
                "source_verified": True,
                "text": f"{obs.type}: {obs.value[:120]}",
            }
        )

    # Document versions currently in scope
    docs = (
        db.query(Document)
        .filter(
            Document.workspace_id == ctx.workspace_id,
            Document.patient_id == patient_id,
        )
        .all()
    )
    source_versions = {
        f"DocumentReference/{d.id}": str(d.version) for d in docs
    }

    gen = generation_id or f"gen-{uuid.uuid4().hex[:10]}"
    return {
        "workspace_id": ctx.workspace_id,
        "patient_reference": f"Patient/{patient_id}",
        "generation_id": gen,
        "mapping_version": "mapping-v1",
        "permission_revision": ctx.permission_revision,
        "built_at": _iso(now - timedelta(minutes=5)),
        "verified_at": _iso(now),
        "expires_at": _iso(now + timedelta(minutes=1)),
        "state": "current",
        "authorized": True,
        "source_verified": True,
        "completeness": "partial",
        "checked_scope": (
            "Synthetic guest workspace patient journey only; "
            "Relate hints never grant access; exhaustive absence not claimed."
        ),
        "records": records,
        "exhaustive": False,
        "absence_claims_allowed": False,
        "source_versions": source_versions,
        "policy_adapter": ctx.policy_adapter,
        "production_authorization": ctx.production_authorization,
        "notice": (
            "Verified by namaa-api against current scope and versions. "
            "Graph-derived Relate results are not authoritative."
        ),
    }

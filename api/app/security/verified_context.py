"""FHIR / Relate boundary — graph hints never grant access (D005)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import Document, FhirResource, Observation
from app.security.context import TrustedRequestContext
from app.security.enforce import authorize
from app.security.revocation import assert_not_revoked
from app.services.rule_snapshots import _compensated_or_revoked, _patient_link


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _aware(value: str) -> str:
    if value.endswith("Z") or "+" in value[10:]:
        return value
    return value + "Z" if "T" in value else f"{value}T00:00:00Z"


def _generation(*, workspace_id: str, patient_id: str, permission_revision: str, versions: dict[str, str]) -> str:
    material = "|".join(
        [workspace_id, patient_id, permission_revision, *sorted(f"{k}={v}" for k, v in versions.items())]
    )
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]
    return f"gen-{digest}"


def build_verified_context(
    db: Session,
    ctx: TrustedRequestContext,
    *,
    patient_id: str,
    generation_id: str | None = None,
    relate_hints: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    assert_not_revoked(db, workspace_id=ctx.workspace_id, principal_id=ctx.user_id)
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
    hint_keys = {
        (str(h.get("resource_type")), str(h.get("logical_id")))
        for h in (relate_hints or [])
        if h.get("resource_type") and h.get("logical_id")
    }

    fhir_rows = (
        db.query(FhirResource)
        .filter(FhirResource.workspace_id == ctx.workspace_id)
        .all()
    )
    for row in fhir_rows:
        try:
            body = json.loads(row.body_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(body, dict):
            continue
        if _compensated_or_revoked(body):
            continue
        if _patient_link(body) != f"Patient/{patient_id}":
            continue
        if hint_keys and (row.resource_type, row.logical_id) not in hint_keys and row.resource_type not in {
            "Patient",
            "Observation",
            "Condition",
            "FamilyMemberHistory",
            "CarePlan",
            "DocumentReference",
        }:
            continue
        reviewed = any(
            isinstance(tag, dict) and tag.get("code") in {"human_reviewed", "synthetic"}
            for tag in ((body.get("meta") or {}).get("tag") or [])
        )
        records.append(
            {
                "source": {
                    "reference": f"{row.resource_type}/{row.logical_id}",
                    "version": str(row.version_id),
                },
                "patient_reference": f"Patient/{patient_id}",
                "source_last_updated": _aware(row.updated_at),
                "verified_at": _iso(now),
                "authorized": True,
                "source_verified": True,
                "reviewed": reviewed,
                "text": f"{row.resource_type}/{row.logical_id} v{row.version_id} (synthetic stub)",
            }
        )

    for obs in (
        db.query(Observation)
        .filter(
            Observation.workspace_id == ctx.workspace_id,
            Observation.patient_id == patient_id,
        )
        .all()
    ):
        if not obs.verified or obs.missing_or_conflict:
            continue
        records.append(
            {
                "source": {
                    "reference": f"Observation/{obs.id}",
                    "version": "app-1",
                },
                "patient_reference": f"Patient/{patient_id}",
                "source_last_updated": _aware(obs.observed_time),
                "verified_at": _iso(now),
                "authorized": True,
                "source_verified": True,
                "reviewed": True,
                "text": f"{obs.type}: {obs.value[:120]}",
            }
        )

    docs = (
        db.query(Document)
        .filter(
            Document.workspace_id == ctx.workspace_id,
            Document.patient_id == patient_id,
        )
        .all()
    )
    source_versions = {f"DocumentReference/{d.id}": str(d.version) for d in docs}
    for rec in records:
        source_versions[rec["source"]["reference"]] = rec["source"]["version"]

    actual_generation = _generation(
        workspace_id=ctx.workspace_id,
        patient_id=patient_id,
        permission_revision=ctx.permission_revision,
        versions=source_versions,
    )
    state = "current"
    if generation_id and generation_id != actual_generation:
        state = "stale"

    return {
        "workspace_id": ctx.workspace_id,
        "patient_reference": f"Patient/{patient_id}",
        "generation_id": actual_generation,
        "mapping_version": "mapping-v1",
        "permission_revision": ctx.permission_revision,
        "built_at": _iso(now),
        "verified_at": _iso(now),
        "expires_at": _iso(now + timedelta(minutes=5)),
        "state": state,
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
            "Verified by namaa-api against current scope, lifecycle and versions. "
            "Graph-derived Relate results are not authoritative. Not a HAPI commit."
        ),
    }

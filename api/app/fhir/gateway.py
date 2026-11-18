"""FHIR gateway boundary — stub store today, HAPI later (D003/D004)."""

from __future__ import annotations

import json
import random
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import FhirResource


class FhirConflictError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class FhirTransientError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class FhirUncertainError(Exception):
    """Outcome unknown after submit — must not blindly retry the same create."""

    def __init__(self, message: str, partial_ids: list[str] | None = None) -> None:
        self.message = message
        self.partial_ids = partial_ids or []
        super().__init__(message)


@dataclass
class BundleResult:
    status: str
    resource_refs: list[str]
    request_id: str


def apply_transaction_bundle(
    db: Session,
    *,
    workspace_id: str,
    request_id: str,
    bundle: dict[str, Any],
    now: str,
) -> BundleResult:
    """Idempotent apply: same request_id returns prior result without duplicating."""
    settings = get_settings()
    if settings.fhir_gateway_mode != "stub":
        raise FhirTransientError("HAPI gateway is not enabled in this deployment.")

    prior = (
        db.query(FhirResource)
        .filter(
            FhirResource.workspace_id == workspace_id,
            FhirResource.request_id == request_id,
        )
        .all()
    )
    if prior:
        refs = [f"{r.resource_type}/{r.logical_id}/_history/{r.version_id}" for r in prior]
        return BundleResult(status="replayed", resource_refs=refs, request_id=request_id)

    if settings.fhir_inject_failure_rate > 0 and random.random() < settings.fhir_inject_failure_rate:
        raise FhirTransientError("Injected transient FHIR gateway failure.")

    entries = bundle.get("entry") or []
    refs: list[str] = []
    for entry in entries:
        resource = entry.get("resource") or {}
        resource_type = resource.get("resourceType")
        if not resource_type:
            raise FhirTransientError("Bundle entry missing resourceType.")
        logical_id = resource.get("id") or f"syn-{uuid.uuid4().hex[:10]}"
        resource = {**resource, "id": logical_id}
        existing = (
            db.query(FhirResource)
            .filter(
                FhirResource.workspace_id == workspace_id,
                FhirResource.resource_type == resource_type,
                FhirResource.logical_id == logical_id,
            )
            .one_or_none()
        )
        if_match = (entry.get("request") or {}).get("ifMatch")
        if existing and if_match:
            expected = if_match.replace("W/", "").strip('"')
            if str(existing.version_id) != expected:
                raise FhirConflictError(
                    f"Version conflict on {resource_type}/{logical_id}: "
                    f"expected {expected}, current {existing.version_id}."
                )
        if existing:
            existing.version_id += 1
            existing.body_json = json.dumps(resource)
            existing.request_id = request_id
            existing.updated_at = now
            version = existing.version_id
        else:
            version = 1
            db.add(
                FhirResource(
                    workspace_id=workspace_id,
                    resource_type=resource_type,
                    logical_id=logical_id,
                    version_id=version,
                    body_json=json.dumps(resource),
                    request_id=request_id,
                    updated_at=now,
                )
            )
        refs.append(f"{resource_type}/{logical_id}/_history/{version}")

    db.flush()
    return BundleResult(status="committed", resource_refs=refs, request_id=request_id)


def compensate_uncertain(
    db: Session,
    *,
    workspace_id: str,
    request_id: str,
    now: str,
) -> BundleResult:
    """Idempotent compensation: mark resources from uncertain request as revoked/tombstoned."""
    rows = (
        db.query(FhirResource)
        .filter(
            FhirResource.workspace_id == workspace_id,
            FhirResource.request_id == request_id,
        )
        .all()
    )
    refs: list[str] = []
    for row in rows:
        body = json.loads(row.body_json)
        body["status"] = body.get("status") or "entered-in-error"
        body["meta"] = {
            **(body.get("meta") or {}),
            "tag": [{"system": "https://namaa.example/fhir", "code": "compensated"}],
        }
        row.version_id += 1
        row.body_json = json.dumps(body)
        row.updated_at = now
        refs.append(f"{row.resource_type}/{row.logical_id}/_history/{row.version_id}")
    db.flush()
    return BundleResult(status="compensated", resource_refs=refs, request_id=request_id)
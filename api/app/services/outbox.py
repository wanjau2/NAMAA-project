"""Transactional outbox + saga compensation for FHIR boundary (D004)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.fhir import (
    FhirConflictError,
    FhirTransientError,
    FhirUncertainError,
    apply_transaction_bundle,
    compensate_uncertain,
)
from app.models import OutboxEntry


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def enqueue_outbox(
    db: Session,
    *,
    workspace_id: str,
    request_id: str,
    action: str,
    bundle: dict[str, Any],
    case_id: str | None = None,
    now: str | None = None,
) -> OutboxEntry:
    settings = get_settings()
    stamp = now or get_settings().demo_now
    existing = (
        db.query(OutboxEntry)
        .filter(
            OutboxEntry.workspace_id == workspace_id,
            OutboxEntry.request_id == request_id,
        )
        .one_or_none()
    )
    if existing:
        return existing

    entry = OutboxEntry(
        id=f"outbox-{uuid.uuid4().hex[:12]}",
        workspace_id=workspace_id,
        request_id=request_id,
        case_id=case_id,
        action=action,
        state="pending",
        intended_bundle_json=json.dumps(bundle),
        attempts=0,
        max_attempts=settings.outbox_max_attempts,
        created_at=stamp,
        updated_at=stamp,
        next_attempt_at=stamp,
    )
    db.add(entry)
    db.flush()
    return entry


def build_evidence_bundle(
    *,
    case_id: str,
    patient_id: str,
    evidence_type: str,
    evidence_reference: str,
    disposition: str,
) -> dict[str, Any]:
    logical = evidence_reference.split("/")[-1] if "/" in evidence_reference else evidence_reference
    return {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": [
            {
                "request": {"method": "PUT", "url": f"{evidence_type}/{logical}"},
                "resource": {
                    "resourceType": evidence_type,
                    "id": logical,
                    "status": "finished" if evidence_type == "Encounter" else "completed",
                    "subject": {"reference": f"Patient/{patient_id}"},
                    "meta": {
                        "tag": [
                            {"system": "https://namaa.example/fhir", "code": "synthetic"},
                            {"system": "https://namaa.example/fhir", "code": disposition},
                        ]
                    },
                    "extension": [
                        {
                            "url": "https://namaa.example/fhir/StructureDefinition/case-id",
                            "valueString": case_id,
                        }
                    ],
                },
            }
        ],
    }


def claim_due_entries(db: Session, *, worker_id: str, limit: int = 10) -> list[OutboxEntry]:
    settings = get_settings()
    now = _utcnow()
    now_s = _iso(now)
    lease_until = _iso(now + timedelta(seconds=settings.outbox_lease_seconds))

    candidates = (
        db.query(OutboxEntry)
        .filter(OutboxEntry.state.in_(["pending", "processing", "compensating"]))
        .order_by(OutboxEntry.pk.asc())
        .limit(limit * 3)
        .all()
    )
    claimed: list[OutboxEntry] = []
    for entry in candidates:
        if len(claimed) >= limit:
            break
        due = entry.next_attempt_at is None or entry.next_attempt_at <= now_s
        lease_expired = entry.lease_until is None or entry.lease_until <= now_s
        if entry.state == "pending" and due:
            pass
        elif entry.state in {"processing", "compensating"} and lease_expired and due:
            pass
        else:
            continue
        entry.state = "compensating" if entry.state == "compensating" else "processing"
        entry.lease_owner = worker_id
        entry.lease_until = lease_until
        entry.updated_at = now_s
        claimed.append(entry)
    db.flush()
    return claimed


def process_entry(db: Session, entry: OutboxEntry) -> OutboxEntry:
    settings = get_settings()
    now = _iso(_utcnow())
    entry.attempts += 1
    entry.updated_at = now
    bundle = json.loads(entry.intended_bundle_json)

    try:
        if entry.state == "compensating" or entry.compensation_reason:
            result = compensate_uncertain(
                db,
                workspace_id=entry.workspace_id,
                request_id=entry.request_id,
                now=now,
            )
            entry.state = "compensated"
            entry.result_json = json.dumps(result.__dict__)
            entry.lease_owner = None
            entry.lease_until = None
            entry.last_error = None
            db.flush()
            return entry

        result = apply_transaction_bundle(
            db,
            workspace_id=entry.workspace_id,
            request_id=entry.request_id,
            bundle=bundle,
            now=now,
        )
        entry.state = "committed"
        entry.result_json = json.dumps(result.__dict__)
        entry.lease_owner = None
        entry.lease_until = None
        entry.last_error = None
        db.flush()
        return entry
    except FhirUncertainError as exc:
        entry.state = "compensating"
        entry.compensation_reason = exc.message
        entry.last_error = exc.message
        entry.next_attempt_at = now
        entry.lease_owner = None
        entry.lease_until = None
        db.flush()
        return entry
    except FhirConflictError as exc:
        entry.state = "dead_lettered"
        entry.dead_lettered_at = now
        entry.last_error = exc.message
        entry.lease_owner = None
        entry.lease_until = None
        db.flush()
        return entry
    except FhirTransientError as exc:
        entry.last_error = exc.message
        if entry.attempts >= entry.max_attempts:
            entry.state = "dead_lettered"
            entry.dead_lettered_at = now
            entry.lease_owner = None
            entry.lease_until = None
        else:
            base = max(0, settings.outbox_backoff_base_seconds)
            backoff = 0 if base == 0 else min(60, base * (2 ** (entry.attempts - 1)))
            entry.state = "pending"
            entry.next_attempt_at = _iso(_utcnow() + timedelta(seconds=backoff))
            entry.lease_owner = None
            entry.lease_until = None
        db.flush()
        return entry


def retry_dead_letter(db: Session, *, workspace_id: str, outbox_id: str) -> OutboxEntry:
    entry = (
        db.query(OutboxEntry)
        .filter(OutboxEntry.workspace_id == workspace_id, OutboxEntry.id == outbox_id)
        .one_or_none()
    )
    if entry is None:
        raise KeyError(outbox_id)
    if entry.state != "dead_lettered":
        return entry
    now = _iso(_utcnow())
    entry.state = "pending"
    entry.dead_lettered_at = None
    entry.attempts = 0
    entry.next_attempt_at = now
    entry.updated_at = now
    entry.last_error = None
    db.flush()
    return entry


def list_outbox(
    db: Session,
    *,
    workspace_id: str,
    state: str | None = None,
) -> list[OutboxEntry]:
    q = db.query(OutboxEntry).filter(OutboxEntry.workspace_id == workspace_id)
    if state:
        q = q.filter(OutboxEntry.state == state)
    return q.order_by(OutboxEntry.pk.desc()).all()

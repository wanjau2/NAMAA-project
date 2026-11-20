"""Transactional outbox + saga compensation for FHIR boundary (D004)."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.fhir import (
    FhirConflictError,
    FhirTransientError,
    FhirUncertainError,
    apply_transaction_bundle,
    compensate_uncertain,
)
from app.models import Case, Command, Event, OutboxEntry
from app.errors import AppError
from app.services.completion import validate_completion_evidence


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
    # Record coordination completion without creating or overwriting the evidence.
    return {
        "resourceType": "Bundle", "type": "transaction",
        "entry": [{
            "request": {"method": "PUT", "url": f"CarePlan/cp-{case_id}"},
            "resource": {
                "resourceType": "CarePlan", "id": f"cp-{case_id}",
                "status": "completed", "intent": "plan",
                "subject": {"reference": f"Patient/{patient_id}"},
                "supportingInfo": [{"reference": evidence_reference}],
                "meta": {"tag": [{"system": "https://namaa.example/fhir", "code": "synthetic"}]},
            },
        }],
    }


def _finalize_completion(db: Session, entry: OutboxEntry, now: str) -> None:
    command = db.query(Command).filter_by(
        workspace_id=entry.workspace_id, outbox_id=entry.id,
        action="close_as_completed",
    ).one_or_none()
    if command is None:
        raise FhirConflictError("Completion command is missing.")
    snapshot = json.loads(command.response_json)["case"]
    case = db.query(Case).filter_by(workspace_id=entry.workspace_id, id=entry.case_id).one()
    try:
        validate_completion_evidence(db, workspace_id=entry.workspace_id,
                                     patient_id=case.patient_id, evidence_type=case.evidence_type,
                                     evidence_reference=case.evidence_reference)
    except AppError as exc:
        raise FhirConflictError(exc.message) from exc
    changed = db.execute(update(Case).where(
        Case.pk == case.pk, Case.revision == snapshot["revision"],
        Case.stage == snapshot["stage"], Case.disposition == snapshot["disposition"],
    ).values(stage="closed", disposition="completed", revision=Case.revision + 1,
             next_action="None — closed with evidence", due_time=None, overdue=False)
      .execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise FhirConflictError("Case changed while completion was pending; review again.")
    db.refresh(case)
    db.add(Event(
        id=f"evt-{uuid.uuid4().hex[:12]}", workspace_id=entry.workspace_id,
        case_id=case.id, timestamp=now, actor_role="system", action="completion_committed",
        prior_state=f"{snapshot['stage']}/{snapshot['disposition']}",
        new_state="closed/completed", evidence_reference=case.evidence_reference,
        request_id=command.request_id,
    ))


def _guard_approval(db: Session, entry: OutboxEntry) -> None:
    """Serialize approval with case changes and reject obsolete care-plan writes.

    Ordinary progress (invitation/attendance) may precede a delayed approval write.
    A later completion command or closure supersedes it, even after reopening.
    The no-op UPDATE holds the case write lock until this transaction commits.
    """
    command = db.query(Command).filter_by(
        workspace_id=entry.workspace_id,
        outbox_id=entry.id,
        case_id=entry.case_id,
        action="approve_pathway",
    ).one_or_none()
    if command is None:
        raise FhirConflictError("Approval command is missing; refusing an unbound care-plan write.")

    locked = db.execute(
        update(Case)
        .where(
            Case.workspace_id == entry.workspace_id,
            Case.id == entry.case_id,
            Case.stage != "closed",
        )
        .values(revision=Case.revision)
        .execution_options(synchronize_session=False)
    )
    if locked.rowcount != 1:
        raise FhirConflictError("Approval superseded: case is closed or no longer exists.")

    newer = db.query(Command.pk).filter(
        Command.workspace_id == entry.workspace_id,
        Command.case_id == entry.case_id,
        Command.pk > command.pk,
        Command.action.in_(["approve_pathway", "close_as_completed"]),
        Command.outbox_id.is_not(None),
    ).first()
    if newer is not None:
        raise FhirConflictError("Approval superseded by a later care-plan command; review current state.")


def claim_due_entries(db: Session, *, worker_id: str, limit: int = 10) -> list[OutboxEntry]:
    settings = get_settings()
    now = _utcnow()
    now_s = _iso(now)
    lease_until = _iso(now + timedelta(seconds=settings.outbox_lease_seconds))

    available = (
        OutboxEntry.state.in_(["pending", "processing", "compensating"]),
        or_(OutboxEntry.next_attempt_at.is_(None), OutboxEntry.next_attempt_at <= now_s),
        or_(OutboxEntry.lease_until.is_(None), OutboxEntry.lease_until <= now_s),
    )
    candidates = db.query(OutboxEntry).filter(*available).order_by(OutboxEntry.pk.asc()).limit(limit).all()
    claimed: list[OutboxEntry] = []
    for entry in candidates:
        changed = db.execute(update(OutboxEntry).where(
            OutboxEntry.pk == entry.pk, *available,
        ).values(state="compensating" if entry.compensation_reason else "processing",
                 lease_owner=worker_id, lease_until=lease_until, updated_at=now_s)
          .execution_options(synchronize_session=False))
        if changed.rowcount == 1:
            db.refresh(entry)
            claimed.append(entry)
    db.flush()
    return claimed


def _process_entry(db: Session, entry: OutboxEntry) -> OutboxEntry:
    settings = get_settings()
    now = _iso(_utcnow())
    entry.attempts += 1
    entry.updated_at = now
    bundle = json.loads(entry.intended_bundle_json)

    try:
        if entry.action == "approve_pathway":
            # Also guard compensation: an old approval must not revoke a newer plan.
            _guard_approval(db, entry)
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

        # Keep the case transition, FHIR stub write, and completion event atomic.
        # A failed/uncertain write rolls back the transition before recording retry state.
        with db.begin_nested():
            if entry.action == "close_as_completed":
                _finalize_completion(db, entry, now)
            result = apply_transaction_bundle(
                db, workspace_id=entry.workspace_id, request_id=entry.request_id,
                bundle=bundle, now=now,
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


def process_entry(db: Session, entry: OutboxEntry) -> OutboxEntry:
    if entry.state in {"committed", "compensated", "dead_lettered"}:
        return entry
    result = _process_entry(db, entry)
    db.query(Command).filter_by(workspace_id=entry.workspace_id, outbox_id=entry.id).update(
        {"saga_state": "fhir_" + result.state}, synchronize_session="fetch"
    )
    db.flush()
    return result


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

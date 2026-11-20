from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.ai_runtime import ensure_namaa_ai
from app.config import get_settings
from app.errors import AppError
from sqlalchemy import and_, or_

from app.models import Document, ExtractionJob, Proposal, Workspace
from app.realtime import extraction_channel, extraction_hub
from app.security.audit import emit_audit
from app.security.context import TrustedRequestContext, build_trusted_context
from app.security.enforce import authorize
from app.services.extraction_fixtures import proposals_for_document
from app.services.proposals import alfred_concept, proposal_to_alfred, source_sha256
from app.security.revocation import assert_not_revoked

ensure_namaa_ai()

from namaa_ai.contracts import ExtractionRequest, ProposedFact  # noqa: E402
from namaa_ai.validation import check_fact  # noqa: E402


TERMINAL = {"succeeded", "failed", "cancelled", "timed_out"}


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def job_event_payload(job: ExtractionJob, *, proposals: list[dict] | None = None) -> dict[str, Any]:
    settings = get_settings()
    started = job.started_at
    elapsed_ms = 0
    if started:
        try:
            start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
            elapsed_ms = int((_utcnow() - start_dt).total_seconds() * 1000)
        except ValueError:
            elapsed_ms = 0
    event_type = "terminal" if job.state in TERMINAL else "progress"
    payload: dict[str, Any] = {
        "event": event_type,
        "job_id": job.id,
        "document_id": job.document_id,
        "document_version": job.document_version,
        "state": job.state,
        "progress_percent": job.progress_percent,
        "message": job.progress_message,
        "elapsed_ms": elapsed_ms,
        "timeout_ms": job.timeout_ms or settings.extraction_timeout_ms,
        "model_revision": job.model_revision,
        "prompt_version": job.prompt_version,
        "error_code": job.error_code,
        "error_message": job.error_message,
        "synthetic": True,
        "inference_mode": (
            "offline_fixture"
            if (job.model_revision or "").startswith("offline-fixture")
            else settings.extraction_mode
        ),
    }
    if proposals is not None:
        payload["proposals"] = proposals
    return payload


async def publish_job(job: ExtractionJob, *, proposals: list[dict] | None = None) -> None:
    await extraction_hub.publish(
        extraction_channel(job.id),
        job_event_payload(job, proposals=proposals),
    )


def queue_extraction(
    db: Session,
    *,
    workspace_id: str,
    document_id: str,
    document_version: int | None = None,
    ctx: TrustedRequestContext | None = None,
) -> ExtractionJob:
    settings = get_settings()
    q = db.query(Document).filter(
        Document.workspace_id == workspace_id,
        Document.id == document_id,
    )
    if document_version is not None:
        q = q.filter(Document.version == document_version)
    doc = q.order_by(Document.version.desc()).first()
    if doc is None:
        raise AppError(
            code="not_found",
            message=f"Document '{document_id}' was not found in this guest session.",
            status_code=404,
        )

    if ctx is not None:
        # Human queue is note.retrieve. Workers re-check model.dispatch as service (D005).
        authorize(
            db,
            ctx,
            action="note.retrieve",
            resource_type="DocumentReference",
            resource_id=doc.id,
            patient_id=doc.patient_id,
            extra_context={"document_version": str(doc.version)},
        )

    # Reuse an active job for the same document version (avoid duplicate inference).
    active = (
        db.query(ExtractionJob)
        .filter(
            ExtractionJob.workspace_id == workspace_id,
            ExtractionJob.document_id == document_id,
            ExtractionJob.document_version == doc.version,
            ExtractionJob.state.in_(["queued", "running"]),
        )
        .one_or_none()
    )
    if active:
        return active

    now = _iso(_utcnow())
    snapshot = ctx.to_public_dict() if ctx else None
    job = ExtractionJob(
        id=f"ext-{uuid.uuid4().hex[:12]}",
        workspace_id=workspace_id,
        document_id=doc.id,
        document_version=doc.version,
        patient_id=doc.patient_id,
        case_id=doc.case_id,
        state="queued",
        attempts=0,
        model_revision=(
            "offline-fixture-v1 (no live inference)"
            if settings.extraction_mode == "offline_fixture"
            else "medgemma-pending"
        ),
        prompt_version="extract-v1.0.1",
        progress_percent=0,
        progress_message="Queued for extraction",
        created_at=now,
        timeout_ms=settings.extraction_timeout_ms,
        initiating_user_id=ctx.user_id if ctx else None,
        initiating_role=ctx.membership_role if ctx else None,
        initiating_purpose=ctx.purpose_of_use if ctx else None,
        initiating_request_id=ctx.request_id if ctx else None,
        principal_snapshot_json=json.dumps(snapshot) if snapshot else None,
    )
    db.add(job)
    if ctx is not None:
        emit_audit(
            db,
            event_type="extraction.queued",
            ctx=ctx,
            action="model.dispatch",
            resource_type="ExtractionJob",
            resource_id=job.id,
            patient_id=doc.patient_id,
            job_id=job.id,
            source_versions={f"DocumentReference/{doc.id}": str(doc.version)},
            model_revision=job.model_revision,
            prompt_version=job.prompt_version,
            reason_code="queued",
        )
    db.commit()
    db.refresh(job)
    return job


def reauthorize_job_execution(db: Session, job: ExtractionJob) -> TrustedRequestContext:
    """Re-authorize when a worker claims a job (preserved initiating scope)."""
    workspace = db.get(Workspace, job.workspace_id)
    if workspace is None:
        raise AppError(code="not_found", message="Workspace missing for job.", status_code=404)
    assert_not_revoked(db, workspace_id=job.workspace_id, principal_id=job.initiating_user_id)
    ctx = build_trusted_context(
        db,
        workspace=workspace,
        role="service",
        request_id=job.initiating_request_id or f"job-{job.id}",
        user_id=f"service:namaa-api",
        user_type="service",
        purpose_of_use=job.initiating_purpose or "demo_model_extraction",
        patient_id=job.patient_id,
    )
    authorize(
        db,
        ctx,
        action="model.dispatch",
        resource_type="ExtractionJob",
        resource_id=job.id,
        patient_id=job.patient_id,
        extra_context={
            "initiating_role": job.initiating_role,
            "initiating_user_id": job.initiating_user_id,
            "model_destination": ctx.approved_model_destination,
        },
    )
    authorize(
        db,
        ctx,
        action="note.retrieve",
        resource_type="DocumentReference",
        resource_id=job.document_id,
        patient_id=job.patient_id,
    )
    return ctx


def authorize_proposal_disclosure(
    db: Session,
    ctx: TrustedRequestContext,
    job: ExtractionJob,
) -> None:
    assert_not_revoked(db, workspace_id=job.workspace_id, principal_id=ctx.user_id)
    assert_not_revoked(db, workspace_id=job.workspace_id, principal_id=job.initiating_user_id)
    authorize(
        db,
        ctx,
        action="proposal.disclose",
        resource_type="ExtractionJob",
        resource_id=job.id,
        patient_id=job.patient_id,
        extra_context={"initiating_user_id": job.initiating_user_id},
    )
    authorize(
        db,
        ctx,
        action="excerpt.display",
        resource_type="DocumentReference",
        resource_id=job.document_id,
        patient_id=job.patient_id,
    )


def get_job(db: Session, *, workspace_id: str, job_id: str) -> ExtractionJob:
    job = (
        db.query(ExtractionJob)
        .filter(ExtractionJob.workspace_id == workspace_id, ExtractionJob.id == job_id)
        .one_or_none()
    )
    if job is None:
        raise AppError(
            code="not_found",
            message=f"Extraction job '{job_id}' was not found.",
            status_code=404,
        )
    return job


def proposals_for_job(db: Session, job: ExtractionJob) -> list[dict]:
    rows = (
        db.query(Proposal)
        .filter(Proposal.workspace_id == job.workspace_id, Proposal.job_id == job.id)
        .order_by(Proposal.pk.asc())
        .all()
    )
    return [proposal_to_alfred(p) for p in rows]


def claim_queued_jobs(db: Session, *, worker_id: str, limit: int = 5) -> list[ExtractionJob]:
    now = _utcnow()
    now_s = _iso(now)
    lease_until = _iso(now + timedelta(seconds=60))
    jobs = (
        db.query(ExtractionJob)
        .filter(ExtractionJob.state.in_(["queued", "running"]))
        .order_by(ExtractionJob.pk.asc())
        .limit(limit * 2)
        .all()
    )
    claimed: list[ExtractionJob] = []
    for job in jobs:
        if len(claimed) >= limit:
            break
        claimed_row = (
            db.query(ExtractionJob)
            .filter(
                ExtractionJob.pk == job.pk,
                or_(
                    ExtractionJob.state == "queued",
                    and_(
                        ExtractionJob.state == "running",
                        or_(
                            ExtractionJob.lease_until.is_(None),
                            ExtractionJob.lease_until <= now_s,
                        ),
                    ),
                ),
            )
            .update(
                {
                    "state": "running",
                    "attempts": ExtractionJob.attempts + 1,
                    "lease_owner": worker_id,
                    "lease_until": lease_until,
                    "started_at": job.started_at or now_s,
                    "progress_message": job.progress_message
                    if job.started_at
                    else "Extracting…",
                    "progress_percent": job.progress_percent if job.started_at else 5,
                },
                synchronize_session="fetch",
            )
        )
        if claimed_row == 1:
            db.refresh(job)
            claimed.append(job)
    db.commit()
    return claimed


def advance_job(db: Session, job: ExtractionJob) -> ExtractionJob:
    """Advance offline-fixture extraction with sparse DB writes + SSE publish points."""
    settings = get_settings()
    now = _utcnow()
    now_s = _iso(now)

    if not job.started_at:
        job.started_at = now_s

    start_dt = datetime.fromisoformat(job.started_at.replace("Z", "+00:00"))
    elapsed_ms = int((now - start_dt).total_seconds() * 1000)
    if elapsed_ms >= job.timeout_ms:
        job.state = "timed_out"
        job.progress_percent = 100
        job.progress_message = "Extraction timed out"
        job.error_code = "extraction_timeout"
        job.error_message = (
            "Inference exceeded the 90s timeout. Retry extraction — "
            "this is not the same as finding no care gap."
        )
        job.finished_at = now_s
        job.lease_owner = None
        job.lease_until = None
        db.commit()
        return job

    # Offline fixture completes quickly (~3s of progress ticks) without DB spam.
    # Progress steps: 5 → 35 → 70 → succeed.
    if job.progress_percent < 35:
        job.progress_percent = 35
        job.progress_message = "Extracting… validating schema"
        job.lease_until = _iso(now + timedelta(seconds=60))
        db.commit()
        return job
    if job.progress_percent < 70:
        job.progress_percent = 70
        job.progress_message = "Extracting… checking source quotes"
        job.lease_until = _iso(now + timedelta(seconds=60))
        db.commit()
        return job

    if settings.extraction_mode != "offline_fixture":
        job.state = "failed"
        job.progress_percent = 100
        job.progress_message = "Hosted extraction is not configured"
        job.error_code = "live_inference_unavailable"
        job.error_message = (
            "NAMAA_EXTRACTION_MODE is not offline_fixture and no hosted adapter ran. "
            "This failure is not a care-gap or no-risk result."
        )
        job.finished_at = now_s
        job.lease_owner = None
        job.lease_until = None
        db.commit()
        return job

    doc = (
        db.query(Document)
        .filter(
            Document.workspace_id == job.workspace_id,
            Document.id == job.document_id,
            Document.version == job.document_version,
        )
        .one()
    )
    fixtures = proposals_for_document(doc.id, doc.text)
    digest = source_sha256(doc.text)
    request = ExtractionRequest(
        request_id=job.id,
        workspace_id=job.workspace_id,
        patient_reference=f"Patient/{job.patient_id}",
        source_id=doc.id,
        source_version=str(doc.version),
        source_date=doc.document_date[:10],
        note_text=doc.text,
    )
    # I07 — immutable proposal id per extraction job (never reuse bare fixture ids).
    job_suffix = job.id.removeprefix("ext-")[:12]
    for item in fixtures:
        relationship = "sibling" if item.get("subject") == "family_member" else None
        fact = ProposedFact.model_validate(
            {
                "concept": alfred_concept(item["concept"]),
                "value_text": item["value_text"],
                "subject": item["subject"],
                "assertion": item["assertion"],
                "effective_date": item["effective_date"],
                "excerpt": item["excerpt"],
                "proposed_resource_type": item["proposed_resource_type"],
                "relationship": relationship,
            }
        )
        start, end, issues = check_fact(request, fact)
        fixture_stem = str(item["id"]).removeprefix("prop-")
        proposal_id = f"prop-{job_suffix}-{fixture_stem}"[:64]
        db.add(
            Proposal(
                id=proposal_id,
                workspace_id=job.workspace_id,
                job_id=job.id,
                patient_id=job.patient_id,
                document_id=doc.id,
                document_version=doc.version,
                version=1,
                source_sha256=digest,
                concept=item["concept"],
                value_text=item["value_text"],
                subject=item["subject"],
                assertion=item["assertion"],
                effective_date=item["effective_date"],
                proposed_resource_type=item["proposed_resource_type"],
                relationship=relationship,
                excerpt=item["excerpt"],
                offset_start=item["offset_start"] if start is None else start,
                offset_end=item["offset_end"] if end is None else end,
                issues_json=json.dumps([issue.model_dump() for issue in issues]),
                model_id="google/medgemma-1.5-4b-it",
                model_revision=job.model_revision,
                prompt_version="extract-v1.0.1",
                model_simulated=True,
                review_state="proposed",
            )
        )
    job.state = "succeeded"
    job.progress_percent = 100
    job.progress_message = "Extraction complete (offline fixture)"
    job.model_revision = "offline-fixture-v1 (no live inference)"
    job.prompt_version = "extract-v1.0.1"
    job.finished_at = now_s
    job.lease_owner = None
    job.lease_until = None
    db.commit()
    return job

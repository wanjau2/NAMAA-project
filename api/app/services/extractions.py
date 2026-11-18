from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import Document, ExtractionJob, Proposal
from app.realtime import extraction_channel, extraction_hub
from app.services.extraction_fixtures import proposals_for_document


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
        "inference_mode": settings.extraction_mode,
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
        prompt_version="extract-v0.3",
        progress_percent=0,
        progress_message="Queued for extraction",
        created_at=now,
        timeout_ms=settings.extraction_timeout_ms,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


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
    return [
        {
            "id": p.id,
            "concept": p.concept,
            "value_text": p.value_text,
            "subject": p.subject,
            "assertion": p.assertion,
            "effective_date": p.effective_date,
            "proposed_resource_type": p.proposed_resource_type,
            "source_document_id": p.document_id,
            "source_document_version": p.document_version,
            "excerpt": p.excerpt,
            "offset_start": p.offset_start,
            "offset_end": p.offset_end,
            "review_state": p.review_state,
        }
        for p in rows
    ]


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
        lease_expired = job.lease_until is None or job.lease_until <= now_s
        if job.state == "queued" or (job.state == "running" and lease_expired):
            job.state = "running"
            job.attempts += 1
            job.lease_owner = worker_id
            job.lease_until = lease_until
            if not job.started_at:
                job.started_at = now_s
                job.progress_message = "Extracting…"
                job.progress_percent = 5
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
    for item in fixtures:
        db.add(
            Proposal(
                id=item["id"],
                workspace_id=job.workspace_id,
                job_id=job.id,
                document_id=doc.id,
                document_version=doc.version,
                concept=item["concept"],
                value_text=item["value_text"],
                subject=item["subject"],
                assertion=item["assertion"],
                effective_date=item["effective_date"],
                proposed_resource_type=item["proposed_resource_type"],
                excerpt=item["excerpt"],
                offset_start=item["offset_start"],
                offset_end=item["offset_end"],
                review_state="proposed",
            )
        )
    job.state = "succeeded"
    job.progress_percent = 100
    job.progress_message = "Extraction complete (offline fixture)"
    job.finished_at = now_s
    job.lease_owner = None
    job.lease_until = None
    if settings.extraction_mode != "offline_fixture":
        job.model_revision = "offline-fixture-v1 (fallback — live model unavailable)"
    db.commit()
    return job

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Document
from app.realtime import extraction_channel, extraction_hub
from app.schemas_extraction import ExtractionAccepted, ExtractionJobOut
from app.security.context import TrustedRequestContext
from app.security.deps import get_trusted_context
from app.security.enforce import authorize
from app.services.extractions import (
    TERMINAL,
    authorize_proposal_disclosure,
    get_job,
    job_event_payload,
    proposals_for_job,
    queue_extraction,
)

router = APIRouter(tags=["extractions"])


@router.get("/api/v1/documents/{document_id}")
def get_document(
    document_id: str,
    document_version: int | None = Query(default=None),
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict:
    """Authorized note retrieval — text only after PDP permit."""
    q = db.query(Document).filter(
        Document.workspace_id == ctx.workspace_id,
        Document.id == document_id,
    )
    if document_version is not None:
        q = q.filter(Document.version == document_version)
    doc = q.order_by(Document.version.desc()).first()
    if doc is None:
        from app.errors import AppError

        raise AppError(code="not_found", message="Document not found.", status_code=404)

    authorize(
        db,
        ctx,
        action="note.retrieve",
        resource_type="DocumentReference",
        resource_id=doc.id,
        patient_id=doc.patient_id,
    )
    db.commit()
    return {
        "id": doc.id,
        "version": doc.version,
        "document_date": doc.document_date,
        "patient_id": doc.patient_id,
        "case_id": doc.case_id,
        "text": doc.text,
        "policy_adapter": ctx.policy_adapter,
        "production_authorization": ctx.production_authorization,
    }


@router.post(
    "/api/v1/documents/{document_id}/extractions",
    response_model=ExtractionAccepted,
    status_code=202,
)
def start_extraction(
    document_id: str,
    document_version: int | None = Query(default=None),
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> ExtractionAccepted:
    job = queue_extraction(
        db,
        workspace_id=ctx.workspace_id,
        document_id=document_id,
        document_version=document_version,
        ctx=ctx,
    )
    return ExtractionAccepted(
        job_id=job.id,
        state=job.state,  # type: ignore[arg-type]
        events_url=f"/api/v1/extractions/{job.id}/events",
        status_url=f"/api/v1/extractions/{job.id}",
    )


@router.get("/api/v1/extractions/{job_id}", response_model=ExtractionJobOut)
def extraction_status(
    job_id: str,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> ExtractionJobOut:
    job = get_job(db, workspace_id=ctx.workspace_id, job_id=job_id)
    proposals: list[dict] = []
    if job.state == "succeeded":
        authorize_proposal_disclosure(db, ctx, job)
        proposals = proposals_for_job(db, job)
    db.commit()
    payload = job_event_payload(job, proposals=proposals if proposals else None)
    payload["proposals"] = proposals
    return ExtractionJobOut(**payload)


@router.get("/api/v1/extractions/{job_id}/events")
async def extraction_events(
    job_id: str,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE stream — replaces 2s polling (D004). Re-checks disclose before terminal payloads."""
    job = get_job(db, workspace_id=ctx.workspace_id, job_id=job_id)
    channel = extraction_channel(job.id)

    async def event_generator():
        queue = await extraction_hub.subscribe(channel)
        try:
            props = None
            if job.state in TERMINAL and job.state == "succeeded":
                authorize_proposal_disclosure(db, ctx, job)
                props = proposals_for_job(db, job)
                db.commit()
            snapshot = job_event_payload(job, proposals=props)
            yield _sse(snapshot.get("event", "progress"), snapshot)

            if job.state in TERMINAL:
                return

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event.get("state") == "succeeded" and event.get("proposals"):
                    # Strip proposals from wire until disclose check passes for this subscriber.
                    try:
                        authorize_proposal_disclosure(db, ctx, job)
                        db.commit()
                    except Exception:
                        event = {**event, "proposals": [], "message": "Proposals withheld — authorization denied"}
                yield _sse(event.get("event", "progress"), event)
                if event.get("state") in TERMINAL:
                    break
        finally:
            await extraction_hub.unsubscribe(channel, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"

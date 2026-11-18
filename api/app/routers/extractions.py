from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_workspace
from app.models import Workspace
from app.realtime import extraction_channel, extraction_hub
from app.schemas_extraction import ExtractionAccepted, ExtractionJobOut
from app.services.extractions import (
    TERMINAL,
    get_job,
    job_event_payload,
    proposals_for_job,
    queue_extraction,
)

router = APIRouter(tags=["extractions"])


@router.post(
    "/api/v1/documents/{document_id}/extractions",
    response_model=ExtractionAccepted,
    status_code=202,
)
def start_extraction(
    document_id: str,
    document_version: int | None = Query(default=None),
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> ExtractionAccepted:
    job = queue_extraction(
        db,
        workspace_id=workspace.id,
        document_id=document_id,
        document_version=document_version,
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
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> ExtractionJobOut:
    job = get_job(db, workspace_id=workspace.id, job_id=job_id)
    proposals = proposals_for_job(db, job) if job.state == "succeeded" else []
    payload = job_event_payload(job, proposals=proposals if proposals else None)
    payload["proposals"] = proposals
    return ExtractionJobOut(**payload)


@router.get("/api/v1/extractions/{job_id}/events")
async def extraction_events(
    job_id: str,
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """SSE stream — replaces 2s polling (D004)."""
    job = get_job(db, workspace_id=workspace.id, job_id=job_id)
    channel = extraction_channel(job.id)

    async def event_generator():
        queue = await extraction_hub.subscribe(channel)
        try:
            # Immediate snapshot so late subscribers do not wait for the next tick.
            props = proposals_for_job(db, job) if job.state in TERMINAL else None
            snapshot = job_event_payload(job, proposals=props)
            yield _sse(snapshot.get("event", "progress"), snapshot)

            if job.state in TERMINAL:
                return

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    # Comment keepalive — no DB hit.
                    yield ": keepalive\n\n"
                    continue
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
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.schemas_extraction import OutboxRetryOut, OutboxRow
from app.security.context import TrustedRequestContext
from app.security.deps import get_trusted_context
from app.security.enforce import authorize
from app.services.outbox import list_outbox, retry_dead_letter

router = APIRouter(prefix="/api/v1/ops", tags=["ops"])


@router.get("/outbox", response_model=list[OutboxRow])
def get_outbox(
    state: str | None = Query(default=None),
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> list[OutboxRow]:
    authorize(db, ctx, action="outbox.read", resource_type="OutboxEntry", resource_id="list")
    rows = list_outbox(db, workspace_id=ctx.workspace_id, state=state)
    db.commit()
    return [
        OutboxRow(
            id=r.id,
            request_id=r.request_id,
            action=r.action,
            state=r.state,
            attempts=r.attempts,
            max_attempts=r.max_attempts,
            last_error=r.last_error,
            case_id=r.case_id,
            created_at=r.created_at,
            updated_at=r.updated_at,
            dead_lettered_at=r.dead_lettered_at,
            compensation_reason=r.compensation_reason,
        )
        for r in rows
    ]


@router.post("/outbox/{outbox_id}/retry", response_model=OutboxRetryOut)
def retry_outbox(
    outbox_id: str,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> OutboxRetryOut:
    authorize(db, ctx, action="outbox.retry", resource_type="OutboxEntry", resource_id=outbox_id)
    try:
        entry = retry_dead_letter(db, workspace_id=ctx.workspace_id, outbox_id=outbox_id)
    except KeyError:
        raise AppError(
            code="not_found",
            message=f"Outbox entry '{outbox_id}' was not found.",
            status_code=404,
            request_id=ctx.request_id,
        ) from None
    db.commit()
    return OutboxRetryOut(
        id=entry.id,
        state=entry.state,
        message="Re-queued for idempotent replay. Compensation runs automatically if uncertain.",
    )

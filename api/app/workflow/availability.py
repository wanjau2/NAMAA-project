"""Server-authored action list for a case. Display hints on the client follow this."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Case, OutboxEntry
from app.schemas import AvailableAction
from app.workflow.actions import ACTIONS


def available_actions_for(db: Session, case: Case) -> list[AvailableAction]:
    pending = (
        db.query(OutboxEntry)
        .filter(
            OutboxEntry.workspace_id == case.workspace_id,
            OutboxEntry.case_id == case.id,
            OutboxEntry.action == "close_as_completed",
            OutboxEntry.state.in_(["pending", "processing", "compensating"]),
        )
        .first()
    )
    items: list[AvailableAction] = []
    for spec in ACTIONS.values():
        if not spec.applies(case):
            continue
        blocked = spec.precondition(case) if spec.precondition else None
        if pending is not None:
            blocked = "Completion is awaiting FHIR persistence."
        items.append(
            AvailableAction(
                id=spec.id,  # type: ignore[arg-type]
                permitted_role=spec.role,  # type: ignore[arg-type]
                blocked_reason=blocked,
            )
        )
    return items

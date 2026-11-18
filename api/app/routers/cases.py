from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_role, require_workspace
from app.errors import AppError
from app.models import Case, Workspace
from app.schemas import ActionRequest, ActionResponse, CaseOut, CaseRow
from app.services.serializers import case_to_out
from app.workflow import apply_action

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


@router.get("", response_model=list[CaseRow])
def list_cases(
    pathway: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> list[CaseRow]:
    q = db.query(Case).filter(Case.workspace_id == workspace.id)
    if pathway:
        q = q.filter(Case.pathway == pathway)
    if stage:
        q = q.filter(Case.stage == stage)
    if overdue is not None:
        q = q.filter(Case.overdue.is_(overdue))
    cases = q.order_by(Case.id.asc()).all()
    rows: list[CaseRow] = []
    for case in cases:
        full = case_to_out(db, case)
        rows.append(CaseRow.model_validate(full.model_dump()))
    return rows


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: str,
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> CaseOut:
    case = (
        db.query(Case)
        .filter(Case.workspace_id == workspace.id, Case.id == case_id)
        .one_or_none()
    )
    if case is None:
        raise AppError(
            code="not_found",
            message=f"Case '{case_id}' was not found in this guest session.",
            status_code=404,
        )
    return case_to_out(db, case)


@router.post("/{case_id}/actions", response_model=ActionResponse)
def post_action(
    case_id: str,
    body: ActionRequest,
    workspace: Workspace = Depends(require_workspace),
    role: str = Depends(get_role),
    db: Session = Depends(get_db),
) -> ActionResponse:
    case = (
        db.query(Case)
        .filter(Case.workspace_id == workspace.id, Case.id == case_id)
        .one_or_none()
    )
    if case is None:
        raise AppError(
            code="not_found",
            message=f"Case '{case_id}' was not found in this guest session.",
            status_code=404,
            request_id=body.request_id,
        )
    return apply_action(
        db,
        workspace_id=workspace.id,
        case=case,
        request=body,
        role=role,
    )
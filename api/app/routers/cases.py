from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import Case, Document
from app.schemas import ActionRequest, ActionResponse, CaseDocumentOut, CaseOut, CaseRow
from app.security.context import TrustedRequestContext
from app.security.deps import get_trusted_context
from app.security.enforce import authorize
from app.services.serializers import case_to_out
from app.workflow import apply_action

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


@router.get("", response_model=list[CaseRow])
def list_cases(
    pathway: str | None = Query(default=None),
    stage: str | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> list[CaseRow]:
    authorize(db, ctx, action="case.read", resource_type="Bundle", resource_id="cases")
    q = db.query(Case).filter(Case.workspace_id == ctx.workspace_id)
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
    db.commit()
    return rows


@router.get("/{case_id}", response_model=CaseOut)
def get_case(
    case_id: str,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> CaseOut:
    case = (
        db.query(Case)
        .filter(Case.workspace_id == ctx.workspace_id, Case.id == case_id)
        .one_or_none()
    )
    if case is None:
        raise AppError(
            code="not_found",
            message=f"Case '{case_id}' was not found in this guest session.",
            status_code=404,
            request_id=ctx.request_id,
        )
    authorize(
        db,
        ctx,
        action="case.read",
        resource_type="Case",
        resource_id=case.id,
        patient_id=case.patient_id,
    )
    db.commit()
    return case_to_out(db, case)


@router.get("/{case_id}/documents", response_model=list[CaseDocumentOut])
def list_case_documents(
    case_id: str,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> list[CaseDocumentOut]:
    case = (
        db.query(Case)
        .filter(Case.workspace_id == ctx.workspace_id, Case.id == case_id)
        .one_or_none()
    )
    if case is None:
        raise AppError(
            code="not_found",
            message=f"Case '{case_id}' was not found in this guest session.",
            status_code=404,
            request_id=ctx.request_id,
        )
    authorize(
        db,
        ctx,
        action="document.list",
        resource_type="Case",
        resource_id=case.id,
        patient_id=case.patient_id,
    )
    docs = (
        db.query(Document)
        .filter(Document.workspace_id == ctx.workspace_id, Document.case_id == case_id)
        .order_by(Document.id.asc(), Document.version.desc())
        .all()
    )
    db.commit()
    return [
        CaseDocumentOut(
            id=doc.id,
            version=doc.version,
            document_date=doc.document_date,
            patient_id=doc.patient_id,
            case_id=doc.case_id,
        )
        for doc in docs
    ]


@router.post("/{case_id}/actions", response_model=ActionResponse)
def post_action(
    case_id: str,
    body: ActionRequest,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> ActionResponse:
    case = (
        db.query(Case)
        .filter(Case.workspace_id == ctx.workspace_id, Case.id == case_id)
        .one_or_none()
    )
    if case is None:
        raise AppError(
            code="not_found",
            message=f"Case '{case_id}' was not found in this guest session.",
            status_code=404,
            request_id=body.request_id,
        )
    authorize(
        db,
        ctx,
        action="case.act",
        resource_type="Case",
        resource_id=case.id,
        patient_id=case.patient_id,
    )
    return apply_action(
        db,
        workspace_id=ctx.workspace_id,
        case=case,
        request=body,
        role=ctx.membership_role,
    )

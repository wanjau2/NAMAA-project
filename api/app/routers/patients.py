from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import EvaluationRequest, EvaluationResult
from app.security.context import TrustedRequestContext
from app.security.deps import get_trusted_context
from app.services.evaluations import run_evaluation

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


@router.post("/{patient_id}/evaluations", response_model=EvaluationResult)
def evaluate_patient_endpoint(
    patient_id: str,
    body: EvaluationRequest | None = None,
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> EvaluationResult:
    pathway = body.pathway if body else None
    return run_evaluation(
        db,
        workspace_id=ctx.workspace_id,
        patient_id=patient_id,
        pathway=pathway,
        ctx=ctx,
    )

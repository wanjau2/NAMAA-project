from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_workspace_id
from app.schemas import DemoResetOut, DemoSessionOut
from app.services.demo import ensure_workspace, reset_workspace

router = APIRouter(prefix="/api/v1/demo", tags=["demo"])


@router.post("/sessions", response_model=DemoSessionOut)
def create_session(db: Session = Depends(get_db)) -> DemoSessionOut:
    ws = ensure_workspace(db)
    return DemoSessionOut(session_id=ws.id, role=ws.role)  # type: ignore[arg-type]


@router.post("/reset", response_model=DemoResetOut)
def reset_session(
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> DemoResetOut:
    ensure_workspace(db, workspace_id)
    count = reset_workspace(db, workspace_id)
    return DemoResetOut(session_id=workspace_id, cases_restored=count)
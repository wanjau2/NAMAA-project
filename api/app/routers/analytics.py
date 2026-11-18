from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import require_workspace
from app.models import Workspace
from app.schemas import AnalyticsOverview
from app.services.analytics import build_overview

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(
    workspace: Workspace = Depends(require_workspace),
    db: Session = Depends(get_db),
) -> AnalyticsOverview:
    return build_overview(db, workspace.id)
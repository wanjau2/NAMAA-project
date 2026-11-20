from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import AnalyticsOverview
from app.security.context import TrustedRequestContext
from app.security.deps import get_trusted_context
from app.security.enforce import authorize
from app.services.analytics import build_overview, build_segments

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverview)
def analytics_overview(
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> AnalyticsOverview:
    authorize(db, ctx, action="analytics.read", resource_type="AnalyticsRelease", resource_id="overview")
    result = build_overview(db, ctx.workspace_id)
    db.commit()
    return result


@router.get("/segments")
def analytics_segments(
    ctx: TrustedRequestContext = Depends(get_trusted_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    authorize(db, ctx, action="analytics.read", resource_type="AnalyticsRelease", resource_id="segments")
    result = build_segments(db, ctx.workspace_id)
    db.commit()
    return result
from fastapi import Depends, Header, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import Workspace
from app.services.demo import ensure_workspace


def get_workspace_id(
    x_namaa_session: str | None = Header(default=None, alias="X-Namaa-Session"),
    session: str | None = Query(
        default=None,
        description="Guest session id for EventSource (cannot set custom headers).",
    ),
) -> str:
    workspace_id = x_namaa_session or session
    if not workspace_id:
        raise AppError(
            code="unauthorized",
            message=(
                "Missing X-Namaa-Session header (or session query param for SSE). "
                "Create a guest session first."
            ),
            status_code=401,
        )
    return workspace_id


def get_role(
    x_namaa_role: str | None = Header(default=None, alias="X-Namaa-Role"),
    role: str | None = Query(
        default=None,
        description="Simulated role for EventSource (cannot set custom headers).",
    ),
    x_namaa_service_token: str | None = Header(
        default=None, alias="X-Namaa-Service-Token"
    ),
) -> str:
    chosen = x_namaa_role or role
    allowed = {"coordinator", "clinical_reviewer", "population_analyst"}
    if x_namaa_service_token and not chosen:
        return "service"
    if not chosen:
        raise AppError(
            code="invalid_role",
            message=(
                "Missing X-Namaa-Role header (or role query param for SSE). "
                "Do not assume coordinator."
            ),
            status_code=400,
        )
    if chosen not in allowed:
        raise AppError(
            code="invalid_role",
            message=f"Unknown simulated role '{chosen}'.",
            status_code=400,
        )
    return chosen


def require_workspace(
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> Workspace:
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        # Auto-provision on first use so a pasted session id from docs still works.
        ws = ensure_workspace(db, workspace_id)
    return ws
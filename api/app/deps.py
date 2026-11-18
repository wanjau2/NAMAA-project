from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import AppError
from app.models import Workspace
from app.services.demo import ensure_workspace


def get_workspace_id(
    x_namaa_session: str | None = Header(default=None, alias="X-Namaa-Session"),
) -> str:
    if not x_namaa_session:
        raise AppError(
            code="unauthorized",
            message="Missing X-Namaa-Session header. Create a guest session first.",
            status_code=401,
        )
    return x_namaa_session


def get_role(
    x_namaa_role: str | None = Header(default=None, alias="X-Namaa-Role"),
) -> str:
    role = x_namaa_role or "coordinator"
    allowed = {"coordinator", "clinical_reviewer", "population_analyst"}
    if role not in allowed:
        raise AppError(
            code="invalid_role",
            message=f"Unknown simulated role '{role}'.",
            status_code=400,
        )
    return role


def require_workspace(
    workspace_id: str = Depends(get_workspace_id),
    db: Session = Depends(get_db),
) -> Workspace:
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        # Auto-provision on first use so a pasted session id from docs still works.
        ws = ensure_workspace(db, workspace_id)
    return ws
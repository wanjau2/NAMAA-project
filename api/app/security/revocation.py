"""Principal revocation checks used at claim, disclosure, and trusted-context build."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import PrincipalRevocation


def is_revoked(db: Session, *, workspace_id: str, principal_id: str | None) -> bool:
    if not principal_id:
        return False
    row = (
        db.query(PrincipalRevocation)
        .filter(
            PrincipalRevocation.workspace_id == workspace_id,
            PrincipalRevocation.principal_id == principal_id,
            PrincipalRevocation.active.is_(True),
        )
        .one_or_none()
    )
    return row is not None


def assert_not_revoked(db: Session, *, workspace_id: str, principal_id: str | None) -> None:
    if is_revoked(db, workspace_id=workspace_id, principal_id=principal_id):
        raise AppError(
            code="forbidden",
            message="Principal has been revoked; processing and disclosure are blocked.",
            status_code=403,
            field_errors={"reason_code": "principal_revoked"},
        )

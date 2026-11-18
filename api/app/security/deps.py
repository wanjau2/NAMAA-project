from __future__ import annotations

import os
import secrets

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_role, get_workspace_id, require_workspace
from app.errors import AppError
from app.models import Workspace
from app.security.constants import DEFAULT_SERVICE_TOKEN, SERVICE_TOKEN_ENV
from app.security.context import TrustedRequestContext, build_trusted_context
from app.security.enforce import new_request_id


def _expected_service_token() -> str:
    return os.getenv(SERVICE_TOKEN_ENV, DEFAULT_SERVICE_TOKEN)


def require_service_or_session(
    x_namaa_service_token: str | None = Header(default=None, alias="X-Namaa-Service-Token"),
    workspace_id: str = Depends(get_workspace_id),
) -> tuple[str, bool]:
    """Returns (workspace_id, is_service). Service token authenticates workers."""
    if x_namaa_service_token:
        expected = _expected_service_token()
        if not secrets.compare_digest(x_namaa_service_token, expected):
            raise AppError(
                code="unauthorized",
                message="Invalid service token.",
                status_code=401,
            )
        return workspace_id, True
    return workspace_id, False


def get_trusted_context(
    workspace: Workspace = Depends(require_workspace),
    role: str = Depends(get_role),
    x_namaa_request_id: str | None = Header(default=None, alias="X-Namaa-Request-Id"),
    x_namaa_service_token: str | None = Header(default=None, alias="X-Namaa-Service-Token"),
    x_namaa_purpose: str | None = Header(default=None, alias="X-Namaa-Purpose"),
    db: Session = Depends(get_db),
) -> TrustedRequestContext:
    is_service = False
    if x_namaa_service_token:
        expected = _expected_service_token()
        if not secrets.compare_digest(x_namaa_service_token, expected):
            raise AppError(
                code="unauthorized",
                message="Invalid service token.",
                status_code=401,
            )
        is_service = True
        role = "service"

    return build_trusted_context(
        db,
        workspace=workspace,
        role=role,
        request_id=x_namaa_request_id or new_request_id(),
        user_type="service" if is_service else "guest",
        purpose_of_use=x_namaa_purpose,
    )

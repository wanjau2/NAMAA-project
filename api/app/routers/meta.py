from fastapi import APIRouter

from app.workflow.actions import ACTION_ROLES, ACTIONS

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get("/actions")
def list_actions() -> dict:
    """Supported action names and role requirements for Mark's client."""
    return {
        "actions": [
            {
                "id": spec.id,
                "role": spec.role,
                "required_fields": [f.name for f in spec.fields if f.required],
            }
            for spec in ACTIONS.values()
        ],
        "roles": sorted(set(ACTION_ROLES.values())),
        "mutation_envelope": {
            "action": "ActionId",
            "expected_revision": "int",
            "request_id": "string (idempotency key)",
            "data": "object",
        },
        "error_shape": {
            "code": "string",
            "message": "string",
            "field_errors": "object",
            "request_id": "string | null",
        },
    }
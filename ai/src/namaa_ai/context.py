"""Optional Relate boundary. No graph process, queries, synchronization or inference."""
from datetime import datetime

from .contracts import VerifiedContext


class VerifiedContextAdapter:
    def __init__(self, *, enabled: bool = False):
        self.enabled = enabled

    def accept(self, context: VerifiedContext, *, workspace_id: str, patient_reference: str,
               permission_revision: str, generation_id: str, now: datetime) -> dict:
        if not self.enabled:
            raise ValueError("verified_context_disabled")
        if not context.authorized or not context.source_verified or context.state != "current":
            raise ValueError("context_not_authorized_and_current")
        if (context.workspace_id, context.patient_reference, context.permission_revision, context.generation_id) != (
                workspace_id, patient_reference, permission_revision, generation_id):
            raise ValueError("context_scope_or_generation_mismatch")
        if not context.built_at <= context.verified_at <= now < context.expires_at:
            raise ValueError("context_stale_or_invalid_time")
        for record in context.records:
            if (not record.authorized or not record.source_verified or record.patient_reference != patient_reference
                    or not context.built_at <= record.verified_at <= context.verified_at
                    or record.source_last_updated > record.verified_at):
                raise ValueError("unverified_context_record")
        return {"context": context.model_dump(mode="json"),
                "exhaustive": False, "absence_claims_allowed": False,
                "notice": "Source-linked context in the checked scope only; empty results mean unknown."}

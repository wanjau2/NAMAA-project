"""Relate hints must cross a fresh authoritative backend verification boundary."""
from datetime import datetime, timezone
from typing import Callable, Literal, Protocol

import httpx

from .contracts import Contract, ContextItem, RelateCandidateBatch, VerifiedContext
from .relate import VerifiedCandidateAdapter


class RelateResolution(Contract):
    state: Literal["verified", "unknown"]
    items: tuple[ContextItem, ...] = ()
    refresh: Literal["not_required", "requested", "failed"]
    absence_claims_allowed: Literal[False] = False


class CandidateVerifier(Protocol):
    async def __call__(self, *, workspace_id: str, patient_reference: str,
                       references: tuple[str, ...]) -> VerifiedContext:
        """Reauthorize session scope and re-read current HAPI versions, never the index."""
        ...


class RefreshRequester(Protocol):
    async def __call__(self, *, workspace_id: str, patient_reference: str) -> None:
        """Idempotently enqueue a refresh for authorized session scope only."""
        ...


class RelateResolver:
    """No graph writes or arbitrary queries; refresh is a backend queue callback.

    Scope arguments come from the authenticated backend session. Even an empty
    or stale batch is rechecked. Unknown results expose no candidate references.
    """
    def __init__(self, verify: CandidateVerifier, request_refresh: RefreshRequester, *,
                 enabled: bool = False, clock: Callable[[], datetime] | None = None):
        self.verify, self.request_refresh, self.enabled = verify, request_refresh, enabled
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    async def resolve(self, batch: RelateCandidateBatch, *, workspace_id: str,
                      patient_reference: str, permission_revision: str) -> RelateResolution:
        if not self.enabled:
            raise ValueError("relate_resolver_disabled")
        batch = RelateCandidateBatch.model_validate(batch.model_dump())
        scoped = (batch.state == "current" and batch.workspace_id == workspace_id
                  and batch.patient_reference == patient_reference
                  and batch.permission_revision == permission_revision)
        candidates = tuple(c for c in batch.candidates if c.patient_reference == patient_reference) if scoped else ()
        references = tuple(sorted({ref for c in candidates for ref in c.supporting_references}))
        try:
            verified = await self.verify(workspace_id=workspace_id,
                patient_reference=patient_reference, references=references)
            # Callback is invoked per resolution, including repeated identical hints.
            items = VerifiedCandidateAdapter(enabled=True).resolve(batch, verified,
                workspace_id=workspace_id, patient_reference=patient_reference,
                permission_revision=permission_revision, generation_id=batch.generation_id, now=self.clock())
            available = {item.source.reference for item in items}
            if (scoped and candidates and len(candidates) == len(batch.candidates)
                    and set(references).issubset(available)):
                return RelateResolution(state="verified", items=items, refresh="not_required")
        except (ValueError, PermissionError, OSError, httpx.HTTPError):
            pass  # No sensitive exception text or graph snippets escape.
        try:
            await self.request_refresh(workspace_id=workspace_id, patient_reference=patient_reference)
        except (ValueError, PermissionError, OSError, httpx.HTTPError):
            return RelateResolution(state="unknown", refresh="failed")
        return RelateResolution(state="unknown", refresh="requested")

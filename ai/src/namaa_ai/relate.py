"""Relate candidate boundary; no graph client or query language."""
from hashlib import sha256
from typing import Protocol

from .context import VerifiedContextAdapter
from .contracts import ContextItem, RelateCandidateBatch, VerifiedContext


class FixedRelateOperations(Protocol):
    """Backend operation interface. Implementations expose named parameterized calls only."""

    def family_history_candidates(self, *, workspace_id: str, patient_reference: str,
                                  limit: int) -> RelateCandidateBatch: ...

    def care_plan_candidates(self, *, workspace_id: str, patient_reference: str,
                             limit: int) -> RelateCandidateBatch: ...


class VerifiedCandidateAdapter:
    """Resolve graph hints only to records already verified in the backend envelope.

    Relate supplies references, not text. Only source text from the current
    VerifiedContext may continue to assembly. Pass enabled=False at a
    composition boundary that must not disclose graph-derived text.
    """

    def __init__(self, *, enabled: bool = True):
        self.enabled = enabled

    def resolve(self, batch: RelateCandidateBatch, verified: VerifiedContext, *,
                workspace_id: str, patient_reference: str, permission_revision: str,
                generation_id: str, now) -> tuple[ContextItem, ...]:
        if not self.enabled:
            raise ValueError("relate_candidate_adapter_disabled")
        VerifiedContextAdapter(enabled=True).accept(
            verified, workspace_id=workspace_id, patient_reference=patient_reference,
            permission_revision=permission_revision, generation_id=generation_id, now=now,
        )
        if (batch.state != "current" or
                (batch.workspace_id, batch.patient_reference, batch.permission_revision, batch.generation_id) !=
                (workspace_id, patient_reference, permission_revision, generation_id)):
            return ()

        # Graph paths cannot grant access. Every referenced resource must already
        # occur in the fresh backend-authorized context for this patient/scope.
        by_reference = {
            record.source.reference: record
            for record in verified.records
            if record.authorized and record.source_verified and record.patient_reference == patient_reference
        }
        allowed = set(by_reference)
        refs: set[str] = set()
        for candidate in batch.candidates:
            if candidate.patient_reference != patient_reference:
                continue
            if set(candidate.supporting_references).issubset(allowed):
                refs.update(candidate.supporting_references)
        return tuple(
            ContextItem(
                item_id="relate-" + sha256(
                    f"{record.source.reference}|{record.source.version}|{verified.generation_id}".encode()
                ).hexdigest()[:24],
                source=record.source,
                patient_reference=record.patient_reference,
                tier="relational",
                source_last_updated=record.source_last_updated,
                verified_at=record.verified_at,
                permission_revision=verified.permission_revision,
                generation_id=verified.generation_id,
                authorized=record.authorized,
                source_verified=record.source_verified,
                reviewed=record.reviewed,
                text=record.text,
                offset_start=record.offset_start,
                offset_end=record.offset_end,
            )
            for record in verified.records if record.source.reference in refs
        )

"""Session-bound bridges to the synthetic API; no local authorization fallback.

Review and evaluation mutations are sent once. The API owns persistence, CAS,
reviewer identity, and commit status. A successful review is not a HAPI commit.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StrictBool, TypeAdapter, model_validator

from .context import VerifiedContextAdapter
from .contracts import (ContextItem, ExtractionProposal, ExtractionRequest, LogicalId,
                        RelateCandidateBatch, ReviewCommand, ReviewDecision, RuleEvaluation, VerifiedContext)
from .handoff import prepare_rule_handoff
from .relate import VerifiedCandidateAdapter
from .security import AuthorizationDenied, BackendHttpClient, TrustedContext


def _id(value: str) -> str:
    # Validate before interpolating a path; never accept paths/URLs from a payload.
    logical_id = TypeAdapter(LogicalId).validate_python(value)
    if logical_id in {".", ".."}:
        raise ValueError("invalid_backend_path_id")
    return logical_id


class BackendExtractionJob(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)
    job_id: str
    document_id: str
    document_version: int | str
    state: Literal["queued", "running", "succeeded", "failed", "cancelled", "timed_out"]
    proposals: tuple[ExtractionProposal, ...] = ()

    @model_validator(mode="after")
    def proposals_match_source(self):
        if self.proposals and self.state != "succeeded":
            raise ValueError("proposals_before_success")
        for proposal in self.proposals:
            if (proposal.source_document_id != self.document_id or
                    proposal.source_document_version != str(self.document_version)):
                raise ValueError("proposal_source_mismatch")
        return self


class BackendRuleResult(BaseModel):
    """Persist rule_evaluation; legacy fields are only a UI compatibility view."""
    model_config = ConfigDict(extra="allow", frozen=True)
    patient_id: str
    rule_evaluation: RuleEvaluation
    legacy_flag_status: Literal["gap", "needs_review", "no_gap"] | None
    api_compatibility: Literal["current_api_outcome_supported", "api_outcome_extension_required"]

    @model_validator(mode="after")
    def lossless_projection(self):
        handoff = prepare_rule_handoff(self.rule_evaluation)
        if self.rule_evaluation.patient_reference != f"Patient/{self.patient_id}":
            raise ValueError("evaluation_patient_mismatch")
        if (self.legacy_flag_status, self.api_compatibility) != (
                handoff.legacy_flag_status, handoff.api_compatibility):
            raise ValueError("evaluation_projection_mismatch")
        return self


class BackendReviewResult(ReviewDecision):
    """Validate the canonical decision while retaining API envelope extensions.

    Commit/outbox metadata is preserved in model_extra, without interpreting it
    as proof of a HAPI transaction. The wire contract awaits deployment validation.
    """
    model_config = ConfigDict(extra="allow", frozen=True, validate_default=True)
    resulting_proposal_version: int = Field(ge=2, strict=True)

    @model_validator(mode="after")
    def decision_matches_command(self):
        expected_state = {"accept": "accepted", "correct": "corrected", "reject": "rejected"}[self.command.action]
        if self.state != expected_state:
            raise ValueError("review_state_mismatch")
        if self.resulting_proposal_version != self.command.expected_proposal_version + 1:
            raise ValueError("review_version_mismatch")
        if (self.fact is None) != (self.command.action == "reject"):
            raise ValueError("review_fact_state_mismatch")
        if self.fact is not None and self.fact.review != self.command:
            raise ValueError("review_fact_command_mismatch")
        return self


class BackendVerifiedContext(VerifiedContext):
    """Explicit API envelope extensions; canonical context remains strict."""
    exhaustive: StrictBool
    absence_claims_allowed: StrictBool
    policy_adapter: Literal["synthetic_guest_v1"]
    production_authorization: StrictBool
    source_versions: dict[str, str] = Field(default_factory=dict)
    notice: str | None = None

    @model_validator(mode="after")
    def synthetic_non_exhaustive(self):
        if self.exhaustive or self.absence_claims_allowed or self.production_authorization:
            raise ValueError("invalid_verified_context_guarantees")
        return self

    def canonical(self) -> VerifiedContext:
        return VerifiedContext.model_validate(self.model_dump(include=set(VerifiedContext.model_fields)))


class BackendApiClient(BackendHttpClient):
    """Use X-Namaa-Session plus optional service token / simulated role headers."""

    async def fetch(self, *, context: TrustedContext, patient_id: str, source_id: str) -> ExtractionRequest:
        """Source-provider implementation for AuthorizedExtractionPipeline."""
        response = await self._request("GET", f"/api/v1/documents/{_id(source_id)}",
                                       request_id=context.request_id)
        data = response.json()
        if (data.get("id") != source_id or data.get("patient_id") != patient_id or
                patient_id not in context.patient_ids or
                context.workspace_id != self.headers["X-Namaa-Session"]):
            raise AuthorizationDenied()
        return ExtractionRequest(
            request_id=f"source-{uuid4().hex}", workspace_id=context.workspace_id,
            patient_reference=f"Patient/{patient_id}", source_id=source_id,
            source_version=str(data["version"]),
            source_date=datetime.fromisoformat(data["document_date"]).date(), note_text=data["text"],
        )

    async def extraction_job(self, job_id: str) -> BackendExtractionJob:
        """One snapshot read; use the API SSE stream for ongoing progress."""
        context = await self.trusted_context()
        response = await self._request("GET", f"/api/v1/extractions/{_id(job_id)}",
                                       request_id=context.request_id)
        job = BackendExtractionJob.model_validate(response.json())
        if job.job_id != job_id:
            raise ValueError("extraction_job_mismatch")
        for proposal in job.proposals:
            if (proposal.workspace_id != context.workspace_id or
                    proposal.patient_reference.removeprefix("Patient/") not in context.patient_ids):
                raise AuthorizationDenied()
        return job

    async def review(self, command: ReviewCommand, *,
                     proposal: ExtractionProposal | None = None) -> BackendReviewResult:
        """Send once and bind the typed response to the submitted command.

        Only an explicit caller-selected ReviewCommand triggers this operation.
        Authorization, reviewer binding, idempotency and version conflicts belong
        to the endpoint. Never interpret a 2xx response as proof of a HAPI write.
        """
        if proposal is not None and (proposal.id, proposal.version) != (
                command.proposal_id, command.expected_proposal_version):
            raise ValueError("review_proposal_mismatch")
        if proposal is not None and proposal.workspace_id != self.headers["X-Namaa-Session"]:
            raise AuthorizationDenied()
        response = await self._request("POST", f"/api/v1/facts/{_id(command.proposal_id)}/review",
                                       json=command.model_dump(mode="json"), request_id=command.request_id)
        result = BackendReviewResult.model_validate(response.json())
        if result.command != command:
            raise ValueError("review_response_command_mismatch")
        if proposal is not None and result.fact is not None and result.fact.proposal != proposal:
            raise ValueError("review_response_proposal_mismatch")
        return result

    async def evaluate(self, patient_id: str, *, pathway: str | None = None) -> BackendRuleResult:
        response = await self._request("POST", f"/api/v1/patients/{_id(patient_id)}/evaluations",
                                       json={} if pathway is None else {"pathway": pathway})
        result = BackendRuleResult.model_validate(response.json())
        if result.patient_id != patient_id:
            raise ValueError("evaluation_patient_mismatch")
        return result

    async def verified_context(self, *, patient_id: str, context: TrustedContext,
                               generation_id: str | None = None,
                               relate_hints: list[dict[str, str]] | None = None) -> VerifiedContext:
        response = await self._request("POST", "/api/v1/security/verified-context",
            request_id=context.request_id, json={"patient_id": _id(patient_id),
                "generation_id": generation_id, "relate_hints": relate_hints or []})
        verified = BackendVerifiedContext.model_validate(response.json()).canonical()
        VerifiedContextAdapter(enabled=True).accept(
            verified, workspace_id=context.workspace_id, patient_reference=f"Patient/{patient_id}",
            permission_revision=context.permission_revision,
            generation_id=generation_id or verified.generation_id, now=datetime.now(timezone.utc))
        return verified

    async def _relate_context(self, operation: str, *, patient_id: str, limit: int) -> tuple[ContextItem, ...]:
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid_relate_limit")
        context = await self.trusted_context()
        response = await self._request("GET", f"/api/v1/relate/{operation}",
            request_id=context.request_id, params={"patient_id": _id(patient_id), "limit": limit})
        batch = RelateCandidateBatch.model_validate(response.json())
        # Treat discovery solely as hints. Even an empty/stale batch goes through
        # the authoritative verification endpoint; no graph text is disclosed.
        scoped = (batch.state == "current" and batch.workspace_id == context.workspace_id and
                  batch.patient_reference == f"Patient/{patient_id}" and
                  batch.permission_revision == context.permission_revision)
        references = sorted({ref for candidate in batch.candidates
                             if scoped and candidate.patient_reference == f"Patient/{patient_id}"
                             for ref in candidate.supporting_references})
        hints = [dict(zip(("resource_type", "logical_id"), ref.split("/"))) for ref in references]
        verified = await self.verified_context(patient_id=patient_id, context=context,
                                               generation_id=batch.generation_id, relate_hints=hints)
        return VerifiedCandidateAdapter(enabled=True).resolve(
            batch, verified, workspace_id=context.workspace_id, patient_reference=f"Patient/{patient_id}",
            permission_revision=context.permission_revision, generation_id=batch.generation_id,
            now=datetime.now(timezone.utc))

    async def family_history_context(self, patient_id: str, *, limit: int = 20) -> tuple[ContextItem, ...]:
        return await self._relate_context("family-history", patient_id=patient_id, limit=limit)

    async def care_plan_context(self, patient_id: str, *, limit: int = 20) -> tuple[ContextItem, ...]:
        return await self._relate_context("care-plans", patient_id=patient_id, limit=limit)

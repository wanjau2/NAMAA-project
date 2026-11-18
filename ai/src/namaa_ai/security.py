"""Fail-closed AI processing boundaries for Ismail's backend-minted security context.

The backend route is an AuthZEN-shaped application adapter, not a claim of
OpenID AuthZEN wire conformance. Decisions are never cached.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictBool


class TrustedContext(BaseModel):
    """Parsed only from GET /api/v1/security/context, never request body claims."""
    model_config = ConfigDict(extra="allow", frozen=True)
    request_id: str
    user_id: str
    user_type: str
    service_id: str
    workspace_id: str
    membership_role: str
    membership_active: StrictBool
    patient_ids: tuple[str, ...]
    care_relationships: tuple[dict[str, str], ...] = ()
    caregiver_authority: dict[str, str] = Field(default_factory=dict)
    purpose_of_use: str
    resource_sensitivity: str
    restrictions: tuple[str, ...] = ()
    approved_model_destination: str
    policy_adapter: str
    policy_revision: str
    permission_revision: str
    production_authorization: StrictBool
    decision_binding: str

    @classmethod
    def from_backend(cls, payload: dict[str, Any]) -> "TrustedContext":
        ctx = cls.model_validate(payload)
        # Guest context is always marked simulated; reject mismatched metadata.
        if ctx.policy_adapter != "synthetic_guest_v1" or ctx.production_authorization:
            raise ValueError("backend_security_context_not_approved")
        if ctx.user_type == "guest" and not ctx.user_id.startswith("guest:"):
            raise ValueError("backend_security_context_invalid_principal")
        return ctx


class PolicyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subject_id: str
    action: str
    resource_type: str
    resource_id: str
    patient_id: str


class PolicyDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: str
    policy_revision: str | None = None
    permission_revision: str | None = None
    decision_id: str | None = None
    policy_adapter: str | None = None
    production_authorization: bool | None = None
    reason_code: str = "policy_indeterminate"


class PolicyDecisionClient(Protocol):
    async def decide(self, *, context: TrustedContext, request: PolicyRequest) -> PolicyDecision: ...


class BackendSecurityClient(Protocol):
    async def trusted_context(self) -> TrustedContext: ...
    async def decide(self, *, context: TrustedContext, request: PolicyRequest) -> PolicyDecision: ...
    async def emit(self, event: "AuditEvent") -> None: ...


class BackendHttpClient:
    """Bridge to the API's context, PDP, and protected audit endpoints.

    Provide the authenticated session headers at construction. Service tokens
    stay in this backend process and are never placed in model payloads.
    """
    def __init__(self, api_base_url: str, headers: dict[str, str], *, transport=None):
        url = urlsplit(api_base_url)
        if url.scheme != "https" and url.hostname not in {"localhost", "127.0.0.1", "testserver"}:
            raise ValueError("backend_api_url_must_use_https")
        if not url.netloc or url.username or url.password or url.query or url.fragment:
            raise ValueError("invalid_backend_api_url")
        if any(k.lower() in {"authorization", "x-namaa-service-token"} and not v for k, v in headers.items()):
            raise ValueError("invalid_backend_auth_header")
        self.base, self.headers, self.transport = api_base_url.rstrip("/"), dict(headers), transport

    @classmethod
    def from_env(cls, headers: dict[str, str], *, transport=None):
        base = os.getenv("NAMAA_API_BASE_URL")
        if not base:
            raise RuntimeError("backend security service configuration is required; access defaults to deny")
        return cls(base, headers, transport=transport)

    async def _client(self):
        return httpx.AsyncClient(transport=self.transport, timeout=httpx.Timeout(5),
                                 follow_redirects=False, trust_env=False)

    async def trusted_context(self) -> TrustedContext:
        async with await self._client() as client:
            response = await client.get(self.base + "/api/v1/security/context", headers=self.headers)
        response.raise_for_status()
        return TrustedContext.from_backend(response.json())

    async def decide(self, *, context: TrustedContext, request: PolicyRequest) -> PolicyDecision:
        body = {"subject": {"type": "user", "id": context.user_id},
                "action": {"name": request.action},
                "resource": {"type": request.resource_type, "id": request.resource_id,
                             "workspace_id": context.workspace_id, "patient_id": request.patient_id},
                "context": {"purpose_of_use": context.purpose_of_use,
                            "model_destination": context.approved_model_destination,
                            "request_id": context.request_id, "patient_id": request.patient_id}}
        try:
            async with await self._client() as client:
                response = await client.post(self.base + "/api/v1/authz/evaluation", json=body,
                                             headers=self.headers)
            if response.status_code != 200:
                return PolicyDecision(outcome="indeterminate", reason_code="pdp_unavailable")
            data = response.json()
            meta = data.get("context") if type(data) is dict else None
            if (type(data) is not dict or type(data.get("decision")) is not bool or
                    type(meta) is not dict or not meta.get("decision_id") or
                    meta.get("policy_adapter") != "synthetic_guest_v1" or
                    meta.get("production_authorization") is not False):
                return PolicyDecision(outcome="indeterminate", reason_code="pdp_invalid_decision")
            allowed = data["decision"] and meta.get("decision_value") == "Permit"
            outcome = "allow" if allowed else "deny"
            return PolicyDecision(outcome=outcome, decision_id=meta["decision_id"],
                                  policy_revision=meta.get("policy_revision"),
                                  permission_revision=meta.get("permission_revision"),
                                  policy_adapter=meta.get("policy_adapter"),
                                  production_authorization=meta.get("production_authorization"),
                                  reason_code=meta.get("reason_code") or "pdp_denied")
        except (httpx.HTTPError, ValueError, KeyError):
            return PolicyDecision(outcome="indeterminate", reason_code="pdp_unavailable")

    async def emit(self, event: "AuditEvent") -> None:
        body = {"event_type": event.event_type, "action": event.action,
                "resource_type": event.resource_type, "resource_id": event.resource_id,
                "patient_id": event.patient_id, "job_id": event.job_id,
                "decision": event.outcome, "decision_id": event.decision_id,
                "source_versions": dict(event.source_versions), "model_revision": event.model_revision,
                "prompt_version": event.prompt_version, "reviewer_id": event.reviewer_reference,
                "reason_code": event.reason_code,
                "detail": {"initiating_user": event.initiating_user,
                           "executing_service": event.executing_service,
                           "permission_revision": event.permission_revision}}
        async with await self._client() as client:
            response = await client.post(self.base + "/api/v1/audit/events", json=body,
                                         headers=self.headers)
        response.raise_for_status()


@dataclass(frozen=True)
class LocalSyntheticPolicy:
    """Deterministic test policy; explicit allowlist and fail-closed default."""
    allow: frozenset[tuple[str, str]] = frozenset()
    policy_revision: str = "synthetic-policy-v1"
    permission_revision: str = "permissions-v1"

    async def decide(self, *, context: TrustedContext, request: PolicyRequest) -> PolicyDecision:
        ok_scope = (request.subject_id == context.user_id and
                    request.patient_id in context.patient_ids and
                    context.membership_active is True and bool(context.workspace_id))
        if request.action == "review.apply" and context.membership_role not in {"clinical_reviewer", "service"}:
            ok_scope = False
        if request.action == "model.dispatch" and context.approved_model_destination not in {
                "offline_fixture", "medgemma_hf_endpoint"}:
            ok_scope = False
        if (request.action in {"note.retrieve", "proposal.disclose", "excerpt.display"}
                and request.patient_id.startswith("pat-synthetic-1")
                and context.caregiver_authority.get(request.patient_id) not in {"verified_caregiver", "self"}
                and context.membership_role != "clinical_reviewer"):
            ok_scope = False
        permitted = ok_scope and (request.action, context.purpose_of_use) in self.allow
        return PolicyDecision(outcome="allow" if permitted else "deny",
                              policy_revision=self.policy_revision,
                              permission_revision=self.permission_revision,
                              decision_id=f"local-{uuid4().hex[:12]}",
                              policy_adapter="synthetic_test_v1", production_authorization=False,
                              reason_code="synthetic_allowlist" if permitted else "default_deny")


class AuthorizationDenied(PermissionError):
    def __init__(self):
        super().__init__("access_denied")
        self.code = "access_denied"


class AuditEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    request_id: str
    job_id: str | None = None
    initiating_user: str
    executing_service: str
    workspace_id: str
    resource_type: str
    resource_id: str
    patient_id: str
    action: str
    purpose_of_use: str
    outcome: str
    policy_revision: str
    permission_revision: str
    decision_id: str | None = None
    reason_code: str
    source_versions: tuple[str, ...] = ()
    model_revision: str | None = None
    prompt_version: str | None = None
    reviewer_reference: str | None = None
    timestamp: float = Field(default_factory=time.time)
    event_type: str = "ai.security.boundary"


class AuditSink(Protocol):
    async def emit(self, event: AuditEvent) -> None: ...


class SecurityEnforcer:
    """Fresh backend decision and audit at every boundary; no decision cache."""
    def __init__(self, policy: PolicyDecisionClient, audit: AuditSink):
        self.policy, self.audit = policy, audit

    async def require(self, *, context: TrustedContext, action: str, resource_type: str,
                      resource_id: str, patient_id: str, job_id: str | None = None,
                      source_versions: tuple[str, ...] = (), model_revision: str | None = None,
                      prompt_version: str | None = None, reviewer_reference: str | None = None) -> PolicyDecision:
        decision: PolicyDecision
        valid = (context.membership_active is True and patient_id in context.patient_ids and
                 bool(context.purpose_of_use and context.policy_revision and context.permission_revision) and
                 context.policy_adapter == "synthetic_guest_v1" and not context.production_authorization)
        if not valid:
            decision = PolicyDecision(outcome="deny", policy_revision=context.policy_revision,
                                      permission_revision=context.permission_revision,
                                      reason_code="trusted_context_incomplete")
        else:
            try:
                decision = await self.policy.decide(context=context, request=PolicyRequest(
                    subject_id=context.user_id, action=action, resource_type=resource_type,
                    resource_id=resource_id, patient_id=patient_id))
            except Exception:
                decision = PolicyDecision(outcome="indeterminate", reason_code="pdp_unavailable")
        permitted = (decision.outcome == "allow" and decision.policy_revision == context.policy_revision and
                     decision.permission_revision == context.permission_revision and
                     decision.production_authorization is False and
                     decision.policy_adapter in {"synthetic_guest_v1", "synthetic_test_v1"} and
                     bool(decision.decision_id))
        outcome = "allow" if permitted else ("deny" if decision.outcome == "deny" else "error")
        event = AuditEvent(request_id=context.request_id, job_id=job_id,
                           initiating_user=context.user_id, executing_service=context.service_id,
                           workspace_id=context.workspace_id, resource_type=resource_type,
                           resource_id=resource_id, patient_id=patient_id, action=action,
                           purpose_of_use=context.purpose_of_use, outcome=outcome,
                           policy_revision=context.policy_revision, permission_revision=context.permission_revision,
                           decision_id=decision.decision_id, reason_code=decision.reason_code,
                           source_versions=source_versions, model_revision=model_revision,
                           prompt_version=prompt_version, reviewer_reference=reviewer_reference)
        try:
            await self.audit.emit(event)
        except Exception:
            # Audit failure fails closed; never disclose a successful operation without evidence.
            raise AuthorizationDenied() from None
        if not permitted:
            raise AuthorizationDenied()
        return decision


class AuthorizedExtractionPipeline:
    """Enforces source-read, separate model dispatch, and post-inference disclosure."""
    def __init__(self, enforcer: SecurityEnforcer, source_provider, adapter):
        self.enforcer, self.source_provider, self.adapter = enforcer, source_provider, adapter

    async def run(self, *, context: TrustedContext, patient_id: str, source_id: str,
                  job_id: str | None = None):
        await self.enforcer.require(context=context, action="note.retrieve", resource_type="DocumentReference",
                                    resource_id=source_id, patient_id=patient_id, job_id=job_id)
        request = await self.source_provider.fetch(context=context, patient_id=patient_id, source_id=source_id)
        if request.workspace_id != context.workspace_id or request.patient_reference != f"Patient/{patient_id}":
            raise AuthorizationDenied()
        await self.enforcer.require(context=context, action="model.dispatch", resource_type="DocumentReference",
                                    resource_id=source_id, patient_id=patient_id, job_id=job_id,
                                    source_versions=(request.source_version,))
        # Dispatch is the irreversibility boundary: a later revocation cannot recall bytes already sent.
        result = await self.adapter.extract(request)
        await self.enforcer.require(context=context, action="proposal.disclose", resource_type="DocumentReference",
                                    resource_id=source_id, patient_id=patient_id, job_id=job_id,
                                    source_versions=(request.source_version,), model_revision=result.model.model_revision,
                                    prompt_version=result.model.prompt_version)
        return result

    async def authorize_excerpt(self, *, context: TrustedContext, patient_id: str, source_id: str,
                                source_version: str, exporting: bool = False):
        """Call immediately before source quotes enter a response or export."""
        return await self.enforcer.require(context=context,
            action="excerpt.export" if exporting else "excerpt.display",
            resource_type="DocumentReference", resource_id=source_id, patient_id=patient_id,
            source_versions=(source_version,))

    async def retrieve_verified_context(self, *, context: TrustedContext, patient_id: str,
                                        patient_reference: str, fetch, job_id: str | None = None):
        """Fixed backend operation only; caller must not offer arbitrary graph queries."""
        await self.enforcer.require(context=context, action="context.retrieve", resource_type="Patient",
                                    resource_id=patient_reference, patient_id=patient_id, job_id=job_id)
        return await fetch(patient_id=patient_id, workspace_id=context.workspace_id)


async def apply_review_authorized(*, enforcer: SecurityEnforcer, context: TrustedContext,
                                  request, proposal, command, current_version: int, reviewed_at,
                                  job_id: str | None = None):
    """The authenticated backend invokes this after binding command to its session.

    A text claim of clinician approval has no authority. Durable CAS and reviewer
    identity validation remain backend responsibilities.
    """
    await enforcer.require(context=context, action="review.apply", resource_type="DocumentReference",
                           resource_id=proposal.source_document_id,
                           patient_id=proposal.patient_reference.removeprefix("Patient/"),
                           source_versions=(proposal.source_document_version,),
                           reviewer_reference=command.reviewer_reference, job_id=job_id)
    from .review import apply_review

    class PermitThisBackendDecision:
        def require_review(self, received_command, received_proposal):
            if received_command != command or received_proposal != proposal:
                raise AuthorizationDenied()

    return apply_review(request, proposal, command, current_version=current_version,
                        reviewed_at=reviewed_at, authorizer=PermitThisBackendDecision())

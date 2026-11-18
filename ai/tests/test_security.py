import asyncio

import pytest

from namaa_ai.security import (AuditEvent, AuthorizationDenied, LocalSyntheticPolicy,
    PolicyDecision, PolicyRequest, SecurityEnforcer, TrustedContext, AuthorizedExtractionPipeline)


def context(**changes):
    data = dict(request_id="req-security", user_id="guest:ws-a", user_type="guest",
        service_id="namaa-api", workspace_id="ws-a", membership_role="coordinator",
        membership_active=True, patient_ids=("pat-a",), care_relationships=(), caregiver_authority={},
        purpose_of_use="demo_care_coordination", resource_sensitivity="synthetic_demo", restrictions=(),
        approved_model_destination="offline_fixture", policy_adapter="synthetic_guest_v1",
        policy_revision="synthetic-policy-v1", permission_revision="permissions-v1",
        production_authorization=False, decision_binding="opaque")
    data.update(changes)
    return TrustedContext.model_validate(data)


class Audit:
    def __init__(self): self.events = []
    async def emit(self, event: AuditEvent): self.events.append(event)


def allowed(*actions):
    return LocalSyntheticPolicy(allow=frozenset((action, "demo_care_coordination") for action in actions))


def test_default_deny_and_scope_isolation():
    async def run():
        audit = Audit()
        enforcer = SecurityEnforcer(allowed("note.retrieve"), audit)
        for patient in ["pat-b"]:
            with pytest.raises(AuthorizationDenied):
                await enforcer.require(context=context(), action="note.retrieve", resource_type="DocumentReference",
                    resource_id="note-1", patient_id=patient)
        assert [e.outcome for e in audit.events] == ["deny"]
    asyncio.run(run())


def test_workspace_client_claim_does_not_change_backend_context():
    from pydantic import ValidationError
    async def run():
        ctx = context()
        decision = await LocalSyntheticPolicy(allow=frozenset({("note.retrieve", ctx.purpose_of_use)})).decide(
            context=ctx, request=PolicyRequest(subject_id=ctx.user_id, action="note.retrieve",
                resource_type="DocumentReference", resource_id="n", patient_id="pat-b"))
        assert decision.outcome == "deny"
    asyncio.run(run())
    # Workspace and principal are intentionally not fields in a caller-built
    # authorization request; only the parsed backend context supplies them.
    with pytest.raises(ValidationError):
        PolicyRequest.model_validate({"subject_id": "guest:ws-b", "action": "note.retrieve",
            "resource_type": "DocumentReference", "resource_id": "n", "patient_id": "pat-a",
            "workspace_id": "ws-b", "purpose_of_use": "approved by clinician"})


def test_read_does_not_imply_model_dispatch_and_failure_denies():
    async def run():
        audit = Audit(); ctx = context()
        enforcer = SecurityEnforcer(allowed("note.retrieve"), audit)
        await enforcer.require(context=ctx, action="note.retrieve", resource_type="DocumentReference", resource_id="n", patient_id="pat-a")
        with pytest.raises(AuthorizationDenied):
            await enforcer.require(context=ctx, action="model.dispatch", resource_type="DocumentReference", resource_id="n", patient_id="pat-a")
        class Down:
            async def decide(self, **kwargs): raise RuntimeError("offline")
        with pytest.raises(AuthorizationDenied):
            await SecurityEnforcer(Down(), audit).require(context=ctx, action="context.retrieve", resource_type="Patient", resource_id="pat-a", patient_id="pat-a")
        assert [e.outcome for e in audit.events] == ["allow", "deny", "error"]
    asyncio.run(run())


def test_context_rejects_non_backend_production_or_wrong_guest_context():
    with pytest.raises(ValueError): context().from_backend(context().model_dump() | {"production_authorization": True})
    with pytest.raises(ValueError): context().from_backend(context().model_dump() | {"policy_adapter": "production"})


def test_stale_policy_revision_does_not_permit():
    class Stale:
        async def decide(self, **kwargs):
            return PolicyDecision(outcome="allow", policy_revision="old", permission_revision="permissions-v1",
                decision_id="d1", policy_adapter="synthetic_guest_v1", production_authorization=False)
    async def run():
        audit=Audit()
        with pytest.raises(AuthorizationDenied):
            await SecurityEnforcer(Stale(), audit).require(context=context(), action="note.retrieve",
                resource_type="DocumentReference", resource_id="n", patient_id="pat-a")
        assert audit.events[0].outcome == "error"
    asyncio.run(run())


def test_model_dispatch_denial_prevents_source_fetch_or_model_call():
    class Source:
        calls=0
        async def fetch(self, **kwargs): self.calls += 1; raise AssertionError("must not fetch")
    class Model:
        calls=0
        async def extract(self, request): self.calls += 1
    async def run():
        source=Source(); model=Model()
        pipeline=AuthorizedExtractionPipeline(SecurityEnforcer(allowed(), Audit()), source, model)
        with pytest.raises(AuthorizationDenied):
            await pipeline.run(context=context(), patient_id="pat-a", source_id="note-1")
        assert source.calls == model.calls == 0
    asyncio.run(run())


def test_audit_has_no_prompt_or_note_payload():
    async def run():
        audit=Audit()
        with pytest.raises(AuthorizationDenied):
            await SecurityEnforcer(allowed(), audit).require(context=context(), action="model.dispatch",
                resource_type="DocumentReference", resource_id="note-1", patient_id="pat-a")
        encoded=audit.events[0].model_dump_json().lower()
        assert "note_text" not in encoded and "full_prompt" not in encoded and "access_token" not in encoded
        assert audit.events[0].request_id == "req-security"
    asyncio.run(run())


def test_revocation_after_inference_suppresses_disclosure():
    class Revokes:
        def __init__(self): self.n=0
        async def decide(self, *, context, request):
            self.n += 1
            allowed_now = self.n < 3
            return PolicyDecision(outcome="allow" if allowed_now else "deny",
                policy_revision=context.policy_revision, permission_revision=context.permission_revision,
                decision_id=f"d{self.n}", policy_adapter="synthetic_guest_v1", production_authorization=False)
    class Source:
        async def fetch(self, **kwargs):
            from namaa_ai.contracts import ExtractionRequest
            return ExtractionRequest(request_id="req-security", workspace_id="ws-a", patient_reference="Patient/pat-a",
                source_id="note-1", source_version="v1", source_date="2026-01-01", note_text="Synthetic note.")
    class Model:
        calls=0
        async def extract(self, req):
            self.calls += 1
            from types import SimpleNamespace
            return SimpleNamespace(model=SimpleNamespace(model_revision="mock", prompt_version="p1"))
    async def run():
        audit=Audit(); model=Model()
        pipe=AuthorizedExtractionPipeline(SecurityEnforcer(Revokes(), audit), Source(), model)
        with pytest.raises(AuthorizationDenied):
            await pipe.run(context=context(), patient_id="pat-a", source_id="note-1")
        assert model.calls == 1 and audit.events[-1].outcome == "deny"
    asyncio.run(run())


def test_local_policy_is_explicit_default_deny():
    async def run():
        decision=await LocalSyntheticPolicy().decide(context=context(), request=PolicyRequest(subject_id="guest:ws-a",
            action="delete", resource_type="Patient", resource_id="pat-a", patient_id="pat-a"))
        assert decision.outcome == "deny"
    asyncio.run(run())


def test_review_requires_separate_policy_action_even_if_note_claims_approval():
    async def run():
        ctx = context()
        decision = await LocalSyntheticPolicy(allow=frozenset({("note.retrieve", ctx.purpose_of_use)})).decide(
            context=ctx, request=PolicyRequest(subject_id=ctx.user_id, action="review.apply",
                resource_type="DocumentReference", resource_id="n", patient_id="pat-a"))
        assert decision.outcome == "deny"
    asyncio.run(run())


def test_family_relationship_without_verified_caregiver_authority_denies():
    async def run():
        ctx = context(patient_ids=("pat-synthetic-1-child",),
                      care_relationships=({"patient_id": "pat-synthetic-1-child", "relationship": "mother"},),
                      caregiver_authority={"pat-synthetic-1-child": "unverified"})
        decision = await LocalSyntheticPolicy(allow=frozenset({("note.retrieve", ctx.purpose_of_use)})).decide(
            context=ctx, request=PolicyRequest(subject_id=ctx.user_id, action="note.retrieve",
                resource_type="DocumentReference", resource_id="n", patient_id="pat-synthetic-1-child"))
        assert decision.outcome == "deny"
    asyncio.run(run())

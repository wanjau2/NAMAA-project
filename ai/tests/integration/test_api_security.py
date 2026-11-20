import asyncio
import json
from datetime import datetime, timezone

import httpx
import pytest

from namaa_ai.backend import BackendApiClient
from namaa_ai.contracts import ExtractionResult, ModelIdentity
from namaa_ai.security import (AuthorizationDenied, AuthorizedExtractionPipeline, PolicyRequest,
                               SecurityEnforcer, decode_authzen_response, encode_authzen_request)

pytestmark = pytest.mark.api_integration
PATIENT = "pat-synthetic-11"
DOCUMENT = "doc-synthetic-11"


def request_for(ctx, action="note.retrieve", patient=PATIENT):
    return PolicyRequest(subject_id=ctx.user_id, action=action, resource_type="DocumentReference",
                         resource_id=DOCUMENT, patient_id=patient)


def test_authzen_codec_against_real_api_responses(api_stack):
    async def run():
        backend = api_stack.backend
        ctx = await backend.trusted_context()
        assert ctx.policy_adapter == "synthetic_guest_v1" and ctx.production_authorization is False
        async with httpx.AsyncClient(transport=api_stack.transport, base_url=backend.base) as http:
            for action, patient, outcome in [("note.retrieve", PATIENT, "allow"),
                                            ("not.an.action", PATIENT, "deny"),
                                            ("note.retrieve", "foreign-patient", "deny")]:
                request = request_for(ctx, action, patient)
                response = await http.post("/api/v1/authz/evaluation", headers=backend.headers,
                                          json=encode_authzen_request(ctx, request))
                assert response.status_code == 200
                raw = response.json()
                decision = decode_authzen_response(raw)
                assert decision.outcome == outcome
                assert decision.decision_id == raw["context"]["decision_id"]
                assert decision.policy_revision == ctx.policy_revision
                assert decision.permission_revision == ctx.permission_revision
                assert (await backend.decide(context=ctx, request=request)).outcome == outcome
    asyncio.run(run())


def test_enforcer_posts_versioned_audit_with_request_correlation(api_stack):
    async def run():
        from app.models import AuditEvent
        backend = api_stack.backend
        ctx = await backend.trusted_context()
        enforcer = SecurityEnforcer(backend, backend)
        decisions = []
        for _ in range(2):
            decisions.append(await enforcer.require(context=ctx, action="note.retrieve",
                resource_type="DocumentReference", resource_id=DOCUMENT, patient_id=PATIENT,
                source_versions={f"DocumentReference/{DOCUMENT}": "opaque-v2"},
                model_revision="simulated-fixture-v1", prompt_version="extract-v1.0.1"))
        assert decisions[0].decision_id != decisions[1].decision_id
        with api_stack.db() as db:
            rows = db.query(AuditEvent).filter_by(event_type="ai.security.boundary").order_by(AuditEvent.pk).all()
            assert len(rows) == 2
            for row, decision in zip(rows, decisions):
                assert row.request_id == ctx.request_id
                assert row.workspace_id == ctx.workspace_id
                assert json.loads(row.source_versions_json) == {f"DocumentReference/{DOCUMENT}": "opaque-v2"}
                assert row.decision_id == decision.decision_id
                assert row.decision == "Permit"
                assert row.model_revision == "simulated-fixture-v1"
                assert "note_text" not in row.safe_detail_json
    asyncio.run(run())


def test_api_denies_review_role_foreign_scope_and_stale_decisions(api_stack):
    async def run():
        backend = BackendApiClient("http://testserver", dict(api_stack.headers, **{"X-Namaa-Role": "coordinator"}),
                                   transport=api_stack.transport)
        ctx = await backend.trusted_context()
        enforcer = SecurityEnforcer(backend, backend)
        for action, patient, context in [("review.apply", PATIENT, ctx),
                                         ("note.retrieve", "foreign-patient", ctx),
                                         ("note.retrieve", PATIENT, ctx.model_copy(update={"permission_revision": "old"}))]:
            with pytest.raises(AuthorizationDenied):
                await enforcer.require(context=context, action=action, resource_type="DocumentReference",
                                       resource_id=DOCUMENT, patient_id=patient)
    asyncio.run(run())


def test_service_token_and_session_are_checked_by_api(api_stack, monkeypatch):
    monkeypatch.setenv("NAMAA_SERVICE_TOKEN", "synthetic-test-service-token")
    async def run():
        for token, valid in [("wrong", False), ("synthetic-test-service-token", True)]:
            backend = BackendApiClient("http://testserver", dict(api_stack.headers, **{"X-Namaa-Service-Token": token}),
                                       transport=api_stack.transport)
            if valid:
                ctx = await backend.trusted_context()
                assert ctx.user_type == ctx.membership_role == "service"
            else:
                with pytest.raises(httpx.HTTPStatusError) as exc:
                    await backend.trusted_context()
                assert exc.value.response.status_code == 401
        async with httpx.AsyncClient(transport=api_stack.transport, base_url="http://testserver") as http:
            assert (await http.get("/api/v1/security/context")).status_code == 401
    asyncio.run(run())


def test_real_source_and_security_boundaries_surround_extraction(api_stack, monkeypatch):
    monkeypatch.setenv("NAMAA_SERVICE_TOKEN", "synthetic-extraction-test-token")
    class SimulatedModel:
        async def extract(self, request):
            assert request.source_id == DOCUMENT and request.source_version == "2"
            return ExtractionResult(status="no_supported_facts", model=ModelIdentity(
                model_revision="simulated-test", simulated=True), latency_ms=0, attempts=1, schema_valid=True)

    async def run():
        from app.models import AuditEvent
        backend = BackendApiClient("http://testserver", dict(api_stack.headers,
            **{"X-Namaa-Service-Token": "synthetic-extraction-test-token"}), transport=api_stack.transport)
        context = await backend.trusted_context()
        assert context.user_type == context.membership_role == "service"
        result = await AuthorizedExtractionPipeline(SecurityEnforcer(backend, backend), backend, SimulatedModel()).run(
            context=context, patient_id=PATIENT, source_id=DOCUMENT)
        assert result.model.simulated is True
        with api_stack.db() as db:
            rows = db.query(AuditEvent).filter_by(event_type="ai.security.boundary").order_by(AuditEvent.pk).all()
            assert [row.action for row in rows] == ["note.retrieve", "model.dispatch", "proposal.disclose"]
            assert json.loads(rows[-1].source_versions_json) == {f"DocumentReference/{DOCUMENT}": "2"}
    asyncio.run(run())


@pytest.mark.parametrize("role", ["coordinator", "clinical_reviewer"])
def test_human_extraction_cannot_dispatch_model(api_stack, role):
    class ForbiddenModel:
        async def extract(self, request):
            pytest.fail("A human principal must not dispatch the model")

    async def run():
        from app.models import AuditEvent
        backend = BackendApiClient("http://testserver", dict(api_stack.headers,
            **{"X-Namaa-Role": role}), transport=api_stack.transport)
        context = await backend.trusted_context()
        with pytest.raises(AuthorizationDenied):
            await AuthorizedExtractionPipeline(SecurityEnforcer(backend, backend), backend, ForbiddenModel()).run(
                context=context, patient_id=PATIENT, source_id=DOCUMENT)
        with api_stack.db() as db:
            rows = db.query(AuditEvent).filter_by(event_type="ai.security.boundary").order_by(AuditEvent.pk).all()
            assert [row.action for row in rows] == ["note.retrieve", "model.dispatch"]
            assert rows[-1].decision == "Deny"
    asyncio.run(run())


def test_audit_endpoint_failure_blocks_boundary(api_stack, monkeypatch):
    from app.errors import AppError
    from app.routers import security

    original = security.emit_audit
    def fail_client_audit(db, **kwargs):
        if kwargs["event_type"] == "ai.security.boundary":
            raise AppError(code="unavailable", message="Synthetic audit failure", status_code=503)
        return original(db, **kwargs)
    monkeypatch.setattr(security, "emit_audit", fail_client_audit)

    async def run():
        backend = api_stack.backend
        with pytest.raises(AuthorizationDenied):
            await SecurityEnforcer(backend, backend).require(context=await backend.trusted_context(),
                action="note.retrieve", resource_type="DocumentReference", resource_id=DOCUMENT, patient_id=PATIENT)
    asyncio.run(run())


@pytest.mark.parametrize("resource_type,link", [("Observation", "subject"), ("FamilyMemberHistory", "patient")])
def test_relate_hints_and_narrative_cannot_grant_patient_scope(api_stack, resource_type, link):
    async def run():
        from app.models import FhirResource
        backend = api_stack.backend
        ctx = await backend.trusted_context()
        now = datetime.now(timezone.utc).isoformat()
        with api_stack.db() as db:
            for logical_id, patient in [("allowed", PATIENT), ("foreign", "pat-synthetic-31")]:
                db.add(FhirResource(workspace_id=ctx.workspace_id, resource_type=resource_type,
                    logical_id=logical_id, version_id=1, updated_at=now,
                    body_json=json.dumps({"resourceType": resource_type, link: {"reference": f"Patient/{patient}"},
                                          "text": {"div": f"Narrative mentions Patient/{PATIENT}"}})))
            db.commit()
        verified = await backend.verified_context(patient_id=PATIENT, context=ctx,
            relate_hints=[{"resource_type": resource_type, "logical_id": "foreign"}])
        references = {record.source.reference for record in verified.records}
        assert f"{resource_type}/allowed" in references
        assert f"{resource_type}/foreign" not in references
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await backend.verified_context(patient_id="outside-workspace", context=ctx,
                relate_hints=[{"resource_type": resource_type, "logical_id": "allowed"}])
        assert exc.value.response.status_code == 403
    asyncio.run(run())

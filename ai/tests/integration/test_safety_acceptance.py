"""Consumer acceptance against the existing SQLite/FHIR-stub API, not live HAPI."""
import asyncio
from uuid import uuid4

import httpx
import pytest

pytestmark = pytest.mark.api_integration


def test_unreviewed_proposals_do_not_change_authoritative_evaluation(api_stack):
    async def run():
        from app.models import FhirResource, Proposal
        from app.services.extractions import advance_job, claim_queued_jobs

        backend = api_stack.backend
        ctx = await backend.trusted_context()
        async with httpx.AsyncClient(transport=api_stack.transport, base_url=backend.base,
                                    headers=api_stack.headers) as http:
            before = await http.post("/api/v1/patients/pat-synthetic-11/evaluations", json={})
            assert before.status_code == 200
            with api_stack.db() as db:
                fhir_before = db.query(FhirResource).filter_by(workspace_id=ctx.workspace_id).count()
            accepted = await http.post("/api/v1/documents/doc-synthetic-11/extractions")
            assert accepted.status_code == 202
            with api_stack.db() as db:
                jobs = claim_queued_jobs(db, worker_id="alfred-acceptance")
                assert len(jobs) == 1
                job = jobs[0]
                for _ in range(5):
                    if job.state in {"succeeded", "failed", "timed_out"}:
                        break
                    job = advance_job(db, job)
                assert job.state == "succeeded"
                proposals = db.query(Proposal).filter_by(workspace_id=ctx.workspace_id).all()
                assert proposals and all(p.review_state == "proposed" for p in proposals)
                assert db.query(FhirResource).filter_by(workspace_id=ctx.workspace_id).count() == fhir_before
            after = await http.post("/api/v1/patients/pat-synthetic-11/evaluations", json={})
            assert after.status_code == 200
            assert after.json()["rule_evaluation"] == before.json()["rule_evaluation"]
    asyncio.run(run())


@pytest.mark.parametrize("role,data", [
    ("clinical_reviewer", {"evidence_type": "Appointment", "evidence_reference": "Appointment/booked", "attestation": True}),
    ("clinical_reviewer", {"attestation": False}),
    ("coordinator", {"evidence_type": "Encounter", "evidence_reference": "Encounter/unverified", "attestation": True}),
])
def test_booking_alone_and_missing_reviewer_authority_cannot_close_case(api_stack, role, data):
    async def run():
        await api_stack.backend.trusted_context()
        async with httpx.AsyncClient(transport=api_stack.transport, base_url=api_stack.backend.base,
                                    headers=api_stack.headers | {"X-Namaa-Role": role}) as http:
            initial = await http.get("/api/v1/cases/case-0002")
            assert initial.status_code == 200
            assert initial.json()["stage"] == "booked"
            response = await http.post("/api/v1/cases/case-0002/actions", json={
                "action": "close_as_completed", "expected_revision": initial.json()["revision"],
                "request_id": str(uuid4()), "data": data})
            assert response.status_code in {403, 422}
            current = await http.get("/api/v1/cases/case-0002")
            assert current.json()["stage"] == "booked"
            assert current.json()["disposition"] != "completed"
            assert current.json()["revision"] == initial.json()["revision"]
    asyncio.run(run())


def test_api_small_cohort_hides_counts_and_denominators(api_stack):
    async def run():
        await api_stack.backend.trusted_context()
        async with httpx.AsyncClient(transport=api_stack.transport, base_url=api_stack.backend.base,
                                    headers=api_stack.headers) as http:
            response = await http.get("/api/v1/analytics/overview")
            assert response.status_code == 200
            for pathway in response.json()["pathways"]:
                for name in ("eligible", "invited", "booked", "attended", "completed", "declined"):
                    cell = pathway[name]
                    assert cell["suppressed"]
                    assert cell["numerator"] is cell["denominator"] is cell["value"] is None
    asyncio.run(run())

"""Opt-in acceptance checks against actual HTTP routes, with fresh guest sessions.

Missing configuration skips by default; --require-backend turns skips into errors.
These tests never substitute mock routes for an absent backend implementation.
"""
import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from namaa_ai.backend import BackendApiClient, BackendRuleResult
from namaa_ai.contracts import ReviewCommand, ReviewDecision
from namaa_ai.security import (PolicyRequest, SecurityEnforcer, decode_authzen_response,
                               encode_authzen_request)

OUTCOMES = ("gap_identified", "no_gap_identified_in_available_data", "needs_review", "not_eligible")


def configured(request, name):
    value = os.getenv(name)
    if not value:
        message = f"Set {name} for this synthetic backend acceptance check"
        if request.config.getoption("--require-backend"):
            pytest.fail(message, pytrace=False)
        pytest.skip(message)
    return value


@pytest.fixture
def live_url(request):
    url = configured(request, "NAMAA_AI_TEST_API_URL")
    BackendApiClient(url, {"X-Namaa-Session": "url-validation-only"})
    return url.rstrip("/")


async def new_session(url):
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as http:
        response = await http.post(url + "/api/v1/demo/sessions")
        response.raise_for_status()
    headers = {"X-Namaa-Session": response.json()["session_id"], "X-Namaa-Role": "clinical_reviewer"}
    if token := os.getenv("NAMAA_AI_TEST_SERVICE_TOKEN"):
        headers["X-Namaa-Service-Token"] = token
    backend = BackendApiClient(url, headers)
    # Confirm the synthetic context before any review/evaluation mutation.
    await backend.trusted_context()
    return backend


async def extraction_proposal(backend):
    response = await backend._request("POST", "/api/v1/documents/doc-synthetic-11/extractions")
    job_id = response.json()["job_id"]
    # Bounded fallback polling for acceptance checks; UI progress uses SSE.
    for _ in range(15):
        job = await backend.extraction_job(job_id)
        if job.state in {"succeeded", "failed", "cancelled", "timed_out"}:
            break
        await asyncio.sleep(2)
    assert job.state == "succeeded" and job.proposals, "Expected nested synthetic extraction proposals"
    candidates = [p for p in job.proposals if not any(issue.severity == "block" for issue in p.issues)]
    assert candidates, "Backend seed needs a source-valid proposal for review acceptance checks"
    return candidates[0]


def command_for(proposal, action):
    return ReviewCommand(request_id=f"review-{uuid4().hex}", proposal_id=proposal.id,
        expected_proposal_version=proposal.version, action=action,
        reviewer_reference=os.getenv("NAMAA_AI_TEST_REVIEWER") or "Practitioner/demo-reviewer",
        reason="Explicit review of a synthetic backend acceptance fixture",
        # Restate the source fact to exercise complete replacement serialization.
        # A changed-value correction is covered using the real AI review module in unit tests.
        correction=proposal.fact if action == "correct" else None,
        acknowledged_issues=tuple(issue.code for issue in proposal.issues if issue.severity == "review"))


@pytest.mark.live_security
def test_authzen_codec_against_live_responses(live_url):
    async def run():
        backend = await new_session(live_url)
        ctx = await backend.trusted_context()
        assert ctx.production_authorization is False and ctx.policy_adapter == "synthetic_guest_v1"
        for action, patient_id, outcome in [("note.retrieve", "pat-synthetic-11", "allow"),
                                            ("unknown.action", "pat-synthetic-11", "deny"),
                                            ("note.retrieve", "outside-workspace", "deny")]:
            policy_request = PolicyRequest(subject_id=ctx.user_id, action=action, resource_type="DocumentReference",
                                            resource_id="doc-synthetic-11", patient_id=patient_id)
            response = await backend._request("POST", "/api/v1/authz/evaluation",
                json=encode_authzen_request(ctx, policy_request), request_id=ctx.request_id)
            raw = response.json()
            parsed = decode_authzen_response(raw)
            assert parsed.outcome == outcome
            assert parsed.decision_id == raw["context"]["decision_id"]
            assert parsed.policy_revision == ctx.policy_revision
            assert parsed.permission_revision == ctx.permission_revision
        verified = await backend.verified_context(patient_id="pat-synthetic-11", context=ctx)
        assert verified.authorized and verified.source_verified
    asyncio.run(run())


@pytest.mark.live_security
def test_audit_boundary_links_its_own_backend_decision(live_url):
    async def run():
        backend = await new_session(live_url)
        ctx = await backend.trusted_context()
        decision = await SecurityEnforcer(backend, backend).require(context=ctx, action="note.retrieve",
            resource_type="DocumentReference", resource_id="doc-synthetic-11", patient_id="pat-synthetic-11",
            source_versions={"DocumentReference/doc-synthetic-11": "2"})
        rows = (await backend._request("GET", "/api/v1/audit/events")).json()
        boundary = [row for row in rows if row["event_type"] == "ai.security.boundary"
                    and row["request_id"] == ctx.request_id]
        assert len(boundary) == 1
        assert boundary[0]["decision_id"] == decision.decision_id, "Boundary event must expose its verified decision link"
        assert boundary[0]["decision"] in {"Permit", "allow"}
        assert boundary[0]["resource_id"] == "doc-synthetic-11"
        assert boundary[0]["patient_id"] == "pat-synthetic-11"
    asyncio.run(run())


@pytest.mark.live_bridges
@pytest.mark.parametrize("action", ["accept", "correct", "reject"])
def test_review_action_round_trip(live_url, action):
    async def run():
        backend = await new_session(live_url)
        proposal = await extraction_proposal(backend)
        command = command_for(proposal, action)
        result = await backend.review(command, proposal=proposal)
        assert result.command == command
        assert result.state == {"accept": "accepted", "correct": "corrected", "reject": "rejected"}[action]
        assert result.resulting_proposal_version == proposal.version + 1
        if result.fact:
            assert result.fact.proposal == proposal
            assert result.fact.fact == (command.correction or proposal.fact)
    asyncio.run(run())


@pytest.mark.live_bridges
def test_review_replay_and_conflicting_request_id(live_url):
    async def run():
        backend = await new_session(live_url)
        proposal = await extraction_proposal(backend)
        command = command_for(proposal, "accept")
        first = await backend.review(command, proposal=proposal)
        replay = await backend.review(command, proposal=proposal)
        fields = set(ReviewDecision.model_fields)
        assert first.model_dump(include=fields) == replay.model_dump(include=fields)
        altered = command.model_copy(update={"reason": "Different payload with the same request ID"})
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await backend.review(altered, proposal=proposal)
        assert exc.value.response.status_code == 409
    asyncio.run(run())


@pytest.mark.live_bridges
def test_review_stale_version_is_rejected(live_url):
    async def run():
        backend = await new_session(live_url)
        proposal = await extraction_proposal(backend)
        await backend.review(command_for(proposal, "reject"), proposal=proposal)
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await backend.review(command_for(proposal, "accept"), proposal=proposal)
        assert exc.value.response.status_code == 409
    asyncio.run(run())


@pytest.mark.live_bridges
def test_review_requires_reviewer_role(live_url):
    async def run():
        backend = await new_session(live_url)
        proposal = await extraction_proposal(backend)
        headers = dict(backend.headers)
        headers.pop("x-namaa-service-token", None)
        headers["x-namaa-role"] = "coordinator"
        coordinator = BackendApiClient(live_url, headers)
        with pytest.raises(httpx.HTTPStatusError) as exc:
            await coordinator.review(command_for(proposal, "reject"), proposal=proposal)
        assert exc.value.response.status_code == 403
    asyncio.run(run())


@pytest.mark.live_bridges
@pytest.mark.parametrize("patient_id", ["pat-synthetic-11", "pat-synthetic-31"])
def test_rule_response_retains_the_complete_canonical_payload(live_url, patient_id):
    async def run():
        backend = await new_session(live_url)
        response = await backend._request("POST", f"/api/v1/patients/{patient_id}/evaluations", json={})
        raw = response.json()
        parsed = BackendRuleResult.model_validate(raw)
        assert parsed.patient_id == patient_id
        assert parsed.rule_evaluation.simulated is True
        assert parsed.rule_evaluation.model_dump(mode="json") == raw["rule_evaluation"]
    asyncio.run(run())


@pytest.mark.live_bridges
@pytest.mark.parametrize("operation", ["family_history_context", "care_plan_context"])
def test_relate_discovery_and_verification(live_url, operation):
    async def run():
        backend = await new_session(live_url)
        records = await getattr(backend, operation)("pat-synthetic-11")
        assert all(record.patient_reference == "Patient/pat-synthetic-11"
                   and record.authorized and record.source_verified for record in records)
    asyncio.run(run())


@pytest.mark.live_rule_outcomes
@pytest.mark.parametrize("outcome", OUTCOMES)
def test_all_canonical_outcomes_from_backend_seed(live_url, request, outcome):
    fixture_path = configured(request, "NAMAA_AI_TEST_RULE_CASES")
    cases = json.loads(Path(fixture_path).read_text())
    assert set(cases) == set(OUTCOMES), "Supply a backend seed patient/pathway for every canonical outcome"
    case = cases[outcome]
    async def run():
        backend = await new_session(live_url)
        result = await backend.evaluate(case["patient_id"], pathway=case.get("pathway"))
        assert result.rule_evaluation.outcome == outcome
        assert result.rule_evaluation.simulated is True
        if outcome == "not_eligible":
            assert result.legacy_flag_status is None
    asyncio.run(run())

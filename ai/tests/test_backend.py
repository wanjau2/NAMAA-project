"""Wire unit tests for announced bridges; API integration lives in integration/."""
import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from namaa_ai.backend import BackendApiClient, BackendReviewResult
from namaa_ai.contracts import ReviewCommand
from namaa_ai.demo import DemoAuthorizer
from namaa_ai.review import apply_review
from namaa_ai.validation import check_fact
from namaa_ai.security import (AuthorizationDenied, BackendHttpClient, PolicyRequest,
                               decode_authzen_response, encode_authzen_request)
from test_security import context

EXAMPLES = Path(__file__).parents[1] / "examples"


def client(handler, *, workspace_id="ws-a"):
    return BackendApiClient("http://testserver", {"X-Namaa-Session": workspace_id, "X-Namaa-Role": "clinical_reviewer"},
                            transport=httpx.MockTransport(handler))


def test_session_is_required_even_with_service_token():
    with pytest.raises(ValueError, match="backend_session_required"):
        BackendHttpClient("http://testserver", {"X-Namaa-Service-Token": "test-token"})


def test_subject_is_not_silently_replaced_with_trusted_principal():
    with pytest.raises(ValueError, match="subject_principal_mismatch"):
        encode_authzen_request(context(), PolicyRequest(subject_id="other-user", action="note.retrieve",
            resource_type="DocumentReference", resource_id="n", patient_id="pat-a"))


@pytest.mark.parametrize("decision,value,expected", [
    (True, "Permit", "allow"), (False, "Deny", "deny"), (False, "Indeterminate", "indeterminate"),
    ("true", "Permit", "indeterminate"), (1, "Permit", "indeterminate"),
    (True, "Deny", "indeterminate"), (False, "Permit", "indeterminate"),
    (True, "unknown", "indeterminate"), (True, ["Permit"], "indeterminate"),
])
def test_authzen_boolean_and_decision_value_must_agree(decision, value, expected):
    payload = {"decision": decision, "context": {"decision_id": "d1", "decision_value": value,
        "policy_revision": "p1", "permission_revision": "v1", "policy_adapter": "synthetic_guest_v1",
        "production_authorization": False, "reason_code": "test"}}
    assert decode_authzen_response(payload).outcome == expected


@pytest.mark.parametrize("key,bad", [("decision_id", 1), ("permission_revision", None),
    ("policy_revision", ""), ("policy_adapter", "production"), ("production_authorization", 0),
    ("production_authorization", "false"), ("reason_code", [])])
def test_authzen_metadata_is_strict(key, bad):
    payload = {"decision": True, "context": {"decision_id": "d1", "decision_value": "Permit",
        "policy_revision": "p1", "permission_revision": "v1", "policy_adapter": "synthetic_guest_v1",
        "production_authorization": False, "reason_code": "test"}}
    payload["context"][key] = bad
    assert decode_authzen_response(payload).outcome == "indeterminate"


@pytest.mark.parametrize("status", [403, 409, 422, 503])
def test_review_sends_complete_command_once_and_preserves_errors(proposal, status):
    command = ReviewCommand(request_id="review-test", proposal_id=proposal.id, expected_proposal_version=proposal.version,
        action="accept", reviewer_reference="Practitioner/reviewer-1", reason="Reviewed source",
        acknowledged_issues=tuple(issue.code for issue in proposal.issues))
    calls = []
    def handle(request):
        calls.append(request)
        assert request.url.path == f"/api/v1/facts/{proposal.id}/review"
        assert json.loads(request.content) == command.model_dump(mode="json")
        assert request.headers["X-Namaa-Session"] == "ws-a"
        assert request.headers["X-Namaa-Request-Id"] == command.request_id
        return httpx.Response(status, json={"code": "test_error"})
    with pytest.raises(httpx.HTTPStatusError) as exc:
        asyncio.run(client(handle).review(command))
    assert exc.value.response.status_code == status and len(calls) == 1


def test_review_preserves_stub_commit_status(proposal):
    command = ReviewCommand(request_id="review-test", proposal_id=proposal.id, expected_proposal_version=1,
        action="reject", reviewer_reference="Practitioner/reviewer-1", reason="Explicit rejection")
    payload = {"command": command.model_dump(mode="json"), "state": "rejected", "fact": None,
               "resulting_proposal_version": 2, "commit": {"mode": "stub", "hapi_committed": False}}
    result = asyncio.run(client(lambda _: httpx.Response(200, json=payload),
                                workspace_id=proposal.workspace_id).review(command, proposal=proposal))
    assert isinstance(result, BackendReviewResult)
    assert result.model_dump(mode="json") == payload


def review_response(request_note, proposal, action):
    correction = proposal.fact.model_copy(update={"assertion": "historical"}) if action == "correct" else None
    issues = check_fact(request_note, correction or proposal.fact)[2]
    command = ReviewCommand(request_id=f"review-{action}", proposal_id=proposal.id, expected_proposal_version=1,
        action=action, reviewer_reference="Practitioner/demo-reviewer", reason="Checked the synthetic source",
        correction=correction, acknowledged_issues=tuple(issue.code for issue in issues))
    result = apply_review(request_note, proposal, command, current_version=1,
        reviewed_at=datetime.now(timezone.utc), authorizer=DemoAuthorizer())
    return command, result.model_dump(mode="json")


@pytest.mark.parametrize("action", ["accept", "correct", "reject"])
def test_review_validates_real_module_decisions_and_reuses_command_on_explicit_retry(request_note, proposal, action):
    command, payload = review_response(request_note, proposal, action)
    sent = []
    def handle(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json=payload)
    backend = client(handle, workspace_id=proposal.workspace_id)
    first = asyncio.run(backend.review(command, proposal=proposal))
    replay = asyncio.run(backend.review(command, proposal=proposal))
    assert first == replay and first.command == command
    assert sent == [command.model_dump(mode="json")] * 2
    assert first.resulting_proposal_version == 2
    assert (first.fact is None) == (action == "reject")
    if action == "correct":
        assert first.fact.fact == command.correction and first.fact.fact != proposal.fact


@pytest.mark.parametrize("mutation", ["empty", "version", "version_string", "state", "missing_fact",
    "request_id", "reviewer", "nested_command", "original_proposal", "rejected_with_fact"])
def test_review_rejects_incomplete_or_mismatched_response(request_note, proposal, mutation):
    command, payload = review_response(request_note, proposal, "accept")
    if mutation == "empty": payload = {}
    if mutation == "version": payload["resulting_proposal_version"] = 3
    if mutation == "version_string": payload["resulting_proposal_version"] = "2"
    if mutation == "state": payload["state"] = "corrected"
    if mutation == "missing_fact": payload["fact"] = None
    if mutation == "request_id": payload["command"]["request_id"] = "different-command"
    if mutation == "reviewer": payload["command"]["reviewer_reference"] = "Practitioner/other"
    if mutation == "nested_command": payload["fact"]["review"]["reason"] = "Different reason"
    if mutation == "original_proposal": payload["fact"]["proposal"]["workspace_id"] = "other-workspace"
    if mutation == "rejected_with_fact":
        payload["command"]["action"] = "reject"
        payload["state"] = "rejected"
    with pytest.raises(ValueError):
        asyncio.run(client(lambda _: httpx.Response(200, json=payload),
                           workspace_id=proposal.workspace_id).review(command, proposal=proposal))


def test_review_binds_rejected_response_to_submitted_command(proposal):
    command = ReviewCommand(request_id="review-test", proposal_id=proposal.id, expected_proposal_version=1,
        action="reject", reviewer_reference="Practitioner/reviewer-1", reason="Explicit rejection")
    payload = {"command": command.model_dump(mode="json") | {"proposal_id": "other-proposal"},
               "state": "rejected", "fact": None, "resulting_proposal_version": 2}
    with pytest.raises(ValueError, match="review_response_command_mismatch"):
        asyncio.run(client(lambda _: httpx.Response(200, json=payload)).review(command))


def test_review_checks_original_version_before_sending(proposal):
    command = ReviewCommand(request_id="review-test", proposal_id=proposal.id, expected_proposal_version=2,
        action="reject", reviewer_reference="Practitioner/reviewer-1", reason="Explicit rejection")
    def no_request(_):
        raise AssertionError("Mismatched proposal must not be sent")
    with pytest.raises(ValueError, match="review_proposal_mismatch"):
        asyncio.run(client(no_request).review(command, proposal=proposal))


def test_review_rejects_foreign_workspace_before_any_mutation(proposal):
    command = ReviewCommand(request_id="review-test", proposal_id=proposal.id, expected_proposal_version=1,
        action="reject", reviewer_reference="Practitioner/reviewer-1", reason="Explicit rejection")
    def no_request(_):
        raise AssertionError("Workspace mismatch must be rejected before sending review")
    with pytest.raises(AuthorizationDenied):
        asyncio.run(client(no_request, workspace_id="other-workspace").review(command, proposal=proposal))


def test_review_timeout_is_not_retried(proposal):
    command = ReviewCommand(request_id="review-test", proposal_id=proposal.id, expected_proposal_version=1,
        action="reject", reviewer_reference="Practitioner/reviewer-1", reason="Explicit rejection")
    calls = []
    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("synthetic timeout", request=request)
    with pytest.raises(httpx.ReadTimeout):
        asyncio.run(client(timeout).review(command))
    assert len(calls) == 1


@pytest.mark.parametrize("proposal_id", [".", ".."])
def test_review_rejects_url_dot_segments(proposal_id):
    command = ReviewCommand(request_id="review-test", proposal_id=proposal_id, expected_proposal_version=1,
        action="reject", reviewer_reference="Practitioner/reviewer-1", reason="Explicit rejection")
    def no_request(_):
        raise AssertionError("Invalid path must not be sent")
    with pytest.raises(ValueError, match="invalid_backend_path_id"):
        asyncio.run(client(no_request).review(command))


@pytest.mark.parametrize("variant", ["nested", "flat", "foreign"])
def test_extraction_requires_nested_scoped_proposals(proposal, variant):
    data = proposal.model_dump(mode="json") | {"workspace_id": "ws-a", "patient_reference": "Patient/pat-a"}
    if variant == "flat":
        data = {"id": proposal.id, **data["fact"]}
    elif variant == "foreign":
        data["workspace_id"] = "ws-b"
    def handle(request):
        if request.url.path == "/api/v1/security/context":
            return httpx.Response(200, json=context().model_dump(mode="json"))
        return httpx.Response(200, json={"job_id": "job-1", "document_id": proposal.source_document_id,
            "document_version": proposal.source_document_version, "state": "succeeded", "proposals": [data]})
    if variant == "nested":
        result = asyncio.run(client(handle).extraction_job("job-1"))
        assert result.proposals[0].model_dump(mode="json") == data
    else:
        with pytest.raises(ValidationError if variant == "flat" else AuthorizationDenied):
            asyncio.run(client(handle).extraction_job("job-1"))


@pytest.mark.parametrize("outcome,legacy", [("gap_identified", "gap"),
    ("no_gap_identified_in_available_data", "no_gap"), ("needs_review", "needs_review"), ("not_eligible", None)])
def test_evaluation_preserves_canonical_outcome_and_provenance(outcome, legacy):
    evaluation = json.loads((EXAMPLES / "rule-evaluation.json").read_text())
    evaluation.update(patient_reference="Patient/pat-a", outcome=outcome)
    payload = {"patient_id": "pat-a", "rule_evaluation": evaluation, "legacy_flag_status": legacy,
        "api_compatibility": "api_outcome_extension_required" if legacy is None else "current_api_outcome_supported"}
    def handle(request):
        assert request.url.path == "/api/v1/patients/pat-a/evaluations"
        return httpx.Response(200, json=payload)
    result = asyncio.run(client(handle).evaluate("pat-a"))
    assert result.rule_evaluation.model_dump(mode="json") == evaluation
    payload.pop("rule_evaluation")
    with pytest.raises(ValidationError):
        asyncio.run(client(handle).evaluate("pat-a"))


@pytest.mark.parametrize("mutation", ["patient", "nested_patient", "legacy", "compatibility", "missing_versions"])
def test_evaluation_rejects_lossy_or_inconsistent_handoffs(mutation):
    handoff = json.loads((EXAMPLES / "rule-evaluation-handoff.json").read_text())
    payload = {"patient_id": "demo-patient", "rule_evaluation": handoff["evaluation"],
               "legacy_flag_status": handoff["legacy_flag_status"], "api_compatibility": handoff["api_compatibility"]}
    if mutation == "patient": payload["patient_id"] = "other-patient"
    if mutation == "nested_patient": payload["rule_evaluation"]["patient_reference"] = "Patient/other-patient"
    if mutation == "legacy": payload["legacy_flag_status"] = "needs_review"
    if mutation == "compatibility": payload["api_compatibility"] = "api_outcome_extension_required"
    if mutation == "missing_versions": del payload["rule_evaluation"]["input_versions"]
    with pytest.raises(ValueError):
        asyncio.run(client(lambda _: httpx.Response(200, json=payload)).evaluate("demo-patient"))


@pytest.mark.parametrize("operation", ["family_history_context", "care_plan_context"])
@pytest.mark.parametrize("variant", ["valid", "empty", "foreign", "stale", "denied", "expired", "permission_changed",
    "foreign_batch_workspace", "unverified_reference", "mixed_support", "generation_changed", "patient_changed",
    "unauthorized", "unverified_record", "production", "string_authorized"])
def test_relate_always_verifies_before_disclosing(operation, variant):
    now = datetime.now(timezone.utc)
    batch = json.loads((EXAMPLES / "relate-candidates.json").read_text())
    batch.update(workspace_id="ws-a", patient_reference="Patient/pat-a")
    batch["candidates"][0].update(patient_reference="Patient/pat-a", supporting_references=["Observation/demo-observation"])
    verified = json.loads((EXAMPLES / "verified-context.json").read_text())
    verified.update(workspace_id="ws-a", patient_reference="Patient/pat-a", built_at=(now-timedelta(seconds=5)).isoformat(),
        verified_at=now.isoformat(), expires_at=(now+timedelta(minutes=1)).isoformat(),
        exhaustive=False, absence_claims_allowed=False, policy_adapter="synthetic_guest_v1", production_authorization=False)
    verified["records"][0].update(patient_reference="Patient/pat-a", verified_at=now.isoformat(),
                                  source_last_updated=(now-timedelta(seconds=3)).isoformat())
    if variant == "empty": batch["candidates"] = []
    if variant == "foreign": batch["candidates"][0]["patient_reference"] = "Patient/pat-b"
    if variant == "stale": batch["state"] = "stale"
    if variant == "expired": verified["expires_at"] = (now-timedelta(seconds=1)).isoformat()
    if variant == "permission_changed": verified["permission_revision"] = "permissions-v2"
    if variant == "foreign_batch_workspace": batch["workspace_id"] = "other-workspace"
    if variant == "unverified_reference": batch["candidates"][0]["supporting_references"] = ["Observation/unverified"]
    if variant == "mixed_support": batch["candidates"][0]["supporting_references"].append("Observation/unverified")
    if variant == "generation_changed": verified["generation_id"] = "generation-other"
    if variant == "patient_changed": verified["patient_reference"] = "Patient/pat-b"
    if variant == "unauthorized": verified["authorized"] = False
    if variant == "unverified_record": verified["records"][0]["source_verified"] = False
    if variant == "production": verified["production_authorization"] = True
    if variant == "string_authorized": verified["authorized"] = "true"
    calls = []
    def handle(request):
        calls.append((request.method, request.url.path))
        if request.url.path == "/api/v1/security/context":
            return httpx.Response(200, json=context().model_dump(mode="json"))
        if request.url.path.startswith("/api/v1/relate/"):
            assert request.url.params["patient_id"] == "pat-a"
            return httpx.Response(200, json=batch)
        assert request.url.path == "/api/v1/security/verified-context"
        body = json.loads(request.content)
        assert body["generation_id"] == batch["generation_id"]
        if variant in {"empty", "foreign", "stale", "foreign_batch_workspace"}: assert body["relate_hints"] == []
        return httpx.Response(403 if variant == "denied" else 200, json=verified)
    backend = client(handle)
    if variant in {"denied", "expired", "permission_changed", "generation_changed", "patient_changed",
                   "unauthorized", "unverified_record", "production", "string_authorized"}:
        with pytest.raises(httpx.HTTPStatusError if variant == "denied" else ValueError):
            asyncio.run(getattr(backend, operation)("pat-a"))
    else:
        result = asyncio.run(getattr(backend, operation)("pat-a"))
        assert len(result) == (1 if variant == "valid" else 0)
        if result: assert result[0].text == verified["records"][0]["text"]
    assert calls[-1] == ("POST", "/api/v1/security/verified-context")
    assert calls[1][1] == "/api/v1/relate/" + ("family-history" if operation == "family_history_context" else "care-plans")

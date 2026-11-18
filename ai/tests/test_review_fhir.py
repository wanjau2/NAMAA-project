from copy import deepcopy
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from namaa_ai.contracts import ExtractionRequest, ModelIdentity, ProposedFact, ReviewCommand
from namaa_ai.demo import DemoAuthorizer
from namaa_ai.fhir import local_mapping_checks, propose_transaction
from namaa_ai.review import ReviewError, apply_review
from namaa_ai.validation import make_proposals

NOW = datetime(2026, 11, 18, 9, tzinfo=timezone.utc)


def command(proposal, **changes):
    return ReviewCommand.model_validate(dict(request_id="review-1", proposal_id=proposal.id, expected_proposal_version=1,
                                            action="accept", reviewer_reference="Practitioner/demo-reviewer", reason="Checked exact source statement") | changes)


def review(req, prop, cmd, **kwargs):
    return apply_review(req, prop, cmd, current_version=kwargs.pop("current_version", 1), reviewed_at=NOW,
                        authorizer=kwargs.pop("authorizer", DemoAuthorizer()), **kwargs)


def test_review_authorization_and_versions(request_note, proposal):
    cmd = command(proposal)
    with pytest.raises(PermissionError):
        apply_review(request_note, proposal, cmd, current_version=1, reviewed_at=NOW)
    with pytest.raises(PermissionError):
        review(request_note, proposal, command(proposal, reviewer_reference="Practitioner/other"))
    with pytest.raises(ReviewError, match="stale_proposal_version"):
        review(request_note, proposal, cmd, current_version=2)
    req = ExtractionRequest.model_validate(request_note.model_dump() | {"source_version": "v2"})
    with pytest.raises(ReviewError, match="source_version_mismatch"):
        review(req, proposal, cmd)
    req = ExtractionRequest.model_validate(request_note.model_dump() | {"note_text": request_note.note_text + " changed"})
    with pytest.raises(ReviewError, match="source_version_mismatch"):
        review(req, proposal, cmd)


def test_reject_and_correct(request_note, proposal, fact):
    rejected = review(request_note, proposal, command(proposal, action="reject"))
    assert rejected.fact is None and rejected.resulting_proposal_version == 2
    with pytest.raises(TypeError):
        propose_transaction(proposal)
    with pytest.raises(ValidationError):
        command(proposal, action="correct")
    corrected = review(request_note, proposal, command(proposal, action="correct", correction=fact.model_dump()))
    assert corrected.state == "corrected"
    bad = fact.model_dump() | {"value_text": "Unsupported diagnosis"}
    with pytest.raises(ReviewError, match="source_validation_blocked"):
        review(request_note, proposal, command(proposal, action="correct", correction=bad))


def test_correction_repairs_attribution_without_bypassing_review(request_note, fact):
    text = "Mother has asthma."
    req = ExtractionRequest.model_validate(request_note.model_dump() | {"note_text": text})
    wrong = ProposedFact.model_validate(fact.model_dump() | {"concept": "family_condition", "excerpt": text, "value_text": text, "effective_date": None})
    prop = make_proposals(req, (wrong,), ModelIdentity(model_revision="simulated-fixture-v1", simulated=True))[0]
    with pytest.raises(ReviewError, match="source_validation_blocked"):
        review(req, prop, command(prop, acknowledged_issues=[i.code for i in prop.issues]))
    corrected = wrong.model_dump() | {"subject": "family_member", "relationship": "mother", "proposed_resource_type": "FamilyMemberHistory"}
    decision = review(req, prop, command(prop, action="correct", correction=corrected, acknowledged_issues=["missing_date"]))
    assert decision.fact.proposal.fact.subject == "patient"  # original is retained for audit
    assert decision.fact.fact.subject == "family_member"
    assert propose_transaction(decision.fact).bundle["entry"][0]["resource"]["resourceType"] == "FamilyMemberHistory"


def test_observation_and_provenance(request_note, proposal):
    accepted = review(request_note, proposal, command(proposal))
    transaction = propose_transaction(accepted.fact)
    r, p = [e["resource"] for e in transaction.bundle["entry"]]
    assert r["resourceType"] == "Observation" and r["effectiveDateTime"] == "2026-09-01"
    assert r["valueString"] == proposal.fact.value_text
    assert "coding" not in r["code"]
    assert p["entity"][0]["what"]["reference"].endswith("source-1/_history/v1")
    assert p["agent"][0]["who"]["reference"] == "Practitioner/demo-reviewer"
    assert p["agent"][1]["who"]["reference"] == "#model"
    assert {v["value"] for v in p["contained"][0]["version"]} == {"simulated-fixture-v1", "extract-v1.0.0"}
    assert transaction.validation.base_r4_validator.startswith("pending") and not transaction.validation.executable
    assert propose_transaction(accepted.fact).bundle == transaction.bundle


@pytest.mark.parametrize("assertion,text,positive", [
    ("present", "Mother has asthma.", True),
    ("absent", "Mother does not have asthma.", False),
    ("uncertain", "Mother may have asthma.", False),
    ("historical", "Mother has a history of asthma.", True),
])
def test_family_mapping_and_acknowledgments(request_note, assertion, text, positive):
    req = ExtractionRequest.model_validate(request_note.model_dump() | {"note_text": text})
    f = ProposedFact(concept="family_condition", value_text=text, subject="family_member", assertion=assertion,
                     effective_date=None, excerpt=text, proposed_resource_type="FamilyMemberHistory", relationship="mother")
    prop = make_proposals(req, (f,), ModelIdentity(model_revision="simulated-fixture-v1", simulated=True))[0]
    with pytest.raises(ReviewError, match="not_acknowledged"):
        review(req, prop, command(prop))
    decision = review(req, prop, command(prop, acknowledged_issues=[i.code for i in prop.issues]))
    r = propose_transaction(decision.fact).bundle["entry"][0]["resource"]
    assert r["resourceType"] == "FamilyMemberHistory"
    assert r["patient"]["reference"] == req.patient_reference
    assert ("condition" in r) == positive
    assert "effectiveDateTime" not in r


@pytest.mark.parametrize("mutation", ["status", "reference", "modifier", "request"])
def test_local_mapping_negative_checks(request_note, proposal, mutation):
    bundle = deepcopy(propose_transaction(review(request_note, proposal, command(proposal)).fact).bundle)
    r = bundle["entry"][0]["resource"]
    if mutation == "status": r["status"] = "approved"
    if mutation == "reference": r["subject"]["reference"] = "https://external.invalid/patient"
    if mutation == "modifier": r["modifierExtension"] = [{"url": "unknown"}]
    if mutation == "request": bundle["entry"][0]["request"]["method"] = "DELETE"
    with pytest.raises(ValueError): local_mapping_checks(bundle)

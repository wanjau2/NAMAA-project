import asyncio
from copy import deepcopy
from datetime import datetime, timezone

import pytest

from namaa_ai.adapters import MockAdapter
from namaa_ai.context import VerifiedContextAdapter
from namaa_ai.contracts import RuleSnapshot, VerifiedContext
from namaa_ai.demo import run_demo, simulated_snapshot
from namaa_ai.evaluation import evaluate_context_retrieval, evaluate_corpus
from namaa_ai.fhir import CONCEPT_TEXT
from namaa_ai.handoff import prepare_rule_handoff
from namaa_ai.rules import RULES, evaluate


def snapshot(rule_id, day="2026-09-01", assertion="present"):
    r = {"resourceType": "Observation", "id": "last-event", "status": "final",
         "subject": {"reference": "Patient/demo-patient"}, "code": {"text": CONCEPT_TEXT[RULES[rule_id][1]]},
         "valueString": "Fictional reviewed event", "effectiveDateTime": day,
         "component": [{"code": {"text": "Source assertion"}, "valueCodeableConcept": {"text": assertion}}]}
    return simulated_snapshot([r], rule_id=rule_id)


@pytest.mark.parametrize("rule_id", list(RULES))
def test_four_rule_outcomes_and_versions(rule_id):
    snap = snapshot(rule_id)
    result = evaluate(snap, rule_id)
    assert result.outcome == "gap_identified"
    assert result.rule_version == "synthetic-1.0.0" and len(result.input_versions) == 3
    assert result.simulated and result.synthetic_rule
    assert evaluate(snapshot(rule_id, "2026-11-10"), rule_id).outcome == "no_gap_identified_in_available_data"
    assert evaluate(simulated_snapshot([], rule_id=rule_id), rule_id).outcome == "needs_review"
    data = snap.model_dump()
    data["resources"][1]["resource"]["valueBoolean"] = False
    assert evaluate(RuleSnapshot.model_validate(data), rule_id).outcome == "not_eligible"


def test_backend_handoff_preserves_canonical_outcome_and_versions():
    gap = evaluate(snapshot("DEMO_WCV_01"), "DEMO_WCV_01")
    handoff = prepare_rule_handoff(gap)
    assert handoff.legacy_flag_status == "gap"
    assert handoff.evaluation == gap
    assert handoff.evaluation.input_versions == gap.input_versions

    data = snapshot("DEMO_WCV_01").model_dump()
    data["resources"][1]["resource"]["valueBoolean"] = False
    excluded = evaluate(RuleSnapshot.model_validate(data), "DEMO_WCV_01")
    handoff = prepare_rule_handoff(excluded)
    assert handoff.evaluation.outcome == "not_eligible"
    assert handoff.legacy_flag_status is None
    assert handoff.api_compatibility == "api_outcome_extension_required"


@pytest.mark.parametrize("change", ["unreviewed", "incomplete", "missing_date", "future", "conflict", "uncertain", "negated", "eligibility_conflict", "missing_eligibility", "duplicate_version"])
def test_rules_fail_closed(change):
    data = snapshot("DEMO_WCV_01").model_dump()
    event = data["resources"][2]["resource"]
    # Convert tuple to list for deliberate mutations.
    data["resources"] = list(data["resources"])
    if change == "unreviewed": data["resources"][2]["reviewed"] = False
    if change == "incomplete": data["complete_for_rule"] = False
    if change == "missing_date": event.pop("effectiveDateTime")
    if change == "future": event["effectiveDateTime"] = "2027-01-01"
    if change in {"uncertain", "negated"}: event["component"][0]["valueCodeableConcept"]["text"] = "uncertain" if change == "uncertain" else "absent"
    if change == "conflict":
        other = deepcopy(data["resources"][2]); other["resource"]["id"] = "conflict"; other["resource"]["effectiveDateTime"] = "2026-08-01"; data["resources"].append(other)
    if change == "eligibility_conflict":
        other = deepcopy(data["resources"][1]); other["resource"]["id"] = "other-card"; other["resource"]["valueBoolean"] = False; data["resources"].append(other)
    if change == "missing_eligibility": data["resources"].pop(1)
    if change == "duplicate_version":
        other = deepcopy(data["resources"][2]); other["resource"]["meta"]["versionId"] = "other-version"; data["resources"].append(other)
    assert evaluate(RuleSnapshot.model_validate(data), "DEMO_WCV_01").outcome == "needs_review"


def test_rules_scope_authority_and_due_boundary(proposal):
    with pytest.raises(TypeError): evaluate(proposal, "DEMO_WCV_01")
    data = snapshot("DEMO_WCV_01").model_dump()
    data["authorized"] = False
    with pytest.raises(PermissionError): evaluate(RuleSnapshot.model_validate(data), "DEMO_WCV_01")
    data["authorized"] = True
    data["resources"][2]["resource"]["subject"]["reference"] = "Patient/another"
    with pytest.raises(PermissionError): evaluate(RuleSnapshot.model_validate(data), "DEMO_WCV_01")
    data = snapshot("DEMO_WCV_01").model_dump()
    data["resources"][2]["resource"]["meta"].pop("versionId")
    with pytest.raises(ValueError, match="opaque version"): evaluate(RuleSnapshot.model_validate(data), "DEMO_WCV_01")
    data = snapshot("DEMO_WCV_01").model_dump()
    data["as_of"] = "2026-10-08"
    assert evaluate(RuleSnapshot.model_validate(data), "DEMO_WCV_01").outcome == "gap_identified"


def context():
    return VerifiedContext.model_validate(dict(workspace_id="demo", patient_reference="Patient/demo", generation_id="g1", mapping_version="m1",
        permission_revision="p1", built_at="2026-11-18T08:00:00Z", verified_at="2026-11-18T08:55:00Z", expires_at="2026-11-18T09:01:00Z",
        state="current", authorized=True, source_verified=True, completeness="unknown", checked_scope="Permitted journey resources", records=[]))


def accept_context(ctx, enabled=True, **changes):
    args = dict(workspace_id="demo", patient_reference="Patient/demo", permission_revision="p1", generation_id="g1", now=datetime(2026,11,18,9,tzinfo=timezone.utc))
    return VerifiedContextAdapter(enabled=enabled).accept(ctx, **(args | changes))


def test_context_default_enabled_and_can_be_disabled():
    with pytest.raises(ValueError, match="disabled"): accept_context(context(), enabled=False)
    out = accept_context(context())
    assert out["exhaustive"] is False and out["absence_claims_allowed"] is False


@pytest.mark.parametrize("changes", [{"state":"stale"}, {"state":"dirty"}, {"authorized":False}, {"source_verified":False},
                                      {"permission_revision":"p2"}, {"generation_id":"g2"}, {"workspace_id":"another"},
                                      {"expires_at":"2026-11-18T08:59:59Z"}])
def test_context_rejections(changes):
    with pytest.raises(ValueError): accept_context(VerifiedContext.model_validate(context().model_dump() | changes))


def test_context_record_checks():
    data = context().model_dump()
    record = dict(source={"reference":"Observation/demo", "version":"opaque-v1"}, patient_reference="Patient/demo",
                  source_last_updated="2026-11-18T08:30:00Z", verified_at="2026-11-18T08:55:00Z", authorized=True, source_verified=True, text="Verified source statement")
    data["records"] = [record]
    assert accept_context(VerifiedContext.model_validate(data))["context"]["records"]
    for changes in ({"source_verified": False}, {"authorized":False}, {"patient_reference":"Patient/other"}, {"verified_at":"2026-11-18T07:00:00Z"}):
        data["records"] = [record | changes]
        with pytest.raises(ValueError): accept_context(VerifiedContext.model_validate(data))


def test_evaluation_reports_denominators_and_failures(corpus):
    notes = corpus[:2]
    adapter = MockAdapter({n["request"]["note_text"]: n["expected"] for n in notes})
    report = asyncio.run(evaluate_corpus(notes, adapter))
    assert report["sample_size_notes"] == 2 and report["simulated"]
    assert report["fields"]["subject"]["precision"] == 1
    assert "NOT MedGemma quality" in report["notice"]
    report = asyncio.run(evaluate_corpus(notes, MockAdapter({})))
    assert report["schema_validity"]["valid"] == 0
    assert report["fields"]["subject"]["recall"] == 0
    assert report["fields"]["subject"]["precision"] is None
    assert report["latency_ms"]["sample_size"] == 2


def test_evaluation_detects_wrong_fields_and_duplicate_additions(corpus):
    note = corpus[0]
    wrong = note["expected"]["facts"][0] | {"assertion": "absent"}
    adapter = MockAdapter({note["request"]["note_text"]: {"facts": [wrong, wrong]}})
    report = asyncio.run(evaluate_corpus([note], adapter))
    assert report["fields"]["assertion"]["tp"] == 0
    assert report["fields"]["assertion"]["fp"] == 2
    assert report["fields"]["assertion"]["fn"] == 1
    assert report["unsupported_additions"]["count"] == 2
    assert report["outcomes"] == {"invalid_output": 1}


def test_context_evaluation_reports_split_and_sample_denominators():
    import json
    from pathlib import Path
    fixtures = json.loads((Path(__file__).parents[1] / "fixtures/context-queries.json").read_text())["queries"]
    dev = evaluate_context_retrieval([q for q in fixtures if q["split"] == "development"])
    held_out = evaluate_context_retrieval([q for q in fixtures if q["split"] == "held_out"])
    assert dev["simulated"] and dev["sample_size_queries"] == 20
    assert held_out["sample_size_queries"] == 20
    assert "not clinical relevance" in dev["notice"]
    assert 0 <= dev["mean_recall_at_k"] <= 1
    assert dev["splits"] == {"development": 20}
    assert held_out["splits"] == {"held_out": 20}


def test_vertical_slice():
    result = asyncio.run(run_demo())
    assert result["before_reviewed_commit"]["outcome"] == "needs_review"
    assert result["after_simulated_commit"]["outcome"] == "gap_identified"
    assert len(result["transaction_proposals"]) == 2
    assert all(t["simulated"] for t in result["transaction_proposals"])

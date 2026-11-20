"""Delayed care-plan writes and review backlogs must not change authoritative truth."""
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Barrier

import pytest

from app.config import get_settings
from app.fhir.gateway import compensate_uncertain
from app.models import Case, Command, FhirResource, Patient, Proposal
from app.schemas import ActionRequest
from app.services.outbox import process_entry, retry_dead_letter
from app.services.rule_snapshots import build_rule_snapshot, infer_pathway, pathway_rule_id
from app.workflow.engine import apply_action
from namaa_ai.fhir import CONCEPT_TEXT
from namaa_ai.rules import evaluate
from test_workflow_integrity import sessions, case, act, close  # isolated database fixture

NOW = "2026-11-20T09:00:00Z"


def approve(db):
    target = case(db)
    # Begin the fixture at the valid approval stage before progressing normally.
    target.stage = "identified"
    target.flag_status = "gap"
    db.commit()
    request_id = str(uuid.uuid4())
    apply_action(db, workspace_id="test", case=target, role="clinical_reviewer",
                 request=ActionRequest(action="approve_pathway", expected_revision=target.revision,
                                       request_id=request_id, data={"attestation": True}))
    from app.models import OutboxEntry
    command = db.query(Command).filter_by(workspace_id="test", request_id=request_id).one()
    return db.query(OutboxEntry).filter_by(id=command.outbox_id).one()


def progress_to_completion(db):
    act(db, "record_contact_preference", {"channel": "phone", "language": "en", "preferred_time": "morning"})
    act(db, "send_invitation", {"template": "wcv_invite_v1"})
    act(db, "book_appointment", {"appointment_time": "2026-11-20", "location": "Demo clinic"})
    act(db, "record_attendance", {"attended": "attended"})
    close(db)
    from app.models import OutboxEntry
    return db.query(OutboxEntry).filter_by(workspace_id="test", action="close_as_completed").one()


def plan(db):
    return db.query(FhirResource).filter_by(
        workspace_id="test", resource_type="CarePlan", logical_id="cp-case-0002"
    ).one()


@pytest.mark.parametrize("approval_state", ["pending", "processing", "compensating", "dead_lettered"])
def test_delayed_approval_never_overwrites_completed_plan(sessions, approval_state):
    with sessions() as db:
        old = approve(db)
        completion = progress_to_completion(db)
        process_entry(db, completion)
        db.commit()
        before = (plan(db).body_json, plan(db).version_id)
        old.state = approval_state
        if approval_state == "compensating":
            old.compensation_reason = "Unknown prior write outcome"
        db.commit()
        if approval_state == "dead_lettered":
            retry_dead_letter(db, workspace_id="test", outbox_id=old.id)
            db.commit()
        process_entry(db, old)
        db.commit()
        assert old.state == "dead_lettered"
        assert "superseded" in old.last_error.lower()
        assert (plan(db).body_json, plan(db).version_id) == before
        assert case(db).disposition == "completed"
        assert db.query(Command).filter_by(outbox_id=old.id).one().saga_state == "fhir_dead_lettered"
        # A manual retry must recheck freshness, not revive the old approval.
        retry_dead_letter(db, workspace_id="test", outbox_id=old.id)
        db.commit()
        process_entry(db, old)
        db.commit()
        assert old.state == "dead_lettered"
        assert (plan(db).body_json, plan(db).version_id) == before


def test_completion_request_supersedes_approval_before_worker_runs(sessions):
    with sessions() as db:
        old = approve(db)
        completion = progress_to_completion(db)
        process_entry(db, old)
        db.commit()
        assert old.state == "dead_lettered"
        assert "later care-plan command" in old.last_error
        process_entry(db, completion)
        db.commit()
        assert json.loads(plan(db).body_json)["status"] == "completed"


def test_reopening_does_not_revive_old_approval(sessions):
    with sessions() as db:
        old = approve(db)
        completion = progress_to_completion(db)
        process_entry(db, completion)
        db.commit()
        act(db, "reopen", {"reason": "New follow-up required"})
        process_entry(db, old)
        db.commit()
        assert old.state == "dead_lettered"
        assert case(db).stage == "follow_up"
        assert json.loads(plan(db).body_json)["status"] == "completed"


def test_delayed_approval_can_retry_after_ordinary_progress(sessions, monkeypatch):
    with sessions() as db:
        old = approve(db)
        monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "1")
        get_settings.cache_clear()
        process_entry(db, old)
        db.commit()
        assert old.state == "pending"
        act(db, "record_contact_preference", {"channel": "phone", "language": "en", "preferred_time": "morning"})
        act(db, "send_invitation", {"template": "wcv_invite_v1"})
        revision = case(db).revision
        monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "0")
        get_settings.cache_clear()
        process_entry(db, old)
        db.commit()
        assert old.state == "committed"
        assert json.loads(plan(db).body_json)["status"] == "active"
        assert case(db).revision == revision


def test_compensation_cannot_revoke_resource_owned_by_newer_write(sessions):
    with sessions() as db:
        old = approve(db)
        process_entry(db, old)
        db.commit()
        completion = progress_to_completion(db)
        process_entry(db, completion)
        db.commit()
        assert plan(db).request_id == completion.request_id
        before = (plan(db).body_json, plan(db).version_id)
        result = compensate_uncertain(db, workspace_id="test", request_id=old.request_id, now=NOW)
        db.commit()
        assert result.resource_refs == []
        assert (plan(db).body_json, plan(db).version_id) == before


def test_competing_approval_and_completion_workers_preserve_completed_plan(sessions):
    from app.models import OutboxEntry
    with sessions() as db:
        old = approve(db)
        completion = progress_to_completion(db)
        ids = [old.id, completion.id]
    barrier = Barrier(2)
    def process(entry_id):
        with sessions() as db:
            entry = db.query(OutboxEntry).filter_by(id=entry_id).one()
            barrier.wait(timeout=5)
            process_entry(db, entry)
            db.commit()
            return entry.state
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(process, ids)) == ["dead_lettered", "committed"]
    with sessions() as db:
        assert case(db).disposition == "completed"
        assert json.loads(plan(db).body_json)["status"] == "completed"


def snapshot(db, patient_id):
    patient = db.query(Patient).filter_by(workspace_id="test", id=patient_id).one()
    pathway = infer_pathway(patient.age_band)
    result = build_rule_snapshot(db, workspace_id="test", patient=patient, pathway=pathway,
                                 as_of=date(2026, 11, 17), authorized=True)
    return result, evaluate(result, pathway_rule_id(pathway))


def add_proposal(db, patient_id):
    proposal = Proposal(
        id=f"prop-{uuid.uuid4().hex}", workspace_id="test", job_id="test-job",
        patient_id=patient_id, document_id="test-note", document_version=1,
        concept="last_wcv", value_text="Unreviewed claim", subject="patient", assertion="present",
        effective_date="2026-11-16", proposed_resource_type="Observation", excerpt="Unreviewed claim",
        offset_start=0, offset_end=16, review_state="proposed",
    )
    db.add(proposal)
    db.commit()
    return proposal


@pytest.mark.parametrize("patient_id,outcome", [
    ("pat-synthetic-11", "needs_review"),
    ("pat-synthetic-12", "gap_identified"),
    ("pat-synthetic-13", "no_gap_identified_in_available_data"),
    ("pat-synthetic-32", "not_eligible"),
])
def test_proposal_backlog_never_changes_authoritative_snapshot(sessions, patient_id, outcome):
    with sessions() as db:
        baseline = snapshot(db, patient_id)
        assert baseline[1].outcome == outcome
        proposal = add_proposal(db, patient_id)
        assert snapshot(db, patient_id) == baseline
        proposal.review_state = "rejected"
        db.commit()
        assert snapshot(db, patient_id) == baseline
        # Even marking a proposal accepted cannot affect rules before a resource commit.
        proposal.review_state = "accepted"
        db.commit()
        assert snapshot(db, patient_id) == baseline


def test_committed_reviewed_fact_changes_rules_even_with_other_pending_proposals(sessions):
    with sessions() as db:
        patient_id = "pat-synthetic-11"
        add_proposal(db, patient_id)
        assert snapshot(db, patient_id)[1].outcome == "needs_review"
        db.add(FhirResource(
            workspace_id="test", resource_type="Observation", logical_id="reviewed-history",
            version_id=1, request_id="reviewed-commit", updated_at=NOW,
            body_json=json.dumps({
                "resourceType": "Observation", "id": "reviewed-history", "status": "final",
                "subject": {"reference": f"Patient/{patient_id}"},
                "code": {"text": CONCEPT_TEXT["last_wcv"]}, "effectiveDateTime": "2020-01-01",
                "component": [{"code": {"text": "Source assertion"},
                               "valueCodeableConcept": {"text": "present"}}],
            }),
        ))
        db.commit()
        after, result = snapshot(db, patient_id)
        assert after.complete_for_rule
        assert result.outcome == "gap_identified"
        assert any(v.reference == "Observation/reviewed-history" for v in result.input_versions)


def test_malformed_authoritative_resource_still_marks_retrieval_incomplete(sessions):
    with sessions() as db:
        db.add(FhirResource(workspace_id="test", resource_type="Observation", logical_id="bad",
                            version_id=1, request_id="bad-source", updated_at=NOW, body_json="{broken"))
        db.commit()
        current, result = snapshot(db, "pat-synthetic-12")
        assert not current.complete_for_rule
        assert result.outcome == "needs_review"
        assert "Authoritative retrieval incomplete for this rule" in result.missing_information

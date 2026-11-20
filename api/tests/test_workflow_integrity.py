"""Regression coverage for concurrency, evidence-backed closure, and funnel outcomes."""
import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import Base
from app.errors import AppError
from app.models import Case, Command, Event, FhirResource, OutboxEntry
from app.schemas import ActionRequest
from app.services.analytics import _funnel_counts
from app.services.demo import ensure_workspace
from app.services.outbox import claim_due_entries, process_entry, retry_dead_letter
from app.workflow.engine import apply_action


@pytest.fixture()
def sessions(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'workflow.sqlite3'}",
        connect_args={"check_same_thread": False, "timeout": 15},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        ensure_workspace(db, "test")
    yield factory
    engine.dispose()
    get_settings.cache_clear()


def case(db, cid="case-0002"):
    return db.query(Case).filter_by(workspace_id="test", id=cid).one()


def act(db, action, data, cid="case-0002", request_id=None):
    target = case(db, cid)
    return apply_action(db, workspace_id="test", case=target, role=(
        "clinical_reviewer" if action in {"close_as_completed", "reopen", "close_other"} else "coordinator"
    ), request=ActionRequest(action=action, expected_revision=target.revision,
                             request_id=request_id or str(uuid.uuid4()), data=data))


def close(db, **overrides):
    return act(db, "close_as_completed", {
        "evidence_type": "Encounter", "evidence_reference": "Encounter/enc-synthetic-02",
        "attestation": True, **overrides,
    })


def drain(db):
    entries = claim_due_entries(db, worker_id="test-worker")
    db.commit()
    for entry in entries:
        process_entry(db, entry)
        db.commit()
    return entries


def test_stale_loaded_case_cannot_overwrite_winner(sessions):
    with sessions() as a, sessions() as b:
        first, stale = case(a), case(b)
        rev = first.revision
        act(a, "reassign_owner", {"owner": "Winner", "reason": "test"})
        with pytest.raises(AppError) as exc:
            apply_action(b, workspace_id="test", case=stale, role="coordinator",
                         request=ActionRequest(action="reassign_owner", expected_revision=rev,
                                               request_id="loser", data={"owner": "Loser", "reason": "test"}))
        assert exc.value.code == "stale_revision"
        assert case(b).owner == "Winner"
        assert case(b).revision == rev + 1
        assert b.query(Command).filter_by(request_id="loser").count() == 0
        assert b.query(Event).filter_by(request_id="loser").count() == 0


def test_rejected_action_rolls_back_revision(sessions):
    with sessions() as db:
        rev = case(db).revision
        with pytest.raises(AppError):
            act(db, "record_attendance", {"attended": "unknown"})
        assert case(db).revision == rev


def test_seed_attendance_uses_persisted_outcome(sessions):
    with sessions() as db:
        row = case(db, "case-0006")
        counts = _funnel_counts(db, "test", [row])
        assert counts["attended"] == 1
        assert counts["completed"] == 1
        event = db.query(Event).filter_by(id="evt-0006-attend").one()
        assert event.outcome == "attended"


def test_no_show_not_counted_and_later_attendance_counted_once(sessions):
    with sessions() as db:
        missed = act(db, "record_attendance", {"attended": "did_not_attend"})
        assert missed.event.outcome == "did_not_attend"
        assert missed.case.stage == "invited"
        assert _funnel_counts(db, "test", [case(db)])["attended"] == 0
        from app.workflow.actions import ACTIONS
        assert ACTIONS["book_appointment"].applies(case(db))
        assert not ACTIONS["record_attendance"].applies(case(db))
        act(db, "book_appointment", {"appointment_time": "2026-12-01", "location": "Clinic A"})
        result = act(db, "record_attendance", {"attended": "attended"}, request_id="attendance")
        replay = act(db, "reassign_owner", {"owner": "New owner", "reason": "test"})
        assert replay.case.stage == "attended"
        assert _funnel_counts(db, "test", [case(db)])["attended"] == 1
        event = db.query(Event).filter_by(id=result.event.id).one()
        assert event.new_state == "attended/active"
        assert event.outcome == "attended"


@pytest.mark.parametrize("evidence_type,reference,reason", [
    ("Encounter", "Procedure/nonexistent", "reference_type_mismatch_or_invalid"),
    ("Encounter", "Encounter/nonexistent", "evidence_not_found"),
    ("Encounter", "Encounter/enc-synthetic-06", "patient_mismatch"),
    ("Observation", "Observation/x", "invalid_resource_type"),
    ("Encounter", "enc-synthetic-02", "reference_type_mismatch_or_invalid"),
])
def test_invalid_evidence_cannot_close(sessions, evidence_type, reference, reason):
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"})
        rev = case(db).revision
        with pytest.raises(AppError) as exc:
            close(db, evidence_type=evidence_type, evidence_reference=reference)
        if reason == "invalid_resource_type":
            assert "evidence_type" in exc.value.field_errors
        else:
            assert exc.value.field_errors["evidence_reference"] == reason
        assert case(db).stage == "attended"
        assert case(db).revision == rev
        assert db.query(OutboxEntry).count() == 0


@pytest.mark.parametrize("status", ["in-progress", "cancelled", "entered-in-error"])
def test_non_completed_evidence_rejected(sessions, status):
    with sessions() as db:
        resource = db.query(FhirResource).filter_by(logical_id="enc-synthetic-02").one()
        body = json.loads(resource.body_json); body["status"] = status
        resource.body_json = json.dumps(body); db.commit()
        act(db, "record_attendance", {"attended": "attended"})
        with pytest.raises(AppError):
            close(db)
        assert case(db).stage == "attended"


def test_completion_waits_for_commit_and_preserves_evidence(sessions):
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"})
        evidence = db.query(FhirResource).filter_by(logical_id="enc-synthetic-02").one()
        original = evidence.body_json
        result = close(db)
        assert result.case.stage == "attended"
        assert result.case.disposition == "active"
        assert _funnel_counts(db, "test", [case(db)])["completed"] == 0
        entries = drain(db)
        assert entries[0].state == "committed"
        assert case(db).stage == "closed"
        assert case(db).revision == result.case.revision + 1
        assert _funnel_counts(db, "test", [case(db)])["completed"] == 1
        db.refresh(evidence)
        assert evidence.body_json == original
        assert evidence.version_id == 1
        assert db.query(Command).filter_by(outbox_id=entries[0].id).one().saga_state == "fhir_committed"
        assert db.query(Event).filter_by(action="completion_committed").count() == 1
        assert drain(db) == []
        assert process_entry(db, entries[0]).state == "committed"
        db.commit()
        assert db.query(Event).filter_by(action="completion_committed").count() == 1


def test_pending_completion_blocks_mutations(sessions):
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"}); close(db)
        rev = case(db).revision
        with pytest.raises(AppError) as exc:
            act(db, "close_other", {"reason": "test"})
        assert exc.value.code == "completion_pending"
        assert case(db).revision == rev


def test_dead_letter_does_not_complete_then_retry_succeeds(sessions, monkeypatch):
    monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "1")
    monkeypatch.setenv("NAMAA_OUTBOX_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"}); result = close(db)
        entry = drain(db)[0]
        assert entry.state == "dead_lettered"
        assert case(db).stage == "attended"
        assert case(db).revision == result.case.revision
        assert _funnel_counts(db, "test", [case(db)])["completed"] == 0
        assert db.query(Event).filter_by(action="completion_committed").count() == 0
        monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "0"); get_settings.cache_clear()
        retry_dead_letter(db, workspace_id="test", outbox_id=entry.id); db.commit()
        drain(db)
        assert case(db).disposition == "completed"


def test_evidence_invalidated_before_worker_cannot_complete(sessions):
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"}); close(db)
        resource = db.query(FhirResource).filter_by(logical_id="enc-synthetic-02").one()
        body = json.loads(resource.body_json); body["status"] = "entered-in-error"
        resource.body_json = json.dumps(body); db.commit()
        assert drain(db)[0].state == "dead_lettered"
        assert case(db).stage == "attended"


def test_completion_replay_does_not_duplicate_request(sessions):
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"})
        target = case(db)
        req = ActionRequest(action="close_as_completed", expected_revision=target.revision,
                            request_id="replay-completion", data={"evidence_type": "Encounter",
                            "evidence_reference": "Encounter/enc-synthetic-02", "attestation": True})
        first = apply_action(db, workspace_id="test", case=target, request=req, role="clinical_reviewer")
        drain(db)
        replay = apply_action(db, workspace_id="test", case=target, request=req, role="clinical_reviewer")
        assert replay == first  # immutable command response; GET shows committed state
        assert db.query(OutboxEntry).count() == 1
        assert case(db).disposition == "completed"


def test_evidence_in_another_workspace_is_not_accepted(sessions):
    with sessions() as db:
        ensure_workspace(db, "other")
        db.query(FhirResource).filter_by(workspace_id="test", logical_id="enc-synthetic-02").delete()
        db.commit()
        act(db, "record_attendance", {"attended": "attended"})
        with pytest.raises(AppError) as exc:
            close(db)
        assert exc.value.field_errors["evidence_reference"] == "evidence_not_found"


@pytest.mark.parametrize("resource_type,status", [("Procedure", "completed"), ("DiagnosticReport", "final")])
def test_other_supported_evidence_types(sessions, resource_type, status):
    with sessions() as db:
        target = case(db)
        db.add(FhirResource(workspace_id="test", resource_type=resource_type, logical_id="evidence",
                            version_id=1, request_id="fixture", updated_at="2026-11-17T09:00:00Z",
                            body_json=json.dumps({"resourceType": resource_type, "id": "evidence",
                            "status": status, "subject": {"reference": f"Patient/{target.patient_id}"}})))
        db.commit()
        act(db, "record_attendance", {"attended": "attended"})
        close(db, evidence_type=resource_type, evidence_reference=f"{resource_type}/evidence")
        drain(db)
        assert case(db).disposition == "completed"


def test_uncertain_write_and_compensation_never_count_completion(sessions, monkeypatch):
    from app.fhir import FhirUncertainError
    import app.services.outbox as outbox
    def uncertain(*args, **kwargs):
        raise FhirUncertainError("outcome unknown")
    monkeypatch.setattr(outbox, "apply_transaction_bundle", uncertain)
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"}); close(db)
        assert drain(db)[0].state == "compensating"
        assert case(db).stage == "attended"
        assert drain(db)[0].state == "compensated"
        assert _funnel_counts(db, "test", [case(db)])["completed"] == 0
        assert db.query(Event).filter_by(action="completion_committed").count() == 0


def test_old_retry_cannot_close_changed_case(sessions, monkeypatch):
    monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "1")
    monkeypatch.setenv("NAMAA_OUTBOX_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"}); close(db)
        entry = drain(db)[0]
        act(db, "close_other", {"reason": "Clinical decision changed"})
        monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "0"); get_settings.cache_clear()
        retry_dead_letter(db, workspace_id="test", outbox_id=entry.id); db.commit()
        assert drain(db)[0].state == "dead_lettered"
        assert case(db).disposition == "clinically_closed_other"


def test_competing_workers_cannot_claim_leased_entry(sessions):
    with sessions() as a, sessions() as b:
        act(a, "record_attendance", {"attended": "attended"}); close(a)
        # Load the entry before another worker claims it, reproducing a stale identity map.
        stale = b.query(OutboxEntry).one()
        assert stale.state == "pending"
        assert len(claim_due_entries(a, worker_id="winner")) == 1
        a.commit()
        assert claim_due_entries(b, worker_id="loser") == []


def test_completion_status_exposes_failure_and_commit(sessions, monkeypatch):
    from app.services.serializers import case_to_out
    monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "1")
    monkeypatch.setenv("NAMAA_OUTBOX_MAX_ATTEMPTS", "1")
    get_settings.cache_clear()
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"})
        assert close(db).case.completion_status == "pending"
        assert case_to_out(db, case(db)).completion_status == "pending"
        entry = drain(db)[0]
        failed = case_to_out(db, case(db))
        assert failed.completion_status == "dead_lettered"
        assert "not persisted" in failed.next_action
        monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "0"); get_settings.cache_clear()
        retry_dead_letter(db, workspace_id="test", outbox_id=entry.id); db.commit()
        drain(db)
        assert case_to_out(db, case(db)).completion_status == "committed"


@pytest.mark.parametrize("same_request", [False, True])
def test_simultaneous_updates_are_atomic_and_retries_idempotent(sessions, same_request):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    barrier = Barrier(2)
    def submit(index):
        with sessions() as db:
            target = case(db)
            request = ActionRequest(action="reassign_owner", expected_revision=target.revision,
                request_id="same" if same_request else f"race-{index}",
                data={"owner": "Winner" if same_request else f"Owner {index}", "reason": "race"})
            barrier.wait(timeout=5)
            try:
                result = apply_action(db, workspace_id="test", case=target,
                                      request=request, role="coordinator")
                return result.event.id
            except AppError as exc:
                return exc.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    if same_request:
        assert results[0] == results[1]
        assert results[0].startswith("evt-")
    else:
        assert results.count("stale_revision") == 1
    with sessions() as db:
        assert db.query(Command).filter_by(action="reassign_owner").count() == 1
        assert db.query(Event).filter_by(action="reassign_owner").count() == 1

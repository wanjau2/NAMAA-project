"""Four isolated reproductions: resume, referral handoff, stale approval after close_other."""
import json

import pytest

from app.errors import AppError
from app.models import FhirResource
from app.services.outbox import process_entry
from app.workflow.availability import available_actions_for
from test_high_priority_boundaries import approve
from test_workflow_integrity import act, case, sessions

BOOKING = {"appointment_time": "2026-12-01", "location": "Demo clinic"}


def _blocked(db, cid, action):
    items = {item.id: item.blocked_reason for item in available_actions_for(db, case(db, cid))}
    return items.get(action)


def test_unreachable_cannot_book_until_resume(sessions):
    with sessions() as db:
        cid = "case-0005"
        assert case(db, cid).stage == "invited"
        assert case(db, cid).disposition == "unreachable"
        with pytest.raises(AppError) as blocked:
            act(db, "book_appointment", BOOKING, cid=cid)
        assert blocked.value.code == "invalid_transition"
        act(
            db,
            "record_contact_preference",
            {"channel": "phone", "language": "en", "preferred_time": "morning"},
            cid=cid,
        )
        act(db, "reassign_owner", {"owner": "Coordinator 2", "reason": "Cover"}, cid=cid)
        with pytest.raises(AppError) as still:
            act(db, "book_appointment", BOOKING, cid=cid)
        assert still.value.code == "invalid_transition"
        resumed = act(db, "resume_pathway", {"reason": "Reached by phone-assisted support"}, cid=cid)
        assert resumed.case.disposition == "active"
        assert resumed.case.stage == "invited"
        booked = act(db, "book_appointment", BOOKING, cid=cid)
        assert booked.case.stage == "booked"
        assert booked.case.disposition == "active"


def test_deferred_cannot_book_until_resume(sessions):
    with sessions() as db:
        cid = "case-0002"
        target = case(db, cid)
        target.stage = "invited"
        db.commit()
        act(db, "defer_with_recall", {"recall_date": "2026-12-15", "reason": "Family travelling"}, cid=cid)
        assert case(db, cid).disposition == "deferred"
        with pytest.raises(AppError) as blocked:
            act(db, "book_appointment", BOOKING, cid=cid)
        assert blocked.value.code == "invalid_transition"
        act(
            db,
            "record_contact_preference",
            {"channel": "sms", "language": "en", "preferred_time": "morning"},
            cid=cid,
        )
        act(db, "reassign_owner", {"owner": "Coordinator 2", "reason": "Cover"}, cid=cid)
        with pytest.raises(AppError) as still:
            act(db, "book_appointment", BOOKING, cid=cid)
        assert still.value.code == "invalid_transition"
        resumed = act(db, "resume_pathway", {"reason": "Recall date reached"}, cid=cid)
        assert resumed.case.disposition == "active"
        assert case(db, cid).recall_date == "2026-12-15"
        booked = act(db, "book_appointment", BOOKING, cid=cid)
        assert booked.case.stage == "booked"


def test_reassignment_clears_rejected_referral_completion_block(sessions):
    with sessions() as db:
        cid = "case-0003"
        assert case(db, cid).referral_outcome == "rejected"
        assert case(db, cid).overdue is True
        assert _blocked(db, cid, "close_as_completed")
        with pytest.raises(AppError) as blocked:
            act(
                db,
                "close_as_completed",
                {
                    "evidence_type": "Encounter",
                    "evidence_reference": "Encounter/enc-synthetic-02",
                    "attestation": True,
                },
                cid=cid,
            )
        assert blocked.value.code == "precondition_failed"
        act(
            db,
            "reassign_owner",
            {"owner": "Coordinator 3", "reason": "Receiving service at capacity"},
            cid=cid,
        )
        handed = case(db, cid)
        assert handed.owner == "Coordinator 3"
        assert handed.referral_outcome == "rejected"
        assert handed.overdue is False
        assert _blocked(db, cid, "close_as_completed") is None


def test_delayed_approval_cannot_write_after_close_other_and_reopen(sessions):
    with sessions() as db:
        old = approve(db)
        act(db, "close_other", {"reason": "Clinically inappropriate for this pathway"})
        assert case(db).stage == "closed"
        act(db, "reopen", {"reason": "New follow-up required"})
        process_entry(db, old)
        db.commit()
        assert old.state == "dead_lettered"
        assert "superseded" in (old.last_error or "").lower()
        plans = db.query(FhirResource).filter_by(
            workspace_id="test", resource_type="CarePlan", logical_id="cp-case-0002"
        ).all()
        assert plans == [] or json.loads(plans[0].body_json)["status"] != "active"
        assert case(db).stage == "follow_up"
        assert db.query(FhirResource).filter_by(
            workspace_id="test", resource_type="CarePlan", request_id=old.request_id
        ).count() == 0

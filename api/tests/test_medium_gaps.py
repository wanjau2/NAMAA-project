"""Typed workflow data, durable bookings, and server-side role boundaries."""
import pytest

from app.errors import AppError
from app.models import AppointmentBooking, Command, Event
from app.services.demo import ensure_workspace, reset_workspace
from app.services.serializers import case_to_out
from app.workflow.actions import ACTIONS
from app.workflow.validation import ACTION_DATA, validate_action_data
from test_workflow_integrity import sessions, act, case  # shared isolated database fixture

VALID = {
    "record_contact_preference": {"channel": "phone", "language": "en", "preferred_time": "morning"},
    "approve_pathway": {"attestation": True},
    "send_invitation": {"template": "wcv_invite_v1"},
    "record_decline": {"reason": "Declined"},
    "record_unreachable": {"attempts": 2, "reason": "No answer"},
    "book_appointment": {"appointment_time": "2026-12-01", "location": "Clinic A"},
    "record_attendance": {"attended": "attended"},
    "record_referral_outcome": {"outcome": "accepted", "reason": "Confirmed"},
    "reassign_owner": {"owner": "Coordinator 2", "reason": "Cover"},
    "defer_with_recall": {"recall_date": "2026-12-01", "reason": "Recall"},
    "close_as_completed": {"evidence_type": "Encounter", "evidence_reference": "Encounter/a", "attestation": True},
    "close_other": {"reason": "Clinical review"},
    "reopen": {"reason": "New information"},
}


def test_every_action_has_a_matching_schema():
    assert set(ACTIONS) == set(ACTION_DATA) == set(VALID)
    for action, spec in ACTIONS.items():
        assert set(ACTION_DATA[action].model_fields) == {f.name for f in spec.fields}


@pytest.mark.parametrize("action", VALID)
def test_valid_payload_and_unknown_fields(action):
    assert validate_action_data(action, VALID[action], "req") == VALID[action]
    with pytest.raises(AppError) as exc:
        validate_action_data(action, {**VALID[action], "unexpected": "value"}, "req")
    assert exc.value.status_code == 422
    assert "unexpected" in exc.value.field_errors


@pytest.mark.parametrize("action,field,bad", [
    ("record_contact_preference", "channel", "fax"),
    ("record_contact_preference", "language", "xx"),
    ("record_contact_preference", "preferred_time", "whenever"),
    ("send_invitation", "template", "invented"),
    ("record_referral_outcome", "outcome", "invented"),
    ("record_attendance", "attended", []),
    ("approve_pathway", "attestation", 1),
    ("close_as_completed", "attestation", "true"),
    ("record_unreachable", "attempts", True),
    ("record_unreachable", "attempts", "2"),
    ("record_unreachable", "attempts", 1.5),
    ("record_unreachable", "attempts", 0),
    ("record_unreachable", "attempts", -1),
    ("record_unreachable", "attempts", 1001),
    ("reassign_owner", "owner", " " * 5),
    ("reassign_owner", "owner", "x" * 129),
    ("record_decline", "reason", {"text": "declined"}),
    ("record_decline", "reason", "x" * 2001),
    ("approve_pathway", "reason", ["note"]),
    ("book_appointment", "location", False),
    ("book_appointment", "appointment_time", "2026-02-30"),
    ("book_appointment", "appointment_time", "20261201"),
    ("book_appointment", "appointment_time", "2026-12-01T09:00:00Z"),
    ("defer_with_recall", "recall_date", "not-a-date"),
    ("defer_with_recall", "recall_date", "2026-W01-1"),
    ("defer_with_recall", "recall_date", 123),
])
def test_invalid_payload_is_a_field_error(action, field, bad):
    with pytest.raises(AppError) as exc:
        validate_action_data(action, {**VALID[action], field: bad}, "request-123")
    assert exc.value.status_code == 422
    assert exc.value.request_id == "request-123"
    assert field in exc.value.field_errors


def test_invalid_date_has_no_workflow_effects(sessions):
    with sessions() as db:
        revision = case(db).revision
        events = db.query(Event).count()
        with pytest.raises(AppError):
            act(db, "defer_with_recall", {"recall_date": "2026-02-30", "reason": "Recall"})
        assert case(db).revision == revision
        assert case(db).recall_date is None
        assert db.query(Event).count() == events
        assert db.query(Command).count() == 0


def test_booking_survives_new_session_and_reset_is_workspace_scoped(sessions):
    with sessions() as db:
        ensure_workspace(db, "other")
        target = case(db)
        target.stage = "invited"
        db.commit()
        booked = act(db, "book_appointment", {"appointment_time": "2028-02-29", "location": "  Demo Clinic  "})
        assert booked.case.stage == "booked"
        assert booked.case.disposition == "active"
        assert booked.case.detail.booking.location == "Demo Clinic"
        assert booked.event.booking == booked.case.detail.booking
        event_id = booked.event.id
    with sessions() as db:
        restored = case_to_out(db, case(db))
        assert restored.detail.booking.appointment_time == "2028-02-29"
        assert restored.detail.booking.location == "Demo Clinic"
        assert next(e for e in restored.detail.events if e.id == event_id).booking == restored.detail.booking
        reset_workspace(db, "other")
        assert db.query(AppointmentBooking).filter_by(workspace_id="test").count() == 1
        reset_workspace(db, "test")
        assert db.query(AppointmentBooking).filter_by(workspace_id="test").count() == 0
        assert case_to_out(db, case(db)).detail.booking is None


def test_booking_replay_creates_one_booking(sessions):
    from app.schemas import ActionRequest
    from app.workflow.engine import apply_action
    with sessions() as db:
        target = case(db)
        target.stage = "invited"
        db.commit()
        request = ActionRequest(action="book_appointment", request_id="book-once",
                                expected_revision=target.revision, data=VALID["book_appointment"])
        first = apply_action(db, workspace_id="test", case=target, request=request, role="coordinator")
        again = apply_action(db, workspace_id="test", case=target, request=request, role="coordinator")
        assert first == again
        assert db.query(AppointmentBooking).count() == 1


from test_api import client  # TestClient with an isolated synthetic database


def test_http_booking_and_role_boundaries(client):
    sid = client.post("/api/v1/demo/sessions").json()["session_id"]
    headers = {"X-Namaa-Session": sid, "X-Namaa-Role": "coordinator"}
    from app.models import Case
    with client.app.state.session_factory() as db:
        target = db.query(Case).filter_by(workspace_id=sid, id="case-0002").one()
        target.stage = "invited"
        revision = target.revision
        db.commit()
    body = {"action": "book_appointment", "expected_revision": revision,
            "request_id": "http-booking", "data": VALID["book_appointment"]}
    result = client.post("/api/v1/cases/case-0002/actions", headers=headers, json=body)
    assert result.status_code == 200
    assert result.json()["event"]["booking"] == VALID["book_appointment"]
    assert client.get("/api/v1/cases/case-0002", headers=headers).json()["detail"]["booking"] == VALID["book_appointment"]
    analyst = {**headers, "X-Namaa-Role": "population_analyst"}
    assert client.get("/api/v1/cases", headers=analyst).status_code == 403
    assert client.get("/api/v1/cases/case-0002", headers=analyst).status_code == 403
    assert client.get("/api/v1/analytics/overview", headers=analyst).status_code == 200


def test_available_actions_follow_the_server(client):
    sid = client.post("/api/v1/demo/sessions").json()["session_id"]
    headers = {"X-Namaa-Session": sid, "X-Namaa-Role": "coordinator"}
    body = client.get("/api/v1/cases/case-0002", headers=headers).json()
    by_id = {item["id"]: item for item in body["available_actions"]}
    assert "record_attendance" in by_id
    assert by_id["record_attendance"]["permitted_role"] == "coordinator"
    assert by_id["record_attendance"]["blocked_reason"] is None
    assert "book_appointment" not in by_id
    assert "approve_pathway" not in by_id


def test_no_show_exposes_rebooking_and_preserves_history(client):
    sid = client.post("/api/v1/demo/sessions").json()["session_id"]
    headers = {"X-Namaa-Session": sid, "X-Namaa-Role": "coordinator"}
    url = "/api/v1/cases/case-0002"
    current = client.get(url, headers=headers).json()

    def submit(action, data, request_id):
        nonlocal current
        response = client.post(url + "/actions", headers=headers, json={
            "action": action, "data": data, "request_id": request_id,
            "expected_revision": current["revision"],
        })
        assert response.status_code == 200, response.text
        current = client.get(url, headers=headers).json()
        return response.json()

    first = submit("record_attendance", {"attended": "did_not_attend"}, "missed-first")
    actions = {item["id"] for item in current["available_actions"]}
    assert current["stage"] == "invited"
    assert "book_appointment" in actions and "record_attendance" not in actions
    booking = {"appointment_time": "2026-12-01", "location": "Clinic A"}
    booked = submit("book_appointment", booking, "rebook-first")
    submit("record_attendance", {"attended": "did_not_attend"}, "missed-again")
    replacement = {"appointment_time": "2026-12-03", "location": "Clinic B"}
    submit("book_appointment", replacement, "rebook-again")
    submit("record_attendance", {"attended": "attended"}, "attended-finally")
    assert current["stage"] == "attended"
    assert current["detail"]["booking"] == replacement
    events = {event["id"]: event for event in current["detail"]["events"]}
    assert first["event"]["id"] in events
    assert events[booked["event"]["id"]]["booking"] == booking


def test_reporting_cases_are_not_on_the_worklist(client):
    sid = client.post("/api/v1/demo/sessions").json()["session_id"]
    headers = {"X-Namaa-Session": sid, "X-Namaa-Role": "coordinator"}
    listed = client.get("/api/v1/cases", headers=headers).json()
    assert len(listed) == 6
    assert all(not row["id"].startswith("rpt-") for row in listed)

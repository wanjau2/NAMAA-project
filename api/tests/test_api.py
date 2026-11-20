import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import Base, get_db
from app.main import create_app
from app.models import Case
from app.services.analytics import _funnel_counts
from app.services.extractions import advance_job, claim_queued_jobs
from app.services.outbox import claim_due_entries, process_entry


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def _override():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app = create_app(start_workers=False)
    app.dependency_overrides[get_db] = _override
    # Expose session factory for worker-style tests
    app.state.session_factory = TestingSession  # type: ignore[attr-defined]
    with TestClient(app) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _session(client: TestClient) -> str:
    res = client.post("/api/v1/demo/sessions")
    assert res.status_code == 200
    return res.json()["session_id"]


def _headers(session_id: str, role: str = "coordinator") -> dict[str, str]:
    return {"X-Namaa-Session": session_id, "X-Namaa-Role": role}


def test_health(client: TestClient):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_seed_and_reset(client: TestClient):
    sid = _session(client)
    cases = client.get("/api/v1/cases", headers=_headers(sid))
    assert cases.status_code == 200
    assert len(cases.json()) == 6

    detail = client.get("/api/v1/cases/case-0002", headers=_headers(sid))
    rev = detail.json()["revision"]
    attend = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid),
        json={
            "action": "record_attendance",
            "expected_revision": rev,
            "request_id": str(uuid.uuid4()),
            "data": {"attended": "attended"},
        },
    )
    assert attend.status_code == 200
    assert attend.json()["case"]["stage"] == "attended"

    reset = client.post("/api/v1/demo/reset", headers=_headers(sid))
    assert reset.status_code == 200
    restored = client.get("/api/v1/cases/case-0002", headers=_headers(sid))
    assert restored.json()["stage"] == "booked"
    assert restored.json()["revision"] == 4


def test_stale_revision_and_idempotency(client: TestClient):
    sid = _session(client)
    case = client.get("/api/v1/cases/case-0002", headers=_headers(sid)).json()
    request_id = str(uuid.uuid4())
    body = {
        "action": "record_attendance",
        "expected_revision": case["revision"],
        "request_id": request_id,
        "data": {"attended": "attended"},
    }
    first = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid),
        json=body,
    )
    assert first.status_code == 200
    event_id = first.json()["event"]["id"]

    second = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid),
        json=body,
    )
    assert second.status_code == 200
    assert second.json()["event"]["id"] == event_id

    stale = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid),
        json={
            "action": "record_referral_outcome",
            "expected_revision": case["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {"outcome": "pending", "reason": "chase"},
        },
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "stale_revision"


def test_did_not_attend_is_not_counted_as_attendance(client: TestClient):
    sid = _session(client)
    case_body = client.get("/api/v1/cases/case-0002", headers=_headers(sid)).json()
    res = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid),
        json={
            "action": "record_attendance",
            "expected_revision": case_body["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {"attended": "did_not_attend"},
        },
    )
    assert res.status_code == 200
    assert res.json()["case"]["stage"] == "invited"
    assert res.json()["event"]["outcome"] == "did_not_attend"
    detail = client.get("/api/v1/cases/case-0002", headers=_headers(sid)).json()
    attend_events = [
        event for event in detail["detail"]["events"] if event["action"] == "record_attendance"
    ]
    assert attend_events[-1]["outcome"] == "did_not_attend"
    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        row = db.query(Case).filter_by(workspace_id=sid, id="case-0002").one()
        assert _funnel_counts(db, sid, [row])["attended"] == 0
    finally:
        db.close()


def test_mismatched_evidence_does_not_complete_before_fhir(client: TestClient):
    sid = _session(client)
    case_body = client.get("/api/v1/cases/case-0002", headers=_headers(sid)).json()
    attend = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid),
        json={
            "action": "record_attendance",
            "expected_revision": case_body["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {"attended": "attended"},
        },
    )
    assert attend.status_code == 200
    closed = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "action": "close_as_completed",
            "expected_revision": attend.json()["case"]["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {
                "evidence_type": "Encounter",
                "evidence_reference": "Procedure/nonexistent",
                "attestation": True,
            },
        },
    )
    assert closed.status_code == 422
    detail = client.get("/api/v1/cases/case-0002", headers=_headers(sid)).json()
    assert detail["stage"] == "attended"
    assert detail["disposition"] == "active"
    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        row = db.query(Case).filter_by(workspace_id=sid, id="case-0002").one()
        counts = _funnel_counts(db, sid, [row])
        assert counts["attended"] == 1
        assert counts["completed"] == 0
    finally:
        db.close()


def test_invalid_completion_does_not_complete(client: TestClient):
    sid = _session(client)
    case = client.get("/api/v1/cases/case-0003", headers=_headers(sid)).json()
    res = client.post(
        "/api/v1/cases/case-0003/actions",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "action": "close_as_completed",
            "expected_revision": case["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {
                "evidence_type": "Encounter",
                "evidence_reference": "Encounter/x",
                "attestation": True,
            },
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "precondition_failed"

    other = client.post(
        "/api/v1/cases/case-0003/actions",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "action": "close_other",
            "expected_revision": case["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {"reason": "Clinically inappropriate for demo pathway"},
        },
    )
    assert other.status_code == 200
    assert other.json()["case"]["disposition"] == "clinically_closed_other"


def test_needs_review_blocks_approve(client: TestClient):
    sid = _session(client)
    case = client.get("/api/v1/cases/case-0001", headers=_headers(sid)).json()
    res = client.post(
        "/api/v1/cases/case-0001/actions",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "action": "approve_pathway",
            "expected_revision": case["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {"attestation": True},
        },
    )
    assert res.status_code == 422
    assert res.json()["code"] == "precondition_failed"


def test_missing_role_is_rejected(client: TestClient):
    sid = _session(client)
    res = client.get("/api/v1/cases", headers={"X-Namaa-Session": sid})
    assert res.status_code == 400
    assert res.json()["code"] == "invalid_role"


def test_analytics_publishes_reporting_cohort(client: TestClient):
    sid = _session(client)
    res = client.get(
        "/api/v1/analytics/overview",
        headers=_headers(sid, "population_analyst"),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["threshold"] >= 10
    assert "reporting cohort" in body["notice"]
    for pathway in body["pathways"]:
        assert pathway["completed"]["suppressed"] is False
        assert pathway["completed"]["numerator"] >= 10
        assert pathway["completed"]["denominator"] >= 40
        assert pathway["eligible"]["suppressed"] is False
        assert pathway["eligible"]["numerator"] >= 40


def test_journey_only_cohort_is_release_suppressed(client: TestClient):
    sid = _session(client)
    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        db.query(Case).filter_by(workspace_id=sid, worklist=False).delete()
        db.commit()
    finally:
        db.close()
    res = client.get("/api/v1/analytics/overview", headers=_headers(sid))
    assert res.status_code == 200
    for pathway in res.json()["pathways"]:
        assert pathway["completed"]["suppressed"] is True
        assert pathway["completed"]["numerator"] is None
        assert pathway["completed"]["denominator"] is None


def test_extraction_sse_reaches_terminal(client: TestClient):
    sid = _session(client)
    accepted = client.post(
        "/api/v1/documents/doc-synthetic-11/extractions",
        headers=_headers(sid),
    )
    assert accepted.status_code == 202
    job_id = accepted.json()["job_id"]

    # Drive the worker path synchronously (workers disabled in tests).
    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        jobs = claim_queued_jobs(db, worker_id="test-worker")
        assert jobs and jobs[0].id == job_id
        job = jobs[0]
        while job.state not in {"succeeded", "failed", "timed_out", "cancelled"}:
            job = advance_job(db, job)
    finally:
        db.close()

    status = client.get(f"/api/v1/extractions/{job_id}", headers=_headers(sid))
    assert status.status_code == 200
    body = status.json()
    assert body["state"] == "succeeded"
    assert body["inference_mode"] == "offline_fixture"
    assert "no live inference" in body["model_revision"]
    assert len(body["proposals"]) >= 1

    # SSE snapshot should emit a terminal frame immediately for completed jobs.
    with client.stream(
        "GET",
        f"/api/v1/extractions/{job_id}/events",
        headers=_headers(sid),
    ) as stream:
        chunks = b"".join(stream.iter_bytes())
    text = chunks.decode("utf-8")
    assert "event: terminal" in text
    assert job_id in text


def test_outbox_commits_evidence_and_retries_dead_letter(client: TestClient, monkeypatch):
    sid = _session(client)
    # Move case-0002 to attended then close with evidence (triggers outbox).
    case = client.get("/api/v1/cases/case-0002", headers=_headers(sid)).json()
    attend = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid),
        json={
            "action": "record_attendance",
            "expected_revision": case["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {"attended": "attended"},
        },
    )
    assert attend.status_code == 200
    attended = attend.json()["case"]
    close_id = str(uuid.uuid4())
    closed = client.post(
        "/api/v1/cases/case-0002/actions",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "action": "close_as_completed",
            "expected_revision": attended["revision"],
            "request_id": close_id,
            "data": {
                "evidence_type": "Encounter",
                "evidence_reference": "Encounter/enc-synthetic-02",
                "attestation": True,
            },
        },
    )
    assert closed.status_code == 200
    pending_case = client.get("/api/v1/cases/case-0002", headers=_headers(sid)).json()
    assert pending_case["stage"] == "attended"
    assert pending_case["disposition"] == "active"
    assert pending_case["completion_status"] == "pending"
    db_pending = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        row = db_pending.query(Case).filter_by(workspace_id=sid, id="case-0002").one()
        assert _funnel_counts(db_pending, sid, [row])["completed"] == 0
    finally:
        db_pending.close()

    pending = client.get("/api/v1/ops/outbox", headers=_headers(sid))
    assert pending.status_code == 200
    assert any(r["case_id"] == "case-0002" for r in pending.json())

    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        entries = claim_due_entries(db, worker_id="test-outbox")
        db.commit()
        assert entries
        for entry in entries:
            process_entry(db, entry)
            db.commit()
    finally:
        db.close()

    committed = client.get(
        "/api/v1/ops/outbox",
        headers=_headers(sid),
        params={"state": "committed"},
    )
    assert any(r["case_id"] == "case-0002" for r in committed.json())
    done = client.get("/api/v1/cases/case-0002", headers=_headers(sid)).json()
    assert done["stage"] == "closed"
    assert done["disposition"] == "completed"
    assert done["completion_status"] == "committed"
    db_done = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        row = db_done.query(Case).filter_by(workspace_id=sid, id="case-0002").one()
        assert _funnel_counts(db_done, sid, [row])["completed"] == 1
    finally:
        db_done.close()

    # Force a dead-letter via injected failures, then retry.
    monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "1.0")
    monkeypatch.setenv("NAMAA_OUTBOX_BACKOFF_BASE_SECONDS", "0")
    get_settings.cache_clear()

    c6 = client.get("/api/v1/cases/case-0006", headers=_headers(sid)).json()
    reopened = client.post(
        "/api/v1/cases/case-0006/actions",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "action": "reopen",
            "expected_revision": c6["revision"],
            "request_id": str(uuid.uuid4()),
            "data": {"reason": "Demo reopen for outbox DLQ test"},
        },
    )
    assert reopened.status_code == 200
    req = str(uuid.uuid4())
    again = client.post(
        "/api/v1/cases/case-0006/actions",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "action": "close_as_completed",
            "expected_revision": reopened.json()["case"]["revision"],
            "request_id": req,
            "data": {
                "evidence_type": "Encounter",
                "evidence_reference": "Encounter/enc-synthetic-06",
                "attestation": True,
            },
        },
    )
    assert again.status_code == 200

    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        # Drain attempts until dead_lettered
        for _ in range(8):
            entries = claim_due_entries(db, worker_id="test-outbox-fail")
            db.commit()
            if not entries:
                break
            for entry in entries:
                process_entry(db, entry)
            db.commit()
    finally:
        db.close()

    dlq = client.get(
        "/api/v1/ops/outbox",
        headers=_headers(sid),
        params={"state": "dead_lettered"},
    )
    assert dlq.status_code == 200
    dead = [r for r in dlq.json() if r["case_id"] == "case-0006"]
    assert dead, dlq.json()

    monkeypatch.setenv("NAMAA_FHIR_INJECT_FAILURE_RATE", "0.0")
    get_settings.cache_clear()

    retried = client.post(
        f"/api/v1/ops/outbox/{dead[0]['id']}/retry",
        headers=_headers(sid),
    )
    assert retried.status_code == 200
    assert retried.json()["state"] == "pending"

    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        entries = claim_due_entries(db, worker_id="test-outbox-retry")
        db.commit()
        for entry in entries:
            process_entry(db, entry)
            db.commit()
    finally:
        db.close()

    ok = client.get(
        "/api/v1/ops/outbox",
        headers=_headers(sid),
        params={"state": "committed"},
    )
    assert any(r["case_id"] == "case-0006" for r in ok.json())

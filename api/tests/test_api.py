import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app


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

    app = create_app()
    app.dependency_overrides[get_db] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


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
    assert {c["id"] for c in cases.json()} == {
        "case-0001",
        "case-0002",
        "case-0003",
        "case-0004",
        "case-0005",
        "case-0006",
    }

    # Mutate then reset
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
    assert reset.json()["cases_restored"] == 6
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


def test_invalid_completion_does_not_complete(client: TestClient):
    sid = _session(client)
    case = client.get("/api/v1/cases/case-0003", headers=_headers(sid)).json()
    # Rejected referral blocks completed closure
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

    # close_other must not become completed
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
    assert other.json()["case"]["stage"] == "closed"


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


def test_analytics_suppresses_small_cells(client: TestClient):
    sid = _session(client)
    res = client.get("/api/v1/analytics/overview", headers=_headers(sid))
    assert res.status_code == 200
    body = res.json()
    assert body["synthetic"] is True
    # Seed cohorts are small (< 10) so completion cells should suppress
    for pathway in body["pathways"]:
        assert pathway["completed"]["suppressed"] is True
        assert pathway["completed"]["reason"] == "small_cell"
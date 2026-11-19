import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.security.constants import POLICY_ADAPTER, POLICY_REVISION


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
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _session(client: TestClient) -> str:
    return client.post("/api/v1/demo/sessions").json()["session_id"]


def _headers(sid: str, role: str = "coordinator") -> dict[str, str]:
    return {
        "X-Namaa-Session": sid,
        "X-Namaa-Role": role,
        "X-Namaa-Request-Id": f"req-{uuid.uuid4().hex[:8]}",
    }


def test_trusted_context_is_backend_minted(client: TestClient):
    sid = _session(client)
    res = client.get("/api/v1/security/context", headers=_headers(sid))
    assert res.status_code == 200
    body = res.json()
    assert body["policy_adapter"] == POLICY_ADAPTER
    assert body["production_authorization"] is False
    assert body["policy_revision"] == POLICY_REVISION
    assert "not_production_authorization" in body["restrictions"]
    assert body["workspace_id"] == sid


def test_authzen_unknown_action_denies(client: TestClient):
    sid = _session(client)
    res = client.post(
        "/api/v1/authz/evaluation",
        headers=_headers(sid),
        json={
            "resource": {"type": "DocumentReference", "id": "doc-synthetic-11"},
            "action": {"name": "not.a.real.action"},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["decision"] is False
    assert body["context"]["reason_code"] == "unknown_or_missing_action"
    assert body["context"]["policy_adapter"] == POLICY_ADAPTER


def test_authzen_note_retrieve_permits_for_assigned_patient(client: TestClient):
    sid = _session(client)
    res = client.post(
        "/api/v1/authz/evaluation",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "resource": {
                "type": "DocumentReference",
                "id": "doc-synthetic-11",
                "workspace_id": sid,
                "patient_id": "pat-synthetic-11",
            },
            "action": {"name": "note.retrieve"},
        },
    )
    assert res.status_code == 200
    assert res.json()["decision"] is True
    assert res.json()["context"]["decision_id"].startswith("dec-")


def test_audit_sink_rejects_note_text(client: TestClient):
    sid = _session(client)
    res = client.post(
        "/api/v1/audit/events",
        headers=_headers(sid),
        json={
            "event_type": "test",
            "action": "audit.write",
            "detail": {"note_text": "should never be stored"},
        },
    )
    assert res.status_code == 422


def test_extraction_queue_enforces_and_preserves_principal(client: TestClient):
    sid = _session(client)
    res = client.post(
        "/api/v1/documents/doc-synthetic-11/extractions",
        headers=_headers(sid, "clinical_reviewer"),
    )
    assert res.status_code == 202
    job_id = res.json()["job_id"]

    # Audit trail should include access evaluations / queue
    audits = client.get("/api/v1/audit/events", headers=_headers(sid))
    assert audits.status_code == 200
    assert len(audits.json()) >= 1
    assert all(a["policy_adapter"] == POLICY_ADAPTER for a in audits.json())
    assert all(a["production_authorization"] is False for a in audits.json())
    assert any(a.get("job_id") == job_id for a in audits.json())


def test_verified_context_relate_hints_do_not_grant_foreign_patient(client: TestClient):
    sid = _session(client)
    res = client.post(
        "/api/v1/security/verified-context",
        headers=_headers(sid),
        json={
            "patient_id": "pat-not-in-workspace",
            "relate_hints": [
                {"resource_type": "Observation", "logical_id": "obs-anything"}
            ],
        },
    )
    assert res.status_code == 403


def test_authzen_review_apply_requires_clinical_reviewer(client: TestClient):
    sid = _session(client)
    denied = client.post(
        "/api/v1/authz/evaluation",
        headers=_headers(sid, "coordinator"),
        json={
            "resource": {
                "type": "Proposal",
                "id": "prop-1101",
                "workspace_id": sid,
                "patient_id": "pat-synthetic-11",
            },
            "action": {"name": "review.apply"},
        },
    )
    assert denied.status_code == 200
    assert denied.json()["decision"] is False

    allowed = client.post(
        "/api/v1/authz/evaluation",
        headers=_headers(sid, "clinical_reviewer"),
        json={
            "resource": {
                "type": "Proposal",
                "id": "prop-1101",
                "workspace_id": sid,
                "patient_id": "pat-synthetic-11",
            },
            "action": {"name": "review.apply"},
        },
    )
    assert allowed.status_code == 200
    assert allowed.json()["decision"] is True


def test_relate_family_history_and_revocation(client: TestClient):
    sid = _session(client)
    ok = client.get(
        "/api/v1/relate/family-history",
        headers=_headers(sid),
        params={"patient_id": "pat-synthetic-11"},
    )
    assert ok.status_code == 200
    assert "candidates" in ok.json()

    rev = client.post(
        "/api/v1/security/revocations",
        headers=_headers(sid),
        json={"principal_id": "guest-synthetic", "reason_code": "demo_revoke"},
    )
    assert rev.status_code == 201
    assert rev.json()["active"] is True

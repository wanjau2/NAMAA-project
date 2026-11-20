import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.services.extractions import advance_job, claim_queued_jobs


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
    app.state.session_factory = TestingSession  # type: ignore[attr-defined]
    with TestClient(app) as test_client:
        test_client.app = app  # type: ignore[attr-defined]
        yield test_client
    app.dependency_overrides.clear()


def _sid(client: TestClient) -> str:
    return client.post("/api/v1/demo/sessions").json()["session_id"]


def _hdr(sid: str, role: str = "clinical_reviewer") -> dict[str, str]:
    return {"X-Namaa-Session": sid, "X-Namaa-Role": role}


def _complete_extraction(client: TestClient, sid: str) -> dict:
    accepted = client.post(
        "/api/v1/documents/doc-synthetic-11/extractions",
        headers=_hdr(sid),
    )
    assert accepted.status_code == 202
    job_id = accepted.json()["job_id"]
    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        jobs = claim_queued_jobs(db, worker_id="t")
        job = jobs[0]
        while job.state not in {"succeeded", "failed", "timed_out"}:
            job = advance_job(db, job)
    finally:
        db.close()
    status = client.get(f"/api/v1/extractions/{job_id}", headers=_hdr(sid))
    assert status.status_code == 200
    props = status.json()["proposals"]
    assert props and "fact" in props[0]
    return props[0]


def test_alfred_shaped_proposal_and_review_accept(client: TestClient):
    sid = _sid(client)
    proposal = _complete_extraction(client, sid)
    prop_id = proposal["id"]
    req = str(uuid.uuid4())
    body = {
        "request_id": req,
        "proposal_id": prop_id,
        "expected_proposal_version": 1,
        "action": "accept",
        "reviewer_reference": "Practitioner/demo-reviewer",
        "reason": "Synthetic reviewer accepts quoted statement for demo.",
        "acknowledged_issues": [i["code"] for i in proposal.get("issues") or []],
    }
    res = client.post(f"/api/v1/facts/{prop_id}/review", headers=_hdr(sid), json=body)
    assert res.status_code == 200, res.text
    assert res.json()["state"] == "accepted"
    assert res.json()["fhir_gateway"] == "stub"
    # Idempotent replay
    again = client.post(f"/api/v1/facts/{prop_id}/review", headers=_hdr(sid), json=body)
    assert again.status_code == 200
    assert again.json()["state"] == "accepted"


def test_review_requires_clinical_role(client: TestClient):
    sid = _sid(client)
    prop_id = _complete_extraction(client, sid)["id"]
    res = client.post(
        f"/api/v1/facts/{prop_id}/review",
        headers=_hdr(sid, "coordinator"),
        json={
            "request_id": str(uuid.uuid4()),
            "expected_proposal_version": 1,
            "action": "reject",
            "reason": "Coordinator must not review",
        },
    )
    assert res.status_code == 403


def test_evaluation_handoff_fields(client: TestClient):
    sid = _sid(client)
    res = client.post(
        "/api/v1/patients/pat-synthetic-11/evaluations",
        headers=_hdr(sid),
        json={},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["rule_evaluation"]["synthetic_rule"] is True
    assert body["rule_evaluation"]["outcome"] in {
        "gap_identified",
        "needs_review",
        "no_gap_identified_in_available_data",
        "not_eligible",
    }
    assert body["api_compatibility"]


def test_relate_does_not_authorize_foreign_patient(client: TestClient):
    sid = _sid(client)
    res = client.get(
        "/api/v1/relate/care-plans",
        headers=_hdr(sid),
        params={"patient_id": "pat-unknown"},
    )
    assert res.status_code == 403

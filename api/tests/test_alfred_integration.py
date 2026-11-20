import uuid

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.services.extractions import advance_job, claim_queued_jobs


def _client():
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
    app.state.session_factory = TestingSession
    return TestClient(app), app


def _sid(client: TestClient) -> str:
    return client.post("/api/v1/demo/sessions").json()["session_id"]


def _hdr(sid: str, role: str = "clinical_reviewer") -> dict[str, str]:
    return {"X-Namaa-Session": sid, "X-Namaa-Role": role}


def test_four_canonical_outcomes_persist_and_read_back():
    client, _app = _client()
    with client:
        sid = _sid(client)
        expected = {
            "pat-synthetic-11": "needs_review",
            "pat-synthetic-12": "gap_identified",
            "pat-synthetic-13": "no_gap_identified_in_available_data",
            "pat-synthetic-32": "not_eligible",
        }
        for patient_id, outcome in expected.items():
            res = client.post(
                f"/api/v1/patients/{patient_id}/evaluations",
                headers=_hdr(sid),
                json={},
            )
            assert res.status_code == 200, res.text
            body = res.json()
            assert body["rule_evaluation"]["outcome"] == outcome
            if outcome in {"not_eligible", "no_gap_identified_in_available_data"}:
                assert body["case"] is None
            if outcome == "not_eligible":
                assert body["legacy_flag_status"] is None
            latest = client.get(
                f"/api/v1/patients/{patient_id}/evaluations/latest",
                headers=_hdr(sid),
            )
            assert latest.status_code == 200
            assert latest.json()["rule_evaluation"]["outcome"] == outcome


def test_review_uses_alfred_validator_and_does_not_upsert_family_history_observation():
    client, app = _client()
    with client:
        sid = _sid(client)
        accepted = client.post(
            "/api/v1/documents/doc-synthetic-31/extractions",
            headers=_hdr(sid),
        )
        assert accepted.status_code == 202
        job_id = accepted.json()["job_id"]
        db = app.state.session_factory()
        try:
            jobs = claim_queued_jobs(db, worker_id="t")
            job = jobs[0]
            while job.state not in {"succeeded", "failed", "timed_out"}:
                job = advance_job(db, job)
        finally:
            db.close()
        status = client.get(f"/api/v1/extractions/{job_id}", headers=_hdr(sid))
        props = status.json()["proposals"]
        family = next(p for p in props if p["fact"]["subject"] == "family_member")
        res = client.post(
            f"/api/v1/facts/{family['id']}/review",
            headers=_hdr(sid),
            json={
                "request_id": str(uuid.uuid4()),
                "proposal_id": family["id"],
                "expected_proposal_version": 1,
                "action": "accept",
                "reviewer_reference": "Practitioner/demo-reviewer",
                "reason": "Checked family history quote for the synthetic demo.",
                "acknowledged_issues": [i["code"] for i in family.get("issues") or []],
            },
        )
        assert res.status_code == 200, res.text
        assert res.json()["state"] == "accepted"
        db = app.state.session_factory()
        try:
            from app.models import FhirResource

            rows = db.query(FhirResource).filter(FhirResource.workspace_id == sid).all()
            assert any(row.resource_type == "FamilyMemberHistory" for row in rows)
            assert not any(
                row.resource_type == "Observation" and "bowel cancer" in row.body_json.lower()
                for row in rows
            )
        finally:
            db.close()
        refused = client.post(
            f"/api/v1/facts/{family['id']}/review",
            headers=_hdr(sid),
            json={
                "request_id": str(uuid.uuid4()),
                "proposal_id": family["id"],
                "expected_proposal_version": 1,
                "action": "correct",
                "reason": "Correction without a replacement fact must fail.",
            },
        )
        assert refused.status_code == 422
        eval_res = client.post(
            "/api/v1/patients/pat-synthetic-31/evaluations",
            headers=_hdr(sid),
            json={"pathway": "adult_screening"},
        )
        assert eval_res.status_code == 200
        assert eval_res.json()["rule_evaluation"]["outcome"] == "needs_review"


def test_denied_note_retrieve_is_auditable_and_analyst_cannot_read_notes():
    client, _app = _client()
    with client:
        sid = _sid(client)
        denied = client.get(
            "/api/v1/documents/doc-synthetic-11",
            headers=_hdr(sid, "population_analyst"),
        )
        assert denied.status_code == 403
        audits = client.get("/api/v1/audit/events", headers=_hdr(sid, "coordinator"))
        assert audits.status_code == 200
        assert any(
            row.get("decision") == "Deny" and row.get("action") == "note.retrieve"
            for row in audits.json()
        )


def test_case_documents_and_segments_exist():
    client, _app = _client()
    with client:
        sid = _sid(client)
        docs = client.get("/api/v1/cases/case-0001/documents", headers=_hdr(sid, "coordinator"))
        assert docs.status_code == 200
        assert any(item["id"] == "doc-synthetic-11" for item in docs.json())
        detail = client.get("/api/v1/cases/case-0001", headers=_hdr(sid, "coordinator"))
        assert detail.json()["detail"]["caregiver_authority"] == "verified_caregiver"
        segments = client.get("/api/v1/analytics/segments", headers=_hdr(sid, "coordinator"))
        assert segments.status_code == 200
        assert segments.json()["suppressed"] is False
        overview = client.get("/api/v1/analytics/overview", headers=_hdr(sid, "coordinator"))
        assert overview.status_code == 200
        assert overview.json()["pathways"][0]["eligible"]["suppressed"] is False

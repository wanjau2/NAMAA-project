"""Isolated reproductions: colliding review IDs, no-gap worklist, pending completion."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import create_app
from app.models import Case, FhirResource, FhirTransactionResult, Observation, OutboxEntry
from app.services.evaluations import run_evaluation
from app.services.extractions import advance_job, claim_queued_jobs
from app.services.outbox import process_entry
from app.services.review import review_outbox_request_id
from test_workflow_integrity import act, case, close, sessions


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


def _colliding_request_ids() -> tuple[str, str]:
    prefix = "R" * 57
    first = prefix + "AAAAAAA"
    second = prefix + "BBBBBBB"
    assert len(first) == len(second) == 64
    assert first != second
    assert f"review.{first}"[:64] == f"review.{second}"[:64]
    return first, second


def _extract_child_proposals(client: TestClient, sid: str) -> list[dict]:
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
    assert len(props) >= 2
    return props


def test_review_outbox_ids_do_not_collide_when_prefixes_match():
    first, second = _colliding_request_ids()
    hashed = review_outbox_request_id(first), review_outbox_request_id(second)
    assert hashed[0] != hashed[1]
    assert all(len(item) == 64 for item in hashed)


def test_prefixed_review_request_ids_persist_distinct_fhir_writes(client: TestClient):
    sid = _sid(client)
    proposals = _extract_child_proposals(client, sid)
    first_id, second_id = _colliding_request_ids()

    for proposal, request_id in zip(proposals[:2], (first_id, second_id), strict=True):
        body = {
            "request_id": request_id,
            "proposal_id": proposal["id"],
            "expected_proposal_version": 1,
            "action": "accept",
            "reviewer_reference": "Practitioner/demo-reviewer",
            "reason": "Synthetic reviewer accepts a quoted statement for the collision check.",
            "acknowledged_issues": [i["code"] for i in proposal.get("issues") or []],
        }
        res = client.post(
            f"/api/v1/facts/{proposal['id']}/review",
            headers=_hdr(sid),
            json=body,
        )
        assert res.status_code == 200, res.text
        assert res.json()["state"] == "accepted"

    db = client.app.state.session_factory()  # type: ignore[attr-defined]
    try:
        observations = (
            db.query(FhirResource)
            .filter(
                FhirResource.workspace_id == sid,
                FhirResource.resource_type == "Observation",
            )
            .all()
        )
        assert len(observations) == 2
        assert len({row.logical_id for row in observations}) == 2
        tx_ids = {
            row.request_id
            for row in db.query(FhirTransactionResult).filter_by(workspace_id=sid).all()
        }
        assert len(tx_ids) == 2
        outbox_ids = {
            row.request_id
            for row in db.query(OutboxEntry).filter_by(workspace_id=sid).all()
            if row.action.startswith("review_")
        }
        assert outbox_ids == {
            review_outbox_request_id(first_id),
            review_outbox_request_id(second_id),
        }
    finally:
        db.close()


def test_no_gap_takes_existing_case_off_worklist_without_closing(sessions):
    with sessions() as db:
        visit = (
            db.query(Observation)
            .filter_by(workspace_id="test", id="obs-12-visit")
            .one()
        )
        visit.value = "2026-11-01"
        visit.observed_time = "2026-11-01T00:00:00Z"
        db.commit()

        result = run_evaluation(
            db, workspace_id="test", patient_id="pat-synthetic-12"
        )
        assert result.rule_evaluation["outcome"] == "no_gap_identified_in_available_data"
        assert result.case is None

        row = case(db, "case-0002")
        assert row.stage != "closed"
        assert row.disposition != "completed"
        assert row.worklist is False
        assert row.eligible is True
        assert "not assurance of health" in row.next_action
        worklist_ids = [
            item.id
            for item in db.query(Case).filter_by(workspace_id="test", worklist=True)
        ]
        assert "case-0002" not in worklist_ids

        visit.value = "2024-03-02"
        visit.observed_time = "2024-03-02T00:00:00Z"
        db.commit()
        restored = run_evaluation(
            db, workspace_id="test", patient_id="pat-synthetic-12"
        )
        assert restored.rule_evaluation["outcome"] == "gap_identified"
        assert restored.case is not None
        assert restored.case.id == "case-0002"
        assert case(db, "case-0002").worklist is True


def test_not_eligible_leaves_case_open_off_worklist(sessions):
    with sessions() as db:
        result = run_evaluation(
            db, workspace_id="test", patient_id="pat-synthetic-32"
        )
        assert result.rule_evaluation["outcome"] == "not_eligible"
        assert result.case is None
        row = case(db, "case-0004")
        assert row.stage != "closed"
        assert row.worklist is False
        assert row.eligible is False


def test_reevaluation_does_not_break_pending_completion(sessions):
    with sessions() as db:
        act(db, "record_attendance", {"attended": "attended"})
        close(db)
        pending = (
            db.query(OutboxEntry)
            .filter_by(
                workspace_id="test",
                action="close_as_completed",
                case_id="case-0002",
            )
            .one()
        )
        assert pending.state == "pending"
        revision = case(db).revision

        result = run_evaluation(
            db, workspace_id="test", patient_id="pat-synthetic-12"
        )
        assert result.rule_evaluation["outcome"] == "gap_identified"
        assert case(db).revision == revision
        assert case(db).stage != "closed"

        processed = process_entry(db, pending)
        db.commit()
        assert processed.state == "committed"
        closed = case(db)
        assert closed.stage == "closed"
        assert closed.disposition == "completed"

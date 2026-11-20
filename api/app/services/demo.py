from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import (
    AuditEvent,
    CareGap,
    Case,
    Command,
    Document,
    Event,
    ExtractionJob,
    FhirResource,
    FhirTransactionResult,
    Observation,
    OutboxEntry,
    Patient,
    PrincipalRevocation,
    Proposal,
    ReviewCommandJournal,
    RuleEvaluation,
    Workspace,
)
from app.seed import SEED_CASES, SEED_EVENTS, SEED_GAPS, SEED_OBSERVATIONS, SEED_PATIENTS
from app.services.extraction_fixtures import SEED_DOCUMENTS


def ensure_workspace(db: Session, workspace_id: str | None = None) -> Workspace:
    wid = workspace_id or f"guest-{uuid.uuid4().hex[:12]}"
    existing = db.get(Workspace, wid)
    if existing:
        return existing

    ws = Workspace(
        id=wid,
        created_at=datetime.now(timezone.utc),
        role="coordinator",
    )
    db.add(ws)
    db.flush()
    load_seed(db, wid)
    db.commit()
    db.refresh(ws)
    return ws


def wipe_workspace_data(db: Session, workspace_id: str) -> None:
    for model in (
        AuditEvent,
        ReviewCommandJournal,
        PrincipalRevocation,
        Proposal,
        ExtractionJob,
        OutboxEntry,
        FhirResource,
        FhirTransactionResult,
        Document,
        Command,
        Event,
        RuleEvaluation,
        Case,
        CareGap,
        Observation,
        Patient,
    ):
        db.query(model).filter(model.workspace_id == workspace_id).delete()
    db.flush()


def load_seed(db: Session, workspace_id: str) -> int:
    for patient in SEED_PATIENTS:
        db.add(
            Patient(
                id=patient["id"],
                workspace_id=workspace_id,
                label=patient["label"],
                age_band=patient["age_band"],
                synthetic=True,
                language=patient.get("language", "en"),
                caregiver_authority=patient.get("caregiver_authority", "unknown"),
            )
        )

    for obs in SEED_OBSERVATIONS:
        db.add(
            Observation(
                id=obs["id"],
                workspace_id=workspace_id,
                patient_id=obs["patient_id"],
                type=obs["type"],
                value=obs["value"],
                source=obs["source"],
                observed_time=obs["observed_time"],
                missing_or_conflict=obs.get("missing_or_conflict", False),
                verified=obs.get("verified", True),
            )
        )

    for gap in SEED_GAPS:
        db.add(
            CareGap(
                id=gap["id"],
                workspace_id=workspace_id,
                patient_id=gap["patient_id"],
                pathway=gap["pathway"],
                rule_id_version=gap["rule_id_version"],
                flag_status=gap["flag_status"],
                factors_json=gap["factors_json"],
                missing_json=gap["missing_json"],
                uncertainty=gap.get("uncertainty", ""),
                explanation=gap["explanation"],
                suggested_review_action=gap["suggested_review_action"],
            )
        )

    for case in SEED_CASES:
        db.add(
            Case(
                id=case["id"],
                workspace_id=workspace_id,
                care_gap_id=case["care_gap_id"],
                patient_id=case["patient_id"],
                patient_label=case["patient_label"],
                age_band=case["age_band"],
                pathway=case["pathway"],
                rule_id_version=case["rule_id_version"],
                flag_status=case["flag_status"],
                stage=case["stage"],
                disposition=case["disposition"],
                owner=case["owner"],
                next_action=case["next_action"],
                due_time=case.get("due_time"),
                overdue=case.get("overdue", False),
                revision=case.get("revision", 1),
                referral_outcome=case.get("referral_outcome"),
                contact_channel=case.get("contact_channel"),
                contact_language=case.get("contact_language"),
                contact_preferred_time=case.get("contact_preferred_time"),
                evidence_type=case.get("evidence_type"),
                evidence_reference=case.get("evidence_reference"),
                eligible=case.get("eligible", True),
            )
        )

    for event in SEED_EVENTS:
        db.add(
            Event(
                id=event["id"],
                workspace_id=workspace_id,
                case_id=event["case_id"],
                timestamp=event["timestamp"],
                actor_role=event["actor_role"],
                action=event["action"],
                prior_state=event.get("prior_state", ""),
                new_state=event.get("new_state", ""),
                reason=event.get("reason"),
                evidence_reference=event.get("evidence_reference"),
                request_id=event.get("request_id"),
            )
        )

    for doc in SEED_DOCUMENTS:
        db.add(
            Document(
                id=doc["id"],
                workspace_id=workspace_id,
                patient_id=doc["patient_id"],
                case_id=doc.get("case_id"),
                version=doc["version"],
                document_date=doc["document_date"],
                text=doc["text"],
            )
        )

    db.flush()
    return len(SEED_CASES)


def reset_workspace(db: Session, workspace_id: str) -> int:
    wipe_workspace_data(db, workspace_id)
    count = load_seed(db, workspace_id)
    db.commit()
    return count
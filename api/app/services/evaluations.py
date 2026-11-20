from __future__ import annotations

import json
import uuid
from datetime import date

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.ai_runtime import ensure_namaa_ai
from app.config import get_settings
from app.errors import AppError
from app.models import CareGap, Case, Event, OutboxEntry, Patient, RuleEvaluation
from app.schemas import EvaluationResult, MissingItem, SourceFact
from app.security.context import TrustedRequestContext
from app.security.enforce import authorize
from app.services.rule_snapshots import (
    build_rule_snapshot,
    infer_pathway,
    pathway_rule_id,
)
from app.services.serializers import case_to_out

ensure_namaa_ai()

from namaa_ai.handoff import prepare_rule_handoff  # noqa: E402
from namaa_ai.rules import evaluate  # noqa: E402

CASE_OUTCOMES = {"gap_identified": "gap", "needs_review": "needs_review"}
_PENDING_COMPLETION = ("pending", "processing", "compensating")


def _as_of(demo_now: str) -> date:
    return date.fromisoformat(demo_now[:10])


def _factors(evaluation) -> list[SourceFact]:
    return [
        SourceFact(
            label=item,
            value=item,
            source=f"Rule/{evaluation.rule_id}",
            observed_time=f"{evaluation.as_of.isoformat()}T00:00:00Z",
            verified=True,
        )
        for item in evaluation.contributing_factors
    ]


def _missing(evaluation) -> list[MissingItem]:
    return [
        MissingItem(
            label=item,
            consequence="The pathway stays blocked until this is resolved. Unknown is not up to date.",
        )
        for item in evaluation.missing_information
    ]


def _open_case(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    pathway: str,
    rule_id: str,
) -> Case | None:
    return (
        db.query(Case)
        .filter(
            Case.workspace_id == workspace_id,
            Case.patient_id == patient_id,
            Case.pathway == pathway,
            Case.rule_id_version == rule_id,
            Case.stage != "closed",
        )
        .one_or_none()
    )


def _completion_in_flight(db: Session, *, workspace_id: str, case_id: str) -> bool:
    return (
        db.query(OutboxEntry.pk)
        .filter(
            OutboxEntry.workspace_id == workspace_id,
            OutboxEntry.case_id == case_id,
            OutboxEntry.action == "close_as_completed",
            OutboxEntry.state.in_(_PENDING_COMPLETION),
        )
        .first()
        is not None
    )


def _write_gap(
    gap: CareGap,
    *,
    flag_status: str,
    factors: list[SourceFact],
    missing: list[MissingItem],
    uncertainty: str,
    explanation: str,
    suggested: str,
) -> None:
    gap.flag_status = flag_status
    gap.factors_json = json.dumps([f.model_dump() for f in factors])
    gap.missing_json = json.dumps([m.model_dump() for m in missing])
    gap.uncertainty = uncertainty
    gap.explanation = explanation
    gap.suggested_review_action = suggested


def _suggested(evaluation) -> str:
    if evaluation.outcome == "needs_review":
        return "Resolve missing or unverified inputs, then re-evaluate before any invitation"
    if evaluation.outcome == "gap_identified":
        return "Clinical reviewer to confirm eligibility"
    if evaluation.outcome == "not_eligible":
        return "No invitation — not eligible on the synthetic enrolment card"
    return "No configured gap in the available data; this is not assurance of health"


def run_evaluation(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    pathway: str | None = None,
    ctx: TrustedRequestContext | None = None,
) -> EvaluationResult:
    settings = get_settings()
    patient = (
        db.query(Patient)
        .filter(Patient.workspace_id == workspace_id, Patient.id == patient_id)
        .one_or_none()
    )
    if patient is None:
        raise AppError(
            code="not_found",
            message=f"Patient '{patient_id}' was not found in this guest session.",
            status_code=404,
        )

    if ctx is not None:
        authorize(
            db,
            ctx,
            action="evaluation.run",
            resource_type="Patient",
            resource_id=patient_id,
            patient_id=patient_id,
        )

    chosen = infer_pathway(patient.age_band, pathway)
    rule_id = pathway_rule_id(chosen)
    snapshot = build_rule_snapshot(
        db,
        workspace_id=workspace_id,
        patient=patient,
        pathway=chosen,
        as_of=_as_of(settings.demo_now),
        authorized=True,
    )
    evaluation = evaluate(snapshot, rule_id)
    handoff = prepare_rule_handoff(evaluation)
    eval_id = f"eval-{uuid.uuid4().hex[:12]}"
    factors = _factors(evaluation)
    missing = _missing(evaluation)
    suggested = _suggested(evaluation)
    uncertainty = evaluation.missing_information[0] if evaluation.missing_information else ""
    explanation = (
        f"{evaluation.rule_id} returned {evaluation.outcome}. "
        "Synthetic demonstration rule only."
    )
    rule_evaluation = evaluation.model_dump(mode="json")
    snapshot_dump = snapshot.model_dump(mode="json")

    db.add(
        RuleEvaluation(
            id=eval_id,
            workspace_id=workspace_id,
            patient_id=patient_id,
            pathway=chosen,
            rule_id_version=evaluation.rule_id,
            input_snapshot_json=json.dumps(
                {
                    "workspace_id": snapshot.workspace_id,
                    "patient_reference": snapshot.patient_reference,
                    "as_of": snapshot.as_of.isoformat(),
                    "authority": snapshot.authority,
                    "authorized": snapshot.authorized,
                    "complete_for_rule": snapshot.complete_for_rule,
                    "rule_id": evaluation.rule_id,
                    "rule_version": evaluation.rule_version,
                    "input_versions": [v.model_dump(mode="json") for v in evaluation.input_versions],
                    "resource_count": len(snapshot.resources),
                }
            ),
            result_json=json.dumps(
                {
                    "rule_evaluation": rule_evaluation,
                    "legacy_flag_status": handoff.legacy_flag_status,
                    "api_compatibility": handoff.api_compatibility,
                    "flag_status": handoff.legacy_flag_status or "not_eligible",
                    "factors": [f.model_dump() for f in factors],
                    "missing": [m.model_dump() for m in missing],
                    "input_snapshot": snapshot_dump,
                }
            ),
            created_at=settings.demo_now,
        )
    )

    case_out = None
    case_flag = CASE_OUTCOMES.get(evaluation.outcome)
    open_case = _open_case(
        db,
        workspace_id=workspace_id,
        patient_id=patient_id,
        pathway=chosen,
        rule_id=evaluation.rule_id,
    )
    pending_completion = open_case is not None and _completion_in_flight(
        db, workspace_id=workspace_id, case_id=open_case.id
    )

    if case_flag is not None and open_case is None:
        gap_id = f"gap-{uuid.uuid4().hex[:8]}"
        case_id = f"case-{uuid.uuid4().hex[:8]}"
        db.add(
            CareGap(
                id=gap_id,
                workspace_id=workspace_id,
                patient_id=patient_id,
                pathway=chosen,
                rule_id_version=evaluation.rule_id,
                flag_status=case_flag,
                factors_json=json.dumps([f.model_dump() for f in factors]),
                missing_json=json.dumps([m.model_dump() for m in missing]),
                uncertainty=uncertainty,
                explanation=explanation,
                suggested_review_action=suggested,
            )
        )
        case = Case(
            id=case_id,
            workspace_id=workspace_id,
            care_gap_id=gap_id,
            patient_id=patient_id,
            patient_label=patient.label,
            age_band=patient.age_band,
            pathway=chosen,
            rule_id_version=evaluation.rule_id,
            flag_status=case_flag,
            stage="identified",
            disposition="active",
            owner="Coordinator 1",
            next_action=suggested,
            due_time=None if evaluation.due_date is None else f"{evaluation.due_date.isoformat()}T09:00:00Z",
            overdue=False,
            revision=1,
            eligible=True,
            worklist=True,
        )
        db.add(case)
        db.add(
            Event(
                id=f"evt-{uuid.uuid4().hex[:12]}",
                workspace_id=workspace_id,
                case_id=case_id,
                timestamp=settings.demo_now,
                actor_role="system",
                action="rule_evaluation",
                prior_state="",
                new_state="identified/active",
                reason=explanation,
                request_id=eval_id,
                outcome=evaluation.outcome,
            )
        )
        db.flush()
        case_out = case_to_out(db, case)
    elif open_case is not None and not pending_completion:
        gap = (
            db.query(CareGap)
            .filter(
                CareGap.workspace_id == workspace_id,
                CareGap.id == open_case.care_gap_id,
            )
            .one()
        )
        prior = f"{open_case.stage}/{open_case.disposition}"
        if case_flag is not None:
            _write_gap(
                gap,
                flag_status=case_flag,
                factors=factors,
                missing=missing,
                uncertainty=uncertainty,
                explanation=explanation,
                suggested=suggested,
            )
            claimed = db.execute(
                update(Case)
                .where(
                    Case.pk == open_case.pk,
                    Case.workspace_id == workspace_id,
                    Case.stage != "closed",
                )
                .values(
                    flag_status=case_flag,
                    next_action=suggested,
                    worklist=True,
                    eligible=True,
                )
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount == 1:
                db.refresh(open_case)
                db.flush()
                case_out = case_to_out(db, open_case)
        else:
            _write_gap(
                gap,
                flag_status=handoff.legacy_flag_status or "not_eligible",
                factors=factors,
                missing=missing,
                uncertainty=uncertainty,
                explanation=explanation,
                suggested=suggested,
            )
            # Keep the workflow open (D006). Drop it from the worklist so an
            # outdated gap/needs_review flag is no longer actionable.
            claimed = db.execute(
                update(Case)
                .where(
                    Case.pk == open_case.pk,
                    Case.workspace_id == workspace_id,
                    Case.stage != "closed",
                )
                .values(
                    next_action=suggested,
                    worklist=False,
                    eligible=evaluation.outcome != "not_eligible",
                    overdue=False,
                )
                .execution_options(synchronize_session=False)
            )
            if claimed.rowcount == 1:
                db.add(
                    Event(
                        id=f"evt-{uuid.uuid4().hex[:12]}",
                        workspace_id=workspace_id,
                        case_id=open_case.id,
                        timestamp=settings.demo_now,
                        actor_role="system",
                        action="rule_evaluation",
                        prior_state=prior,
                        new_state=prior,
                        reason=explanation,
                        request_id=eval_id,
                        outcome=evaluation.outcome,
                    )
                )
                db.flush()
    elif open_case is not None and pending_completion and case_flag is not None:
        # Leave revision/stage/disposition untouched so the completion CAS still
        # matches the command snapshot. The evaluation itself is already stored.
        case_out = case_to_out(db, open_case)

    db.commit()
    legacy = handoff.legacy_flag_status or "not_eligible"
    return EvaluationResult(
        patient_id=patient_id,
        pathway=chosen,  # type: ignore[arg-type]
        rule_id_version=evaluation.rule_id,
        flag_status=legacy,  # type: ignore[arg-type]
        factors=factors,
        missing=missing,
        uncertainty=uncertainty,
        suggested_review_action=suggested,
        case=case_out,
        evaluation_id=eval_id,
        rule_evaluation=rule_evaluation,
        legacy_flag_status=handoff.legacy_flag_status,
        api_compatibility=handoff.api_compatibility,
    )


def latest_evaluation(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    ctx: TrustedRequestContext | None = None,
) -> dict:
    if ctx is not None:
        authorize(
            db,
            ctx,
            action="evaluation.run",
            resource_type="Patient",
            resource_id=patient_id,
            patient_id=patient_id,
        )
    row = (
        db.query(RuleEvaluation)
        .filter(
            RuleEvaluation.workspace_id == workspace_id,
            RuleEvaluation.patient_id == patient_id,
        )
        .order_by(RuleEvaluation.pk.desc())
        .first()
    )
    if row is None:
        raise AppError(
            code="not_found",
            message="No evaluation recorded for this patient in this session.",
            status_code=404,
        )
    stored = json.loads(row.result_json)
    if ctx is not None:
        db.commit()
    return {
        "patient_id": patient_id,
        "evaluation_id": row.id,
        "pathway": row.pathway,
        "rule_id_version": row.rule_id_version,
        "created_at": row.created_at,
        "input_snapshot": json.loads(row.input_snapshot_json),
        "rule_evaluation": stored.get("rule_evaluation"),
        "legacy_flag_status": stored.get("legacy_flag_status"),
        "api_compatibility": stored.get("api_compatibility"),
        "flag_status": stored.get("flag_status"),
        "factors": stored.get("factors", []),
        "missing": stored.get("missing", []),
    }


def list_evaluations(
    db: Session,
    *,
    workspace_id: str,
    patient_id: str,
    ctx: TrustedRequestContext | None = None,
) -> list[dict]:
    if ctx is not None:
        authorize(
            db,
            ctx,
            action="evaluation.run",
            resource_type="Patient",
            resource_id=patient_id,
            patient_id=patient_id,
        )
    rows = (
        db.query(RuleEvaluation)
        .filter(
            RuleEvaluation.workspace_id == workspace_id,
            RuleEvaluation.patient_id == patient_id,
        )
        .order_by(RuleEvaluation.pk.desc())
        .all()
    )
    results = []
    for row in rows:
        stored = json.loads(row.result_json)
        results.append(
            {
                "patient_id": patient_id,
                "evaluation_id": row.id,
                "pathway": row.pathway,
                "rule_id_version": row.rule_id_version,
                "created_at": row.created_at,
                "rule_evaluation": stored.get("rule_evaluation"),
                "legacy_flag_status": stored.get("legacy_flag_status"),
                "api_compatibility": stored.get("api_compatibility"),
                "flag_status": stored.get("flag_status"),
            }
        )
    if ctx is not None:
        db.commit()
    return results

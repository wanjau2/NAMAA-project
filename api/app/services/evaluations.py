from __future__ import annotations

import json
import uuid

from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.models import CareGap, Case, Event, Observation, Patient, RuleEvaluation
from app.rules import evaluate_patient
from app.schemas import EvaluationResult
from app.security.context import TrustedRequestContext
from app.security.enforce import authorize
from app.services.serializers import case_to_out

_OUTCOME_TO_LEGACY = {
    "gap_identified": "gap",
    "no_gap_identified_in_available_data": "no_gap",
    "needs_review": "needs_review",
    "not_eligible": "not_eligible",
}


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

    observations = (
        db.query(Observation)
        .filter(
            Observation.workspace_id == workspace_id,
            Observation.patient_id == patient_id,
        )
        .all()
    )

    result = evaluate_patient(patient, observations, pathway)
    eval_id = f"eval-{uuid.uuid4().hex[:12]}"

    db.add(
        RuleEvaluation(
            id=eval_id,
            workspace_id=workspace_id,
            patient_id=patient_id,
            pathway=result.pathway,
            rule_id_version=result.rule_id_version,
            input_snapshot_json=json.dumps(
                {
                    "patient_id": patient_id,
                    "age_band": patient.age_band,
                    "observation_ids": [o.id for o in observations],
                }
            ),
            result_json=json.dumps(
                {
                    "flag_status": result.flag_status,
                    "factors": result.factors,
                    "missing": result.missing,
                }
            ),
            created_at=settings.demo_now,
        )
    )

    case_out = None
    if result.flag_status in {"gap", "needs_review"}:
        open_case = (
            db.query(Case)
            .filter(
                Case.workspace_id == workspace_id,
                Case.patient_id == patient_id,
                Case.pathway == result.pathway,
                Case.rule_id_version == result.rule_id_version,
                Case.stage != "closed",
            )
            .one_or_none()
        )
        if open_case is None:
            gap_id = f"gap-{uuid.uuid4().hex[:8]}"
            case_id = f"case-{uuid.uuid4().hex[:8]}"
            gap = CareGap(
                id=gap_id,
                workspace_id=workspace_id,
                patient_id=patient_id,
                pathway=result.pathway,
                rule_id_version=result.rule_id_version,
                flag_status=result.flag_status,
                factors_json=json.dumps(result.factors),
                missing_json=json.dumps(result.missing),
                uncertainty=result.uncertainty,
                explanation=result.explanation,
                suggested_review_action=result.suggested_review_action,
            )
            case = Case(
                id=case_id,
                workspace_id=workspace_id,
                care_gap_id=gap_id,
                patient_id=patient_id,
                patient_label=patient.label,
                age_band=patient.age_band,
                pathway=result.pathway,
                rule_id_version=result.rule_id_version,
                flag_status=result.flag_status,
                stage="identified",
                disposition="active",
                owner="Coordinator 1",
                next_action=result.suggested_review_action,
                due_time=None,
                overdue=False,
                revision=1,
                eligible=True,
            )
            db.add(gap)
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
                    reason=result.explanation,
                    request_id=eval_id,
                )
            )
            db.flush()
            case_out = case_to_out(db, case)
        else:
            gap = (
                db.query(CareGap)
                .filter(
                    CareGap.workspace_id == workspace_id,
                    CareGap.id == open_case.care_gap_id,
                )
                .one()
            )
            gap.flag_status = result.flag_status
            gap.factors_json = json.dumps(result.factors)
            gap.missing_json = json.dumps(result.missing)
            gap.uncertainty = result.uncertainty
            gap.explanation = result.explanation
            gap.suggested_review_action = result.suggested_review_action
            open_case.flag_status = result.flag_status
            open_case.next_action = result.suggested_review_action
            open_case.revision += 1
            db.flush()
            case_out = case_to_out(db, open_case)

    outcome = getattr(result, "outcome", None) or {
        "gap": "gap_identified",
        "needs_review": "needs_review",
        "no_gap": "no_gap_identified_in_available_data",
        "not_eligible": "not_eligible",
    }.get(result.flag_status, "needs_review")
    legacy = _OUTCOME_TO_LEGACY.get(outcome, result.flag_status)
    rule_evaluation = {
        "patient_reference": f"Patient/{patient_id}",
        "as_of": settings.demo_now[:10],
        "rule_id": result.rule_id_version,
        "rule_version": getattr(result, "rule_version", "synthetic-1.0.0"),
        "outcome": outcome,
        "input_versions": result.input_versions
        or [{"reference": f"Patient/{patient_id}", "version": "app-1"}],
        "contributing_factors": [f.get("label", "") for f in result.factors],
        "missing_information": [m.get("label", "") for m in result.missing],
        "due_date": getattr(result, "due_date", None),
        "simulated": True,
        "synthetic_rule": True,
    }
    api_compat = (
        "api_outcome_extension_required"
        if legacy == "not_eligible"
        else "current_api_outcome_supported"
    )

    db.commit()
    return EvaluationResult(
        patient_id=patient_id,
        pathway=result.pathway,  # type: ignore[arg-type]
        rule_id_version=result.rule_id_version,
        flag_status=legacy,  # type: ignore[arg-type]
        factors=result.factors,  # type: ignore[arg-type]
        missing=result.missing,  # type: ignore[arg-type]
        uncertainty=result.uncertainty,
        suggested_review_action=result.suggested_review_action,
        case=case_out,
        evaluation_id=eval_id,
        rule_evaluation=rule_evaluation,
        legacy_flag_status=None if legacy == "not_eligible" else legacy,
        api_compatibility=api_compat,
    )
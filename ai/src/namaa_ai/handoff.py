"""Lossless rule-evaluation handoff for backend integration."""
from .contracts import RuleEvaluation, RuleEvaluationHandoff


def prepare_rule_handoff(evaluation: RuleEvaluation) -> RuleEvaluationHandoff:
    """Preserve Alfred's full result and expose an explicitly lossy legacy projection.

    This is not a direct payload for ``EvaluationResult``: the backend response
    schema also requires API-specific factors, uncertainty and case fields. The
    canonical nested result must be persisted alongside any legacy flag.
    """
    if not isinstance(evaluation, RuleEvaluation):
        raise TypeError("Expected a canonical Alfred RuleEvaluation")
    status = {
        "gap_identified": "gap",
        "no_gap_identified_in_available_data": "no_gap",
        "needs_review": "needs_review",
        "not_eligible": None,
    }[evaluation.outcome]
    return RuleEvaluationHandoff(
        evaluation=evaluation,
        legacy_flag_status=status,
        api_compatibility=("api_outcome_extension_required" if status is None
                           else "current_api_outcome_supported"),
    )

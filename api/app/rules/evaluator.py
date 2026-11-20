"""Placeholder removed. Evaluations call `namaa_ai.rules.evaluate` via the evaluation service."""

from __future__ import annotations


def evaluate_patient(*_args, **_kwargs):
    raise RuntimeError(
        "app.rules.evaluator.evaluate_patient was removed. "
        "Use namaa_ai.rules.evaluate on a reviewed RuleSnapshot."
    )

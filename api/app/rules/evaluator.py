"""Deterministic demo rules — placeholder until Alfred's module lands.

Labels DEMO_WCV_01 / DEMO_ADULT_01 are demonstration rules only.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.models import Observation, Patient


@dataclass
class RuleResult:
    pathway: str
    rule_id_version: str
    flag_status: str
    factors: list[dict]
    missing: list[dict]
    uncertainty: str
    suggested_review_action: str
    explanation: str


def evaluate_patient(
    patient: Patient,
    observations: list[Observation],
    pathway: str | None = None,
) -> RuleResult:
    age = patient.age_band
    is_child = age.startswith(("0", "1", "2", "3", "4", "5")) or "years" in age and any(
        x in age for x in ("0–", "1–", "2–", "3–", "4–", "5–")
    )
    # Prefer explicit pathway; otherwise infer from age band used in seed.
    chosen = pathway or ("child_wcv" if is_child else "adult_screening")

    if chosen == "child_wcv":
        visit = next((o for o in observations if o.type == "last_wcv"), None)
        if visit is None or visit.missing_or_conflict or not visit.verified:
            return RuleResult(
                pathway="child_wcv",
                rule_id_version="DEMO_WCV_01",
                flag_status="needs_review",
                factors=[
                    {
                        "label": "Age band",
                        "value": patient.age_band,
                        "source": f"Patient/{patient.id}",
                        "observed_time": "2026-11-17T09:00:00Z",
                        "verified": True,
                    },
                    {
                        "label": "Last well-child visit",
                        "value": visit.value if visit else "Not documented in available records",
                        "source": visit.source if visit else f"Patient/{patient.id}",
                        "observed_time": visit.observed_time if visit else "2026-11-17T09:00:00Z",
                        "verified": False,
                    },
                ],
                missing=[
                    {
                        "label": "Last well-child visit date is unknown",
                        "consequence": (
                            "Cannot determine whether a visit is overdue. "
                            "Unknown is not the same as up to date."
                        ),
                    }
                ],
                uncertainty="Last visit date unknown",
                suggested_review_action=(
                    "Resolve the unknown last-visit date, then re-evaluate before any invitation"
                ),
                explanation=(
                    "DEMO_WCV_01 could not establish whether a well-child visit is due, "
                    "because the last visit date is unknown. The rule returns needs review "
                    "rather than an invitation."
                ),
            )

        return RuleResult(
            pathway="child_wcv",
            rule_id_version="DEMO_WCV_01",
            flag_status="gap",
            factors=[
                {
                    "label": "Last well-child visit",
                    "value": visit.value,
                    "source": visit.source,
                    "observed_time": visit.observed_time,
                    "verified": True,
                }
            ],
            missing=[],
            uncertainty="",
            suggested_review_action="Clinical reviewer to confirm eligibility",
            explanation=(
                "DEMO_WCV_01 matched on verified records. Prioritization for human review only."
            ),
        )

    screening = next((o for o in observations if o.type == "screening_window"), None)
    return RuleResult(
        pathway="adult_screening",
        rule_id_version="DEMO_ADULT_01",
        flag_status="gap",
        factors=[
            {
                "label": "No screening record within the configured window",
                "value": screening.value if screening else "None found in available records",
                "source": screening.source if screening else f"Patient/{patient.id}",
                "observed_time": (
                    screening.observed_time if screening else "2026-11-17T09:00:00Z"
                ),
                "verified": True,
            }
        ],
        missing=[],
        uncertainty="",
        suggested_review_action="Clinical reviewer to confirm eligibility before invitation",
        explanation=(
            "DEMO_ADULT_01 identified a screening gap from available verified records. "
            "This is not a diagnosis or an automatic screening order."
        ),
    )
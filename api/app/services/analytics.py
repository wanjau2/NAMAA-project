from __future__ import annotations

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Case
from app.schemas import AnalyticsOverview, MetricCell, PathwayMetrics


def _cell(
    *,
    label: str,
    numerator: int,
    denominator: int,
    threshold: int,
    as_rate: bool = False,
) -> MetricCell:
    """Suppress when either numerator or complementary count is below threshold."""
    if denominator == 0:
        return MetricCell(
            label=label,
            numerator=0,
            denominator=0,
            value=0.0 if as_rate else None,
            suppressed=False,
        )

    complementary = denominator - numerator
    if numerator < threshold or complementary < threshold:
        return MetricCell(
            label=label,
            numerator=None,
            denominator=None,
            value=None,
            suppressed=True,
            reason="small_cell",
            threshold=threshold,
        )

    value = round(numerator / denominator, 4) if as_rate else None
    return MetricCell(
        label=label,
        numerator=numerator,
        denominator=denominator,
        value=value,
        suppressed=False,
        threshold=threshold,
    )


def _count(cases: list[Case], pred) -> int:
    return sum(1 for c in cases if pred(c))


def build_overview(db: Session, workspace_id: str) -> AnalyticsOverview:
    settings = get_settings()
    threshold = settings.small_cell_threshold
    cases = (
        db.query(Case)
        .filter(Case.workspace_id == workspace_id, Case.eligible.is_(True))
        .all()
    )

    pathways: list[PathwayMetrics] = []
    for pathway in ("child_wcv", "adult_screening"):
        cohort = [c for c in cases if c.pathway == pathway]
        eligible = len(cohort)
        invited = _count(
            cohort,
            lambda c: c.stage in {"invited", "booked", "attended", "follow_up", "closed"}
            or c.disposition in {"declined", "unreachable"},
        )
        booked = _count(
            cohort, lambda c: c.stage in {"booked", "attended", "follow_up", "closed"}
        )
        attended = _count(
            cohort, lambda c: c.stage in {"attended", "follow_up", "closed"}
        )
        follow_up = _count(cohort, lambda c: c.stage in {"follow_up", "closed"})
        completed = _count(cohort, lambda c: c.disposition == "completed")
        declined = _count(cohort, lambda c: c.disposition == "declined")
        unreachable = _count(cohort, lambda c: c.disposition == "unreachable")

        pathways.append(
            PathwayMetrics(
                pathway=pathway,  # type: ignore[arg-type]
                eligible=_cell(
                    label="Eligible due",
                    numerator=eligible,
                    denominator=max(eligible, 1),
                    threshold=threshold,
                ),
                invited=_cell(
                    label="Invited",
                    numerator=invited,
                    denominator=eligible,
                    threshold=threshold,
                ),
                booked=_cell(
                    label="Booked",
                    numerator=booked,
                    denominator=eligible,
                    threshold=threshold,
                ),
                attended=_cell(
                    label="Attended",
                    numerator=attended,
                    denominator=eligible,
                    threshold=threshold,
                ),
                follow_up=_cell(
                    label="Follow-up",
                    numerator=follow_up,
                    denominator=eligible,
                    threshold=threshold,
                ),
                completed=_cell(
                    label="Completed care",
                    numerator=completed,
                    denominator=eligible,
                    threshold=threshold,
                    as_rate=True,
                ),
                declined=_cell(
                    label="Declined",
                    numerator=declined,
                    denominator=eligible,
                    threshold=threshold,
                ),
                unreachable=_cell(
                    label="Unreachable",
                    numerator=unreachable,
                    denominator=eligible,
                    threshold=threshold,
                ),
            )
        )

    return AnalyticsOverview(
        as_of=settings.demo_now,
        threshold=threshold,
        pathways=pathways,
    )
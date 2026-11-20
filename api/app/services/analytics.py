from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai_runtime import ensure_namaa_ai
from app.config import get_settings
from app.models import Case, Event
from app.schemas import AnalyticsOverview, MetricCell, PathwayMetrics

ensure_namaa_ai()

from namaa_ai.analytics import funnel_cells, publish_population  # noqa: E402

COMPLETION_EVIDENCE = {"Encounter", "Procedure", "DiagnosticReport"}
EVENT_ACTIONS = {
    "invited": "send_invitation",
    "booked": "book_appointment",
    "attended": "record_attendance",
    "follow-up": "record_referral_outcome",
}


def _published_cell(published, *, label: str, as_rate: bool = False, threshold: int) -> MetricCell:
    return MetricCell(
        label=label,
        numerator=published.count,
        denominator=published.denominator,
        value=None if published.rate is None or not as_rate else round(published.rate, 4),
        suppressed=published.suppressed,
        reason=published.suppression_reason,
        threshold=threshold,
    )


def _eligible_cell(*, eligible: int, suppressed: bool, threshold: int) -> MetricCell:
    """Cohort size is a denominator, never a self-complement cell (I19)."""
    if suppressed:
        return MetricCell(
            label="Eligible due (denominator)",
            numerator=None,
            denominator=None,
            suppressed=True,
            reason="release_suppressed",
            threshold=threshold,
        )
    return MetricCell(
        label="Eligible due (denominator)",
        numerator=eligible,
        denominator=None,
        suppressed=False,
        threshold=threshold,
    )


def _case_ids_with_action(
    db: Session, workspace_id: str, case_ids: set[str], action: str
) -> set[str]:
    if not case_ids:
        return set()
    rows = (
        db.query(Event.case_id)
        .filter(
            Event.workspace_id == workspace_id,
            Event.case_id.in_(case_ids),
            Event.action == action,
        )
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def _funnel_counts(
    db: Session, workspace_id: str, cohort: list[Case]
) -> dict[str, int]:
    ids = {c.id for c in cohort}
    invited = _case_ids_with_action(db, workspace_id, ids, EVENT_ACTIONS["invited"])
    booked = _case_ids_with_action(db, workspace_id, ids, EVENT_ACTIONS["booked"])
    attended = _case_ids_with_action(db, workspace_id, ids, EVENT_ACTIONS["attended"])
    follow_up = _case_ids_with_action(db, workspace_id, ids, EVENT_ACTIONS["follow-up"])
    completed = {
        c.id
        for c in cohort
        if c.disposition == "completed" and c.evidence_type in COMPLETION_EVIDENCE
    }
    declined = {c.id for c in cohort if c.disposition == "declined"}
    unreachable = {c.id for c in cohort if c.disposition == "unreachable"}
    return {
        "eligible": len(cohort),
        "invited": len(invited),
        "booked": len(booked),
        "attended": len(attended),
        "follow-up": len(follow_up),
        "completed": len(completed),
        "declined": len(declined),
        "unreachable": len(unreachable),
    }


def _release(db: Session, workspace_id: str):
    settings = get_settings()
    cases = (
        db.query(Case)
        .filter(Case.workspace_id == workspace_id, Case.eligible.is_(True))
        .all()
    )
    child = [c for c in cases if c.pathway == "child_wcv"]
    adult = [c for c in cases if c.pathway == "adult_screening"]
    segments = {
        "overview": _funnel_counts(db, workspace_id, cases),
        "child_wcv": _funnel_counts(db, workspace_id, child),
        "adult_screening": _funnel_counts(db, workspace_id, adult),
    }
    cells = funnel_cells(segments)
    views = publish_population(
        cells,
        projection_version="demo-analytics-1",
        threshold=max(10, settings.small_cell_threshold),
    )
    return views, segments, max(10, settings.small_cell_threshold), settings.demo_now


def _pathway_metrics(views, segments: dict[str, dict[str, int]], pathway: str, threshold: int) -> PathwayMetrics:
    by_id = {cell.metric_id: cell for cell in views.segments if cell.segment == pathway}
    counts = segments[pathway]
    return PathwayMetrics(
        pathway=pathway,  # type: ignore[arg-type]
        eligible=_eligible_cell(
            eligible=counts["eligible"],
            suppressed=views.suppressed,
            threshold=threshold,
        ),
        invited=_published_cell(by_id["invited"], label="Invited", threshold=threshold),
        booked=_published_cell(by_id["booked"], label="Booked", threshold=threshold),
        attended=_published_cell(by_id["attended"], label="Attended", threshold=threshold),
        follow_up=_published_cell(by_id["follow-up"], label="Follow-up", threshold=threshold),
        completed=_published_cell(
            by_id["completed"], label="Completed care", as_rate=True, threshold=threshold
        ),
        declined=_published_cell(by_id["declined"], label="Declined", threshold=threshold),
        unreachable=_published_cell(by_id["unreachable"], label="Unreachable", threshold=threshold),
    )


def build_overview(db: Session, workspace_id: str) -> AnalyticsOverview:
    views, segments, threshold, as_of = _release(db, workspace_id)
    return AnalyticsOverview(
        as_of=as_of,
        threshold=threshold,
        pathways=[
            _pathway_metrics(views, segments, "child_wcv", threshold),
            _pathway_metrics(views, segments, "adult_screening", threshold),
        ],
        notice=(
            "All figures are synthetic demo data. "
            "Eligible is a denominator, not a self-complement cell. "
            "One suppress_population() family feeds overview and segments."
        ),
    )


def build_segments(db: Session, workspace_id: str) -> dict:
    views, _segments, threshold, as_of = _release(db, workspace_id)
    return {
        "synthetic": True,
        "as_of": as_of,
        "threshold": threshold,
        "projection_version": views.projection_version,
        "suppressed": views.suppressed,
        "segments": [cell.model_dump(mode="json") for cell in views.segments],
        "notice": (
            "Segments are a view of the same publication family as /overview. "
            "Do not recover hidden counts by subtraction."
        ),
    }

"""Pure disclosure policy over rebuildable, backend-scoped population counts.

Release overview and all segment margins together. If any cell or its complement
is small, suppress the entire release, including totals and denominators. This
conservative policy prevents subtraction within that release. The backend owns
fixed cohorts, authorization and protections against differencing across releases.
"""
from typing import Literal

from pydantic import Field, StrictBool, model_validator

from .contracts import Contract, LogicalId


class MetricCount(Contract):
    metric_id: LogicalId
    segment: str = Field(min_length=1, max_length=120)
    count: int = Field(ge=0, strict=True)
    denominator: int = Field(ge=0, strict=True)
    denominator_label: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def subset(self):
        if self.count > self.denominator:
            raise ValueError("metric_count_exceeds_denominator")
        return self


class PublishedMetric(Contract):
    metric_id: LogicalId
    segment: str
    count: int | None
    denominator: int | None
    denominator_label: str
    rate: float | None
    suppressed: bool
    suppression_reason: Literal["release_suppressed"] | None


class AnalyticsRelease(Contract):
    projection_version: LogicalId
    suppression_threshold: int = Field(ge=10)
    cells: tuple[PublishedMetric, ...]


class AnalyticsViews(Contract):
    """Overview and segments selected from one suppressed release. Never recompute."""
    projection_version: LogicalId
    suppression_threshold: int = Field(ge=10)
    suppressed: StrictBool
    overview: tuple[PublishedMetric, ...]
    segments: tuple[PublishedMetric, ...]


OVERVIEW_SEGMENT = "overview"
FUNNEL_METRICS = ("invited", "booked", "attended", "follow_up", "completed", "declined", "unreachable")


def suppress_population(cells: tuple[MetricCount, ...], *, projection_version: str,
                        threshold: int = 10) -> AnalyticsRelease:
    """One fixed, complete publication family; never pass individual cells here."""
    if type(threshold) is not int or threshold < 10:
        raise ValueError("suppression_threshold_must_be_at_least_ten")
    cells = tuple(MetricCount.model_validate(cell.model_dump()) for cell in cells)
    keys = [(cell.metric_id, cell.segment) for cell in cells]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate_metric_segment")
    suppressed = any(min(cell.count, cell.denominator, cell.denominator - cell.count) < threshold
                     for cell in cells)
    return AnalyticsRelease(projection_version=projection_version, suppression_threshold=threshold,
        cells=tuple(PublishedMetric(metric_id=cell.metric_id, segment=cell.segment,
            count=None if suppressed else cell.count,
            denominator=None if suppressed else cell.denominator,
            denominator_label=cell.denominator_label,
            rate=None if suppressed else cell.count / cell.denominator,
            suppressed=suppressed, suppression_reason="release_suppressed" if suppressed else None)
            for cell in cells))


def funnel_cells(
    segments: dict[str, dict[str, int]],
    *,
    denominator_label: str = "Eligible patient-pathways at cohort entry",
) -> tuple[MetricCount, ...]:
    """Build the publication family. Cohort size is the denominator, never a cell.

    Do not pass eligible/eligible rows: a zero complement would suppress the
    entire release even for a large cohort.
    """
    cells = []
    for segment, counts in segments.items():
        if "eligible" not in counts:
            raise ValueError("funnel_requires_eligible_denominator")
        eligible = counts["eligible"]
        for metric_id, count in counts.items():
            if metric_id == "eligible":
                continue
            if metric_id not in FUNNEL_METRICS:
                raise ValueError("unsupported_funnel_metric")
            cells.append(MetricCount(metric_id=metric_id, segment=segment, count=count,
                                     denominator=eligible, denominator_label=denominator_label))
    return tuple(cells)


def publish_population(cells: tuple[MetricCount, ...], *, projection_version: str,
                       threshold: int = 10) -> AnalyticsViews:
    """Suppress once, then expose overview and segment views of the same release."""
    release = suppress_population(cells, projection_version=projection_version, threshold=threshold)
    overview = tuple(cell for cell in release.cells if cell.segment == OVERVIEW_SEGMENT)
    segments = tuple(cell for cell in release.cells if cell.segment != OVERVIEW_SEGMENT)
    return AnalyticsViews(projection_version=release.projection_version,
                          suppression_threshold=release.suppression_threshold,
                          suppressed=any(cell.suppressed for cell in release.cells),
                          overview=overview, segments=segments)

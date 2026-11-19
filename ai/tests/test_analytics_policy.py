import pytest
from pydantic import ValidationError

from namaa_ai.analytics import (FUNNEL_METRICS, MetricCount, funnel_cells,
                                publish_population, suppress_population)
from namaa_ai.engagement import METRICS


def cell(count, denominator, segment="overview"):
    return MetricCount(metric_id="completed", segment=segment, count=count, denominator=denominator,
                       denominator_label="Eligible patient-pathways at cohort entry")


@pytest.mark.parametrize("count,denominator", [(0, 0), (0, 20), (9, 30), (10, 19), (19, 20), (20, 20)])
def test_small_cells_and_complements_hide_counts_denominators_and_rates(count, denominator):
    published = suppress_population((cell(count, denominator),), projection_version="p1").cells[0]
    assert published.suppressed
    assert published.count is published.denominator is published.rate is None
    assert published.denominator_label == "Eligible patient-pathways at cohort entry"


def test_complementary_suppression_covers_overview_and_other_segments():
    # Overview minus the large segment would disclose the small segment's count.
    cells = (cell(25, 50), cell(5, 10, "group-a"), cell(20, 40, "group-b"))
    release = suppress_population(cells, projection_version="p1")
    assert all(c.suppressed and c.count is c.denominator is c.rate is None for c in release.cells)
    assert {c.suppression_reason for c in release.cells} == {"release_suppressed"}


def test_threshold_is_inclusive_and_published_denominators_are_explicit():
    result = suppress_population((cell(10, 20),), projection_version="p1")
    assert result.cells[0].model_dump() == dict(metric_id="completed", segment="overview", count=10,
        denominator=20, denominator_label="Eligible patient-pathways at cohort entry", rate=.5,
        suppressed=False, suppression_reason=None)


@pytest.mark.parametrize("count,denominator", [(True, 20), (1.0, 20), (21, 20), (-1, 20)])
def test_invalid_projection_counts_fail_closed(count, denominator):
    with pytest.raises(ValidationError):
        cell(count, denominator)


def test_threshold_cannot_be_weakened_and_duplicate_segments_are_rejected():
    with pytest.raises(ValueError):
        suppress_population((cell(10, 20),), projection_version="p1", threshold=9)
    with pytest.raises(ValueError, match="duplicate"):
        suppress_population((cell(10, 20), cell(10, 20)), projection_version="p1")


def test_overview_and_segments_share_one_suppressed_release():
    views = publish_population(
        (cell(25, 50), cell(5, 10, "child_wcv"), cell(20, 40, "adult_screening")),
        projection_version="p1")
    assert views.suppressed
    assert len(views.overview) == 1 and len(views.segments) == 2
    assert all(item.count is item.denominator is item.rate is None
               for item in (*views.overview, *views.segments))


def test_funnel_uses_eligible_as_denominator_not_a_self_complement_cell():
    cells = funnel_cells({
        "child_wcv": {"eligible": 40, "completed": 12, "declined": 10},
        "adult_screening": {"eligible": 40, "completed": 11, "declined": 10},
    })
    assert {cell.metric_id for cell in cells} == {"completed", "declined"}
    assert all(cell.denominator == 40 for cell in cells)
    views = publish_population(cells, projection_version="demo-projection-1")
    assert not views.suppressed
    assert views.overview == ()
    assert {cell.segment for cell in views.segments} == {"child_wcv", "adult_screening"}


def test_funnel_rejects_missing_eligible_denominator():
    with pytest.raises(ValueError, match="eligible"):
        funnel_cells({"child_wcv": {"completed": 12}})


def test_funnel_rejects_metrics_outside_the_fixed_family():
    assert "eligible" not in FUNNEL_METRICS
    with pytest.raises(ValueError, match="unsupported_funnel_metric"):
        funnel_cells({"child_wcv": {"eligible": 40, "completed": 12, "other": 1}})


def test_completion_definition_requires_evidence_and_reviewer_authorization():
    metric = next(m for m in METRICS if m.metric_id == "gap-completion-rate")
    assert "reviewer authorization" in metric.numerator
    assert all(t in metric.numerator for t in ("Encounter", "Procedure", "DiagnosticReport"))
    assert "attendance without" in " ".join(metric.exclusions)

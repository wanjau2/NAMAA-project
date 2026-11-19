import pytest
from pydantic import ValidationError

from namaa_ai.analytics import MetricCount, suppress_population
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


def test_completion_definition_requires_evidence_and_reviewer_authorization():
    metric = next(m for m in METRICS if m.metric_id == "gap-completion-rate")
    assert "reviewer authorization" in metric.numerator
    assert all(t in metric.numerator for t in ("Encounter", "Procedure", "DiagnosticReport"))
    assert "attendance without" in " ".join(metric.exclusions)

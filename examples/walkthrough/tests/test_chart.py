"""Plotly adapters preserve financial data, dates, units and caller ownership."""

from datetime import date

import plotly.graph_objects as go
import plotly.io as pio
import pytest
from helpers.chart import plot_distribution, plot_flows, plot_pairs

from rangekeeper.model.duration import Frequency, PeriodTiming, make_periods
from rangekeeper.model.flux import Flow


def test_flow_panels_preserve_dates_units_signs_and_inputs():
    dates = [date(2027, 12, 31), date(2028, 12, 31)]
    income = Flow.from_events(dates, [120, 130], units="AUD")
    cost = Flow.from_events(dates, [-40, -50], units="AUD")
    area = Flow.from_events(dates, [1000, 1100], units="m^2")
    flows = {"Income": income, "Area": area, "Cost": cost}
    before = {key: flow.to_data() for key, flow in flows.items()}
    default = pio.templates.default

    figure = plot_flows(flows)

    assert isinstance(figure, go.Figure)
    assert [trace.name for trace in figure.data] == list(flows)
    assert [trace.yaxis for trace in figure.data] == ["y", "y2", "y"]
    assert tuple(figure.data[0].x) == tuple(dates)
    assert tuple(figure.data[2].y) == (-40, -50)
    assert figure.layout.yaxis.title.text == "AUD"
    assert figure.layout.yaxis2.title.text == "m^2"
    assert {key: flow.to_data() for key, flow in flows.items()} == before
    assert pio.templates.default == default


def test_period_flows_require_explicit_timing_and_resolved_values():
    periods = make_periods(date(2027, 1, 1), frequency=Frequency.YEAR, count=2)
    flow = Flow.from_periods(periods, [10, 20], units="AUD")
    with pytest.raises(ValueError):
        plot_flows({"Rent": flow})
    figure = plot_flows({"Rent": flow}, timing=PeriodTiming.LAST)
    assert tuple(figure.data[0].x) == (date(2027, 12, 31), date(2028, 12, 31))
    unknown = Flow.from_periods(periods, [10, None], units="AUD")
    with pytest.raises(ValueError, match="resolved"):
        plot_flows({"Rent": unknown}, timing=PeriodTiming.LAST)
    with pytest.raises(ValueError, match="requires Flows"):
        plot_flows({})


def test_distribution_preserves_samples_and_empirical_probabilities():
    samples = {"Base": [3, -1, 3, 2]}
    histogram = plot_distribution(samples, units="AUD")
    assert tuple(histogram.data[0].x) == (3, -1, 3, 2)
    assert histogram.layout.yaxis.title.text == "Scenario count"
    cumulative = plot_distribution(samples, units="AUD", cumulative=True)
    assert tuple(cumulative.data[0].x) == (-1, 2, 3, 3)
    assert tuple(cumulative.data[0].y) == (0.25, 0.5, 0.75, 1)
    assert cumulative.data[0].line.shape == "hv"
    assert tuple(cumulative.layout.yaxis.range) == (0, 1)
    assert samples == {"Base": [3, -1, 3, 2]}


@pytest.mark.parametrize("values", [[], [float("nan")], [float("inf")]])
def test_distribution_rejects_unusable_samples(values):
    with pytest.raises(ValueError, match="nonempty finite"):
        plot_distribution({"Sample": values}, units="AUD")


def test_pairs_preserve_scenario_alignment_and_labels():
    figure = plot_pairs([3, 1], [-8, 4], x_label="Base (AUD)", y_label="Change (AUD)")
    assert list(zip(figure.data[0].x, figure.data[0].y, strict=True)) == [
        (3, -8),
        (1, 4),
    ]
    assert figure.layout.xaxis.title.text == "Base (AUD)"
    assert figure.layout.yaxis.title.text == "Change (AUD)"
    for x, y in [([], []), ([1], [1, 2]), ([float("nan")], [1])]:
        with pytest.raises(ValueError, match="matching finite"):
            plot_pairs(x, y, x_label="x", y_label="y")

"""Flows carry quantities; model-selected operations supply their interpretation."""

import json
from datetime import date
from uuid import uuid4

import pytest

from rangekeeper.duration import Frequency, Span, make_period, make_periods
from rangekeeper.flow import (
    Flow,
    MeanWeighting,
    MissingValueHandling,
    Movement,
    ResamplingMethod,
    Stream,
)
from rangekeeper.quantity import Quantity
from rangekeeper.shared.errors import ValidationError
from tests.streams import lines


@pytest.mark.parametrize("field", ["basis", "kind"])
def test_flow_wire_contract_rejects_semantic_classification(field):
    flow = Flow.from_events([date(2026, 1, 1)], [100], units="AUD")
    payload = flow.to_data()
    assert set(payload) == {"units", "movements"}
    assert Flow.from_json(json.dumps(payload)) == flow
    with pytest.raises(ValidationError):
        Flow.from_data({**payload, field: "movement"})


@pytest.mark.parametrize("include_movements", [False, True])
def test_old_samples_field_is_rejected_instead_of_losing_entries(include_movements):
    movement = Movement(id=uuid4(), key="payment", date=date(2026, 1, 1), magnitude=100)
    payload = {"units": "AUD", "samples": [movement.to_data()]}
    if include_movements:
        payload["movements"] = []
    with pytest.raises(ValidationError):
        Flow.from_data(payload)


@pytest.mark.parametrize(
    "reduction,expected",
    [("sum", 30), ("first", 10), ("last", 20), ("min", 10), ("max", 20), ("mean", 15)],
)
def test_model_can_select_different_reductions_for_the_same_flow(reduction, expected):
    flow = Flow.from_events(
        [date(2026, 1, 1), date(2026, 1, 31)], [10, 20], units="AUD"
    )
    before = flow.to_data()
    result = flow.resample(
        [make_period(date(2026, 1, 1), date(2026, 2, 1))],
        method=ResamplingMethod(reduction),
        weighting=MeanWeighting.OBSERVATIONS if reduction == "mean" else None,
    )
    assert result.movements[0].magnitude == expected
    assert result.units == "AUD" and flow.to_data() == before


def test_means_require_a_choice_and_do_not_infer_weighting_from_units():
    periods = make_periods(date(2026, 1, 1), frequency=Frequency.MONTH, count=2)
    flow = Flow.from_periods(periods, [10, 20], units="dimensionless")
    target = [make_period(periods[0].start, periods[-1].end)]
    with pytest.raises(ValueError, match="weighting"):
        flow.resample(target, method=ResamplingMethod.MEAN)
    observed = flow.resample(
        target, method=ResamplingMethod.MEAN, weighting=MeanWeighting.OBSERVATIONS
    )
    elapsed = flow.resample(
        target, method=ResamplingMethod.MEAN, weighting=MeanWeighting.ELAPSED
    )
    assert observed.movements[0].magnitude == 15
    assert elapsed.movements[0].number == pytest.approx((31 * 10 + 28 * 20) / 59)


def test_products_preserve_time_dimensions_and_scaled_dimensionless_units():
    periods = make_periods(date(2026, 1, 1), frequency=Frequency.MONTH, count=1)
    rates = Flow.from_periods(periods, [2], units="AUD/day")
    factors = Flow.from_periods(periods, [50], units="percent")
    squared = rates.multiply(rates, factors).convert(units="AUD**2/day**2")
    assert squared.movements[0].magnitude == 2
    dimensionless = factors.multiply(factors)
    assert dimensionless.units == "dimensionless"
    assert dimensionless.movements[0].magnitude == 0.25


def test_exposure_is_an_explicit_operation_without_a_rate_classification():
    length = Flow.from_events([date(2026, 1, 1)], [2], units="m")
    area = length.integrate(exposures=[Quantity(magnitude=3, units="m")], units="m**2")
    assert area.movements[0].magnitude == 6
    assert length.movements[0].magnitude == 2
    with pytest.raises(ValueError, match="exposures or day_count"):
        length.integrate()


@pytest.mark.parametrize("reduction", ["sum", "last", "mean"])
def test_explicit_zero_fill_does_not_resolve_present_unknowns(reduction):
    periods = make_periods(date(2026, 1, 1), frequency=Frequency.MONTH, count=3)
    flow = Flow.from_periods(periods[:2], [10, None], units="AUD")
    result = lines([flow]).resample(
        periods,
        method=ResamplingMethod(reduction),
        weighting=MeanWeighting.OBSERVATIONS if reduction == "mean" else None,
        missing=MissingValueHandling.ZERO,
    )
    assert [s.magnitude for s in result.flows[0].movements] == [10, None, 0]
    assert result.coverage["0"] == (1, 0, 0)


def test_flow_and_stream_trim_take_the_same_span():
    periods = make_periods(date(2026, 1, 1), frequency=Frequency.MONTH, count=3)
    flow = Flow.from_periods(periods, [1, 2, 3], units="AUD")
    span = Span(start=periods[1].start, end=periods[2].end, name="later")
    assert [m.number for m in flow.trim(span).movements] == [2, 3]
    assert flow.trim(span) == Stream({"a": flow}).trim(span).flows[0]
    with pytest.raises(TypeError, match="Period or Span"):
        flow.trim((periods[1].start, periods[2].end))

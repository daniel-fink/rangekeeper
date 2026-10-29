"""Flows carry quantities; model-selected operations supply their interpretation."""

import json
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from uuid import uuid4

import pytest

from rangekeeper.duration import DayCount, Frequency, Period, Periods, Span
from rangekeeper.errors import Code, MissingReferenceError
from rangekeeper.flow import (
    Flow,
    MissingValueHandling,
    Movement,
    ResampleMethod,
    Stream,
)
from rangekeeper.money import RoundingMode
from rangekeeper.quantity import Quantity
from rangekeeper.shared.errors import ValidationError
from tests.streams import lines


@pytest.mark.parametrize("field", ["basis", "kind"])
def test_flow_wire_contract_rejects_semantic_classification(field):
    flow = Flow.from_events(dates=[date(2026, 1, 1)], magnitudes=[100], units="AUD")
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
        dates=[date(2026, 1, 1), date(2026, 1, 31)], magnitudes=[10, 20], units="AUD"
    )
    before = flow.to_data()
    result = flow.resample(
        periods=[Period(start=date(2026, 1, 1), end=date(2026, 2, 1))],
        method=ResampleMethod(reduction),
    )
    assert result.movements[0].magnitude == expected
    assert result.units == "AUD" and flow.to_data() == before


def test_each_mean_is_its_own_method_and_units_do_not_choose_it():
    periods = Periods(start=date(2026, 1, 1), frequency=Frequency.MONTH, count=2)
    flow = Flow.from_periods(
        periods=periods, magnitudes=[10, 20], units="dimensionless"
    )
    target = [Period(start=periods[0].start, end=periods[-1].end)]
    observed = flow.resample(periods=target, method=ResampleMethod.MEAN)
    elapsed = flow.resample(periods=target, method=ResampleMethod.ELAPSED_MEAN)
    assert observed.movements[0].magnitude == 15
    assert elapsed.movements[0].number == pytest.approx((31 * 10 + 28 * 20) / 59)


def test_products_preserve_time_dimensions_and_scaled_dimensionless_units():
    periods = Periods(start=date(2026, 1, 1), frequency=Frequency.MONTH, count=1)
    rates = Flow.from_periods(periods=periods, magnitudes=[2], units="AUD/day")
    factors = Flow.from_periods(periods=periods, magnitudes=[50], units="percent")
    squared = rates.multiply(rates, factors).convert(units="AUD**2/day**2")
    assert squared.movements[0].magnitude == 2
    dimensionless = factors.multiply(factors)
    assert dimensionless.units == "dimensionless"
    assert dimensionless.movements[0].magnitude == 0.25


def test_exposure_is_an_explicit_operation_without_a_rate_classification():
    length = Flow.from_events(dates=[date(2026, 1, 1)], magnitudes=[2], units="m")
    area = length.integrate(exposures=[Quantity(magnitude=3, units="m")], units="m**2")
    assert area.movements[0].magnitude == 6
    assert length.movements[0].magnitude == 2
    with pytest.raises(ValueError, match="exposure count"):
        length.integrate(exposures=[])
    with pytest.raises(ValueError, match="bounded periods"):
        length.integrate_time(day_count=DayCount.ACTUAL_365)


@pytest.mark.parametrize("reduction", ["sum", "last", "mean"])
def test_explicit_zero_fill_does_not_resolve_present_unknowns(reduction):
    periods = Periods(start=date(2026, 1, 1), frequency=Frequency.MONTH, count=3)
    flow = Flow.from_periods(periods=periods[:2], magnitudes=[10, None], units="AUD")
    result = lines([flow], missing=MissingValueHandling.ZERO).resample(
        periods=periods, method=ResampleMethod(reduction)
    )
    assert [s.magnitude for s in result.flows[0].movements] == [10, None, 0]
    assert result.coverage["0"] == (1, 0, 0)


def test_flow_and_stream_trim_take_the_same_span():
    periods = Periods(start=date(2026, 1, 1), frequency=Frequency.MONTH, count=3)
    flow = Flow.from_periods(periods=periods, magnitudes=[1, 2, 3], units="AUD")
    span = Span(start=periods[1].start, end=periods[2].end, name="later")
    assert [m.number for m in flow.trim(span=span).movements] == [2, 3]
    assert flow.trim(span=span) == Stream(flows={"a": flow}).trim(span=span).flows[0]
    with pytest.raises(TypeError, match="Period or Span"):
        flow.trim(span=(periods[1].start, periods[2].end))


def test_total_and_collapse_take_every_missing_policy():
    days = [date(2026, 1, 1), date(2026, 1, 2)]
    partial = Flow.from_events(dates=days, magnitudes=[5, None], units="AUD")
    unknown = Flow.from_events(dates=days, magnitudes=[None, None], units="AUD")
    with pytest.raises(ValueError, match="unresolved"):
        partial.total()
    assert partial.total(missing=MissingValueHandling.PROPAGATE) is None
    assert partial.total(missing=MissingValueHandling.SKIP).number == 5
    assert partial.total(missing=MissingValueHandling.ZERO).number == 5
    assert unknown.total(missing=MissingValueHandling.SKIP) is None
    assert unknown.total(missing=MissingValueHandling.ZERO).number == 0
    collapsed = unknown.collapse(on=days[0], missing=MissingValueHandling.ZERO)
    assert collapsed.movements[0].number == 0


def test_multiply_and_scale_follow_the_operator():
    days = [date(2026, 1, 1), date(2026, 1, 2)]
    claim = uuid4()
    rates = Flow.from_events(dates=days, magnitudes=[2, None], units="AUD/day")
    rates = rates.replace(
        movements=tuple(m.replace(claims=(claim,)) for m in rates.movements)
    )
    factors = Flow.from_events(dates=days, magnitudes=[50, 10], units="percent")
    product = rates.multiply(factors)
    assert product == rates * factors
    assert [m.magnitude for m in product.movements] == [1, None]
    assert product.movements[0].claims == (claim,)
    assert rates.scale(3) == 3 * rates
    with pytest.raises(TypeError, match="number"):
        rates.scale("3")  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="Flows"):
        rates.multiply(2)  # type: ignore[arg-type]


def test_rounding_mode_is_an_enum_of_the_decimal_constants():
    flow = Flow.from_events(dates=[date(2026, 1, 1)], magnitudes=["0.125"], units="AUD")
    assert flow.round().movements[0].magnitude == Decimal("0.12")
    rounded = flow.round(mode=RoundingMode.HALF_UP)
    assert rounded.movements[0].magnitude == Decimal("0.13")
    assert RoundingMode.HALF_UP == ROUND_HALF_UP


def test_select_values_and_with_policy():
    flow = Flow.from_events(dates=[date(2026, 1, 1)], magnitudes=[None], units="AUD")
    stream = Stream(flows={"a": flow, "b": flow})
    with pytest.raises(MissingReferenceError) as missing:
        stream.select_values([uuid4()])
    assert missing.value.code is Code.REFERENCE_MISSING
    assert missing.value.by == "id" and missing.value.where == "Stream"
    with pytest.raises(MissingReferenceError) as named:
        stream.select("c")
    assert named.value.candidates == () and named.value.by == "name"
    with pytest.raises(ValueError, match="at least one"):
        stream.select()
    skipping = stream.with_policy(missing=MissingValueHandling.SKIP)
    assert skipping.missing is MissingValueHandling.SKIP
    assert skipping.join is stream.join
    assert skipping.sum().movements[0].magnitude is None
    with pytest.raises(ValueError, match="unresolved"):
        stream.sum()

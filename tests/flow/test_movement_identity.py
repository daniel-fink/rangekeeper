"""One Movement identity rule for transforms (#162).

A transform keeps the ID of each Movement that it passes through: one that it
selects, or whose amount it gives in other units. Each Movement that it
calculates, its amount or its coordinate, gets a fresh ID, also when the result
equals the input. ``docs/reference/identity.md`` gives the table that these
tests check.
"""

from collections.abc import Callable
from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.duration import Frequency, Period, Periods, PeriodTiming
from rangekeeper.flow import (
    AggregationMethod,
    Flow,
    MissingValueHandling,
    ResampleMethod,
    Stream,
)

QUARTERS = Periods(start=date(2027, 1, 1), frequency=Frequency.QUARTER, count=8)
YEARS = Periods(start=date(2027, 1, 1), frequency=Frequency.YEAR, count=2)


def flow() -> Flow:
    amounts = dict(zip(QUARTERS, (0, 1, 2, 3, 4, 5, 6, 7), strict=True))
    return Flow(amounts=amounts, units="AUD")


def events() -> Flow:
    return Flow(amounts={date(2027, 1, 1): 1, date(2027, 7, 1): 2}, units="AUD")


def ids(result: Flow) -> set[object]:
    return {movement.id for movement in result.movements}


SELECT: dict[str, Callable[[Flow], Flow]] = {
    "trim": lambda f: f.trim(span=YEARS[0]),
    "clean": lambda f: f.clean(),
    "drop_zeroes": lambda f: f.drop_zeroes(),
    "trim_empty": lambda f: f.trim_empty(),
    "convert": lambda f: f.convert(units="AUD"),
    "stream select": lambda f: Stream(flows={"a": f, "b": 2 * f}).select("a")["a"],
    "stream trim": lambda f: Stream(flows={"a": f}).trim(span=YEARS[1])["a"],
    "stream with_flows": lambda f: Stream(flows={"b": 2 * f}).with_flows(
        flows={"a": f}
    )["a"],
    "stream with_policy": lambda f: Stream(flows={"a": f}).with_policy(
        missing=MissingValueHandling.ZERO
    )["a"],
}

CALCULATE: dict[str, Callable[[Flow], Flow]] = {
    "add": lambda f: f + f,
    "subtract": lambda f: f - f,
    "multiply by a number": lambda f: f * 1,
    "divide by a Quantity": lambda f: f / rk.Quantity(text="1 ratio"),
    "unary minus": lambda f: -f,
    "scale": lambda f: f.scale(1),
    "negate": lambda f: f.negate(),
    "round": lambda f: f.round(),
    "shift": lambda f: f.shift(by=0),
    "multiply": lambda f: f.multiply(f),
    "integrate": lambda f: f.integrate(
        exposures=[rk.Quantity(text="1 ratio")] * len(f.movements)
    ),
    "integrate_time": lambda f: f.integrate_time(
        day_count=rk.duration.DayCount.ACTUAL_365, units="AUD year"
    ),
    "cumulative": lambda f: f.cumulative(),
    "diff": lambda f: f.diff(),
    "split": lambda f: f.split(periods=QUARTERS),
    "resample": lambda f: f.resample(periods=QUARTERS, method=ResampleMethod.SUM),
    "collapse": lambda f: f.collapse(on=PeriodTiming.END),
    "clone": lambda f: f.clone(),
    "stream resample": lambda f: Stream(flows={"a": f}).resample(
        periods=QUARTERS, method=ResampleMethod.SUM
    )["a"],
    "stream split": lambda f: Stream(flows={"a": f}).split(periods=QUARTERS)["a"],
    "stream aggregate": lambda f: (
        Stream(flows={"a": f}).aggregate(method=AggregationMethod.SUM).flow
    ),
    "stream sum": lambda f: Stream(flows={"a": f}).sum(),
    "stream min": lambda f: Stream(flows={"a": f}).min(),
    "stream max": lambda f: Stream(flows={"a": f}).max(),
    "stream dated": lambda f: Stream(flows={"a": f}).dated()["a"],
    "present value": lambda f: rk.finance.pv(
        flow=f, rate="5 % pa", on=date(2027, 1, 1)
    ),
}


@pytest.mark.parametrize("name", list(SELECT))
def test_a_transform_that_passes_movements_through_keeps_their_ids(name):
    source = flow()
    result = SELECT[name](source)
    assert result.movements
    assert ids(result) <= ids(source)


@pytest.mark.parametrize("name", list(CALCULATE))
def test_a_transform_that_calculates_movements_gives_fresh_ids(name):
    source = flow()
    result = CALCULATE[name](source)
    assert result.movements
    assert not ids(result) & ids(source)


def test_a_calculation_that_gives_the_same_amounts_still_gives_fresh_ids():
    source = flow()
    for same in (source.scale(1), source.shift(by=0), source.negate().negate()):
        assert same == source
        assert not ids(same) & ids(source)


def test_since_and_until_keep_what_they_pass_and_renew_each_zero():
    source = flow()
    kept, zeros = source.movements[4:], source.movements[:4]
    since = source.since(on=YEARS[1].start)
    assert [m.id for m in since.movements[4:]] == [m.id for m in kept]
    assert not {m.id for m in since.movements[:4]} & {m.id for m in zeros}
    until = source.until(on=QUARTERS[3].start)
    assert [m.id for m in until.movements[:4]] == [m.id for m in zeros]
    assert not {m.id for m in until.movements[4:]} & {m.id for m in kept}


def test_alignment_keeps_present_movements_and_renews_placeholders():
    source = flow()
    short = source.trim(span=YEARS[0])
    aligned = Stream(
        flows={"short": short, "long": source}, missing=MissingValueHandling.ZERO
    ).align()
    assert [m.id for m in aligned["short"].movements[:4]] == [
        m.id for m in short.movements
    ]
    placeholders = ids(aligned["short"]) - ids(short)
    assert len(placeholders) == 4 and not placeholders & ids(source)
    assert ids(aligned["long"]) == ids(source)


def test_dated_keeps_dated_amounts_and_renews_each_period_amount():
    original, period = events(), Flow(amounts={YEARS[0]: 5}, units="AUD")
    dated = Stream(flows={"events": original, "period": period}).dated()
    assert ids(dated["events"]) == ids(original)
    assert dated["period"].movements[0].date == date(2028, 1, 1)
    assert not ids(dated["period"]) & ids(period)


def test_a_passed_through_flow_needs_clone_under_a_second_value():
    source = flow()
    copy = source.trim(span=Period(start=date(2027, 1, 1), end=date(2029, 1, 1)))
    assert ids(copy) == ids(source)
    assert not ids(copy.clone()) & ids(source)

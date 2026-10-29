"""Value types keep their local rules from construction (ADR-011)."""

from datetime import date, timedelta
from uuid import uuid4

import pytest

from rangekeeper.duration import Frequency, Period, Periods, Span
from rangekeeper.flow import Flow, Movement
from rangekeeper.model import Distribution, DistributionFamily, Value, ValueKind
from rangekeeper.shared.errors import ValidationError

DAY = date(2026, 1, 1)


def events(*days, keys=None):
    keys = keys or [None] * len(days)
    return tuple(
        Movement(id=uuid4(), date=day, key=key, magnitude=1)
        for day, key in zip(days, keys, strict=True)
    )


def test_a_period_starts_before_it_ends():
    for end in (DAY, DAY - timedelta(days=1)):
        with pytest.raises(ValidationError, match="end must follow start"):
            Period(start=DAY, end=end)
        with pytest.raises(ValidationError, match="end must follow start"):
            Period.from_data({"start": DAY.isoformat(), "end": end.isoformat()})
        with pytest.raises(ValidationError, match="end must follow start"):
            Span(name="x", start=DAY, end=end)
    period = Period(start=DAY, end=DAY + timedelta(days=1))
    with pytest.raises(ValidationError, match="end must follow start"):
        period.replace(end=DAY)


@pytest.mark.parametrize(
    "movements, message",
    [
        (events(DAY + timedelta(days=1), DAY), "ordered by date"),
        (events(DAY, DAY), "distinct nonblank matching keys"),
        (
            (*events(DAY), *events(DAY + timedelta(days=1)))[:1] * 2,
            "duplicate Movement UUID",
        ),
        (
            (
                *events(DAY),
                Movement(
                    id=uuid4(), period=Period(start=DAY, end=DAY + timedelta(days=1))
                ),
            ),
            "cannot mix",
        ),
    ],
)
def test_a_flow_is_ordered_with_unique_ids(movements, message):
    with pytest.raises(ValidationError, match=message):
        Flow(units="AUD", movements=movements)
    data = {"units": "AUD", "movements": [m.to_data() for m in movements]}
    with pytest.raises(ValidationError, match=message):
        Flow.from_data(data)
    valid = Flow(units="AUD", movements=events(DAY))
    with pytest.raises(ValidationError, match=message):
        valid.replace(movements=movements)


def test_overlapping_periods_are_rejected():
    periods = Periods(start=DAY, frequency=Frequency.MONTH, count=2)
    flow = Flow.from_periods(periods, [1, 2], units="AUD")
    with pytest.raises(ValidationError, match="overlap or are out of order"):
        flow.replace(movements=tuple(reversed(flow.movements)))


def test_nested_value_types_are_checked_by_from_data():
    flow = Flow(units="AUD", movements=events(DAY))
    value = Value(
        id=uuid4(), key="v", kind=ValueKind.FLOW, measure=uuid4(), flow=flow
    ).to_data()
    value["flow"]["movements"] *= 2
    with pytest.raises(ValidationError) as error:
        Value.from_data(value)
    assert error.value.report.issues[0].code == "invariant.Flow"
    assert error.value.report.issues[0].path == "/flow"


def test_distribution_parameters_hold_from_construction():
    with pytest.raises(ValidationError, match="mode outside bounds"):
        Distribution(
            kind=DistributionFamily.TRIANGULAR, lower=0, upper=1, mode=2, units="AUD"
        )
    uniform = Distribution.uniform(lower=0, upper=1)
    with pytest.raises(ValidationError, match="bounds"):
        uniform.replace(lower=2)

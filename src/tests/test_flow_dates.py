"""Date-only coordinates, independent payment dates and explicit timing contracts."""

from rangekeeper.model.duration import Frequency, PeriodTiming, DayCount
from rangekeeper.model.flow import MissingValueHandling
from rangekeeper.calculations.series import (
    AlignmentJoin,
    AggregationReducer,
    ResamplingReduction,
    MeanWeighting,
)
from rangekeeper.calculations.projection import ProjectionMethod
from rangekeeper.calculations.account import Balance, CurrentInterest, InterestTreatment
from rangekeeper.schema.enums import ValueKind

from rangekeeper.model.flow import Flow

from uuid import uuid4
from datetime import date, datetime, timezone

import pytest

from rangekeeper.shared.errors import ValidationError
from rangekeeper.model.duration import Period
from rangekeeper.model.flow import Movement
from rangekeeper.model.duration import make_period, make_periods, offset
from rangekeeper.calculations import financial, series


JANUARY = make_period(date(2026, 1, 1), date(2026, 2, 1))


def test_schema_date_or_timestamp_union_retains_timestamp_support():
    from uuid import uuid4
    from rangekeeper.schema.records import Source

    source = Source(
        id=uuid4(),
        name="Schedule",
        checksum="abc",
        issued_at=date(2026, 1, 1),
        received_at="2026-01-02T09:30:00+11:00",
    )
    restored = Source.from_data(source.to_data())
    assert restored.issued_at == date(2026, 1, 1)
    assert restored.received_at == "2026-01-02T09:30:00+11:00"
    assert restored.to_data() == source.to_data()


def test_date_records_and_detached_wire_format():
    movement = Movement(id=uuid4(), key="delivery", date=date(2026, 1, 2), magnitude=2)
    assert type(movement.date) is date
    assert movement.to_data() == {
        "id": str(movement.id),
        "key": "delivery",
        "date": "2026-01-02",
        "magnitude": 2,
    }
    assert Period.from_data(JANUARY.to_data()) == JANUARY
    assert type(JANUARY.start_inclusive) is date
    data = JANUARY.to_data()
    data["start_inclusive"] = "2000-01-01"
    assert JANUARY.start_inclusive == date(2026, 1, 1)


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 1, 1),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    ],
)
def test_datetimes_are_not_flow_coordinates(value):
    for operation in (
        lambda: Flow.from_events([value], [1], units="m"),
        lambda: make_period(value, date(2026, 2, 1)),
        lambda: offset(value, frequency=Frequency.DAY),
        lambda: Movement(id=uuid4(), key="event", date=value),
        lambda: Period(start_inclusive=value, end_exclusive=date(2026, 2, 1)),
    ):
        with pytest.raises((TypeError, ValidationError)):
            operation()


@pytest.mark.parametrize("value", ["2026-01-01T00:00:00", "2026-02-30", "01/01/2026"])
def test_wire_dates_must_be_valid_iso_dates(value):
    with pytest.raises(ValidationError):
        Movement.from_data({"id": str(uuid4()), "key": "event", "date": value})


def test_sample_needs_date_or_period():
    # Generated records check structure; Flow validation checks this cross-field rule.
    for movement in (
        Movement(id=uuid4(), key="missing"),
        Movement(id=uuid4(), key="null", date=None, period=None),
    ):
        with pytest.raises(ValueError, match="date or period"):
            Flow(units="m", movements=(movement,)).check()


def test_period_timing_is_explicit_and_does_not_change_content():
    flow = Flow.from_periods([JANUARY], [100], units="AUD")
    original = flow.to_data()
    assert "date" not in original["movements"][0]
    for timing, expected in (
        (PeriodTiming.FIRST, date(2026, 1, 1)),
        (PeriodTiming.LAST, date(2026, 1, 31)),
        (PeriodTiming.END, date(2026, 2, 1)),
    ):
        assert flow.movements[0].resolve(timing=timing) == expected
    with pytest.raises(ValueError, match="explicit timing"):
        flow.movements[0].resolve()
    with pytest.raises(ValueError, match="explicit timing"):
        financial.calculate_xnpv(flow, rate=0.1, valuation_date=date(2026, 1, 1))
    assert financial.calculate_xnpv(
        flow, rate=0.1, valuation_date=date(2026, 1, 1), timing=PeriodTiming.END
    ).magnitude == pytest.approx(100 / 1.1 ** (31 / 365))
    assert flow.to_data() == original


def test_payment_date_is_independent_of_coverage():
    flow = Flow.from_periods([JANUARY], [100], units="AUD", dates=[date(2026, 2, 5)])
    assert flow.movements[0].resolve(timing=PeriodTiming.FIRST) == date(2026, 2, 5)
    assert financial.calculate_xnpv(
        flow, rate=0.1, valuation_date=date(2026, 1, 1), timing=PeriodTiming.LAST
    ).magnitude == pytest.approx(100 / 1.1 ** (35 / 365))
    assert flow.trim(start=JANUARY.start_inclusive, end=JANUARY.end) == flow
    assert flow.extent() == (JANUARY.start_inclusive, JANUARY.end)
    with pytest.raises(ValueError, match="crosses a movement period"):
        flow.trim(start=date(2026, 1, 2), end=JANUARY.end)
    # Period aggregation states coverage, rather than inventing one payment date.
    aggregated = series.resample(
        flow, periods=[JANUARY], reduction=ResamplingReduction.SUM
    ).flow
    assert aggregated.movements[0].magnitude == 100
    assert "date" not in aggregated.movements[0].field_names()
    conflicting = Flow.from_periods(
        [JANUARY], [100], units="AUD", dates=[date(2026, 2, 6)]
    )
    with pytest.raises(ValueError, match="coordinates differ"):
        series.align([flow, conflicting])


def test_period_irr_requires_timing_and_resolves_payment_order():
    periods = make_periods(date(2026, 1, 1), frequency=Frequency.YEAR, count=2)
    flow = Flow.from_periods(periods, [-100, 110], units="AUD")
    with pytest.raises(ValueError, match="explicit timing"):
        financial.calculate_irr(flow)
    assert financial.calculate_irr(
        flow, timing=PeriodTiming.FIRST
    ).rate == pytest.approx(0.1)
    # Coverage order can differ from payment order. IRR uses the actual dates.
    reversed_dates = Flow.from_periods(
        periods, [110, -100], units="AUD", dates=[date(2027, 1, 1), date(2026, 1, 1)]
    )
    assert financial.calculate_irr(reversed_dates).rate == pytest.approx(0.1)


def test_collapse_requires_a_date_or_convention():
    flow = Flow.from_periods([JANUARY], [100], units="AUD")
    with pytest.raises(ValueError, match="explicit timing"):
        flow.collapse()
    result = flow.collapse(on=date(2026, 2, 5))
    assert result.movements[0].date == date(2026, 2, 5)
    assert result.movements[0].period is None
    assert flow.collapse(timing=PeriodTiming.END).movements[0].date == JANUARY.end


def test_polars_date_projection():
    from rangekeeper.adapters.polars import dates

    flow = Flow.from_periods([JANUARY], [100], units="AUD")
    with pytest.raises(ValueError, match="explicit timing"):
        dates(flow)
    assert dates(flow, timing=PeriodTiming.LAST)["date"].to_list() == [
        date(2026, 1, 31)
    ]


def test_date_and_period_null_presence_survives_frames():
    from rangekeeper.adapters import polars as module

    flow = Flow.from_data(
        {
            "units": "m",
            "movements": [
                {
                    "id": str(uuid4()),
                    "key": "a",
                    "date": None,
                    "period": JANUARY.to_data(),
                    "magnitude": 0,
                },
                {
                    "id": str(uuid4()),
                    "key": "b",
                    "period": {
                        "start_inclusive": "2026-02-01",
                        "end_exclusive": "2026-03-01",
                    },
                    "magnitude": None,
                },
            ],
        }
    )
    assert (
        module.from_frame(module.to_frame(flow), units=flow.units).to_data()
        == flow.to_data()
    )

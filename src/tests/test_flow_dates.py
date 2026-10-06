"""Date-only coordinates, independent payment dates and explicit timing contracts."""

from datetime import date, datetime, timezone

import pytest

from rangekeeper.errors import ValidationError
from rangekeeper.model.duration import Period
from rangekeeper.model.flow import (
    Flow,
    Movement,
    from_events,
    from_periods,
    resolve_date,
    validate_flow,
)
from rangekeeper.duration import make_period, make_periods, offset
from rangekeeper.calculations import financial, series


JANUARY = make_period(date(2026, 1, 1), date(2026, 2, 1))


def test_schema_date_or_timestamp_union_retains_timestamp_support():
    from uuid import uuid4
    from rangekeeper._schema.records import Source

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
    movement = Movement(key="delivery", date=date(2026, 1, 2), magnitude=2)
    assert type(movement.date) is date
    assert movement.to_data() == {"key": "delivery", "date": "2026-01-02", "magnitude": 2}
    assert Period.from_data(JANUARY.to_data()) == JANUARY
    assert type(JANUARY.start) is date
    data = JANUARY.to_data()
    data["start"] = "2000-01-01"
    assert JANUARY.start == date(2026, 1, 1)


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 1, 1),
        datetime(2026, 1, 1, tzinfo=timezone.utc),
    ],
)
def test_datetimes_are_not_flow_coordinates(value):
    for operation in (
        lambda: from_events([value], [1], units="m"),
        lambda: make_period(value, date(2026, 2, 1)),
        lambda: offset(value, frequency="day"),
        lambda: Movement(key="event", date=value),
        lambda: Period(start=value, end=date(2026, 2, 1)),
    ):
        with pytest.raises((TypeError, ValidationError)):
            operation()


@pytest.mark.parametrize("value", ["2026-01-01T00:00:00", "2026-02-30", "01/01/2026"])
def test_wire_dates_must_be_valid_iso_dates(value):
    with pytest.raises(ValidationError):
        Movement.from_data({"key": "event", "date": value})


def test_sample_needs_date_or_period():
    # Generated records check structure; Flow validation checks this cross-field rule.
    for movement in (
        Movement(key="missing"),
        Movement(key="null", date=None, period=None),
    ):
        with pytest.raises(ValueError, match="date or period"):
            validate_flow(Flow(units="m", movements=(movement,)))


def test_period_timing_is_explicit_and_does_not_change_content():
    flow = from_periods([JANUARY], [100], units="AUD")
    original = flow.to_data()
    assert "date" not in original["movements"][0]
    for timing, expected in (
        ("start", date(2026, 1, 1)),
        ("last_day", date(2026, 1, 31)),
        ("end", date(2026, 2, 1)),
    ):
        assert resolve_date(flow.movements[0], timing=timing) == expected
    with pytest.raises(ValueError, match="explicit timing"):
        resolve_date(flow.movements[0])
    with pytest.raises(ValueError, match="explicit timing"):
        financial.calculate_xnpv(flow, rate=0.1, valuation_date=date(2026, 1, 1))
    assert financial.calculate_xnpv(
        flow, rate=0.1, valuation_date=date(2026, 1, 1), timing="end"
    ).magnitude == pytest.approx(100 / 1.1 ** (31 / 365))
    assert flow.to_data() == original


def test_payment_date_is_independent_of_coverage():
    flow = from_periods([JANUARY], [100], units="AUD", dates=[date(2026, 2, 5)])
    assert resolve_date(flow.movements[0], timing="start") == date(2026, 2, 5)
    assert financial.calculate_xnpv(
        flow, rate=0.1, valuation_date=date(2026, 1, 1), timing="last_day"
    ).magnitude == pytest.approx(100 / 1.1 ** (35 / 365))
    assert series.trim(flow, start=JANUARY.start, end=JANUARY.end) == flow
    assert series.find_extent(flow) == (JANUARY.start, JANUARY.end)
    with pytest.raises(ValueError, match="crosses a movement period"):
        series.trim(flow, start=date(2026, 1, 2), end=JANUARY.end)
    # Period aggregation states coverage, rather than inventing one payment date.
    aggregated = series.resample(flow, periods=[JANUARY], reduction="sum").flow
    assert aggregated.movements[0].magnitude == 100
    assert "date" not in aggregated.movements[0].field_names()
    conflicting = from_periods([JANUARY], [100], units="AUD", dates=[date(2026, 2, 6)])
    with pytest.raises(ValueError, match="coordinates differ"):
        series.align([flow, conflicting])


def test_period_irr_requires_timing_and_resolves_payment_order():
    periods = make_periods(date(2026, 1, 1), frequency="year", count=2)
    flow = from_periods(periods, [-100, 110], units="AUD")
    with pytest.raises(ValueError, match="explicit timing"):
        financial.calculate_irr(flow)
    assert financial.calculate_irr(flow, timing="start").rate == pytest.approx(0.1)
    # Coverage order can differ from payment order. IRR uses the actual dates.
    reversed_dates = from_periods(
        periods, [110, -100], units="AUD", dates=[date(2027, 1, 1), date(2026, 1, 1)]
    )
    assert financial.calculate_irr(reversed_dates).rate == pytest.approx(0.1)


def test_collapse_requires_a_date_or_convention():
    flow = from_periods([JANUARY], [100], units="AUD")
    with pytest.raises(ValueError, match="explicit timing"):
        series.collapse(flow)
    result = series.collapse(flow, on=date(2026, 2, 5))
    assert result.movements[0].date == date(2026, 2, 5)
    assert result.movements[0].period is None
    assert series.collapse(flow, timing="end").movements[0].date == JANUARY.end


def test_pandas_date_projection_and_midnight_import():
    import pandas as pd
    from rangekeeper.adapters.pandas import from_series, to_series

    flow = from_periods([JANUARY], [100], units="AUD")
    with pytest.raises(ValueError, match="explicit timing"):
        to_series(flow)
    assert list(to_series(flow, timing="last_day").index) == [date(2026, 1, 31)]
    for day in (date(2026, 1, 1), pd.Timestamp("2026-01-01")):
        imported = from_series(pd.Series([1], index=[day]), units="m")
        assert imported.movements[0].date == date(2026, 1, 1)
    for day in (
        pd.Timestamp("2026-01-01 01:00"),
        pd.Timestamp("2026-01-01", tz="UTC"),
        pd.Timestamp("2026-01-01 00:00:00.000000001"),
    ):
        with pytest.raises(ValueError, match="naive midnight"):
            from_series(pd.Series([1], index=[day]), units="m")


@pytest.mark.parametrize("adapter", ["pandas", "polars"])
def test_date_and_period_null_presence_survives_frames(adapter):
    from importlib import import_module

    module = import_module(f"rangekeeper.adapters.{adapter}")
    flow = Flow.from_data(
        {
            "units": "m",
            "movements": [
                {"key": "a", "date": None, "period": JANUARY.to_data(), "magnitude": 0},
                {
                    "key": "b",
                    "period": {"start": "2026-02-01", "end": "2026-03-01"},
                    "magnitude": None,
                },
            ],
        }
    )
    assert (
        module.from_frame(
            module.to_frame(flow), units=flow.units
        ).to_data()
        == flow.to_data()
    )

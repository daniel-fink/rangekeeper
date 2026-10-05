"""Independent finance oracles and PyXIRR integration boundary checks."""

from datetime import date, datetime
import math
from uuid import uuid4

import pytest

from rangekeeper.calculations.financial import (
    calculate_irr,
    calculate_pv,
    calculate_xnpv,
)
from rangekeeper.model.flow import Flow, Movement, from_events
from rangekeeper.temporal.calendar import year_fraction


@pytest.mark.parametrize(
    "convention,periods,valuation_periods",
    [
        ("actual/365", (30 / 365, 59 / 365, 366 / 365), (0, 45 / 365, 366 / 365)),
        ("actual/360", (30 / 360, 59 / 360, 366 / 360), (0, 45 / 360, 366 / 360)),
        ("actual/actual", (30 / 366, 59 / 366, 1), (0, 45 / 366, 1)),
        ("30/360", (29 / 360, 58 / 360, 1), (0, 44 / 360, 1)),
    ],
)
@pytest.mark.parametrize("rate", [0, 0.1, -0.1])
def test_explicit_valuation_before_between_and_after_payments(
    convention, periods, valuation_periods, rate
):
    amounts = (100, -10, 110)
    flow = from_events(
        [date(2020, 1, 31), date(2020, 2, 29), date(2021, 1, 1)], amounts, units="AUD"
    )
    for valuation_date, origin in zip(
        (date(2020, 1, 1), date(2020, 2, 15), date(2021, 1, 1)), valuation_periods
    ):
        expected = math.fsum(
            amount / (1 + rate) ** (period - origin)
            for amount, period in zip(amounts, periods)
        )
        result = calculate_xnpv(
            flow, rate=rate, valuation_date=valuation_date, day_count=convention
        )
        assert result.magnitude == pytest.approx(expected, rel=1e-12)
        assert result.units == "AUD"


def test_day_count_boundaries_and_reversed_dates():
    start, end = date(2019, 12, 31), date(2020, 3, 1)
    assert year_fraction(start, end, convention="actual/actual") == pytest.approx(
        1 / 365 + 60 / 366
    )
    assert year_fraction(end, start, convention="actual/actual") == pytest.approx(
        -(1 / 365 + 60 / 366)
    )
    assert year_fraction(
        date(2020, 1, 31), date(2020, 2, 29), convention="30/360"
    ) == pytest.approx(29 / 360)
    with pytest.raises(TypeError, match="calendar date"):
        year_fraction(datetime(2020, 1, 1), end, convention="actual/365")
    with pytest.raises(ValueError, match="unsupported day count"):
        year_fraction(start, end, convention="unsupported")


@pytest.mark.parametrize("first_period", [-1, 0, 1, 3])
def test_pv_keeps_records_and_non_currency_units(first_period):
    source = Flow(
        units="kg",
        movements=(
            Movement(
                key="a", date=date(2026, 1, 1), magnitude=100, claims=(uuid4(),)
            ),
            Movement(key="b", date=date(2026, 2, 1), magnitude=-110),
        ),
    )
    before = source.to_data()
    result = calculate_pv(source, rate=0.1, first_period=first_period)
    assert source.to_data() == before and result.units == "kg"
    for i, (original, discounted) in enumerate(zip(source.movements, result.movements)):
        expected = original.to_data()
        expected["magnitude"] = pytest.approx(
            original.magnitude / 1.1 ** (first_period + i)
        )
        assert discounted.to_data() == expected


def test_empty_zero_and_single_payment_flows():
    empty = from_events([], [], units="m")
    assert (
        calculate_xnpv(empty, rate=0.1, valuation_date=date(2026, 1, 1)).magnitude == 0
    )
    assert calculate_pv(empty, rate=0.1).movements == ()
    for amount in (0, 100, -100):
        flow = from_events([date(2027, 1, 1)], [amount], units="m")
        assert calculate_xnpv(
            flow, rate=0.1, valuation_date=date(2026, 1, 1)
        ).magnitude == pytest.approx(amount / 1.1)
        with pytest.raises(ValueError, match="positive and negative"):
            calculate_irr(flow)
    with pytest.raises(ValueError, match="positive and negative"):
        calculate_irr(empty)


def test_repeated_payment_dates_are_retained():
    flow = from_events(
        [date(2026, 1, 1), date(2026, 1, 1), date(2027, 1, 1)],
        [-60, -40, 110],
        units="AUD",
        keys=["a", "b", "c"],
    )
    result = calculate_irr(flow)
    assert result.rate == pytest.approx(0.1)
    assert result.method == "pyxirr.xirr" and result.guess is None
    assert abs(result.residual.magnitude) < 1e-7


@pytest.mark.parametrize(
    "convention,period",
    [
        ("actual/365", 366 / 365),
        ("actual/360", 366 / 360),
        ("actual/actual", 1),
        ("30/360", 1),
    ],
)
def test_irr_uses_selected_day_count(convention, period):
    flow = from_events([date(2020, 1, 1), date(2021, 1, 1)], [-100, 110], units="AUD")
    result = calculate_irr(flow, day_count=convention)
    assert result.rate == pytest.approx(1.1 ** (1 / period) - 1, rel=1e-10)


def test_guess_can_select_different_roots_and_no_root_is_an_error():
    dates = [date(2021, 1, 1), date(2022, 1, 1), date(2023, 1, 1)]
    flow = from_events(dates, [-100, 230, -132], units="AUD")
    # -100 + 230/(1+r) - 132/(1+r)^2 has roots 0.1 and 0.2.
    assert calculate_irr(flow, guess=0.05).rate == pytest.approx(0.1)
    assert calculate_irr(flow, guess=0.3).rate == pytest.approx(0.2)
    no_root = from_events(dates, [-100, 200, -150], units="AUD")
    with pytest.raises(ValueError, match="finite result"):
        calculate_irr(no_root)
    same_day = from_events(
        [dates[0], dates[0]], [-100, 100], units="AUD", keys=["a", "b"]
    )
    with pytest.raises(ValueError, match="distinct dates"):
        calculate_irr(same_day)


@pytest.mark.parametrize("bad_result", [None, float("nan"), float("inf"), -1.0, 0.5])
def test_irr_rejects_failed_or_inaccurate_backend_results(monkeypatch, bad_result):
    import pyxirr

    flow = from_events([date(2026, 1, 1), date(2027, 1, 1)], [-100, 110], units="AUD")
    monkeypatch.setattr(pyxirr, "xirr", lambda *args, **kwargs: bad_result)
    with pytest.raises(ValueError):
        calculate_irr(flow)


def test_unresolved_content_is_not_financial_input():
    flow = from_events(
        [date(2026, 1, 1), date(2027, 1, 1)], [100, None], units="AUD"
    )
    for operation in (
        lambda: calculate_pv(flow, rate=0.1),
        lambda: calculate_xnpv(flow, rate=0.1, valuation_date=date(2026, 1, 1)),
        lambda: calculate_irr(flow),
    ):
        with pytest.raises(ValueError, match="unresolved/nonfinite movement"):
            operation()

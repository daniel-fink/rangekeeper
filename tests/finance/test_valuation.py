"""rk.finance pv, npv, irr and payment against standard definitions (#167)."""

import math
from datetime import date

import pytest

import rangekeeper as rk
from rangekeeper.duration import DayCount, Frequency, Periods, PeriodTiming
from rangekeeper.errors import ContractError, NumericalError, UnitError
from rangekeeper.finance import irr, npv, payment, pv
from rangekeeper.flow import Flow
from rangekeeper.quantity import Quantity, isclose

START = date(2001, 1, 1)
YEARS = Periods(start=START, frequency=Frequency.YEAR, count=10)


def yearly(amounts, units="USD"):
    return Flow(amounts=dict(zip(YEARS, amounts, strict=False)), units=units)


def test_pv_divides_each_amount_by_the_discount_factor():
    flow = yearly([110, 121])
    values = pv(flow=flow, rate="10 % pa", on=START)
    # Period amounts are paid at the end of the Period: one and two years.
    assert values == yearly([100, 100])
    assert {m.id for m in values.movements}.isdisjoint(m.id for m in flow.movements)
    first = pv(flow=flow, rate="10 % pa", on=START, timing=PeriodTiming.FIRST)
    assert first.at(on=START) == Quantity(text="110 USD")
    assert rk.finance.pv is pv


def test_actual_actual_makes_each_calendar_year_one_year():
    # 2004 and 2008 are leap years; ISDA actual/actual still counts whole years.
    flow = yearly([0] * 9 + [100])
    expected = 100 / 1.07**10
    value = npv(flow=flow, rate="7 % pa", on=START).number
    assert value == pytest.approx(expected, rel=1e-14)
    actual_365 = npv(flow=flow, rate="7 % pa", on=START, day_count=DayCount.ACTUAL_365)
    assert actual_365.number < value


def test_npv_is_the_total_of_pv_and_matches_the_textbook():
    # Brealey, Myers and Allen: 1000 a year for three years at 10 %.
    flow = yearly([1000, 1000, 1000])
    value = npv(flow=flow, rate="10 % pa", on=START)
    assert value == pv(flow=flow, rate="10 % pa", on=START).total()
    assert value.number == pytest.approx(2486.85199098422, rel=1e-12)
    assert npv(flow=Flow(units="USD", movements=()), rate="5 % pa", on=START) == (
        Quantity(text="0 USD")
    )
    dated = Flow.from_events([date(2002, 1, 1)], [110], units="AUD")
    assert npv(flow=dated, rate=Quantity(text="0.1 pa"), on=START) == Quantity(
        text="100 AUD"
    )


def test_irr_is_the_rate_of_zero_npv():
    flow = Flow.from_events(
        [date(2001, 1, 1), date(2002, 1, 1)], [-100, 110], units="USD"
    )
    assert isclose(actual=irr(flow=flow), expected=Quantity(text="10 % pa"))
    assert irr(flow=flow).units == "% pa"
    # -1000, then 300, 400 and 500 a year later each; bisection of the NPV
    # polynomial gives 8.896339469335 %.
    uneven = Flow.from_events(
        [date(2001 + i, 1, 1) for i in range(4)], [-1000, 300, 400, 500], units="AUD"
    )
    rate = irr(flow=uneven)
    assert rate.magnitude == pytest.approx(8.896339469335, rel=1e-11)
    assert npv(flow=uneven, rate=rate, on=START).number == pytest.approx(0, abs=1e-9)
    assert isclose(actual=irr(flow=uneven, guess="20 % pa"), expected=rate)


def test_a_price_equal_to_the_npv_earns_the_discount_rate():
    cash = yearly([50 * 1.02**i for i in range(10)])
    value = npv(flow=cash, rate="7 % pa", on=START)
    investment = rk.flow.Stream(
        flows={"Purchase": Flow(amounts={START: -value}), "Cash": cash}
    ).sum()
    assert isclose(actual=irr(flow=investment), expected=Quantity(text="7 % pa"))


def test_irr_needs_both_signs_and_two_dates():
    with pytest.raises(NumericalError, match="both"):
        irr(flow=yearly([1, 2]))
    with pytest.raises(NumericalError, match="two dates"):
        irr(
            flow=Flow.from_events([START, START], [-1, 2], units="USD", keys=["a", "b"])
        )


def test_payment_is_pmt_with_units():
    # PMT(6 % / 12, 240, -1) = 0.00716431058...
    monthly = payment(
        principal="1 AUD", rate="6 % pa", term="20 years", frequency=Frequency.MONTH
    )
    assert monthly.units == "AUD per month"
    assert monthly.magnitude == pytest.approx(0.00716431058478, rel=1e-12)
    constant = (monthly / Quantity(text="1 AUD")).to(units="% pa")
    assert constant.magnitude == pytest.approx(8.597172701738, rel=1e-12)
    annual = payment(
        principal="100000 USD", rate="5 % pa", term="3 years", frequency=Frequency.YEAR
    )
    assert annual.number == pytest.approx(36720.8564, rel=1e-8)
    assert payment(
        principal="1200 USD", rate="0 % pa", term="1 year", frequency=Frequency.MONTH
    ) == Quantity(text="100 USD per month")
    quarterly = payment(
        principal="1 AUD", rate="8 % pa", term="2 years", frequency=Frequency.QUARTER
    )
    r = 0.02
    assert quarterly.number == pytest.approx(r / (1 - (1 + r) ** -8))


def test_payment_errors():
    with pytest.raises(UnitError):
        payment(
            principal="1 sqm", rate="6 % pa", term="1 year", frequency=Frequency.MONTH
        )
    with pytest.raises(ContractError, match="no unit"):
        payment(
            principal="1 AUD",
            rate="6 % pa",
            term="2 years",
            frequency=Frequency.BIENNIUM,
        )
    with pytest.raises(UnitError, match="whole number"):
        payment(
            principal="1 AUD",
            rate="6 % pa",
            term="1 month",
            frequency=Frequency.QUARTER,
        )
    with pytest.raises(UnitError, match="same kind"):
        payment(
            principal="1 AUD", rate="6 % pa", term="10 days", frequency=Frequency.MONTH
        )
    with pytest.raises(ValueError):
        pv(flow=yearly([1]), rate="-100 % pa", on=START)
    assert math.isfinite(
        payment(
            principal="1 AUD", rate="6 % pa", term="52 weeks", frequency=Frequency.WEEK
        ).number
    )

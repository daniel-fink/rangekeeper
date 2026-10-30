"""Profile timing: ``base``, ``start`` and ``every`` for growth, ``start`` and ``length``
for distribution (#303, #168).

Lesson 03 uses them in equations: ``rx.profile.compounding(initial=a_income,
rate=rent_growth, start=a_open)``, the renewals with ``start=a_open + 5 years,
every=5 years`` (cells 7 and 7b), and ``rx.profile.uniform(total=a_cost,
start=a_start, length=2 years)`` (cell 6). These tests run the profiles that
the equation functions mirror, through ``Flow.from_profile``.
"""

from datetime import date, datetime

import pytest

from rangekeeper.duration import NEVER, AlignmentError, Frequency, Periods, Span
from rangekeeper.errors import Code, ContractError, UnitError
from rangekeeper.flow import Flow
from rangekeeper.model import Distribution
from rangekeeper.profile import Compounding, Constant, Linear, SCurve, Uniform
from rangekeeper.quantity import Quantity

YEARS = Span(start=date(2027, 1, 1), end=date(2038, 1, 1)).periods(
    frequency=Frequency.YEAR
)


def amounts(flow: Flow) -> list[float]:
    return [movement.number for movement in flow.movements]


def test_start_gives_zero_before_a_date_and_growth_keeps_its_calendar():
    """Lesson 03 cell 7: rents grow from 2027, but earn nothing until opening."""
    a_open = date(2030, 1, 1)
    a_rent = Flow.from_profile(
        profile=Compounding(rate="3 % pa", start=a_open),
        periods=YEARS,
        initial="10e6 AUD",
    )
    assert amounts(a_rent)[:3] == [0, 0, 0]
    assert amounts(a_rent)[3:5] == pytest.approx([10e6 * 1.03**3, 10e6 * 1.03**4])
    assert len(a_rent.movements) == len(YEARS)


def test_start_keeps_the_period_that_contains_it_and_never_gives_zero():
    profile = Constant(start=date(2028, 6, 30))
    assert profile.factors(periods=YEARS[:3]) == (0.0, 1.0, 1.0)
    assert Constant(start=NEVER).factors(periods=YEARS[:3]) == (0.0, 0.0, 0.0)
    assert Compounding(rate="3 % pa", start=NEVER).factors(periods=YEARS[:2]) == (
        0.0,
        0.0,
    )


def test_every_repeats_the_amount_from_start():
    """Lesson 03 cell 7b: renewals every five years after opening, grown from 2027."""
    a_renewals = Flow.from_profile(
        profile=Compounding(rate="3.5 % pa", start=date(2035, 1, 1), every="5 years"),
        periods=YEARS,
        initial="2e6 AUD",
    )
    values = amounts(a_renewals)
    assert [i for i, v in enumerate(values) if v] == [8]
    assert values[8] == pytest.approx(2e6 * 1.035**8)
    longer = YEARS.extend(count=10)
    assert [
        i
        for i, factor in enumerate(Constant(every="5 years").factors(periods=longer))
        if factor
    ] == [0, 5, 10, 15, 20]


def test_every_counts_each_occurrence_in_a_period():
    twice = Constant(every="6 months").factors(periods=YEARS[:2])
    assert twice == (2.0, 2.0)
    late = Constant(start=date(2027, 7, 1), every="1 year").factors(periods=YEARS[:3])
    assert late == (1.0, 1.0, 1.0)


def test_base_is_the_date_of_the_initial_amount():
    """#168: growth from an opening date, without a hand-written loop."""
    opening = Compounding(rate="10 % pa", base=date(2029, 1, 1))
    assert opening.factors(periods=YEARS[:4]) == pytest.approx(
        (1.1**-2, 1.1**-1, 1, 1.1)
    )
    linear = Linear(rate="10 % pa", base=date(2028, 1, 1), start=date(2028, 1, 1))
    assert linear.factors(periods=YEARS[:3]) == pytest.approx((0, 1, 1.1))
    mid_year = Compounding(rate="10 % pa", base=date(2026, 7, 1))
    assert mid_year.factors(periods=YEARS[:1]) == pytest.approx((1.1**0.5,))


def test_the_defaults_keep_the_first_period_as_the_base():
    assert Compounding(rate="2 % pa") == Compounding(
        rate="2 % pa", base=None, start=None, every=None
    )
    assert Compounding(rate="2 % pa").factors(periods=YEARS[:3]) == pytest.approx(
        Compounding(rate="2 % pa", base=YEARS.start).factors(periods=YEARS[:3])
    )


def test_a_distribution_divides_its_total_over_its_window():
    """Lesson 03 cell 6: works divided evenly over two years from their start."""
    a_works = Flow.from_profile(
        profile=Uniform(start=date(2028, 1, 1), length="2 years"),
        periods=YEARS,
        total="80e6 AUD",
    )
    assert amounts(a_works)[:4] == [0, 40e6, 40e6, 0]
    assert a_works.total() == Quantity(text="80e6 AUD")
    curve = Flow.from_profile(
        profile=SCurve(start=date(2029, 1, 1), length="4 years"),
        periods=YEARS,
        total="1 AUD",
    )
    values = amounts(curve)
    assert [i for i, v in enumerate(values) if v] == [2, 3, 4, 5]
    assert values[2:6] == pytest.approx(values[2:6][::-1])
    assert curve.total() == Quantity(text="1 AUD")


def test_the_last_period_with_a_share_takes_the_remainder():
    thirds = Flow.from_profile(
        profile=Uniform(start=date(2027, 1, 1), length="3 years"),
        periods=YEARS[:5],
        total="1 ratio",
    )
    values = amounts(thirds)
    assert values[:2] == [1 / 3, 1 / 3] and values[3:] == [0, 0]
    assert values[2] == 1 - (1 / 3 + 1 / 3)
    sevenths = Flow.from_profile(
        profile=Uniform(start=date(2027, 1, 1), length="7 years"),
        periods=YEARS,
        total="1e6 AUD",
    )
    assert sevenths.total() == Quantity(text="1e6 AUD")
    point = SCurve(distribution=Distribution.uniform(lower=0, upper=0))
    assert amounts(
        Flow.from_profile(profile=point, periods=YEARS[:3], total="5 AUD")
    ) == [5, 0, 0]


def test_a_distribution_that_never_starts_spends_nothing():
    """Lesson 05: Building B's works when B never starts."""
    b_works = Flow.from_profile(
        profile=Uniform(start=NEVER, length="2 years"), periods=YEARS, total="9 AUD"
    )
    assert amounts(b_works) == [0] * len(YEARS)


@pytest.mark.parametrize(
    ("start", "length", "code"),
    [
        (date(2028, 7, 1), "1 year", Code.ALIGNMENT_CROSSES),
        (date(2028, 1, 1), "6 months", Code.ALIGNMENT_CROSSES),
        (date(2036, 1, 1), "3 years", Code.ALIGNMENT_PARTIAL),
        (date(2026, 1, 1), "2 years", Code.ALIGNMENT_PARTIAL),
    ],
)
def test_a_distribution_window_covers_whole_periods_inside_the_periods(
    start, length, code
):
    with pytest.raises(AlignmentError) as raised:
        Uniform(start=start, length=length).factors(periods=YEARS)
    assert raised.value.code is code
    assert "window" in raised.value.values


def test_profile_options_are_checked_when_the_profile_is_made():
    with pytest.raises(UnitError):
        Constant(every="1.5 years")
    with pytest.raises(UnitError):
        Uniform(length="0 years")
    with pytest.raises(TypeError):
        Compounding(rate="2 % pa", base=datetime(2027, 1, 1))
    with pytest.raises(TypeError):
        Compounding(rate="2 % pa", base=NEVER)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Constant(start="2027-01-01")  # type: ignore[arg-type]
    with pytest.raises(ContractError):
        Compounding(rate="-100 % pa")
    with pytest.raises(ContractError) as raised:
        Uniform().factors(
            periods=Periods(start=date(2027, 1, 1), frequency=Frequency.YEAR, count=0)
        )
    assert raised.value.values == {"periods": 0}
    assert Constant(every=Quantity(text="5 years")) == Constant(every="5 years")

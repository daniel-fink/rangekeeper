"""A profile of an amount per year gives each Period that amount times its length (#500).

Lesson 03 declares the incomes in ``AUD pa`` (cell 5b) and the rent Flows in
``AUD`` (cell 5c), and cell 7 writes ``a_rent =
rx.profile.compounding(initial=a_income, ...)``. So a growth profile of an
amount per unit of time gives each Period that amount times the Period's
length, and a plain amount, as in lesson 01, does not change.
"""

from datetime import date

import pytest

import rangekeeper as rk
import rangekeeper.expressions as rx
from rangekeeper.duration import Frequency, Period, Periods, Span
from rangekeeper.errors import UnitError
from rangekeeper.flow import Flow
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.profile import (
    Compounding,
    Constant,
    Linear,
    SCurve,
    Uniform,
    period_scales,
    period_units,
)
from rangekeeper.quantity import Quantity, default_units

START = date(2027, 1, 1)
YEARS = Periods(start=START, frequency=Frequency.YEAR, count=4)
QUARTERS = Periods(start=START, frequency=Frequency.QUARTER, count=8)
MONTHS = Periods(start=START, frequency=Frequency.MONTH, count=12)


def amounts(flow: Flow) -> list[float]:
    return [movement.number for movement in flow.movements]


def test_yearly_periods_hold_the_amount_of_each_year_in_aud():
    rent = Flow.from_profile(
        profile=Compounding(rate="3 % pa"), periods=YEARS, initial="1e6 AUD pa"
    )
    assert rent.units == "AUD"
    assert amounts(rent) == pytest.approx([1e6, 1.03e6, 1.03**2 * 1e6, 1.03**3 * 1e6])


def test_quarterly_and_monthly_periods_hold_their_part_of_each_year():
    quarters = Flow.from_profile(
        profile=Constant(), periods=QUARTERS, initial="1e6 AUD pa"
    )
    assert quarters.units == "AUD"
    assert amounts(quarters) == [250e3] * 8
    yearly = quarters.resample(
        frequency=Frequency.YEAR, method=rk.flow.ResampleMethod.SUM
    )
    assert yearly == Flow.from_profile(
        profile=Constant(), periods=YEARS[:2], initial="1e6 AUD pa"
    )
    months = Flow.from_profile(profile=Constant(), periods=MONTHS, initial="12 AUD pa")
    assert amounts(months) == pytest.approx([1] * 12)
    growing = Flow.from_profile(
        profile=Compounding(rate="10 % pa"), periods=QUARTERS, initial="4e6 AUD pa"
    )
    assert amounts(growing)[4] == pytest.approx(1e6 * 1.1)


def test_a_partial_period_holds_its_days_of_the_year():
    partial = Span(start=START, end=date(2027, 3, 15)).periods(
        frequency=Frequency.MONTH, include_partial=True
    )
    flow = Flow.from_profile(
        profile=Constant(), periods=partial, initial="365.25 AUD pa"
    )
    assert amounts(flow) == pytest.approx([365.25 / 12, 365.25 / 12, 14])


def test_month_end_periods_count_whole_months():
    month_ends = Periods(start=date(2027, 1, 31), frequency=Frequency.MONTH, count=3)
    assert period_scales(units="AUD pa", periods=month_ends) == pytest.approx(
        (1 / 12,) * 3
    )


def test_every_and_start_scale_each_occurrence_by_its_period():
    renewals = Flow.from_profile(
        profile=Linear(rate="0 % pa", start=date(2028, 1, 1), every="2 years"),
        periods=QUARTERS,
        initial="4e6 AUD pa",
    )
    assert renewals.units == "AUD"
    assert amounts(renewals) == [0, 0, 0, 0, 1e6, 0, 0, 0]
    opening = Flow.from_profile(
        profile=Compounding(rate="3 % pa", start=date(2028, 1, 1)),
        periods=YEARS,
        initial="1e6 AUD pa",
    )
    assert amounts(opening) == pytest.approx([0, 1.03e6, 1.03**2 * 1e6, 1.03**3 * 1e6])


def test_other_units_per_unit_of_time_convert_to_a_year_first():
    monthly = Flow.from_profile(
        profile=Constant(), periods=YEARS, initial="1e3 AUD per month"
    )
    assert monthly.units == "AUD" and amounts(monthly) == pytest.approx([12e3] * 4)
    rates = Flow.from_profile(profile=Constant(), periods=QUARTERS, initial="6 % pa")
    assert amounts(rates) == pytest.approx([0.015] * 8)


def test_a_plain_amount_does_not_change():
    """Lesson 01: ``initial="100 USD"`` gives 100 USD in the first year."""
    pgi = Flow.from_profile(
        profile=Compounding(rate="2 % pa"), periods=QUARTERS, initial="100 USD"
    )
    assert pgi.units == "USD"
    assert amounts(pgi)[0] == 100
    assert amounts(pgi)[4] == pytest.approx(102)
    assert period_units(units="USD") == "USD"
    assert period_scales(units="USD", periods=QUARTERS) == (1.0,) * 8


def test_distribution_windows_divide_a_plain_total():
    works = Flow.from_profile(
        profile=Uniform(start=date(2027, 7, 1), length="1 year"),
        periods=QUARTERS,
        total="8e6 AUD",
    )
    assert works.units == "AUD"
    assert amounts(works) == [0, 0, 2e6, 2e6, 2e6, 2e6, 0, 0]
    curve = Flow.from_profile(
        profile=SCurve(start=date(2028, 1, 1), length="2 years"),
        periods=YEARS,
        total="1e6 AUD",
    )
    assert curve.total() == Quantity(text="1e6 AUD")


@pytest.mark.parametrize("profile", [Uniform(), SCurve(start=START, length="1 year")])
def test_a_distribution_of_a_total_per_unit_of_time_raises(profile):
    with pytest.raises(UnitError) as raised:
        Flow.from_profile(profile=profile, periods=YEARS, total="1e6 AUD pa")
    assert raised.value.suggestions == ("AUD",)


def test_the_units_rule_reads_the_time_dimension():
    assert default_units.per_time(units="AUD pa")
    assert default_units.per_time(units="AUD per month")
    assert default_units.per_time(units="% pa")
    assert not default_units.per_time(units="AUD")
    assert not default_units.per_time(units="AUD year")
    assert not default_units.per_time(units="ratio")
    assert period_units(units="AUD pa") == "AUD"
    assert period_units(units="AUD per month") == "AUD"
    with pytest.raises(UnitError):
        default_units.per_time(units="AUD per fortnightly")


def test_the_equation_functions_give_the_same_units():
    """``rx.profile.*`` gives the units of ``Flow.from_profile``, for inference (#282)."""
    compounding = functions.function(name="profile.compounding")
    assert compounding.units(arguments={"initial": "AUD pa"}) == "AUD"
    assert compounding.units(arguments={"initial": "USD"}) == "USD"
    assert compounding.units(arguments={"initial": None}) is None
    uniform = functions.function(name="profile.uniform")
    assert uniform.units(arguments={"total": "AUD"}) == "AUD"
    value = compounding.evaluate(
        arguments={
            "initial": Quantity(text="1e6 AUD pa"),
            "rate": Quantity(text="3 % pa"),
        },
        periods=tuple(QUARTERS),
    )
    assert isinstance(value, Flow) and value.units == "AUD"
    assert amounts(value)[0] == 250e3


def test_cells_5b_5c_and_7_declare_matching_units():
    """Lesson 03: ``a_rent`` in AUD is a profile of ``a_income`` in AUD pa."""
    draft = rk.Model(name="Rents").edit()
    project = draft.add_entity(code="project", classification="project")
    a_income = project.value(key="a_income", units="AUD pa")
    rent_growth = project.value(key="rent_growth", units="% pa")
    a_open = project.date(key="a_open")
    a_rent = project.flow(key="a_rent", units="AUD", periods=YEARS)
    project.equations(
        a_rent
        == rx.profile.compounding(initial=a_income, rate=rent_growth, start=a_open)
    )
    assert draft.commit().value(key="a_rent").kind is rk.model.ValueKind.FLOW


def test_a_period_counts_twelve_months_to_a_year():
    year = Period(start=date(2027, 3, 1), end=date(2028, 3, 1))
    assert period_scales(units="AUD pa", periods=[year]) == (1.0,)


def test_the_draft_infers_each_periods_units_of_a_profile():
    """A result that a profile adds to is in AUD, not AUD pa (#282, D44)."""
    draft = rk.Model(name="Income").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="rent", units="AUD pa")
    project.flow(key="parking", units="AUD", periods=YEARS)
    project.equations("income = rx.profile.constant(initial=rent) + parking")
    model = draft.commit()
    value = model.value(key="income")
    assert value.kind is rk.model.ValueKind.FLOW
    assert model.record_by_id(value.measure).record.units == "AUD"

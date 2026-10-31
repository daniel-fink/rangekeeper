"""Running totals, differences, date masks, ends and extremes of one Flow (#275).

Lessons 03 and 05 use these methods in equations: ``funding_need =
-(net_cash_flow + loan_interest).cumulative()``, ``loan_draws =
loan_principal.diff()``, ``(a_works.cumulative() - a_works.total()).since(on=a_start)``,
``project_cash.until(on=sale_date)`` and ``shortfall.max()``. These tests run
the value methods that the equations mirror.
"""

from datetime import date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.duration import NEVER, Frequency, Periods
from rangekeeper.errors import Code, ContractError, NumericalError
from rangekeeper.flow import Flow, Movement

YEARS = Periods(start=date(2027, 1, 1), frequency=Frequency.YEAR, count=5)


def yearly(*amounts: float | None, units: str = "AUD") -> Flow:
    return Flow(amounts=dict(zip(YEARS, amounts, strict=True)), units=units)


def amounts(flow: Flow) -> list[object]:
    return [movement.magnitude for movement in flow.movements]


def test_cumulative_gives_the_running_totals_on_the_same_periods():
    flow = yearly(-10, -20, 5, 30, 40)
    totals = flow.cumulative()
    assert amounts(totals) == [Decimal(n) for n in (-10, -30, -25, 5, 45)]
    assert [m.period for m in totals.movements] == list(YEARS)
    assert totals.units == "AUD"
    assert totals.last() == flow.total()


def test_cumulative_is_exact_where_a_float_sum_drifts():
    flow = yearly(0.1, 0.2, 0.3, 1e16, -1e16, units="ratio")
    assert amounts(flow.cumulative()) == [0.1, 0.30000000000000004, 0.6, 1e16, 0.6]


def test_diff_reverses_cumulative_and_starts_from_zero():
    flow = yearly(-10, -20, 5, 30, 40)
    assert flow.cumulative().diff() == flow
    assert flow.diff().cumulative() == flow
    assert amounts(yearly(3, 5, 4, 4, 0, units="ratio").diff()) == [3, 2, -1, 0, -4]


def test_an_unresolved_amount_gives_unresolved_totals_and_differences():
    flow = yearly(1, 2, None, 4, 5, units="ratio")
    assert amounts(flow.cumulative()) == [1, 3, None, None, None]
    assert amounts(flow.diff()) == [1, 1, None, None, 1]


def test_running_totals_and_differences_work_on_dated_events():
    flow = Flow(
        amounts={date(2027, 1, 1): -100, date(2027, 7, 1): 30, date(2028, 1, 1): 70},
        units="AUD",
    )
    assert flow.cumulative() == Flow(
        amounts={date(2027, 1, 1): -100, date(2027, 7, 1): -70, date(2028, 1, 1): 0},
        units="AUD",
    )
    assert flow.cumulative().diff() == flow
    empty = Flow(units="AUD", movements=())
    assert empty.cumulative() == empty and empty.diff() == empty


def test_totals_and_differences_have_fresh_ids_and_the_claims_they_use():
    first, second = uuid4(), uuid4()
    flow = Flow(
        units="AUD",
        movements=(
            Movement(id=uuid4(), period=YEARS[0], magnitude=1, claims=(first,)),
            Movement(id=uuid4(), period=YEARS[1], magnitude=2),
            Movement(id=uuid4(), period=YEARS[2], magnitude=3, claims=(second,)),
        ),
    )
    totals, changes = flow.cumulative(), flow.diff()
    for result in (totals, changes):
        assert not {m.id for m in result.movements} & {m.id for m in flow.movements}
    assert [m.claims for m in totals.movements] == [
        (first,),
        (first,),
        (first, second),
    ]
    assert [m.claims for m in changes.movements] == [(first,), (first,), (second,)]


def test_since_gives_zero_before_a_date_and_keeps_the_period_that_contains_it():
    flow = yearly(-10, -20, 5, 30, 40)
    since = flow.since(on=date(2028, 6, 30))
    assert amounts(since) == [Decimal(n) for n in (0, -20, 5, 30, 40)]
    assert flow.since(on=date(2028, 1, 1)) == since
    assert flow.since(on=date(2027, 1, 1)) == flow
    assert flow.since(on=NEVER) == yearly(0, 0, 0, 0, 0)


def test_until_gives_zero_after_a_date_and_keeps_the_period_that_contains_it():
    flow = yearly(-10, -20, 5, 30, 40)
    until = flow.until(on=date(2028, 1, 1))
    assert amounts(until) == [Decimal(n) for n in (-10, -20, 0, 0, 0)]
    assert flow.until(on=date(2028, 12, 31)) == until
    assert flow.until(on=NEVER) == flow
    assert flow.until(on=date(2026, 12, 31)) == yearly(0, 0, 0, 0, 0)


def test_since_and_until_compare_event_dates_and_give_zero_for_any_amount():
    flow = Flow(
        amounts={date(2027, 1, 1): None, date(2027, 7, 1): 30, date(2028, 1, 1): 70},
        units="AUD",
    )
    assert amounts(flow.since(on=date(2027, 7, 1))) == [0, 30, 70]
    assert amounts(flow.until(on=date(2027, 7, 1))) == [None, 30, 0]


def test_since_and_until_keep_the_ids_of_the_movements_they_keep():
    flow = yearly(-10, -20, 5, 30, 40)
    since = flow.since(on=date(2029, 1, 1))
    kept = [m.id for m in since.movements[2:]]
    assert kept == [m.id for m in flow.movements[2:]]
    zeros = {m.id for m in since.movements[:2]}
    assert not zeros & {m.id for m in flow.movements}
    assert all(not m.claims for m in since.movements[:2])


def test_since_and_until_take_a_date_value():
    flow = yearly(1, 2, 3, 4, 5)
    with pytest.raises(TypeError):
        flow.since(on=datetime(2028, 1, 1))
    with pytest.raises(TypeError):
        flow.until(on="2028-01-01")  # type: ignore[arg-type]


def test_first_last_min_and_max_return_quantities():
    flow = yearly(-10, -20.5, 5, 30, 40)
    assert flow.first() == rk.Quantity(text="-10 AUD")
    assert flow.last() == rk.Quantity(text="40 AUD")
    assert flow.min() == rk.Quantity(text="-20.5 AUD")
    assert flow.max() == rk.Quantity(text="40 AUD")
    assert isinstance(flow.min().magnitude, Decimal)


def test_the_ends_need_only_their_own_amount_and_the_extremes_need_all():
    flow = yearly(1, None, 3, 4, 5, units="ratio")
    assert flow.first() == rk.Quantity(magnitude=1, units="ratio")
    assert flow.last() == rk.Quantity(magnitude=5, units="ratio")
    for extreme in (flow.min, flow.max):
        with pytest.raises(NumericalError) as raised:
            extreme()
        assert raised.value.targets == (flow.movements[1].id,)
    assert flow.clean().min() == rk.Quantity(magnitude=1, units="ratio")
    with pytest.raises(NumericalError):
        yearly(None, 2, 3, 4, 5).first()


@pytest.mark.parametrize("operation", ["first", "last", "min", "max"])
def test_an_empty_flow_has_no_end_or_extreme(operation):
    with pytest.raises(ContractError) as raised:
        getattr(Flow(units="AUD", movements=()), operation)()
    assert raised.value.code is Code.CONTRACT
    assert raised.value.values == {"operation": operation, "units": "AUD"}


def test_the_lesson_03_funding_cascade_reads_its_balances_with_these_methods():
    """The value form of lesson 03 cells 12 and 21, with no loan interest."""
    net_cash_flow = yearly(-60e6, -30e6, 10e6, 20e6, 100e6)
    loan_interest = 0 * net_cash_flow
    funding_need = -(net_cash_flow + loan_interest).cumulative()
    assert amounts(funding_need) == [
        Decimal(n) for n in (60e6, 90e6, 80e6, 60e6, -40e6)
    ]
    loan_principal = yearly(10e6, 40e6, 30e6, 10e6, 0)
    loan_draws = loan_principal.diff()
    equity_cash_flow = net_cash_flow + loan_interest + loan_draws
    assert amounts(equity_cash_flow) == [Decimal(n) for n in (-50e6, 0, 0, 0, 90e6)]
    assert loan_principal.max() == rk.Quantity(text="40e6 AUD")
    a_works = Flow(
        amounts={YEARS[1]: -20e6, YEARS[2]: -20e6, YEARS[3]: 0, YEARS[4]: 0},
        units="AUD",
    )
    a_paid = a_works.cumulative()
    assert a_paid.last() == a_works.total()
    assert amounts(a_paid.since(on=date(2028, 1, 1)).until(on=date(2029, 1, 1))) == [
        Decimal(n) for n in (-20e6, -40e6, 0, 0)
    ]

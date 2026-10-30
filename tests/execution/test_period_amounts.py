"""A solve lowers a profile of an amount per year to each Period's amount (#500).

``execution.expansion`` reads the rows of a profile from its value function,
``Flow.from_profile``, so a Flow in ``AUD`` over quarters is a profile of an
amount in ``AUD pa``: each quarter holds a quarter of the year's amount, both
when the amount is fixed and when the solve finds it.
"""

from datetime import date

import rangekeeper as rk
from rangekeeper.execution import Status, solve
from rangekeeper.quantity import isclose

QUARTERS = rk.duration.Span(start=date(2027, 1, 1), length="2 years").periods(
    frequency=rk.duration.Frequency.QUARTER
)


def model() -> rk.Model:
    draft = rk.Model(name="Quarterly rent").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="rent", units="AUD pa")
    project.value(key="growth", units="% pa")
    project.value(key="received", units="AUD")
    project.date(key="opening")
    project.flow(key="income", units="AUD", periods=QUARTERS)
    project.equations(
        "income = rx.profile.compounding(initial=rent, rate=growth, start=opening)",
        "received = income.total()",
    )
    return draft.commit()


def test_each_quarter_holds_a_quarter_of_the_years_amount():
    specification = (
        model()
        .specify(name="Fixed rent")
        .fix(rent="4e6 AUD pa", growth="0 % pa", opening=date(2027, 7, 1))
    )
    outcome = solve(specification=specification)
    assert outcome.status is Status.FEASIBLE
    income = outcome["income"]
    assert income.units == "AUD"
    assert [m.number for m in income.movements] == [0, 0] + [1e6] * 6
    assert isclose(actual=outcome["received"], expected="6e6 AUD")


def test_the_solve_finds_the_yearly_amount_from_the_quarters():
    specification = (
        model()
        .specify(name="Rent for a total")
        .fix(received="8e6 AUD", growth="0 % pa", opening=date(2027, 1, 1))
    )
    outcome = solve(specification=specification)
    assert outcome.status is Status.FEASIBLE
    assert isclose(actual=outcome["rent"], expected="4e6 AUD pa")

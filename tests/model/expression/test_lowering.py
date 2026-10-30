"""Flow-valued equations as one scalar equation for each period (``per_period``)."""

from datetime import date

import pytest

import rangekeeper as rk
import rangekeeper.expressions as rx
from rangekeeper.errors import Code, ContractError, UnsupportedError
from rangekeeper.model.expression.evaluation import evaluate_fixed
from rangekeeper.model.expression.lowering import per_period

YEARS = rk.duration.Periods(
    start=date(2027, 1, 1), frequency=rk.duration.Frequency.YEAR, count=3
)
LATER = rk.duration.Periods(
    start=date(2027, 1, 1), frequency=rk.duration.Frequency.YEAR, count=2
)


@pytest.fixture
def declared():
    """Return the project handle of a draft, and the Movements of each Flow."""
    draft = rk.Model(name="Rows").edit()
    project = draft.add_entity(code="project", classification="project")
    project.value(key="rate", units="ratio")
    project.value(key="amount", units="AUD")
    project.date(key="start")
    for key in ("cash", "costs"):
        project.flow(key=key, units="AUD", periods=YEARS)
    project.flow(key="short", units="AUD", periods=LATER)
    model = draft.commit()
    shapes = {
        model.value(key=key).id: [m.id for m in model.value(key=key).flow.movements]
        for key in ("cash", "costs", "short")
    }
    return model.edit().entity(code="project"), shapes


def handles(project, *keys):
    return [project.ref(key=key) for key in keys]


def test_an_equation_without_flows_stays_one_equation(declared):
    project, shapes = declared
    rate, amount = handles(project, "rate", "amount")
    equation = (amount == rate * "10 AUD").to_expression()
    assert per_period(expression=equation, flows=shapes) == (equation,)


@pytest.mark.parametrize(
    ("build", "expected"),
    [
        (
            lambda c, k, a: c == k * 2 + a,
            lambda c, k, a: [ci == 2 * ki + a for ci, ki in zip(c, k, strict=True)],
        ),
        (
            lambda c, k, a: c == k.cumulative(),
            lambda c, k, a: [c[i] == sum(k[: i + 1]) for i in range(3)],
        ),
        (
            lambda c, k, a: c == k.diff(),
            lambda c, k, a: [c[0] == k[0]] + [c[i] == k[i] - k[i - 1] for i in (1, 2)],
        ),
        (
            lambda c, k, a: c == rx.max("0 AUD", k),
            lambda c, k, a: [ci == max(0, ki) for ci, ki in zip(c, k, strict=True)],
        ),
        (
            lambda c, k, a: c >= k.total() / 3,
            lambda c, k, a: [ci >= sum(k) / 3 for ci in c],
        ),
        (
            lambda c, k, a: c == k.first() + k.last(),
            lambda c, k, a: [ci == k[0] + k[2] for ci in c],
        ),
    ],
)
def test_each_row_holds_on_the_movements_of_its_period(declared, build, expected):
    project, shapes = declared
    cash, costs, amount = handles(project, "cash", "costs", "amount")
    equation = build(cash, costs, amount).to_expression()
    rows = per_period(expression=equation, flows=shapes)
    assert len(rows) == 3
    c = [12.0, -4.0, 10.0]
    k = [5.0, -2.0, 7.0]
    values = {amount.id: rk.Quantity(text="2 AUD")}
    for movement, number in zip(shapes[cash.id], c, strict=True):
        values[movement] = rk.Quantity(magnitude=number, units="AUD")
    for movement, number in zip(shapes[costs.id], k, strict=True):
        values[movement] = rk.Quantity(magnitude=number, units="AUD")
    holds = [evaluate_fixed(expression=row, values=values) for row in rows]
    assert holds == expected(c, k, 2.0)


def test_flows_with_other_periods_do_not_make_rows(declared):
    project, shapes = declared
    cash, short = handles(project, "cash", "short")
    equation = (cash == cash).to_expression()
    other = equation.replace(
        operands=(equation.operands[0], (short == short).to_expression().operands[0])
    )
    with pytest.raises(ContractError) as error:
        per_period(expression=other, flows=shapes)
    assert error.value.code is Code.ALIGNMENT_DIFFER


def test_a_call_that_needs_the_staged_solve_is_not_lowered(declared):
    project, shapes = declared
    cash, amount, start = handles(project, "cash", "amount", "start")
    for term in (
        cash == rx.flow.event(amount=amount, on=start),
        cash == cash.since(on=start),
    ):
        with pytest.raises(UnsupportedError, match="#276"):
            per_period(expression=term.to_expression(), flows=shapes)

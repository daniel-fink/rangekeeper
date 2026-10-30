"""Dates and NEVER in equation text: they parse, render and read back (#280, D26)."""

from datetime import date

import pytest

import rangekeeper as rk
import rangekeeper.expressions as rx
from rangekeeper.errors import Code, EquationError
from rangekeeper.model.expression.authoring import date_literal
from rangekeeper.model.expression.evaluation import evaluate_fixed
from rangekeeper.model.expression.text import read
from rangekeeper.schema.enums import DomainKind

YEARS = rk.duration.Periods(
    start=date(2027, 1, 1), frequency=rk.duration.Frequency.YEAR, count=3
)


class Names:
    """The names of equation text on one entity handle."""

    units = rk.quantity.default_units

    def __init__(self, project) -> None:
        self.project = project

    def value(self, path: tuple[str, ...]):
        return self.project.ref(key=".".join(path))


def strip(data: object) -> object:
    if isinstance(data, dict):
        return {k: strip(v) for k, v in data.items() if k != "id"}
    if isinstance(data, list):
        return [strip(item) for item in data]
    return data


@pytest.fixture
def draft():
    return rk.Model(name="Dates").edit()


@pytest.fixture
def project(draft):
    project = draft.add_entity(code="project", classification="project")
    project.date(key="start_date")
    project.date(key="b_start")
    project.date(key="b_sale_date")
    project.value(key="amount", units="AUD")
    project.flow(key="cash", units="AUD", periods=YEARS)
    project.flow(key="sale", units="AUD", periods=YEARS)
    return project


def test_a_date_literal_is_written_as_in_python(project):
    term = read(text="start_date = date(2027, 1, 1)", names=Names(project))
    literal = term.to_expression().operands[1]
    assert strip(literal.to_data()) == strip(date_literal(date(2027, 1, 1)).to_data())
    assert term.text == "start_date = date(2027, 1, 1)"
    equation = project.ref(key="start_date") == date(2027, 1, 1)
    assert equation.text == term.text
    assert strip(equation.to_expression().to_data()) == strip(
        term.to_expression().to_data()
    )


@pytest.mark.parametrize(
    "source",
    [
        "b_start = NEVER",
        "b_start >= date(2027, 1, 1) + 1 year",
        "b_start = NEVER or b_start <= start_date + 2 years",
        "sale = rx.flow.event(amount=amount, on=NEVER)",
        "sale = cash.since(on=NEVER)",
        "sale = cash.until(on=date(2028, 6, 30))",
        "amount = cash.at(on=date(2028, 1, 1))",
    ],
)
def test_dates_and_never_read_back_and_commit(draft, project, source):
    assert read(text=source, names=Names(project)).text == source
    project.equations(source)
    draft.commit()


def test_rx_takes_dates_and_never(project):
    cash, sale = project.ref(key="cash"), project.ref(key="sale")
    term = sale == cash.until(on=date(2028, 6, 30))
    assert term.text == "sale = cash.until(on=date(2028, 6, 30))"
    never = sale == rx.flow.event(
        amount=project.ref(key="amount"), on=rk.duration.NEVER
    )
    assert never.text == "sale = rx.flow.event(amount=amount, on=NEVER)"
    assert (project.ref(key="b_start") + "1 year").kind is DomainKind.DATE


@pytest.mark.parametrize(
    "source",
    [
        "b_start = date(2027, 13, 1)",
        "b_start = date(2027, 1)",
        "b_start = date(2027, 1, 1 year)",
        "b_start = date(year=2027, month=1, day=1)",
        "b_start = date(2027, 1, 1.5)",
    ],
)
def test_a_date_that_is_not_a_calendar_date_fails(project, source):
    with pytest.raises(EquationError) as error:
        project.equations(source)
    assert error.value.code is Code.EQUATION_SYNTAX
    assert error.value.text[error.value.start : error.value.end].startswith("date(")


def test_never_on_fixed_data_gives_no_flow(project):
    cash = rk.flow.Flow(amounts=dict(zip(YEARS, (1, 2, 3), strict=True)), units="AUD")
    values = {
        project.ref(key="cash").id: cash,
        project.ref(key="amount").id: rk.Quantity(text="5 AUD"),
    }
    since = read(text="cash.since(on=NEVER)", names=Names(project)).to_expression()
    assert [
        m.number for m in evaluate_fixed(expression=since, values=values).movements
    ] == [0, 0, 0]
    until = read(text="cash.until(on=date(2027, 6, 1))", names=Names(project))
    assert [
        m.number
        for m in evaluate_fixed(
            expression=until.to_expression(), values=values
        ).movements
    ] == [1, 0, 0]

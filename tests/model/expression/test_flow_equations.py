"""Flow-valued equations: period by period, with Periods from declarations (#279, D32)."""

from datetime import date

import pytest

import rangekeeper as rk
import rangekeeper.expressions as rx
from rangekeeper.errors import Code, ContractError, EquationError, ValidationError
from rangekeeper.model.expression.evaluation import evaluate_fixed
from rangekeeper.schema.enums import DomainKind

YEARS = rk.duration.Periods(
    start=date(2027, 1, 1), frequency=rk.duration.Frequency.YEAR, count=3
)
LATER = rk.duration.Periods(
    start=date(2028, 1, 1), frequency=rk.duration.Frequency.YEAR, count=3
)


@pytest.fixture
def draft():
    return rk.Model(name="Flows").edit()


@pytest.fixture
def project(draft):
    project = draft.add_entity(code="project", classification="project")
    project.value(key="rate", units="ratio")
    project.value(key="amount", units="AUD")
    project.value(key="growth", units="% pa")
    project.date(key="start")
    project.flow(key="cash", units="AUD", periods=YEARS)
    project.flow(key="costs", units="AUD", periods=YEARS)
    project.flow(key="other", units="AUD", periods=LATER)
    project.flow(key="net", units="AUD")
    return project


def test_a_handle_has_the_declared_periods(project):
    assert project.ref(key="cash").periods == tuple(YEARS)
    assert project.ref(key="net").periods is None
    assert project.ref(key="amount").periods is None


def test_flows_combine_period_by_period_and_commit(draft, project):
    project.equations(
        "net = cash - costs",
        "cash = 2 * costs + amount",
        "net >= 0 AUD",
        "costs = rx.max(0 AUD, cash - net)",
        "cash = rx.profile.compounding(initial=amount, rate=growth)",
        "costs = -rx.flow.event(amount=amount, on=start)",
    )
    cash, amount = project.ref(key="cash"), project.ref(key="amount")
    term = cash * project.ref(key="rate") - amount
    assert (term.kind, term.periods) == (DomainKind.FLOW, tuple(YEARS))
    assert rx.max("0 AUD", cash).periods == tuple(YEARS)
    assert cash.cumulative().periods == tuple(YEARS)
    model = draft.commit()
    (formulation,) = model.system.formulations
    assert len(formulation.constraints) == 6


@pytest.mark.parametrize(
    "source",
    ["net = cash + other", "net = rx.max(cash, other)", "cash >= other"],
)
def test_flows_with_other_periods_do_not_combine(project, source):
    with pytest.raises(EquationError) as error:
        project.equations(source)
    assert error.value.code is Code.ALIGNMENT_DIFFER
    assert "different Periods" in str(error.value)
    cash, other = project.ref(key="cash"), project.ref(key="other")
    with pytest.raises(ContractError) as caught:
        cash + other  # noqa: B018
    assert caught.value.code is Code.ALIGNMENT_DIFFER


@pytest.mark.parametrize(
    "source",
    [
        "net = rx.flow.event(amount=amount, on=start)",
        "net = -rx.profile.uniform(total=amount)",
        "rx.profile.constant(initial=amount) >= 0 AUD",
    ],
)
def test_a_flow_made_from_amounts_needs_declared_periods(project, source):
    with pytest.raises(EquationError) as error:
        project.equations(source)
    assert error.value.code is Code.EQUATION_FUNCTION
    assert "periods=" in str(error.value)


def test_a_flow_without_periods_takes_them_from_its_equations(project):
    project.equations("net = cash - costs", "net = cash.diff()")


@pytest.mark.parametrize("source", ["net = cash + start", "rate >= 0 and cash"])
def test_commit_rejects_a_flow_with_a_date_or_as_a_condition(draft, project, source):
    project.equations(source)
    with pytest.raises(ValidationError):
        draft.commit()


def test_a_condition_on_flows_commits(draft, project):
    project.equations("cash >= 0 AUD and rate >= 0")
    draft.commit()


def test_an_equation_on_fixed_flows_holds_period_by_period(project):
    cash = rk.flow.Flow(
        amounts=dict(zip(YEARS, (100, 103, 106.09), strict=True)), units="AUD"
    )
    values = {
        project.ref(key="cash").id: cash,
        project.ref(key="amount").id: rk.Quantity(text="100 AUD"),
        project.ref(key="growth").id: rk.Quantity(text="3 % pa"),
    }
    equation = project.ref(key="cash") == rx.profile.compounding(
        initial=project.ref(key="amount"), rate=project.ref(key="growth")
    )
    assert evaluate_fixed(expression=equation.to_expression(), values=values) is True
    bound = project.ref(key="cash") >= "101 AUD"
    assert evaluate_fixed(expression=bound.to_expression(), values=values) is False

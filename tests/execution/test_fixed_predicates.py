"""A false fixed predicate is infeasible, the same as a false constraint (#153)."""

import pytest

import rangekeeper as rk
from rangekeeper.errors import UnsupportedError
from rangekeeper.execution import OutcomeError, Status, solve
from rangekeeper.execution.backends import Termination
from rangekeeper.run import SolutionStatus


def model_with(*equations: str) -> rk.Model:
    """Return a Model with the AUD values a, b and total, and these equations."""
    draft = rk.Model(name="Fixed predicates").edit()
    project = draft.add_entity(code="project", classification="project")
    for key in ("a", "b", "total"):
        project.value(key=key, units="AUD")
    project.equations("total = a + b", *equations)
    return draft.commit()


def solved(*equations: str) -> rk.execution.Outcome:
    """Solve with a and b fixed and the total free."""
    model = model_with(*equations)
    return solve(specification=model.specify(name="Fixed").fix(a="3 AUD", b="4 AUD"))


@pytest.mark.parametrize(
    "equation",
    [
        "False",
        "a > b",
        "b < a",
        "a != 3 AUD",
        "a > b or b > 5 AUD",
        "not a < b",
        "a + b > 7 AUD",
    ],
)
def test_a_false_fixed_predicate_is_infeasible(equation):
    outcome = solved(equation)
    assert outcome.status is Status.INFEASIBLE
    assert outcome.run.report.status.solution == SolutionStatus.INFEASIBLE
    assert outcome.evidence.termination is Termination.INFEASIBLE
    assert outcome.outputs == ()
    with pytest.raises(OutcomeError) as raised:
        outcome.raise_for_status()
    assert raised.value.status is Status.INFEASIBLE


def test_the_outcome_is_the_outcome_of_a_false_constraint():
    def summary(outcome):
        return (
            outcome.status,
            outcome.run.report.status.completion,
            outcome.run.report.status.solution,
            outcome.evidence.termination,
            sorted({d.code for d in outcome.diagnostics}),
        )

    assert summary(solved("a > b")) == summary(solved("False"))


@pytest.mark.parametrize(
    "equation",
    ["True", "a < b", "a != b", "a > b or b > 3 AUD", "not a > b", "a + b > 6 AUD"],
)
def test_a_true_fixed_predicate_needs_no_row(equation):
    outcome = solved(equation).raise_for_status()
    assert outcome["total"] == rk.Quantity(text="7 AUD")


@pytest.mark.parametrize("equation", ["total > a", "total != 7 AUD", "not total < a"])
def test_a_predicate_of_an_unknown_stays_unsupported(equation):
    outcome = solved(equation)
    assert outcome.status is Status.UNSUPPORTED
    with pytest.raises(UnsupportedError):
        outcome.raise_for_status()

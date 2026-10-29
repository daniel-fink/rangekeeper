"""Staged solve: values that earlier rows determine make the other rows affine (#276)."""

import pytest

from rangekeeper.execution import Status, bind_roles, resolve_cases, solve, validate
from rangekeeper.execution.backends import BackendResult, PyomoHighs, Termination
from rangekeeper.execution.staging import stage
from rangekeeper.quantity import isclose
from rangekeeper.schema.records import Severity
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import UnsupportedError
from tests.execution.lesson02 import (
    CONSTANT,
    DATA,
    EQUATIONS,
    MODEL,
    USES,
    back,
    front,
    q,
    store,
)


def expected_rent_factor() -> float:
    """Return the front door's rent factor, calculated by hand once."""
    total = 20e6 + float(DATA["works_cost"].magnitude)
    noi = 1.25 * float(CONSTANT.magnitude) / 100 * 0.65 * total
    reference = sum(
        float(DATA[f"{use}_area"].magnitude)
        * float(DATA[f"{use}_rent"].magnitude)
        * (1 - float(DATA[f"{use}_vacancy"].magnitude))
        for use in USES
    )
    return (noi + float(DATA["operating_cost"].magnitude)) / reference


@pytest.fixture(scope="module")
def front_outcome():
    return solve(specification=front())


def test_the_front_door_solves_in_stages(front_outcome):
    front_outcome.raise_for_status()
    assert isclose(
        actual=front_outcome["rent_factor"],
        expected=q(f"{expected_rent_factor()} ratio"),
        relative=1e-7,
    )
    assert isclose(
        actual=front_outcome["effective_income"],
        expected=front_outcome["rent_factor"] * front_outcome["reference_income"],
    )
    steps = [step.message for step in front_outcome.run.report.trace]
    assert any("earlier stages determined" in message for message in steps)
    assert any(message.startswith("Stage of") for message in steps)
    terminations = [
        d for d in front_outcome.diagnostics if d.code == Code.SOLVER_TERMINATION
    ]
    assert len(terminations) == 1  # only the last solve is the Run's evidence
    assert front_outcome.evidence.termination is Termination.FEASIBLE


def test_the_round_trip_gives_back_the_land_cost(front_outcome):
    round_trip = back().fix(rent_factor=front_outcome["rent_factor"])
    assert isclose(
        actual=solve(specification=round_trip)["land_cost"],
        expected=q("20e6 AUD"),
        relative=1e-7,
    )


def test_a_stronger_market_and_a_longer_loan_follow(front_outcome):
    longer = solve(specification=front().fix(mortgage_constant=q("7.73 % pa")))
    assert longer["rent_factor"] < front_outcome["rent_factor"]
    loose = solve(specification=back().free("rent_factor"))
    assert loose.status is Status.UNDERDETERMINED
    assert {"land_cost", "rent_factor"} <= set(loose.free_unknowns)


def test_a_product_of_two_undetermined_unknowns_stays_unsupported():
    both_free = back().fix(land_cost=q("20e6 AUD")).free("leverage", "coverage")
    outcome = solve(specification=both_free)
    assert outcome.status is Status.UNSUPPORTED
    with pytest.raises(UnsupportedError) as raised:
        outcome.raise_for_status()
    # The stages determine the NOI; the row that still fails is its equation.
    constraint = MODEL.record_by_id(raised.value.targets[0]).record
    assert constraint.predicate == EQUATIONS["noi"]


def test_an_infeasible_stage_ends_the_solve():
    conflict = front().fix(mortgage=q("1 AUD"))
    outcome = solve(specification=conflict)
    assert outcome.status is Status.INFEASIBLE
    assert outcome.evidence.termination is Termination.INFEASIBLE
    assert not [d for d in outcome.diagnostics if d.severity == Severity.ERROR]


def binding_of(specification):
    cases = resolve_cases(specification, resolver=store())
    composition = cases.compositions[specification.id]
    return bind_roles(validate(composition, resolver=cases))


def test_stage_calls_the_backend_only_for_rows_that_need_it():
    calls = []

    def recorded(problem):
        calls.append(problem)
        return PyomoHighs().solve(problem, limits=_limits(), remaining=30.0, options={})

    staged = stage(binding_of(back()), solve=recorded)
    assert calls == [] and staged.stages == () and staged.determined == {}
    binding = binding_of(front())
    staged = stage(binding, solve=recorded)
    assert len(calls) == 1 and len(staged.stages) == 1
    reference = MODEL._value_at("reference_income").id
    assert reference in staged.determined
    assert reference not in staged.problem.variables
    assert set(staged.problem.variables) | set(staged.determined) == set(
        binding.unknowns
    )


def test_a_stage_that_ends_returns_its_result():
    def proves(problem):
        return BackendResult(Termination.INFEASIBLE)

    staged = stage(binding_of(front()), solve=proves)
    assert staged.ended is not None
    assert staged.ended.termination is Termination.INFEASIBLE


def _limits():
    from rangekeeper.execution import Limits

    return Limits()

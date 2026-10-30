"""Piecewise equations with a free value: the active side of each max or min (#308)."""

from collections.abc import Callable
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.errors import Code, NumericalError
from rangekeeper.execution import (
    Status,
    bind_roles,
    make_candidate,
    resolve_cases,
    solve,
    validate,
    verify,
)
from rangekeeper.execution.piecewise import Pieces
from rangekeeper.io import MemoryStore
from rangekeeper.model.expression.authoring import (
    add,
    equal,
    literal,
    reference,
    subtract,
)
from rangekeeper.quantity import isclose
from rangekeeper.schema.records import Expression, Reference
from tests.execution.cascade import (
    LAND,
    MODEL,
    YEARS,
    by_hand,
    call,
    forward,
    target,
    target_land,
    with_functions,
)


def q(text: str) -> rk.Quantity:
    return rk.Quantity(text=text)


def aud(magnitude: float) -> rk.Quantity:
    return rk.Quantity(magnitude=magnitude, units="AUD")


def steps(outcome) -> list[str]:
    return [step.message for step in outcome.run.report.trace]


@pytest.fixture(scope="module")
def forward_outcome():
    return solve(specification=forward())


@pytest.fixture(scope="module")
def target_outcome():
    return solve(specification=target())


def test_the_cascade_draws_the_loan_after_the_equity(forward_outcome):
    forward_outcome.raise_for_status()
    expected = by_hand(LAND)
    for year in YEARS:
        for key in ("need", "principal", "draws", "equity_cash"):
            assert isclose(
                actual=forward_outcome[f"{key}_{year}"],
                expected=aud(expected[f"{key}_{year}"]),
                tolerance="1e-3 AUD",
            ), f"{key}_{year}"
    # The equity pays first: no loan in the first year beyond what it cannot cover.
    assert isclose(
        actual=forward_outcome["principal_1"],
        expected=aud(LAND + 30e6 - 50e6),
        tolerance="1e-3 AUD",
    )
    assert forward_outcome["principal_4"] == aud(0)


def test_a_target_npv_finds_the_land_cost(target_outcome):
    """Lesson 03 cell 15 in scalar form: fix the target and free the land cost."""
    target_outcome.raise_for_status()
    assert isclose(
        actual=target_outcome["land_cost"],
        expected=aud(target_land()),
        relative=1e-7,
    )
    expected = by_hand(target_outcome["land_cost"].number)
    for year in YEARS:
        assert isclose(
            actual=target_outcome[f"principal_{year}"],
            expected=aud(expected[f"principal_{year}"]),
            tolerance="1e-3 AUD",
        )


def test_the_trace_records_the_rounds(target_outcome):
    assert any(
        "Picked the active sides of 4 max" in step for step in steps(target_outcome)
    )
    codes = [d.code for d in target_outcome.diagnostics]
    assert Code.ACTIVE_SIDE.value not in codes
    assert codes.count(Code.SOLVER_TERMINATION.value) == 1


def test_verification_reads_the_active_side_from_the_candidate(forward_outcome):
    """A candidate with a wrong side fails verification, whatever the solve picked."""
    specification = forward()
    store = MemoryStore()
    store.put(MODEL)
    cases = resolve_cases(specification=specification, resolver=store)
    binding = bind_roles(
        validation=validate(
            composition=cases.compositions[specification.id], resolver=cases
        )
    )
    right = {
        id: forward_outcome.quantity(binding.references[id]).number
        for id in binding.unknowns
    }
    principal = MODEL.value(key="principal_4").id
    wrong = {**right, principal: right[MODEL.value(key="need_4").id] - 50e6}
    for unknowns, passed in ((right, True), (wrong, False)):
        candidate = make_candidate(binding=binding, unknowns=unknowns, run_id=uuid4())
        assert verify(binding=binding, candidate=candidate).passed is passed


def small_model(*keys: str) -> tuple[rk.Model, Callable[[str], Expression]]:
    """Return a Model with these AUD values and the max and min Functions.

    The function returns a new reference to a value each time it is called.
    """
    draft = rk.Model(name="Piecewise").edit()
    project = draft.add_entity(code="project", classification="project")
    for key in keys:
        project.value(key=key, units="AUD")
    model = with_functions(draft.commit())

    def r(key: str) -> Expression:
        return reference(Reference(target=model.value(key=key).id))

    return model, r


def with_equations(model: rk.Model, *equations) -> rk.Model:
    draft = model.edit()
    draft.entity(code="project").equations(*equations)
    return draft.commit()


def test_a_max_of_fixed_values_is_a_constant():
    model, r = small_model("need", "equity", "principal")
    model = with_equations(
        model,
        equal(
            r("principal"),
            call(model, "rx.max", literal(0, "AUD"), subtract(r("need"), r("equity"))),
        ),
    )
    for need, principal in ((80, 30), (40, 0)):
        outcome = solve(
            specification=model.specify(name="Fixed").fix(
                need=aud(need), equity=aud(50)
            )
        )
        assert outcome.raise_for_status()["principal"] == aud(principal)
        assert not any("Picked the active" in step for step in steps(outcome))


def test_an_inverse_question_moves_a_constant_side():
    """The side 0 AUD leaves no unknown: the next round takes the other side."""
    model, r = small_model("need", "equity", "principal")
    model = with_equations(
        model,
        equal(
            r("principal"),
            call(model, "rx.max", literal(0, "AUD"), subtract(r("need"), r("equity"))),
        ),
    )
    back = model.specify(name="Back").fix(principal=aud(30), equity=aud(50))
    assert solve(specification=back).raise_for_status()["need"] == aud(80)
    loose = model.specify(name="Loose").fix(principal=aud(0), equity=aud(50))
    outcome = solve(specification=loose)
    # Any need up to the equity gives no principal: the solve names it.
    assert outcome.status is Status.UNDERDETERMINED
    assert outcome.free_unknowns == ("need",)


def test_min_takes_the_smaller_side():
    model, r = small_model("limit", "need", "drawn", "left")
    model = with_equations(
        model,
        equal(r("drawn"), call(model, "rx.min", r("limit"), r("need"))),
        equal(r("left"), subtract(r("limit"), r("drawn"))),
    )
    for need, drawn in ((40, 40), (90, 60)):
        outcome = solve(
            specification=model.specify(name="Forward").fix(
                limit=aud(60), need=aud(need)
            )
        )
        assert outcome.raise_for_status()["drawn"] == aud(drawn)
    back = model.specify(name="Back").fix(limit=aud(60), left=aud(20))
    outcome = solve(specification=back).raise_for_status()
    assert isclose(actual=outcome["need"], expected=aud(40))


def test_no_side_that_holds_is_reported():
    """x = max(0, x + 1) has no solution: the solve says so, and claims nothing more."""
    model, r = small_model("x")
    model = with_equations(
        model,
        equal(
            r("x"),
            call(model, "rx.max", literal(0, "AUD"), add(r("x"), literal(1, "AUD"))),
        ),
    )
    outcome = solve(specification=model.specify(name="None"))
    assert outcome.status is Status.FAILED
    with pytest.raises(NumericalError) as raised:
        outcome.raise_for_status()
    assert raised.value.code is Code.ACTIVE_SIDE
    assert raised.value.targets == (only_constraint(model),)
    assert "does not prove" in str(raised.value)


def test_sides_that_repeat_are_reported():
    """max(x + 1, 1 - x) is never zero: the sides alternate, and the solve stops."""
    model, r = small_model("x", "z")
    model = with_equations(
        model,
        equal(
            r("z"),
            call(
                model,
                "rx.max",
                add(r("x"), literal(1, "AUD")),
                subtract(literal(1, "AUD"), r("x")),
            ),
        ),
    )
    outcome = solve(specification=model.specify(name="Cycle").fix(z=aud(0)))
    assert outcome.status is Status.FAILED
    diagnostic = next(d for d in outcome.diagnostics if d.code == Code.ACTIVE_SIDE)
    assert "disagree" in diagnostic.message


def test_rows_without_a_max_that_conflict_are_infeasible():
    model, r = small_model("need", "equity", "principal", "total")
    model = with_equations(
        model,
        equal(
            r("principal"),
            call(model, "rx.max", literal(0, "AUD"), subtract(r("need"), r("equity"))),
        ),
        equal(r("total"), add(r("need"), r("equity"))),
    )
    conflict = model.specify(name="Conflict").fix(
        total=aud(10), need=aud(80), equity=aud(50), principal=aud(1)
    )
    outcome = solve(specification=conflict.free("principal"))
    assert outcome.status is Status.INFEASIBLE


def test_pieces_are_the_declared_max_and_min_functions():
    pieces = Pieces.of(MODEL)
    assert sorted(kind.sign for kind in pieces.kinds.values()) == [-1.0, 1.0]
    assert Pieces.of(rk.Model(name="Empty")).kinds == {}


def only_constraint(model: rk.Model):
    """Return the UUID of the one Constraint of a small Model."""
    formulations = model.system.formulations
    return formulations[0].constraints[0].id

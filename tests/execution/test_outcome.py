"""Read an Outcome: values by key, status, errors, free unknowns and evidence (#127)."""

from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper import Specification
from rangekeeper.execution import (
    Evidence,
    ExecutionConfig,
    OutcomeError,
    Status,
    solve,
)
from rangekeeper.execution.analysis import undetermined
from rangekeeper.execution.backends import BackendResult, Termination
from rangekeeper.flow import Flow
from rangekeeper.schema.records import Severity
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    MissingReferenceError,
    NumericalError,
    UnsupportedError,
    ValidationError,
)
from tests.execution.lesson02 import MODEL, back, q, store

A, B, C, D = (uuid4() for _ in range(4))


@pytest.fixture(scope="module")
def back_outcome():
    return solve(back(), store())


def test_a_value_is_read_by_key_or_dotted_path(back_outcome):
    land = back_outcome["land_cost"]
    assert isinstance(land, rk.Quantity)
    assert land.units == "AUD"
    assert back_outcome["project.land_cost"] == land
    value = MODEL._value_at("land_cost")
    assert back_outcome.quantity(value.id) == land
    assert back_outcome.model is back_outcome.outputs[0]
    with pytest.raises(MissingReferenceError):
        back_outcome["land_costs"]


def test_a_feasible_outcome_has_its_status_and_evidence(back_outcome):
    assert back_outcome.status is Status.FEASIBLE
    assert back_outcome.raise_for_status() is back_outcome
    assert back_outcome.free_unknowns == ()
    evidence = back_outcome.evidence
    assert isinstance(evidence, Evidence)
    assert evidence.termination is Termination.FEASIBLE
    assert "termination" not in evidence.backend
    assert evidence.backend["termination_condition"]
    assert (evidence.equality_rank, evidence.unknown_count) == (None, None)
    kinds = {item.kind.value for item in evidence.implementations}
    assert kinds >= {"compiler", "solver"}
    assert back_outcome.diagnostics == back_outcome.run.report.diagnostics


def with_termination(outcome, word):
    """Return the Outcome with another word in its solver_termination evidence."""
    data = outcome.run.to_data()
    for item in data["report"]["diagnostics"]:
        if item["code"] == Code.SOLVER_TERMINATION.value:
            item["values"]["termination"] = word
    return rk.execution.Outcome(run=rk.Run.from_data(data), outputs=outcome.outputs)


@pytest.mark.parametrize(
    "word,termination",
    [("limit", Termination.LIMITED), ("error", Termination.FAILED)],
)
def test_evidence_reads_the_termination_words_of_an_older_run(
    back_outcome, word, termination
):
    older = with_termination(back_outcome, word)
    assert older.evidence.termination is termination


def test_equations_that_leave_values_free_name_them():
    loose = back().free("works_cost")
    outcome = solve(loose, store())
    assert outcome.status is Status.UNDERDETERMINED
    assert set(outcome.free_unknowns) == {"land_cost", "works_cost"}
    assert outcome.evidence.equality_rank == outcome.evidence.unknown_count - 1
    # A determined value is still readable; the free ones hold one candidate.
    assert outcome["noi"].units == "AUD pa"
    with pytest.raises(OutcomeError) as raised:
        outcome.raise_for_status()
    assert raised.value.status is Status.UNDERDETERMINED
    assert raised.value.code is Code.UNDERDETERMINED


def test_fixed_values_that_disagree_are_infeasible():
    tight = back().fix(land_cost=q("20e6 AUD"))
    outcome = solve(tight, store())
    assert outcome.status is Status.INFEASIBLE
    assert outcome.evidence.termination is Termination.INFEASIBLE
    with pytest.raises(OutcomeError) as raised:
        outcome.raise_for_status()
    assert raised.value.status is Status.INFEASIBLE
    with pytest.raises(OutcomeError):
        outcome["land_cost"]


def test_a_product_of_two_unknowns_is_unsupported():
    both_free = back().fix(land_cost=q("20e6 AUD")).free("leverage", "coverage")
    outcome = solve(both_free, store())
    assert outcome.status is Status.UNSUPPORTED
    assert outcome.evidence.termination is None
    with pytest.raises(UnsupportedError) as raised:
        outcome.raise_for_status()
    # The decisive diagnostic gives the code and the equation's text.
    decisive = [d for d in outcome.diagnostics if d.severity == Severity.ERROR]
    assert raised.value.code == decisive[-1].code == Code.NONAFFINE_UNKNOWNS
    assert raised.value.equation == decisive[-1].values["equation"]
    assert raised.value.target is not None
    with pytest.raises(UnsupportedError):
        outcome["noi"]


def test_an_invalid_specification_raises_a_validation_error():
    fixed = MODEL.specify().fix(land_cost=q("20e6 AUD"))
    # A record that frees no value lacks the roles of the other values.
    missing = Specification(fixed.record.replace(unknowns=()), model=MODEL)
    outcome = solve(missing, store())
    assert outcome.status is Status.INVALID
    with pytest.raises(ValidationError) as raised:
        outcome.raise_for_status()
    assert raised.value.code is Code.SPECIFICATION_INVALID


class Ends:
    """A backend that ends with one termination and no candidate."""

    def __init__(self, termination):
        self.termination = termination

    def solve(self, problem, **kwargs):
        return BackendResult(self.termination)


class Breaks:
    def solve(self, problem, **kwargs):
        raise NumericalError("the backend found a non-finite coefficient")


@pytest.mark.parametrize(
    "backend,status,error",
    [
        (Ends(Termination.LIMITED), Status.LIMITED, OutcomeError),
        (Ends(Termination.FAILED), Status.FAILED, OutcomeError),
        (Ends(Termination.UNKNOWN), Status.FAILED, OutcomeError),
        (Breaks(), Status.FAILED, NumericalError),
    ],
)
def test_limits_and_failures_have_their_status_and_error(backend, status, error):
    outcome = solve(back(), store(), config=ExecutionConfig(backend=backend))
    assert outcome.status is status
    with pytest.raises(error) as raised:
        outcome.raise_for_status()
    if isinstance(raised.value, OutcomeError):
        assert raised.value.status is status
        assert raised.value.code is Code.SOLVER_TERMINATION


def batch_of(*leaves):
    return Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(MODEL.id),
            "cases": [str(leaf.id) for leaf in leaves],
        }
    )


def test_a_batch_takes_the_status_of_its_first_case_that_is_not_feasible():
    feasible, later = back(), back()
    unsupported = back().fix(land_cost=q("20e6 AUD")).free("leverage", "coverage")
    batch = batch_of(feasible, unsupported, later)
    outcome = solve(batch, store(feasible, unsupported, later, batch))
    assert [case.status for case in outcome.cases] == [
        Status.FEASIBLE,
        Status.UNSUPPORTED,
        Status.FEASIBLE,
    ]
    assert outcome.status is Status.UNSUPPORTED
    with pytest.raises(UnsupportedError):
        outcome.raise_for_status()
    for name in ("model", "evidence", "free_unknowns"):
        with pytest.raises(TypeError, match="batch"):
            getattr(outcome, name)
    with pytest.raises(TypeError, match="batch"):
        outcome["land_cost"]
    whole = batch_of(feasible, later)
    assert solve(whole, store(feasible, later, whole)).status is Status.FEASIBLE


def test_a_flow_value_reads_as_a_flow():
    from datetime import date

    from rangekeeper.model.expression.authoring import equal, literal, reference
    from rangekeeper.schema.records import Reference

    years = rk.duration.Span(start=date(2027, 1, 1), end=date(2029, 1, 1)).periods(
        frequency=rk.duration.Frequency.YEAR
    )
    draft = rk.Model(name="Rent").edit()
    project = draft.add_entity(code="project", classification="project")
    rent = project.flow(key="rent", units="AUD", periods=years)
    model = draft.commit()
    movements = model.value(rent.id).flow.movements
    draft = model.edit()
    draft.entity(code="project").equations(
        *(
            equal(reference(Reference(target=item.id)), literal(100, "AUD"))
            for item in movements
        )
    )
    model = draft.commit()
    found = rk.io.MemoryStore()
    found.put(model)
    outcome = solve(model.specify().free("rent"), found)
    outcome.raise_for_status()
    assert isinstance(outcome["rent"], Flow)
    assert outcome.quantity(movements[0].id) == q("100 AUD")


@pytest.mark.parametrize(
    "rows,expected",
    [
        ([], (A, B, C)),
        ([{A: 1.0}], (B, C)),
        ([{A: 1.0, B: -1.0}], (A, B, C)),
        ([{A: 1.0, B: -1.0}, {B: 1.0}], (C,)),
        ([{A: 1.0, B: 1.0, C: 1.0}, {A: 1.0, B: 1.0}], (A, B)),
        ([{A: 1.0, B: 1.0}, {A: 2.0, B: 2.0}, {C: 1.0}], (A, B)),
    ],
)
def test_undetermined_unknowns_follow_the_row_space(rows, expected):
    assert undetermined(rows, (A, B, C)) == expected

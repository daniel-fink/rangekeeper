"""Each execution stage is a typed function that writes nothing and starts no process."""

import subprocess
from uuid import UUID, uuid4

import pytest

from rangekeeper import Model, Specification
from rangekeeper.errors import Code
from rangekeeper.execution import (
    AffineProblem,
    Binding,
    Cases,
    ExecutionConfig,
    Tolerances,
    Validation,
    Verification,
    assemble,
    bind_roles,
    build_problem,
    make_candidate,
    resolve_cases,
    validate,
    verify,
)
from rangekeeper.execution.attempt import Attempt
from rangekeeper.execution.backends import Result
from rangekeeper.execution.settings import Limits
from rangekeeper.run import Run, SolutionStatus
from rangekeeper.shared.errors import NumericalError, UnsupportedError, ValidationError
from tests.execution.test_execution import (
    CAPITAL,
    NOI,
    RATE,
    RENT,
    binary,
    data,
    formulation,
    fresh,
    reference,
    setup,
    spec,
)

SOLUTION = {NOI: 550000.0, CAPITAL: 11000000.0}


@pytest.fixture(autouse=True)
def no_subprocess(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("a stage started a process")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)


class Unchanged:
    """Wrap a store and fail on any write."""

    def __init__(self, store):
        self.store = store

    def put(self, document):
        raise AssertionError("a stage wrote to the store")

    def load_model(self, id):
        return self.store.load_model(id)

    def load_specification(self, id):
        return self.store.load_specification(id)

    def load_run(self, id):
        return self.store.load_run(id)


def stages(specification=None):
    store, model = setup()
    specification = spec() if specification is None else specification
    store.put(specification)
    resolver = Unchanged(store)
    cases = resolve_cases(specification, resolver=resolver)
    return cases, cases.compositions[specification.id], model


class Exact:
    """A backend that returns the known solution."""

    def solve(self, problem, *, limits, remaining, options):
        assert isinstance(problem, AffineProblem)
        return Result("optimal", SOLUTION)


def attempt(cases, composition):
    return Attempt(
        ExecutionConfig(), Exact(), cases.root, composition, resolver=cases
    ).execute()


def bound(specification=None):
    cases, composition, _ = stages(specification)
    return cases, bind_roles(validate(composition, resolver=cases))


def test_resolve_cases_composes_each_leaf_and_resolves_its_revisions():
    store, model = setup()
    good, other = spec(), spec()
    conflict = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "includes": [str(good.id), str(other.id)],
        }
    )
    batch = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(model.id),
            "cases": [str(good.id), str(conflict.id)],
        }
    )
    for document in (good, other, conflict):
        store.put(document)
    cases = resolve_cases(batch, resolver=Unchanged(store))
    assert isinstance(cases, Cases)
    assert cases.root is batch
    assert set(cases.documents) == {batch.id, good.id, other.id, conflict.id}
    assert set(cases.models) == {model.id}
    assert set(cases.compositions) == {good.id, conflict.id}
    assert cases.compositions[good.id].model_id == model.id
    assert isinstance(cases.compositions[conflict.id], ValidationError)
    assert cases.load_specification(good.id) is cases.documents[good.id]
    assert cases.load_model(model.id) is cases.models[model.id]


def test_resolve_cases_raises_for_a_contradicted_batch_pin():
    store, model = setup()
    other = Model.from_data(fresh(model.to_data()))
    store.put(other)
    leaf = spec()
    store.put(leaf)
    batch = Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(other.id),
            "cases": [str(leaf.id)],
        }
    )
    with pytest.raises(ValidationError, match="batch input Model"):
        resolve_cases(batch, resolver=Unchanged(store))


def test_validate_reports_problems_and_raises_nothing():
    cases, composition, model = stages()
    validation = validate(composition, resolver=cases)
    assert isinstance(validation, Validation)
    assert validation.report.valid
    assert validation.model is not None and validation.model.id == model.id
    assert validation.units == model.unit_system

    payload = fresh(data("specification-forward"))
    payload["assignments"] = [
        a for a in payload["assignments"] if a["target"]["target"] != str(RENT)
    ]
    cases, composition, _ = stages(Specification.from_data(payload))
    invalid = validate(composition, resolver=cases)
    assert not invalid.report.valid
    with pytest.raises(ValidationError):
        bind_roles(invalid)


def test_bind_roles_gives_each_value_its_role_in_measure_units():
    _, binding = bound()
    assert isinstance(binding, Binding)
    assert set(binding.unknowns) == {NOI, CAPITAL}
    assert binding.assignments[RENT].units == binding.value_units[RENT]
    assert binding.assignments[RATE].number == pytest.approx(0.05)
    assert binding.assertions


def test_bind_roles_rejects_objectives_before_any_backend():
    payload = fresh(data("specification-objectives"))
    cases, composition, _ = stages(Specification.from_data(payload))
    with pytest.raises(UnsupportedError, match="objectives"):
        bind_roles(validate(composition, resolver=cases))


def test_build_problem_lowers_assertions_and_checks_limits():
    _, binding = bound()
    problem = build_problem(binding)
    assert isinstance(problem, AffineProblem)
    assert problem.binding is binding
    assert len(problem.rows) == len(binding.assertions) > 1
    assert all(set(row.residual.coefficients) <= {NOI, CAPITAL} for row in problem.rows)
    with pytest.raises(UnsupportedError) as symbols:
        build_problem(binding, limits=Limits(symbol_limit=1))
    assert symbols.value.code == Code.SYMBOL_LIMIT
    with pytest.raises(UnsupportedError) as rows:
        build_problem(binding, limits=Limits(constraint_limit=1))
    assert rows.value.code == Code.CONSTRAINT_LIMIT
    assert rows.value.target is not None


def test_build_problem_names_the_declaration_outside_the_affine_slice():
    payload = fresh(data("specification-forward"))
    payload["formulations"] = [
        formulation(
            binary(
                "equal",
                reference(CAPITAL),
                binary("multiply", reference(NOI), reference(CAPITAL)),
            )
        )
    ]
    specification = Specification.from_data(payload)
    _, binding = bound(specification)
    with pytest.raises(UnsupportedError, match="nonlinear") as error:
        build_problem(binding)
    assert error.value.document == specification.id
    assert error.value.target == UUID(
        payload["formulations"][0]["constraints"][0]["id"]
    )


def test_make_candidate_writes_solved_values_into_a_new_revision():
    _, binding = bound()
    candidate = make_candidate(binding, SOLUTION, run_id=uuid4())
    assert candidate.id != binding.model.id
    assert candidate.value(CAPITAL).quantity.number == pytest.approx(11000000)
    with pytest.raises(NumericalError, match="unknown symbols"):
        make_candidate(binding, {NOI: 550000.0}, run_id=uuid4())


def test_verify_accepts_the_solution_and_rejects_another():
    _, binding = bound()
    accepted = verify(binding, make_candidate(binding, SOLUTION, run_id=uuid4()))
    assert isinstance(accepted, Verification)
    assert accepted.accepted
    wrong = {**SOLUTION, CAPITAL: 12000000.0}
    rejected = verify(
        binding,
        make_candidate(binding, wrong, run_id=uuid4()),
        tolerances=Tolerances(),
    )
    assert not rejected.accepted
    assert any(d.code == "constraint_residual" for d in rejected.diagnostics)


def test_assemble_validates_the_run_with_its_output_laid_over_the_resolver():
    cases, composition, _ = stages()
    attempted, output = attempt(cases, composition)
    run = assemble(
        cases.root,
        attempted.report,
        id=attempted.id,
        output=output,
        resolver=cases,
    )
    assert isinstance(run, Run)
    assert run.to_data() == attempted.to_data()
    with pytest.raises(ValidationError):
        assemble(cases.root, attempted.report, id=uuid4(), output=None, resolver=cases)


def test_an_attempt_runs_every_stage_with_a_backend_that_starts_no_process():
    cases, composition, _ = stages()
    run, output = attempt(cases, composition)
    assert run.report.status.solution == SolutionStatus.FEASIBLE
    assert run.record.outputs == (output.id,)
    assert output.value(NOI).quantity.number == pytest.approx(550000)

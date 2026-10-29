"""``solve`` needs no store; ``execute`` publishes outputs, then Runs (#126)."""

from collections import Counter
from uuid import uuid4

import pytest

from rangekeeper import Specification
from rangekeeper.execution import ExecutionConfig, Outcome, execute, solve
from rangekeeper.execution.backends import BackendResult, Termination
from rangekeeper.io import MemoryStore
from rangekeeper.model import Model
from rangekeeper.run import Run, SolutionStatus
from rangekeeper.shared.errors import MissingReferenceError
from tests.execution.test_execution import CAPITAL, NOI, fresh, setup, spec
from tests.execution.test_stages import Unchanged


class Exact:
    """A backend that returns the known solution, in this process."""

    def solve(self, *, problem, **kwargs):
        return BackendResult(
            termination=Termination.FEASIBLE,
            candidate={NOI: 550000.0, CAPITAL: 11000000.0},
        )


CONFIG = ExecutionConfig(backend=Exact())


class Recording(MemoryStore):
    """A MemoryStore that records the kind of each put, in order."""

    def __init__(self):
        super().__init__()
        self.puts: list[tuple[str, object]] = []

    def put(self, document):
        self.puts.append((type(document).__name__, document.id))
        return super().put(document)


def batch_of(model, *leaves):
    return Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(model.id),
            "cases": [str(leaf.id) for leaf in leaves],
        }
    )


def count_validations(monkeypatch):
    from rangekeeper.execution import pipeline
    from rangekeeper.io import memory

    counts: Counter = Counter()

    def counted(original):
        def validate(run, **kwargs):
            counts[run.id] += 1
            return original(run, **kwargs)

        return validate

    monkeypatch.setattr(
        pipeline, "validate_executed", counted(pipeline.validate_executed)
    )
    monkeypatch.setattr(memory, "validate_run", counted(memory.validate_run))
    return counts


def test_solve_needs_no_store_and_returns_the_whole_tree():
    store, model = setup()
    first, second = spec(), spec()
    batch = batch_of(model, first, second)
    for document in (first, second, batch):
        store.put(document)
    outcome = solve(specification=batch, resolver=Unchanged(store), config=CONFIG)
    assert isinstance(outcome, Outcome)
    assert len(outcome.cases) == 2
    assert all(
        case.run.report.status.solution == SolutionStatus.FEASIBLE
        for case in outcome.cases
    )
    assert {model.id for model in outcome.outputs} == set(outcome.run.record.outputs)
    with pytest.raises(MissingReferenceError):
        store.load_run(outcome.run.id)


def test_solve_validates_each_run_once(monkeypatch):
    counts = count_validations(monkeypatch)
    store, _ = setup()
    specification = spec()
    store.put(specification)
    outcome = solve(specification=specification, resolver=store, config=CONFIG)
    assert counts == {outcome.run.id: 1}


def test_execute_publishes_outputs_then_runs_and_validates_the_tree_once(monkeypatch):
    counts = count_validations(monkeypatch)
    store = Recording()
    _, model = setup(store)
    first, second = spec(), spec()
    batch = batch_of(model, first, second)
    for document in (first, second):
        store.put(document)
    store.puts.clear()
    outcome = execute(specification=batch, store=store, config=CONFIG)
    leaves = outcome.cases
    assert store.puts == [
        ("Specification", batch.id),
        ("Model", leaves[0].outputs[0].id),
        ("Run", leaves[0].run.id),
        ("Model", leaves[1].outputs[0].id),
        ("Run", leaves[1].run.id),
        ("Run", outcome.run.id),
    ]
    # One validation of the whole tree; store.put does not repeat it.
    assert counts == {outcome.run.id: 1}
    assert store.load_run(outcome.run.id).to_data() == outcome.run.to_data()
    assert isinstance(store.load_model(leaves[0].outputs[0].id), Model)


def test_execute_puts_nothing_when_solving_raises():
    store = Recording()
    _, model = setup(store)
    store.puts.clear()
    missing = spec(model=Model.from_data(data=fresh(model.to_data())))
    with pytest.raises(MissingReferenceError):
        execute(specification=missing, store=store, config=CONFIG)
    assert store.puts == []


def test_an_outcome_matches_its_run():
    store, _ = setup()
    specification = spec()
    store.put(specification)
    outcome = solve(specification=specification, resolver=store, config=CONFIG)
    with pytest.raises(ValueError, match="outputs"):
        Outcome(run=outcome.run)
    with pytest.raises(ValueError, match="cases"):
        Outcome(run=outcome.run, outputs=outcome.outputs, cases=(outcome,))
    with pytest.raises(TypeError):
        Outcome(run=outcome.run.to_data())  # type: ignore[arg-type]
    assert isinstance(outcome.run, Run)

"""Each execution runs each composition, Specification and Run check once (#132)."""

from collections import Counter
from uuid import uuid4

import pytest

from rangekeeper import Specification
from rangekeeper.execution import ExecutionConfig, execute, solve
from rangekeeper.execution.backends import BackendResult, Termination
from rangekeeper.io import DirectoryStore, MemoryStore
from rangekeeper.run import validation as run_validation
from rangekeeper.run.validation import mark_validated, validated_in
from rangekeeper.shared.errors import ValidationError
from rangekeeper.specification import composition, validation
from tests.execution.test_execution import CAPITAL, NOI, setup, spec


class Exact:
    def solve(self, problem, **kwargs):
        return BackendResult(
            termination=Termination.FEASIBLE, candidate={NOI: 550000.0, CAPITAL: 11e6}
        )


CONFIG = ExecutionConfig(backend=Exact())


@pytest.fixture
def counts(monkeypatch):
    found: Counter = Counter()
    for module, name in (
        (composition, "compose_specification"),
        (validation, "check_specification"),
        (run_validation, "validate_records"),
        (run_validation, "check_specification"),
        (run_validation, "compose_specification"),
    ):
        original = getattr(module, name)

        def counted(*args, _original=original, _name=name, **kwargs):
            found[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(module, name, counted)
    return found


def batch(count, store):
    _, model = setup(store)
    leaves = [spec() for _ in range(count)]
    for leaf in leaves:
        store.put(leaf)
    return Specification.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(model.id),
            "cases": [str(leaf.id) for leaf in leaves],
        }
    )


def solve_with(specification, store, *, config):
    return solve(specification=specification, resolver=store, config=config)


def execute_with(specification, store, *, config):
    return execute(specification=specification, store=store, config=config)


@pytest.mark.parametrize("verb", [solve_with, execute_with])
@pytest.mark.parametrize("leaves", [1, 3])
def test_each_leaf_is_composed_and_checked_once(counts, verb, leaves):
    store = MemoryStore()
    root = batch(leaves, store)
    counts.clear()
    outcome = verb(root, store, config=CONFIG)
    assert len(outcome.cases) == leaves
    assert counts["compose_specification"] == leaves
    assert counts["check_specification"] == leaves
    assert counts["validate_records"] == 1


def test_a_store_trusts_only_its_own_validation():
    store = MemoryStore()
    root = batch(2, store)
    outcome = solve(specification=root, resolver=store, config=CONFIG)
    leaf = outcome.cases[0]
    # solve marks nothing: a store validates what solve returns.
    assert not validated_in(leaf.run, store, lambda id: True)

    other = MemoryStore()
    mark_validated(leaf.run, other, {leaf.outputs[0].id})
    assert not validated_in(leaf.run, store, lambda id: True)
    assert not validated_in(leaf.run, other, lambda id: False)
    assert validated_in(leaf.run, other, lambda id: True)


def test_execute_marks_each_run_against_its_store(tmp_path):
    store = DirectoryStore(tmp_path)
    root = batch(2, store)
    outcome = execute(specification=root, store=store, config=CONFIG)
    for item in outcome.walk():
        assert validated_in(
            item.run, store, lambda id: (tmp_path / f"{id}.json").exists()
        )
    # Another store validates the same Run in full and refuses it without its inputs.
    fresh = MemoryStore()
    with pytest.raises(ValidationError):
        fresh.put(outcome.cases[0].run)

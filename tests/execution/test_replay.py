"""``replay`` solves a stored Run again and compares the results (#294).

Replay reads the Run's documents from a store and writes nothing. Each
difference in a case's status, outputs or values is a ``replay_mismatch``
diagnostic, and ``raise_for_status()`` raises the first. It is not the path
replay of ``rangekeeper.market``.
"""

from copy import deepcopy
from decimal import Decimal
from uuid import UUID

import pytest

import rangekeeper as rk
from rangekeeper.execution import (
    ExecutionConfig,
    Limits,
    Replay,
    Status,
    Tolerances,
    execute,
    replay,
    solve,
)
from rangekeeper.execution.replaying import _differences
from rangekeeper.io import DirectoryStore, MemoryStore
from rangekeeper.model import Model
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError
from tests.execution.test_execution import records
from tests.execution.test_pipeline import dated

pytest.importorskip("pyomo")
pytest.importorskip("highspy")

CASES = {"low": {"rate": "5 % pa"}, "high": {"rate": "9 % pa"}}


class Changed:
    """A store that returns another revision in place of one stored Model."""

    def __init__(self, store: MemoryStore, model: Model) -> None:
        self.store = store
        self.model = model

    def load_model(self, id: UUID) -> Model:
        return self.model if id == self.model.id else self.store.load_model(id)

    def load_specification(self, id: UUID) -> rk.Specification:
        return self.store.load_specification(id)

    def load_run(self, id: UUID) -> rk.Run:
        return self.store.load_run(id)


def changed(model: Model, **magnitudes: object) -> Model:
    """Return ``model`` with other magnitudes: of a scalar, or of a Flow's first amount."""
    data = deepcopy(model.to_data())
    for record in records(data):
        if record.get("key") in magnitudes:
            magnitude = str(magnitudes[record["key"]])
            if "flow" in record:
                record["flow"]["movements"][0]["magnitude"] = magnitude
            else:
                record["quantity"]["magnitude"] = magnitude
    return Model.from_data(data=data)


def test_a_replay_of_a_stored_batch_gives_the_stored_result(tmp_path):
    store = DirectoryStore(path=tmp_path / "runs")
    outcome = execute(specification=dated().cases(cases=CASES), store=store)
    files = sorted(store.root.iterdir())
    # As in a new kernel: a new store of the same folder, and nothing else.
    fresh = DirectoryStore(path=tmp_path / "runs")
    run = fresh.find_runs(specification="Dated")[-1]
    replayed = replay(run=run, store=fresh)
    assert isinstance(replayed, Replay)
    assert replayed.diagnostics == ()
    assert replayed.raise_for_status() is replayed
    assert repr(replayed) == f"Replay(run={run.id}, differences=0)"
    assert replayed.stored.run.to_data() == outcome.run.to_data()
    assert [case.key for case in replayed.stored.cases] == ["low", "high"]
    assert [case.key for case in replayed.outcome.cases] == ["low", "high"]
    low = replayed.outcome.case(key="low")
    assert low["npv"] == outcome.case(key="low")["npv"]
    assert replayed.stored.case(key="low")["works"] == low["works"]
    assert replayed.outcome.run.id != run.id
    assert sorted(store.root.iterdir()) == files  # replay writes nothing


def test_a_replay_of_a_leaf_run():
    store = MemoryStore()
    outcome = execute(specification=dated(), store=store)
    replayed = replay(run=outcome.run, store=store).raise_for_status()
    assert replayed.stored.key == "Dated"
    assert replayed.outcome.status is Status.FEASIBLE
    assert replayed.outcome["npv"] == outcome["npv"]


def test_a_changed_value_is_a_replay_mismatch():
    store = MemoryStore()
    outcome = execute(specification=dated(), store=store)
    model = changed(outcome.model, npv="-9000000", works="-4000000")
    replayed = replay(run=outcome.run, store=Changed(store, model))
    works, npv = replayed.diagnostics
    assert {works.code, npv.code} == {Code.REPLAY_MISMATCH.value}
    assert works.values == {
        "case": None,
        "key": "works",
        "on": "2027-01-01/2028-01-01",
        "stored": "-4000000 AUD",
        "replayed": "-5000000 AUD",
    }
    assert dict(npv.values) == {
        "case": None,
        "key": "npv",
        "stored": "-9000000 AUD",
        "replayed": str(outcome["npv"]),
    }
    with pytest.raises(ContractError, match="works") as error:
        replayed.raise_for_status()
    assert error.value.code is Code.REPLAY_MISMATCH
    assert error.value.document_id == outcome.run.id
    assert error.value.values == dict(works.values)


def test_values_agree_within_the_tolerances():
    store = MemoryStore()
    outcome = execute(specification=dated(), store=store)
    npv = outcome["npv"].magnitude
    assert isinstance(npv, Decimal)
    nearby = changed(outcome.model, npv=npv + Decimal("1e-8"))
    within = replay(run=outcome.run, store=Changed(store, nearby))
    assert within.diagnostics == ()
    exact = ExecutionConfig(tolerances=Tolerances(absolute=0, relative=0))
    strict = replay(run=outcome.run, store=Changed(store, nearby), config=exact)
    assert [item.values["key"] for item in strict.diagnostics] == ["npv"]


def test_another_status_is_a_replay_mismatch():
    store = MemoryStore()
    outcome = execute(specification=dated(), store=store)
    limited = ExecutionConfig(limits=Limits(symbol_limit=1))
    replayed = replay(run=outcome.run, store=store, config=limited)
    (mismatch,) = replayed.diagnostics
    assert replayed.outcome.status is Status.UNSUPPORTED
    assert mismatch.values == {
        "case": None,
        "stored": "feasible",
        "replayed": "unsupported",
    }


def test_other_outputs_are_a_replay_mismatch():
    store = MemoryStore()
    loose = dated().free("cost")
    published = ExecutionConfig(allow_underdetermined=True)
    outcome = execute(specification=loose, store=store, config=published)
    assert outcome.status is Status.UNDERDETERMINED and outcome.outputs
    assert replay(run=outcome.run, store=store, config=published).diagnostics == ()
    (mismatch,) = replay(run=outcome.run, store=store).diagnostics
    assert mismatch.values == {"case": None, "stored": 1, "replayed": 0}


def test_replay_takes_a_run():
    with pytest.raises(TypeError, match="run"):
        replay(run=dated(), store=MemoryStore())  # type: ignore[arg-type]


def test_other_cases_are_one_replay_mismatch():
    """Pair the cases of two Outcomes by key.

    A private helper: a Run and its replay solve the same Specification, so a
    store cannot give them other cases.
    """
    base = dated()
    stored = solve(specification=base.cases(cases=CASES))
    other = solve(specification=base.cases(cases={"low": {}, "middle": {}}))
    (mismatch,) = _differences(stored, other, tolerances=Tolerances())
    assert mismatch.values == {
        "stored": ("low", "high"),
        "replayed": ("low", "middle"),
    }

"""Cases: a batch of named Specifications, one solve and one comparable table."""

import importlib.util
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, MissingReferenceError, UnitError
from rangekeeper.specification import Role, Specification
from tests.specification.lesson_02 import lesson_02_model
from tests.specification.test_roles import front_door

requires_execution = pytest.mark.skipif(
    any(importlib.util.find_spec(name) is None for name in ("pyomo", "highspy")),
    reason="requires the optional execution extra",
)

CASES = {
    "low": {"leverage": "50 %"},
    "reference": {},
    "high": {"leverage": "70 %", "coverage": 1.3},
}


def leverage(specification):
    model = specification.model
    target = model.value(owner=model.entity(code="project").id, key="leverage")
    return specification.roles.row(target.id).values["quantity"]


def test_cases_make_a_batch_of_named_revisions():
    model = lesson_02_model()
    front = front_door(model)
    batch = front.cases(cases=CASES)
    assert batch.metadata.name == "Front door"
    assert batch.metadata.previous == front.id
    assert batch.model_id == model.id
    assert batch.model is model
    record = batch.to_data()
    assert set(record) == {"metadata", "model", "cases"}
    cases = [batch.case(key=key) for key in CASES]
    assert list(batch.record.cases) == [case.id for case in cases]
    for key, case in zip(CASES, cases, strict=True):
        assert case.metadata.name == key
        assert case.metadata.previous == front.id
        assert case.model_id == model.id
        assert not case.record.cases
    # A case's values replace the base's fixes; the rest stay.
    assert leverage(batch.case(key="low")) == rk.Quantity(text="50 %")
    assert leverage(batch.case(key="reference")) == rk.Quantity(text="65 %")
    high = batch.case(key="high")
    assert leverage(high) == rk.Quantity(text="70 %")
    assert len(high.record.assignments) == len(front.record.assignments)
    assert {row.values["role"] for row in high.roles.rows} == {
        Role.FIXED,
        Role.FREE,
    }
    # The base does not change.
    assert not front.record.cases
    assert leverage(front) == rk.Quantity(text="65 %")


def test_case_finds_a_case_by_key():
    model = lesson_02_model()
    batch = front_door(model).cases(cases=CASES)
    with pytest.raises(MissingReferenceError) as error:
        batch.case(key="weak")
    assert error.value.candidates == ("low", "reference", "high")
    assert (error.value.kind, error.value.by) == ("Specification", "key")
    with pytest.raises(ContractError) as error:
        front_door(model).case(key="low")
    assert error.value.code is Code.BATCH_REQUIRED


def test_a_batch_read_from_data_loads_its_cases():
    from rangekeeper.io import MemoryStore

    model = lesson_02_model()
    batch = front_door(model).cases(cases=CASES)
    store = MemoryStore()
    store.put(model)
    for key in CASES:
        store.put(batch.case(key=key))
    store.put(batch)
    loaded = Specification.from_data(batch.to_data())
    with pytest.raises(ContractError) as error:
        loaded.case(key="low")
    assert error.value.code is Code.RESOLVER_MISSING
    attached = Specification(record=loaded.record, model=model, resolver=store)
    assert attached.case(key="high").id == batch.case(key="high").id
    assert attached.resolver is store


def test_cases_check_their_arguments():
    model = lesson_02_model()
    front = front_door(model)
    with pytest.raises(TypeError, match="mapping"):
        front.cases(cases={})
    with pytest.raises(TypeError, match="mapping"):
        front.cases(cases={"low": "50 %"})  # type: ignore[dict-item]
    with pytest.raises(ContractError, match="key"):
        front.cases(cases={" ": {}})
    with pytest.raises(TypeError, match="key"):
        front.cases(cases={1: {}})  # type: ignore[dict-item]
    with pytest.raises(UnitError):
        front.cases(cases={"low": {"leverage": "5 AUD"}})
    with pytest.raises(MissingReferenceError):
        front.cases(cases={"low": {"leverag": "50 %"}})
    batch = front.cases(cases=CASES)
    for call in (
        lambda: batch.cases(cases=CASES),
        lambda: batch.fix(leverage="50 %"),
        lambda: batch.roles,
        lambda: batch.on(model=model),
    ):
        with pytest.raises(ContractError) as error:
            call()
        assert error.value.code is Code.BATCH_UNSUPPORTED
    record = rk.specification.SpecificationRecord(
        metadata=rk.model.Metadata(id=uuid4(), schema_version="1.0.0"),
        model=model.id,
    )
    with pytest.raises(ContractError, match="no Model") as error:
        Specification(record=record).cases(cases=CASES)
    assert error.value.code is Code.MODEL_MISSING


@requires_execution
def test_a_batch_solves_each_case():
    model = lesson_02_model()
    front = front_door(model)
    batch = front.cases(cases=CASES)
    batch_outcome = rk.execution.solve(specification=batch)
    batch_outcome.raise_for_status()
    assert [case.key for case in batch_outcome.cases] == list(CASES)
    assert batch_outcome.key == "Front door"
    reference = rk.execution.solve(specification=front)["rent_factor"]
    assert batch_outcome.case(key="reference")["rent_factor"] == reference
    assert (
        batch_outcome.case(key="low")["rent_factor"]
        < reference
        < batch_outcome.case(key="high")["rent_factor"]
    )


@requires_execution
def test_execute_puts_the_cases_before_the_batch():
    from rangekeeper.io import MemoryStore

    model = lesson_02_model()
    batch = front_door(model).cases(cases=CASES)
    store = MemoryStore()
    store.put(model)
    outcome = rk.execution.execute(specification=batch, store=store)
    for key in CASES:
        case = batch.case(key=key)
        assert store.load_specification(case.id).metadata.name == key
    assert store.load_specification(batch.id).record.cases == batch.record.cases
    assert store.load_run(outcome.run.id).record.spawns == tuple(
        case.run.id for case in outcome.cases
    )

"""``solve`` resolves the documents that made the Specification (#293)."""

from uuid import uuid4

import pytest

from rangekeeper import Specification
from rangekeeper.execution import Status, solve
from rangekeeper.io import MemoryStore
from rangekeeper.quantity import isclose
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.shared.errors import MissingReferenceError
from tests.execution.lesson02 import MODEL, back, q, store


def test_solve_needs_no_resolver_for_a_specification_of_a_model():
    back_outcome = solve(specification=back())
    back_outcome.raise_for_status()
    with_store = solve(specification=back(), resolver=store())
    assert isclose(actual=back_outcome["land_cost"], expected=with_store["land_cost"])


def test_each_chained_specification_keeps_its_model():
    lower = solve(specification=back().fix(leverage=q("50 %")))
    higher = solve(specification=back())
    assert lower.status is Status.FEASIBLE
    assert lower["land_cost"] > higher["land_cost"]  # less debt for each dollar
    assert lower.run.record.specification != higher.run.record.specification


def test_the_specification_s_own_resolver_supplies_its_includes():
    included = back()
    documents = MemoryStore()
    documents.put(MODEL)
    documents.put(included)
    record = SpecificationRecord.from_data(
        {
            "metadata": {"id": str(uuid4()), "schema_version": "1.0.0"},
            "model": str(MODEL.id),
            "includes": [str(included.id)],
        }
    )
    including = Specification(record=record, model=MODEL, resolver=documents)
    assert solve(specification=including).status is Status.FEASIBLE


def test_a_specification_read_from_data_needs_a_resolver():
    detached = Specification.from_data(back().to_data())
    with pytest.raises(MissingReferenceError, match="pass resolver="):
        solve(specification=detached)
    assert solve(specification=detached, resolver=store()).status is Status.FEASIBLE

"""A Value by its key: ``Model.value(key=)`` and its inverse ``Model.key_of``."""

from datetime import date
from uuid import uuid4

import pytest

import rangekeeper as rk
from rangekeeper.model import Update
from rangekeeper.schema.records import Characteristics, Value, ValueKind
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    MissingReferenceError,
    ReferenceTypeError,
)

YEARS = rk.duration.Span(start=date(2027, 1, 1), end=date(2029, 1, 1)).periods(
    frequency=rk.duration.Frequency.YEAR
)


def keyed():
    """Return a Model where Entity ``a`` and a Relationship each have ``income``."""
    draft = rk.Model(name="Keys").edit()
    a = draft.add_entity(code="a")
    a.value(key="income", units="AUD")
    a.value(key="cost", units="AUD")
    a.flow(key="rent", units="AUD", periods=YEARS)
    draft.add_entity(code="b")
    lease = draft.add_relationship(source="a", target="b", classification="leases")
    model = draft.commit()
    measure = model.definitions.measures[0].id
    shared = Value(
        id=uuid4(), key="income", kind=ValueKind.MEASUREMENT, measure=measure
    )
    relationship = model.relationship(lease.id).replace(
        characteristics=Characteristics(values=(shared,))
    )
    system = model.system.replace(relationships=(relationship,))
    metadata = model.metadata.replace(id=uuid4(), previous=model.id)
    return model.revise(Update(system=system, metadata=metadata)), shared.id


def test_key_of_gives_the_key_that_value_reads():
    model, shared = keyed()
    a = model.entity(code="a").id
    income = model.value(owner=a, key="income").id
    cost = model.value(owner=a, key="cost").id
    assert model.key_of(cost) == "cost"
    assert model.key_of(income) == "a.income"
    # The Relationship has no code: its Value has the text of its UUID.
    assert model.key_of(shared) == str(shared)
    for identity in (cost, income, shared):
        assert model.value(key=model.key_of(identity)).id == identity
    rent = model.value(owner=a, key="rent")
    movement = rent.flow.movements[0].id
    assert model.key_of(movement) == "rent"


def test_an_ambiguous_key_lists_keys_that_resolve():
    model, shared = keyed()
    with pytest.raises(AmbiguousReferenceError) as error:
        model.value(key="income")
    assert error.value.candidates == ("a.income", str(shared))
    for candidate in error.value.candidates:
        assert model.value(key=candidate).key == "income"


def test_a_key_that_names_no_value_raises():
    model, _ = keyed()
    with pytest.raises(MissingReferenceError) as error:
        model.value(key="incme")
    assert (error.value.by, error.value.candidates) == ("key", ("income",))
    with pytest.raises(MissingReferenceError) as error:
        model.value(key="a.incme")
    assert (error.value.by, error.value.requested) == ("path", "a.incme")
    assert error.value.candidates[0] == "a.income"
    with pytest.raises(MissingReferenceError):
        model.value(key=str(uuid4()))
    with pytest.raises(ReferenceTypeError):
        model.key_of(model.entity(code="a").id)
    with pytest.raises(TypeError):
        model.value(owner=model.entity(code="a").id)


def test_roles_name_each_value_by_the_key_that_fix_takes():
    model, shared = keyed()
    spec = model.specify().fix({str(shared): "1 AUD", "a.income": "2 AUD"})
    keys = [row.values["key"] for row in spec.roles.rows]
    assert keys == ["a.income", str(shared)]
    for key in keys:
        assert spec.free(key).fix({key: "3 AUD"}).roles.rows

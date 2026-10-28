"""Typed target lookups agree with the raw-mapping checks of the same Model."""

from datetime import date
from uuid import uuid4

import pytest

from rangekeeper.flow import Flow
from rangekeeper.model import (
    Characteristics,
    Definitions,
    Entity,
    Measure,
    Metadata,
    Model,
    Reference,
    System,
    Value,
    ValueKind,
)
from rangekeeper.model._scope import (
    numerical_units,
    recorded_quantity,
    scope_for_model,
)
from rangekeeper.model.targets import recorded_scalar, target_units, target_value
from rangekeeper.quantity import Quantity
from rangekeeper.shared.errors import ContractError


def example():
    money = Measure(id=uuid4(), code="money", name="Money", units="AUD")
    price = Value(
        id=uuid4(),
        key="price",
        kind=ValueKind.MEASUREMENT,
        measure=money.id,
        quantity=Quantity(magnitude=0, units="AUD"),
    )
    unknown = Value(
        id=uuid4(), key="unknown", kind=ValueKind.MEASUREMENT, measure=money.id
    )
    cash = Value(
        id=uuid4(),
        key="cash",
        kind=ValueKind.FLOW,
        measure=money.id,
        flow=Flow.from_events([date(2027, 1, 1)], [30_000], units="AUD"),
    )
    note = Value(id=uuid4(), key="note", kind=ValueKind.PROPERTY)
    owner = Entity(
        id=uuid4(),
        characteristics=Characteristics(values=(price, unknown, cash, note)),
    )
    model = Model.create(
        metadata=Metadata(id=uuid4(), schema_version="1.0.0"),
        definitions=Definitions(measures=(money,)),
        system=System(entities=(owner,)),
    )
    return model, price, unknown, cash, note


def test_typed_lookups_match_the_raw_mapping_checks():
    model, price, unknown, cash, _ = example()
    scope = scope_for_model(model)
    movement = cash.flow.movements[0]
    for value, target in (
        (price, price.id),
        (unknown, unknown.id),
        (cash, movement.id),
    ):
        reference = Reference(target=target)
        raw = reference.to_data()
        assert target_value(model, reference) == value
        assert target_units(model, reference) == "AUD"
        assert numerical_units(raw, scope.targets, scope.measures) == "AUD"
        scalar = recorded_scalar(model, reference)
        quantity = recorded_quantity(raw, scope.targets, scope.measures)
        assert (None if scalar is None else scalar.to_data()) == quantity
    assert recorded_scalar(model, Reference(target=price.id)).magnitude == 0
    assert recorded_scalar(model, Reference(target=unknown.id)) is None
    assert recorded_scalar(model, Reference(target=movement.id)) == Quantity(
        magnitude=30_000, units="AUD"
    )


def test_a_property_value_has_no_scalar_units_in_either_form():
    model, *_, note = example()
    reference = Reference(target=note.id)
    with pytest.raises(ContractError) as typed:
        target_units(model, reference)
    scope = scope_for_model(model)
    with pytest.raises(ContractError) as raw:
        numerical_units(reference.to_data(), scope.targets, scope.measures)
    assert typed.value.code == raw.value.code
    assert str(typed.value) == str(raw.value)

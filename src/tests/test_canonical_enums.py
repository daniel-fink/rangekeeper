"""Typed choices and wire values have explicit, separate boundaries."""

from enum import Enum
from uuid import uuid4

import pytest

from rangekeeper.schema.enums import _ENUM_TYPES
from rangekeeper.model import Value, ValueKind
from rangekeeper.model.content import encode
from rangekeeper.shared.errors import ValidationError
from rangekeeper.model.expression import Expression, ExpressionKind, Operator
from rangekeeper.specification.policy import Action, ActionKind
from rangekeeper.run import CompletionStatus


def test_generated_enums_are_unique_plain_enums_with_unchanged_wire_values():
    for kind in _ENUM_TYPES.values():
        assert issubclass(kind, Enum) and not issubclass(kind, str)
        assert len(kind.__members__) == len(kind)
        assert all(type(member.value) is str for member in kind)
        assert all(member != member.value for member in kind)
    assert ValueKind.MEASUREMENT.value == "measurement"
    assert Operator.LESS_THAN.value == "less_than"
    assert ActionKind.ASSIGN.value == "assign"
    assert CompletionStatus.COMPLETED.value == "completed"


def test_record_construction_and_replacement_require_the_correct_enum():
    identity = uuid4()
    with pytest.raises(TypeError, match="ValueKind"):
        Value(id=identity, key="test", kind="property")
    with pytest.raises(TypeError, match="ValueKind"):
        Value(id=identity, key="test", kind=ExpressionKind.BOOLEAN)
    record = Value(
        id=identity, key="test", kind=ValueKind.PROPERTY, content=encode("measurement")
    )
    assert record.kind is ValueKind.PROPERTY
    assert record.to_data()["kind"] == "property"
    assert record.content == encode("measurement")
    assert Value.from_data(record.to_data()) == record
    with pytest.raises(TypeError, match="ValueKind"):
        record.replace(kind="property")
    with pytest.raises((TypeError, ValidationError)):
        Value.from_data({**record.to_data(), "kind": ValueKind.PROPERTY})


def test_nested_decoding_returns_the_same_public_enum_classes():
    expression = Expression.from_data(
        {"id": str(uuid4()), "kind": "boolean", "boolean": True}
    )
    action = Action.from_data({"kind": "terminate"})
    assert expression.kind is ExpressionKind.BOOLEAN
    assert action.kind is ActionKind.TERMINATE


def test_currency_catalogue_restrictions_are_sorted_immutable_and_historical():
    from rangekeeper.shared.units import UnitSystem, default_units
    from moneyed import list_all_currencies

    assert set(default_units.currencies) == {
        item.code for item in list_all_currencies()
    }
    assert {"AUD", "USD", "DEM"} <= set(default_units.currencies)
    selected = UnitSystem(currencies=("USD", "AUD", "USD"))
    assert selected.currencies == ("AUD", "USD")
    assert selected.compatible("AUD/year", "AUD/year")
    assert not selected.compatible("AUD", "USD")

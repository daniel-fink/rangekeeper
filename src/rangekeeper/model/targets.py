"""Typed lookups of a Reference target in one Model revision.

Each function takes a Model and a Reference and returns typed records. The checks
over raw wire mappings, which run before a Model exists, are in
``rangekeeper.model._scope``.
"""

from typing import TYPE_CHECKING

from rangekeeper.flow import Movement
from rangekeeper.schema.records import Measure, Quantity, Reference, Value, ValueKind
from rangekeeper.shared.validation import require

if TYPE_CHECKING:
    from rangekeeper.model.model import Model


def _target(model: "Model", target: Reference) -> tuple[Value, Movement | None]:
    record = model.resolve(target)
    if isinstance(record, Movement):
        owner = model.owner_of(record.id)
        assert owner is not None  # a Movement's owner is its Value
        return model.value(owner), record
    return record, None


def _units(model: "Model", value: Value, movement: Movement | None) -> str:
    if movement is not None:
        assert value.flow is not None  # a Movement is inside its Value's Flow
        return value.flow.units
    require(
        value.kind == ValueKind.MEASUREMENT,
        "numerical roles require a scalar measurement or Movement",
    )
    assert value.measure is not None  # Model validation requires the Measure
    return model._index.get(value.measure, Measure).units


def target_value(model: "Model", target: Reference) -> Value:
    """Return the owning Value with one target-resolution operation."""
    return _target(model, target)[0]


def target_units(model: "Model", target: Reference) -> str:
    """Read declared scalar units without inferring a solve role."""
    value, movement = _target(model, target)
    return _units(model, value, movement)


def recorded_scalar(model: "Model", target: Reference) -> Quantity | None:
    """Read explicit scalar content using the same eligibility rules as validation."""
    value, movement = _target(model, target)
    units = _units(model, value, movement)
    if movement is not None:
        return (
            None
            if movement.magnitude is None
            else Quantity(magnitude=movement.magnitude, units=units)
        )
    return value.quantity

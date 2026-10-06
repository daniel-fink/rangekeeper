"""Resolve numerical symbols without changing canonical Value identities."""

from uuid import UUID

from .._schema.records import ValueReference, Quantity
from ..model import Model
from ..model._references import reference_key
from ..model.definitions import measure


def key(reference: ValueReference) -> str:
    """Return a private backend key; never persist it as a domain UUID."""
    return reference_key(reference.to_data())


def reference(token: str) -> ValueReference:
    """Decode a private symbol token whose UUID occupies the first 36 characters."""
    return ValueReference(
        value=UUID(token[:36]), **({"movement": token[37:]} if len(token) > 36 else {})
    )


def units_for(model: Model, target: ValueReference) -> str:
    """Return scalar Measure units or the declared units of a Flow payload."""
    value = model.value(target.value)
    if target.movement is None:
        if value.kind != "measurement" or value.measure is None:
            raise ValueError("numerical Flow references require a Movement key")
        return measure(model.definitions, value.measure).units
    if value.flow is None or not any(
        m.key == target.movement for m in value.flow.movements
    ):
        raise ValueError("unknown Movement or undeclared Flow shape")
    return value.flow.units


def read(model: Model, target: ValueReference) -> Quantity | None:
    """Explicitly read recorded content; callers decide whether reuse is allowed."""
    value = model.value(target.value)
    units = units_for(model, target)
    if target.movement is None:
        return value.quantity
    assert value.flow is not None
    item = next(m for m in value.flow.movements if m.key == target.movement)
    return (
        None
        if item.magnitude is None
        else Quantity(magnitude=item.magnitude, units=units)
    )

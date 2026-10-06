"""Read numerical declarations through the Model's identity and ownership indexes."""

from uuid import UUID
from .._schema.records import Reference, Quantity, Movement
from ..model import Model
from ..model.definitions import measure


def key(reference: Reference) -> str:
    """Use the target UUID directly; no owner/key encoding is needed."""
    return str(reference.target)


def reference(token: str) -> Reference:
    """Decode a backend symbol as one declaration UUID."""
    return Reference(target=UUID(token))


def owner(model: Model, target: Reference):
    """Return the Value that supplies a target's content and units."""
    record = model.resolve(target)
    if isinstance(record, Movement):
        identity = model.owner_of(record.id)
        assert identity is not None
        return model.value(identity)
    return record


def units_for(model: Model, target: Reference) -> str:
    """Use a scalar's Measure or a Movement's owning Flow; never infer units from labels."""
    record = model.resolve(target)
    value = owner(model, target)
    if isinstance(record, Movement):
        assert value.flow is not None
        return value.flow.units
    if value.kind != "measurement" or value.measure is None:
        raise ValueError("numerical roles require a scalar measurement or Movement")
    return measure(model.definitions, value.measure).units


def read(model: Model, target: Reference) -> Quantity | None:
    """Read recorded content explicitly; it does not acquire an assignment role."""
    record = model.resolve(target)
    units = units_for(model, target)
    if isinstance(record, Movement):
        return (
            None
            if record.magnitude is None
            else Quantity(magnitude=record.magnitude, units=units)
        )
    return record.quantity

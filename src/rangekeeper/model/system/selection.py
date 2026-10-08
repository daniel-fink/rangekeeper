"""Explicit selection of one owner-local Value; a Measure is not a Value key."""

from collections.abc import Callable
from uuid import UUID
from rangekeeper.model import Model, Entity, Value, Measure
from rangekeeper.model.characteristics import value
from rangekeeper.shared.arguments import require_text, require_uuid
from rangekeeper.model.system.errors import SelectionError

ValueSelector = Callable[[Model, Entity], Value | None]


def _local_value(entity: Entity, key: str, measure: UUID | None) -> Value | None:
    """Read a canonical Entity after the caller has prepared its Model and request."""
    selected = value(entity.characteristics, key)
    if selected is not None and measure is not None and selected.measure != measure:
        raise SelectionError(
            f"Value {selected.id} at {entity.id}/{key} does not use Measure {measure}"
        )
    return selected


def _recorded_quantity(selected, units, unit_system):
    """Convert an available recorded quantity; caller retains kind eligibility."""
    if selected is None or selected.quantity is None:
        return None
    return unit_system.convert(selected.quantity, to=units)


def select_value(key: str, *, measure: UUID | None = None) -> ValueSelector:
    """Build a selector for one local key, optionally asserting its Measure UUID.

    Selection resolves the Entity against the supplied Model, never reading stale
    fields from an object passed from another revision. An absent key returns None;
    a present key with a different Measure raises SelectionError. A supplied Measure
    must exist even when the key is absent. No code guessing or first-match lookup.
    """
    require_text(key, "key")
    if measure is not None:
        require_uuid(measure, "measure")

    def select(model: Model, entity: Entity) -> Value | None:
        if not isinstance(model, Model) or not isinstance(entity, Entity):
            raise TypeError("selector requires a Model and schema Entity")
        canonical = model.entity(entity.id)
        if measure is not None:
            model._index.get(measure, Measure)
        return _local_value(canonical, key, measure)

    return select


__all__ = ["ValueSelector", "select_value"]

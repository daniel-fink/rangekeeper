"""Explicit selection of one owner-local Value; a Measure is not a Value key."""

from collections.abc import Callable
from uuid import UUID
from ..model import Model, Entity, Value
from ..model.characteristics import value
from ..model.definitions import measure as find_measure
from ..validate import require_text, require_uuid
from .errors import SelectionError

ValueSelector = Callable[[Model, Entity], Value | None]


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
            find_measure(model.definitions, measure)
        selected = value(canonical.characteristics, key)
        if selected is not None and measure is not None and selected.measure != measure:
            raise SelectionError(
                f"Value {selected.id} at {canonical.id}/{key} does not use Measure {measure}"
            )
        return selected

    return select


__all__ = ["ValueSelector", "select_value"]

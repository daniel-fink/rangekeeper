"""Explicit scalar/Movement references and deliberate reuse of recorded amounts."""

from collections.abc import Sequence
from uuid import UUID

from .._schema.records import Assignment, ValueReference, Quantity
from ..model import Model


def scalar(value: UUID) -> ValueReference:
    """Reference a whole Value; numerical roles require a scalar measurement."""
    return ValueReference(value=value)


def movement(value: UUID, key: str) -> ValueReference:
    """Reference one stable owner-local Movement key, never an array position."""
    return ValueReference(value=value, movement=key)


def _select(model: Model, value: UUID, keys: Sequence[str] | None):
    item = model.value(value)
    if item.kind != "flow" or item.flow is None:
        raise ValueError("a declared Flow shape is required")
    selected = (
        tuple(m.key for m in item.flow.movements) if keys is None else tuple(keys)
    )
    by_key = {m.key: m for m in item.flow.movements}
    if len(set(selected)) != len(selected) or not set(selected) <= by_key.keys():
        raise ValueError("unknown or duplicate Movement selection")
    return item.flow, tuple(by_key[k] for k in selected)


def assign_flow(
    model: Model, value: UUID, *, keys: Sequence[str] | None = None
) -> tuple[Assignment, ...]:
    """Copy selected recorded magnitudes into explicit assignments in Flow units.

    This is an authoring choice, not a load-time default. Missing/null magnitudes
    fail; finite zero is retained. The Model and its records remain unchanged.
    """
    flow, selected = _select(model, value, keys)
    if any(m.magnitude is None for m in selected):
        raise ValueError("cannot assign unresolved Movements")
    return tuple(
        Assignment(
            target=movement(value, m.key),
            quantity=Quantity(magnitude=m.magnitude, units=flow.units),
        )
        for m in selected
    )


def unknown_flow(
    model: Model, value: UUID, *, keys: Sequence[str] | None = None
) -> tuple[ValueReference, ...]:
    """Declare selected Movements unknown even when recorded amounts are present."""
    _, selected = _select(model, value, keys)
    return tuple(movement(value, m.key) for m in selected)

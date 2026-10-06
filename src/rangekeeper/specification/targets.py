"""Explicit scalar/Movement references and deliberate reuse of recorded amounts."""

from collections.abc import Sequence
from uuid import UUID

from .._schema.records import Assignment, Reference, Quantity
from ..model import Model


def scalar(value: UUID) -> Reference:
    """Reference a whole Value; numerical roles require a scalar measurement."""
    return Reference(target=value)


def movement(id: UUID) -> Reference:
    """Reference a Movement directly by its declaration UUID."""
    return Reference(target=id)


def _select(model: Model, value: UUID, ids: Sequence[UUID] | None):
    item = model.value(value)
    if item.kind != "flow" or item.flow is None:
        raise ValueError("a declared Flow shape is required")
    selected = tuple(m.id for m in item.flow.movements) if ids is None else tuple(ids)
    by_id = {m.id: m for m in item.flow.movements}
    if len(set(selected)) != len(selected) or not set(selected) <= by_id.keys():
        raise ValueError("unknown or duplicate Movement selection")
    return item.flow, tuple(by_id[k] for k in selected)


def assign_flow(
    model: Model, value: UUID, *, ids: Sequence[UUID] | None = None
) -> tuple[Assignment, ...]:
    """Copy selected recorded magnitudes into explicit assignments in Flow units.

    This is an authoring choice, not a load-time default. Missing/null magnitudes
    fail; finite zero is retained. The Model and its records remain unchanged.
    """
    flow, selected = _select(model, value, ids)
    if any(m.magnitude is None for m in selected):
        raise ValueError("cannot assign unresolved Movements")
    return tuple(
        Assignment(
            target=movement(m.id),
            quantity=Quantity(magnitude=m.magnitude, units=flow.units),
        )
        for m in selected
    )


def unknown_flow(
    model: Model, value: UUID, *, ids: Sequence[UUID] | None = None
) -> tuple[Reference, ...]:
    """Declare selected Movements unknown even when recorded amounts are present."""
    _, selected = _select(model, value, ids)
    return tuple(movement(m.id) for m in selected)

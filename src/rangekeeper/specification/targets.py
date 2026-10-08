"""Explicit scalar/Movement references and deliberate reuse of recorded amounts."""

from collections.abc import Sequence
from uuid import UUID

from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.records import Assignment, Reference, Quantity
from rangekeeper.model import Model


def _select(model: Model, value: UUID, ids: Sequence[UUID] | None):
    item = model.value(value)
    if item.kind is not ValueKind.FLOW or item.flow is None:
        raise ValueError("a declared Flow shape is required")
    selected = tuple(m.id for m in item.flow.movements) if ids is None else tuple(ids)
    by_id = {m.id: m for m in item.flow.movements}
    if len(set(selected)) != len(selected) or not set(selected) <= by_id.keys():
        raise ValueError("unknown or duplicate Movement selection")
    return item.flow, tuple(by_id[k] for k in selected)


def assign_flow(
    model: Model,
    value: UUID,
    *,
    ids: Sequence[UUID] | None = None,
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
            target=Reference(target=m.id),
            quantity=Quantity(magnitude=m.magnitude, units=flow.units),
        )
        for m in selected
    )


def unknown_flow(
    model: Model,
    value: UUID,
    *,
    ids: Sequence[UUID] | None = None,
) -> tuple[Reference, ...]:
    """Declare selected Movements unknown even when recorded amounts are present."""
    _, selected = _select(model, value, ids)
    return tuple(Reference(target=m.id) for m in selected)

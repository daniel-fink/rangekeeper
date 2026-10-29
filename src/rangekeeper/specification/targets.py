"""Explicit scalar/Movement references and deliberate reuse of recorded amounts."""

from collections.abc import Sequence
from uuid import UUID

from rangekeeper.flow import Flow, Movement
from rangekeeper.model import Model
from rangekeeper.model.targets import target_units
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.records import Assignment, Reference, Value
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, MissingReferenceError


def _select(
    model: Model,
    value: UUID,
    ids: Sequence[UUID] | None,
) -> tuple[Flow, tuple[Movement, ...]]:
    """Return the Flow of a Value and its Movements with ``ids``, or all of them.

    A Value without a declared Flow raises ContractError. A UUID that is not a
    Movement of the Flow raises MissingReferenceError; a UUID given twice raises
    ContractError with the code ``UNIQUE``.
    """
    item = model.value(id=value)
    if item.kind is not ValueKind.FLOW or item.flow is None:
        raise ContractError(
            f"Value {item.key} has no declared Flow shape",
            targets=(item.id,),
            values={"key": item.key, "kind": item.kind},
        )
    by_id = {m.id: m for m in item.flow.movements}
    selected = tuple(by_id) if ids is None else tuple(ids)
    for identity in selected:
        if identity not in by_id:
            raise MissingReferenceError(
                identity, kind="Movement", by="id", where=f"Value {item.key}"
            )
    repeated = tuple(dict.fromkeys(k for k in selected if selected.count(k) > 1))
    if repeated:
        raise ContractError(
            "a Movement is selected more than once",
            code=Code.UNIQUE,
            targets=repeated,
        )
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
    unresolved = tuple(m.id for m in selected if m.magnitude is None)
    if unresolved:
        raise ContractError(
            "a Movement without a recorded amount cannot be assigned",
            targets=unresolved,
        )
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


def expand_targets(
    model: Model,
    target: UUID | Reference,
    *,
    ids: Sequence[UUID] | None = None,
) -> tuple[Reference, ...]:
    """Resolve a scalar, Movement or explicit whole-Flow selection without amounts."""
    ref = Reference(target=target) if isinstance(target, UUID) else target
    if not isinstance(ref, Reference):
        raise TypeError("target must be a UUID or Reference")
    record = model._index.records.get(ref.target)
    if isinstance(record, Value) and record.kind is ValueKind.FLOW:
        return unknown_flow(model, record.id, ids=ids)
    if ids is not None:
        raise ContractError(
            "Movement UUIDs select from a whole Flow Value only",
            targets=(ref.target,),
        )
    target_units(model, ref)
    return (ref,)

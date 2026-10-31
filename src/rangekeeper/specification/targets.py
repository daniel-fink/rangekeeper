"""Explicit scalar/Movement references and deliberate reuse of recorded amounts."""

from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from uuid import UUID

from rangekeeper.flow import Flow, Movement
from rangekeeper.model import Model
from rangekeeper.model.targets import date_target, target_units
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.records import Assignment, Reference, Value
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, MissingReferenceError, UnitError


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


def flow_amounts(model: Model, value: UUID, *, flow: Flow) -> dict[UUID, Quantity]:
    """Return the amount of ``flow`` for each Movement of a Flow Value, by coordinate.

    Each Movement of the Value takes the amount of the Movement of ``flow``
    over the same Period, or on the same date when it has no Period. A Flow
    with other coordinates raises ContractError with ``ALIGNMENT_DIFFER``; an
    unresolved amount raises ContractError.
    """
    _, movements = _select(model, value, None)
    given = {_coordinate(m): m for m in flow.movements}
    wanted = [_coordinate(m) for m in movements]
    if sorted(given, key=str) != sorted(wanted, key=str):
        raise ContractError(
            f"the Flow that fixes {model.key_of(value)} has other Periods or dates "
            "than the Flow Value",
            code=Code.ALIGNMENT_DIFFER,
            targets=(value,),
            values={"given": len(given), "declared": len(wanted)},
        )
    unresolved = tuple(m.id for m in flow.movements if m.magnitude is None)
    if unresolved:
        raise ContractError(
            f"the Flow that fixes {model.key_of(value)} has an unresolved amount",
            targets=(value,),
        )
    return {
        m.id: Quantity(magnitude=given[key].magnitude, units=flow.units)
        for m, key in zip(movements, wanted, strict=True)
    }


def _coordinate(movement: Movement) -> tuple[date, date] | date | None:
    """Return the Period of a Movement as its bounds, or else its date."""
    if movement.period is not None:
        return (movement.period.start, movement.period.end)
    return movement.date


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
    if not date_target(model, ref):
        target_units(model, ref)
    return (ref,)


def checked_quantity(
    value: object,
    *,
    target: object,
    units: str,
    unit_system: UnitSystem,
) -> Quantity:
    """Return the Quantity that fixes a target, after a check of its units.

    Text is read as a Quantity. A bare number is a ratio, so its target must have
    dimensionless units.
    """
    if isinstance(value, Quantity):
        quantity = value
    elif isinstance(value, str):
        quantity = Quantity(text=value)
    elif isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        quantity = Quantity(magnitude=value, units="ratio")
        if not unit_system.compatible("ratio", units):
            raise UnitError(
                f"a bare number fixes a ratio, but {target} has units {units!r}; "
                f"give a Quantity or text with units, such as '{value} {units}'",
                code=Code.INCOMPATIBLE_UNITS,
            )
    else:
        raise TypeError(
            f"the value of {target} must be a Quantity, Quantity text, a number "
            "or a mapping from Movement UUIDs to these"
        )
    if not unit_system.compatible(quantity.units, units):
        raise UnitError(
            f"incompatible units: {target} has units {units!r}, and the quantity "
            f"that fixes it {quantity.units!r}",
            code=Code.INCOMPATIBLE_UNITS,
        )
    unit_system.convert(quantity=quantity, to=units)
    return quantity

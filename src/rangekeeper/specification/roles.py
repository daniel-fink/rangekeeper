"""The role of each value in a Specification: fixed, free or decided by a rule."""

from enum import StrEnum, unique
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.schema.enums import ExpressionKind, ValueKind
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import (
    Constraint,
    Expression,
    Movement,
    Value,
)
from rangekeeper.schema.records import Specification as SpecificationRecord
from rangekeeper.shared.table import Row, Table

if TYPE_CHECKING:
    from rangekeeper.model import Model


@unique
class Role(StrEnum):
    """The role of a value in a Specification."""

    FIXED = "fixed"
    """The Specification gives the value a Quantity."""
    FREE = "free"
    """The solve finds the value. A value that is not fixed is free."""
    DECIDED = "decided"
    """A rule fixes the value on its decision date."""


ROLE_COLUMNS = ("key", "movement", "role", "quantity")


def equation_targets(
    model: "Model",
    record: SpecificationRecord,
) -> tuple[UUID, ...]:
    """Return the Values and Movements that the equations refer to, in Model order.

    The equations are the Constraints of the Model and of the local Formulations
    of ``record``. A reference to a Flow refers to each of its Movements.
    """
    expressions: dict[UUID, Expression] = {}
    constraints: list[Constraint] = []
    records = list(model._index.records.values())
    for formulation in record.formulations or ():
        records.extend(item for item, _, _ in walk(formulation))
    for item in records:
        if isinstance(item, Expression):
            expressions[item.id] = item
        elif isinstance(item, Constraint):
            constraints.append(item)
    found: dict[UUID, None] = {}
    for constraint in constraints:
        predicate = expressions.get(constraint.predicate)
        if predicate is None:
            continue
        for item, _, _ in walk(predicate):
            if (
                isinstance(item, Expression)
                and item.kind is ExpressionKind.REFERENCE
                and item.target is not None
            ):
                found.setdefault(item.target.target, None)
    targets: list[UUID] = []
    for identity in found:
        value = model._index.records.get(identity)
        if (
            isinstance(value, Value)
            and value.kind is ValueKind.FLOW
            and value.flow is not None
        ):
            targets.extend(movement.id for movement in value.flow.movements)
        else:
            targets.append(identity)
    return in_model_order(model, targets)


def in_model_order(model: "Model", targets) -> tuple:
    """Sort UUIDs, or References, by the position of their target in the Model.

    A target that the Model does not declare keeps its order, after the others.
    """
    position = {identity: index for index, identity in enumerate(model._index.records)}

    def identity(item) -> UUID:
        return item if isinstance(item, UUID) else item.target

    return tuple(
        sorted(targets, key=lambda item: position.get(identity(item), len(position)))
    )


def role_table(
    model: "Model",
    record: SpecificationRecord,
) -> Table:
    """Return one row for each value that has a role in ``record``.

    ``record`` is a composed, concrete Specification of ``model``. The columns are
    ``key``, ``movement`` (the Movement UUID, or None for a scalar Value), ``role``
    (a Role) and ``quantity`` (the fixed Quantity, or None). Each Row's ``id`` is
    the UUID of its target.
    """
    roles: dict[UUID, tuple[Role, object]] = {}
    for assignment in record.assignments or ():
        roles[assignment.target.target] = (Role.FIXED, assignment.quantity)
    for reference in record.unknowns or ():
        roles[reference.target] = (Role.FREE, None)
    if record.rules is not None:
        for reference in record.rules.targets:
            roles[reference.target] = (Role.DECIDED, None)
    keys = _key_counts(model)
    rows = []
    for identity in in_model_order(model, roles):
        role, quantity = roles[identity]
        key, movement = _name(model, identity, keys)
        rows.append(
            Row(
                {
                    "key": key,
                    "movement": movement,
                    "role": role,
                    "quantity": quantity,
                },
                identity,
            )
        )
    return Table(ROLE_COLUMNS, rows)


def target_key(model: "Model", identity: UUID) -> str:
    """Return the key that ``fix`` takes for a Value, or for a Movement's Value."""
    return _name(model, identity, _key_counts(model))[0]


def _key_counts(model: "Model") -> dict[str, int]:
    """Return the number of Values with each key."""
    keys: dict[str, int] = {}
    for item in model._index.records.values():
        if isinstance(item, Value):
            keys[item.key] = keys.get(item.key, 0) + 1
    return keys


def _name(model: "Model", identity: UUID, keys) -> tuple[str, UUID | None]:
    """Return the key that ``fix`` takes for a target, and its Movement UUID."""
    item = model._index.records.get(identity)
    movement = None
    if isinstance(item, Movement):
        movement = item.id
        owner = model.owner_of(item.id)
        item = model._index.records.get(owner) if owner is not None else None
    if not isinstance(item, Value):
        return str(identity), movement
    if keys.get(item.key, 0) == 1:
        return item.key, movement
    owner = model.owner_of(item.id)
    return (f"{model._path(owner)}.{item.key}" if owner else item.key), movement


__all__ = ["Role"]

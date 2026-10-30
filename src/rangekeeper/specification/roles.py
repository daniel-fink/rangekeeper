"""The role of each value in a Specification: fixed, free or decided by a rule."""

from enum import StrEnum, unique
from typing import TYPE_CHECKING
from uuid import UUID

from rangekeeper.duration.dates import NEVER
from rangekeeper.schema.enums import ExpressionKind, ValueKind
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import (
    Assignment,
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
    (a Role) and ``quantity`` (the fixed Quantity, date or NEVER, or None). Each Row's ``id`` is
    the UUID of its target.
    """
    roles: dict[UUID, tuple[Role, object]] = {}
    for assignment in record.assignments or ():
        roles[assignment.target.target] = (Role.FIXED, fixed_content(assignment))
    for reference in record.unknowns or ():
        roles[reference.target] = (Role.FREE, None)
    if record.rules is not None:
        for reference in record.rules.targets:
            roles[reference.target] = (Role.DECIDED, None)
    rows = []
    for identity in in_model_order(model, roles):
        role, quantity = roles[identity]
        target = model._index.records.get(identity)
        movement = identity if isinstance(target, Movement) else None
        rows.append(
            Row(
                {
                    "key": _key(model, identity),
                    "movement": movement,
                    "role": role,
                    "quantity": quantity,
                },
                identity,
            )
        )
    return Table(ROLE_COLUMNS, rows)


def fixed_content(assignment: Assignment) -> object:
    """Return the content of an Assignment: a Quantity, a date or NEVER."""
    if assignment.quantity is not None:
        return assignment.quantity
    return NEVER if assignment.never is not None else assignment.date


def _key(model: "Model", identity: UUID) -> str:
    """Return the key that ``fix`` takes for a target, or its UUID text.

    The key is ``model.key_of``: for a Movement, the key of its Flow Value. A
    target that ``model`` does not declare gives its UUID text.
    """
    try:
        return model.key_of(identity)
    except LookupError:
        return str(identity)


__all__ = ["Role"]

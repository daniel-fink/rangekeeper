"""Small constructors for ordered declarations; none reads or calculates Values."""

from collections.abc import Sequence
from uuid import UUID, uuid4
from .._schema.records import Expression, Quantity, ValueReference


def literal(
    magnitude: float, units: str = "dimensionless", *, id: UUID | None = None
) -> Expression:
    """Declare an explicit numerical constant, including zero, with its units."""
    return Expression(
        id=id or uuid4(),
        kind="quantity",
        quantity=Quantity(magnitude=magnitude, units=units),
    )


def reference(target: ValueReference, *, id: UUID | None = None) -> Expression:
    """Declare a symbol; its recorded magnitude is never read."""
    return Expression(id=id or uuid4(), kind="reference", target=target)


def binary(
    operator, left: Expression, right: Expression, *, id: UUID | None = None
) -> Expression:
    """Declare an ordered binary expression; domain validation checks its operands."""
    return Expression(
        id=id or uuid4(), kind="binary", operator=operator, operands=(left, right)
    )


def add(left: Expression, right: Expression, *, id: UUID | None = None) -> Expression:
    """Declare addition of compatible quantities without conversion or evaluation."""
    return binary("add", left, right, id=id)


def subtract(
    left: Expression, right: Expression, *, id: UUID | None = None
) -> Expression:
    """Declare ordered subtraction of compatible quantities."""
    return binary("subtract", left, right, id=id)


def multiply(
    left: Expression, right: Expression, *, id: UUID | None = None
) -> Expression:
    """Declare multiplication; resulting units retain every operand dimension."""
    return binary("multiply", left, right, id=id)


def divide(
    left: Expression, right: Expression, *, id: UUID | None = None
) -> Expression:
    """Declare division; a zero denominator fails during execution."""
    return binary("divide", left, right, id=id)


def power(left: Expression, right: Expression, *, id: UUID | None = None) -> Expression:
    """Declare a power with a dimensionless exponent."""
    return binary("power", left, right, id=id)


def equal(left: Expression, right: Expression, *, id: UUID | None = None) -> Expression:
    """Declare numerical equality, without choosing assignments or unknowns."""
    return binary("equal", left, right, id=id)


def sum_expressions(expressions: Sequence[Expression]) -> Expression:
    """Declare a left-associated sum in supplied order; reject an empty sequence."""
    if not expressions:
        raise ValueError("sum requires at least one expression")
    result = expressions[0]
    for item in expressions[1:]:
        result = add(result, item)
    return result

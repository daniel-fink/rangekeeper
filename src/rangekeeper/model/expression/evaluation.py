"""Pure arithmetic over expressions and explicitly supplied quantities and dates."""

import math
import operator
from collections.abc import Mapping
from datetime import date
from uuid import UUID

from rangekeeper.duration.dates import NEVER, DateValue, order, shift
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.records import Expression, ExpressionKind, Operator
from rangekeeper.shared.errors import UnsupportedError


def finite_quantity(magnitude: float, units: str) -> Quantity:
    """Reject Boolean, complex and nonfinite numerical results."""
    if type(magnitude) not in (int, float) or not math.isfinite(magnitude):
        raise ValueError("expression evaluation produced a non-finite magnitude")
    return Quantity(magnitude=float(magnitude), units=units)


def evaluate(
    node: Expression,
    values: Mapping[UUID, Quantity],
    *,
    units: UnitSystem,
) -> Quantity:
    """Read only supplied values; never obtain quantities from a Model or resolver."""
    if node.kind is ExpressionKind.QUANTITY:
        if node.quantity is None:
            raise ValueError("quantity expression requires a quantity")
        return node.quantity
    if node.kind is ExpressionKind.REFERENCE:
        if node.target is None:
            raise ValueError("reference expression requires a target")
        return values[node.target.target]
    if node.kind is ExpressionKind.UNARY and node.operator is Operator.NEGATE:
        if node.operand is None:
            raise ValueError("negation requires an operand")
        value = evaluate(node.operand, values, units=units)
        return finite_quantity(-value.number, value.units)
    if node.kind is not ExpressionKind.BINARY or node.operator not in {
        Operator.ADD,
        Operator.SUBTRACT,
        Operator.MULTIPLY,
        Operator.DIVIDE,
        Operator.POWER,
    }:
        raise UnsupportedError(
            f"unsupported numerical expression: {node.kind}/{node.operator}"
        )
    if node.operands is None or len(node.operands) != 2:
        raise ValueError("binary expression requires two operands")
    left, right = (evaluate(child, values, units=units) for child in node.operands)
    a, b = left.number, right.number
    if node.operator in (Operator.ADD, Operator.SUBTRACT):
        b = units.convert(right, to=left.units).number
        return finite_quantity(
            a + b if node.operator is Operator.ADD else a - b, left.units
        )
    if node.operator is Operator.MULTIPLY:
        return finite_quantity(a * b, f"({left.units}) * ({right.units})")
    if node.operator is Operator.DIVIDE:
        return finite_quantity(a / b, f"({left.units}) / ({right.units})")
    b = units.convert(right, to="dimensionless").number
    return finite_quantity(a**b, f"({left.units}) ** {b}")


_ORDERED = {
    Operator.EQUAL: operator.eq,
    Operator.NOT_EQUAL: operator.ne,
    Operator.LESS_THAN: operator.lt,
    Operator.LESS_THAN_OR_EQUAL: operator.le,
    Operator.GREATER_THAN: operator.gt,
    Operator.GREATER_THAN_OR_EQUAL: operator.ge,
}


def evaluate_date(
    node: Expression,
    values: Mapping[UUID, Quantity | DateValue],
    *,
    units: UnitSystem,
) -> DateValue:
    """Evaluate a date Expression: a date or NEVER literal or reference, plus or minus a length.

    Read only supplied values. A length is a whole number of days, weeks,
    months, quarters or years; NEVER plus or minus a length is NEVER.
    """
    if node.kind is ExpressionKind.DATE:
        if node.date is None:
            raise ValueError("date expression requires a date")
        return node.date
    if node.kind is ExpressionKind.NEVER:
        return NEVER
    if node.kind is ExpressionKind.REFERENCE:
        if node.target is None:
            raise ValueError("reference expression requires a target")
        value = values[node.target.target]
        if not (value is NEVER or isinstance(value, date)):
            raise TypeError("a date expression references a date Value")
        return value
    if node.kind is not ExpressionKind.BINARY or node.operator not in (
        Operator.ADD,
        Operator.SUBTRACT,
    ):
        raise UnsupportedError(
            f"unsupported date expression: {node.kind}/{node.operator}"
        )
    if node.operands is None or len(node.operands) != 2:
        raise ValueError("binary expression requires two operands")
    left, right = node.operands
    if node.operator is Operator.ADD and not _is_date(left, values):
        left, right = right, left
    length = evaluate(right, values, units=units)  # type: ignore[arg-type]
    if node.operator is Operator.SUBTRACT:
        length = Quantity(magnitude=-length.number, units=length.units)
    return shift(evaluate_date(left, values, units=units), by=length)


def compare_dates(relation: Operator, left: DateValue, right: DateValue) -> bool:
    """Compare two dates or NEVER; NEVER equals NEVER and is later than every date."""
    if relation not in _ORDERED:
        raise UnsupportedError(f"dates do not support {relation}")
    return bool(_ORDERED[relation](order(left), order(right)))


def _is_date(node: Expression, values: Mapping[UUID, object]) -> bool:
    """Whether an operand gives a date: a date literal or Value, or a shift of one."""
    if node.kind in (ExpressionKind.DATE, ExpressionKind.NEVER):
        return True
    if node.kind is ExpressionKind.REFERENCE and node.target is not None:
        value = values.get(node.target.target)
        return value is NEVER or isinstance(value, date)
    if node.kind is ExpressionKind.BINARY and node.operands is not None:
        return node.operator in (Operator.ADD, Operator.SUBTRACT) and any(
            _is_date(item, values) for item in node.operands
        )
    return False

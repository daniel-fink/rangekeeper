"""Pure numerical arithmetic over expressions and explicitly supplied quantities."""

from collections.abc import Mapping
import math
from uuid import UUID

from ..._schema.records import Expression, ExpressionKind, Operator, Quantity
from ...units import UnitSystem


class UnsupportedExpression(ValueError):
    """The expression is outside the finite numerical arithmetic contract."""


def quantity(magnitude: float, units: str) -> Quantity:
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
        return quantity(-float(value.magnitude), value.units)
    if node.kind is not ExpressionKind.BINARY or node.operator not in {
        Operator.ADD,
        Operator.SUBTRACT,
        Operator.MULTIPLY,
        Operator.DIVIDE,
        Operator.POWER,
    }:
        raise UnsupportedExpression(
            f"unsupported numerical expression: {node.kind}/{node.operator}"
        )
    if node.operands is None or len(node.operands) != 2:
        raise ValueError("binary expression requires two operands")
    left, right = (evaluate(child, values, units=units) for child in node.operands)
    a, b = float(left.magnitude), float(right.magnitude)
    if node.operator in (Operator.ADD, Operator.SUBTRACT):
        b = float(units.convert(right, to=left.units).magnitude)
        return quantity(a + b if node.operator is Operator.ADD else a - b, left.units)
    if node.operator is Operator.MULTIPLY:
        return quantity(a * b, f"({left.units}) * ({right.units})")
    if node.operator is Operator.DIVIDE:
        return quantity(a / b, f"({left.units}) / ({right.units})")
    b = float(units.convert(right, to="dimensionless").magnitude)
    return quantity(a**b, f"({left.units}) ** {b}")

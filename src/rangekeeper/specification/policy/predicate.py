"""Exact policy truth, separate from numerical acceptance and its tolerances."""

import operator

from rangekeeper.schema.records import Expression, ExpressionKind, Operator, Quantity
from rangekeeper.model.expression.evaluation import evaluate as numerical
from rangekeeper.shared.units import UnitSystem


_COMPARISONS = {
    Operator.EQUAL: operator.eq,
    Operator.NOT_EQUAL: operator.ne,
    Operator.LESS_THAN: operator.lt,
    Operator.LESS_THAN_OR_EQUAL: operator.le,
    Operator.GREATER_THAN: operator.gt,
    Operator.GREATER_THAN_OR_EQUAL: operator.ge,
}


def evaluate(node: Expression, quantities, *, units: UnitSystem):
    """Short-circuit Boolean operators and compare converted quantities exactly."""
    if node.kind is ExpressionKind.BOOLEAN:
        if type(node.boolean) is not bool:
            raise ValueError("Boolean literal required")
        return node.boolean
    if node.kind is ExpressionKind.UNARY and node.operator is Operator.LOGICAL_NOT:
        if node.operand is None:
            raise ValueError("logical negation requires an operand")
        value = evaluate(node.operand, quantities, units=units)
        if type(value) is not bool:
            raise ValueError("Boolean operand required")
        return not value
    if node.kind is ExpressionKind.BINARY and node.operator in {
        Operator.LOGICAL_AND,
        Operator.LOGICAL_OR,
        *_COMPARISONS,
    }:
        if node.operands is None or len(node.operands) != 2:
            raise ValueError("binary expression requires two operands")
        left = evaluate(node.operands[0], quantities, units=units)
        if node.operator in (Operator.LOGICAL_AND, Operator.LOGICAL_OR):
            if type(left) is not bool:
                raise ValueError("Boolean operand required")
            if node.operator is Operator.LOGICAL_AND and not left:
                return False
            if node.operator is Operator.LOGICAL_OR and left:
                return True
            right = evaluate(node.operands[1], quantities, units=units)
            if type(right) is not bool:
                raise ValueError("Boolean operand required")
            return right
        right = evaluate(node.operands[1], quantities, units=units)
        if (
            type(left) is bool
            and type(right) is bool
            and node.operator in (Operator.EQUAL, Operator.NOT_EQUAL)
        ):
            return _COMPARISONS[node.operator](left, right)
        if not isinstance(left, Quantity) or not isinstance(right, Quantity):
            raise ValueError("numerical operands required")
        return _COMPARISONS[node.operator](
            float(left.magnitude), float(units.convert(right, to=left.units).magnitude)
        )
    return numerical(node, quantities, units=units)

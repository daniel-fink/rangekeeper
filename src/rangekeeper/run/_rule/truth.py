"""The truth of a rule's condition over its readings: true, false or unknown.

A direct reference to an undecided value is unknown (ADR-021). Logic is Kleene's:
``False and unknown`` is false, ``True or unknown`` is true, and any other
expression that reads an unknown is unknown. Comparison is exact, as in
``run._rule.predicate``; acceptance tolerances play no part. The engine and the
trace check evaluate a condition with this one function, from recorded readings.
"""

import operator
from collections.abc import Callable
from datetime import date
from enum import Enum

from rangekeeper.duration.dates import NEVER, DateValue, shift
from rangekeeper.model.expression.evaluation import compare_dates, finite_quantity
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.records import Expression, ExpressionKind, Operator
from rangekeeper.shared.errors import UnsupportedError


class _Unknown(Enum):
    UNKNOWN = "unknown"


UNKNOWN = _Unknown.UNKNOWN
"""The value of an undecided reference, and of what depends on it."""

Content = Quantity | DateValue | bool | _Unknown
Read = Callable[[Expression], Quantity | DateValue | _Unknown]

_COMPARISONS = {
    Operator.EQUAL: operator.eq,
    Operator.NOT_EQUAL: operator.ne,
    Operator.LESS_THAN: operator.lt,
    Operator.LESS_THAN_OR_EQUAL: operator.le,
    Operator.GREATER_THAN: operator.gt,
    Operator.GREATER_THAN_OR_EQUAL: operator.ge,
}


def truth(condition: Expression, *, read: Read, units: UnitSystem) -> bool | None:
    """Return True, False or None for unknown, from what ``read`` gives each leaf."""
    value = _value(condition, read, units)
    if value is UNKNOWN:
        return None
    if type(value) is not bool:
        raise UnsupportedError("a rule's condition must be a condition, not a value")
    return value


def _value(node: Expression, read: Read, units: UnitSystem) -> Content:
    kind = node.kind
    if kind is ExpressionKind.BOOLEAN:
        return bool(node.boolean)
    if kind is ExpressionKind.QUANTITY:
        assert node.quantity is not None
        return node.quantity
    if kind is ExpressionKind.DATE:
        return NEVER if node.never is not None else _literal_date(node)
    if kind in (ExpressionKind.REFERENCE, ExpressionKind.CALL):
        return read(node)
    if kind is ExpressionKind.UNARY:
        assert node.operand is not None
        return _unary(node.operator, _value(node.operand, read, units))
    if kind is ExpressionKind.BINARY:
        return _binary(node, read, units)
    raise UnsupportedError(f"a rule's condition cannot use {kind}")


def _literal_date(node: Expression) -> date:
    assert node.date is not None
    return node.date


def _unary(relation: Operator | None, value: Content) -> Content:
    if value is UNKNOWN:
        return UNKNOWN
    if relation is Operator.LOGICAL_NOT and type(value) is bool:
        return not value
    if relation is Operator.NEGATE and isinstance(value, Quantity):
        return finite_quantity(-value.number, value.units)
    raise UnsupportedError(f"a rule's condition cannot apply {relation} to {value}")


def _binary(node: Expression, read: Read, units: UnitSystem) -> Content:
    assert node.operands is not None and node.operator is not None
    left, right = (_value(item, read, units) for item in node.operands)
    if node.operator in (Operator.LOGICAL_AND, Operator.LOGICAL_OR):
        return _logic(node.operator, left, right)
    if left is UNKNOWN or right is UNKNOWN:
        return UNKNOWN
    if node.operator in _COMPARISONS:
        return _compare(node.operator, left, right, units=units)
    return _arithmetic(node.operator, left, right, units=units)


def _logic(relation: Operator, left: Content, right: Content) -> Content:
    decisive = relation is Operator.LOGICAL_OR
    for value in (left, right):
        if value is not UNKNOWN and type(value) is not bool:
            raise UnsupportedError("logic in a rule's condition takes conditions")
    if left is decisive or right is decisive:
        return decisive
    if left is UNKNOWN or right is UNKNOWN:
        return UNKNOWN
    return not decisive


def _compare(
    relation: Operator, left: Content, right: Content, *, units: UnitSystem
) -> bool:
    if isinstance(left, Quantity) and isinstance(right, Quantity):
        converted = units.convert(quantity=right, to=left.units)
        return bool(_COMPARISONS[relation](left.number, converted.number))
    if _is_date(left) and _is_date(right):
        assert not isinstance(left, (Quantity, bool, _Unknown))
        assert not isinstance(right, (Quantity, bool, _Unknown))
        return compare_dates(relation, left, right)
    if type(left) is bool and type(right) is bool:
        return bool(_COMPARISONS[relation](left, right))
    raise UnsupportedError(f"a rule's condition cannot compare {left} and {right}")


def _is_date(value: Content) -> bool:
    return value is NEVER or isinstance(value, date)


def _arithmetic(
    relation: Operator, left: Content, right: Content, *, units: UnitSystem
) -> Content:
    if _is_date(left) and isinstance(right, Quantity):
        assert not isinstance(left, (Quantity, bool, _Unknown))
        length = right if relation is Operator.ADD else _negated(right)
        return shift(on=left, by=length)
    if isinstance(left, Quantity) and isinstance(right, Quantity):
        return _numbers(relation, left, right, units=units)
    raise UnsupportedError(f"a rule's condition cannot combine {left} and {right}")


def _negated(length: Quantity) -> Quantity:
    return Quantity(magnitude=-length.number, units=length.units)


def _numbers(
    relation: Operator, left: Quantity, right: Quantity, *, units: UnitSystem
) -> Quantity:
    a, b = left.number, right.number
    if relation in (Operator.ADD, Operator.SUBTRACT):
        c = units.convert(quantity=right, to=left.units).number
        total = a + c if relation is Operator.ADD else a - c
        return finite_quantity(total, left.units)
    if relation is Operator.MULTIPLY:
        return finite_quantity(a * b, f"({left.units}) * ({right.units})")
    if relation is Operator.DIVIDE:
        return finite_quantity(a / b, f"({left.units}) / ({right.units})")
    raise UnsupportedError(f"a rule's condition cannot use {relation}")


__all__ = ["UNKNOWN", "Content", "Read", "truth"]

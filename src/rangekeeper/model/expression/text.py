"""The text form of an Expression, for diagnostics and errors.

The text names each reference with ``name`` and writes equality as ``=``, as an
equation is written: ``noi = coverage * debt_service``. Calls, selections and
queries have a short placeholder; the full text form of every expression is
[#309](https://github.com/daniel-fink/rangekeeper/issues/309).
"""

from collections.abc import Callable

from rangekeeper.schema.enums import ExpressionKind, Operator
from rangekeeper.schema.records import Expression, Reference

# Each binary operator's symbol and precedence; a higher precedence binds tighter.
# The order is Python's, so the logical operators bind tighter than comparisons.
_COMPARISON = 1
_BINARY: dict[Operator, tuple[str, int]] = {
    Operator.EQUAL: ("=", _COMPARISON),
    Operator.NOT_EQUAL: ("!=", _COMPARISON),
    Operator.LESS_THAN: ("<", _COMPARISON),
    Operator.LESS_THAN_OR_EQUAL: ("<=", _COMPARISON),
    Operator.GREATER_THAN: (">", _COMPARISON),
    Operator.GREATER_THAN_OR_EQUAL: (">=", _COMPARISON),
    Operator.LOGICAL_OR: ("|", 2),
    Operator.LOGICAL_AND: ("&", 3),
    Operator.ADD: ("+", 5),
    Operator.SUBTRACT: ("-", 5),
    Operator.MULTIPLY: ("*", 6),
    Operator.DIVIDE: ("/", 6),
    Operator.POWER: ("**", 8),
}
_UNARY: dict[Operator, tuple[str, int]] = {
    Operator.LOGICAL_NOT: ("~", 7),
    Operator.NEGATE: ("-", 7),
}
_ATOM = 9


def render(expression: Expression, *, name: Callable[[Reference], str]) -> str:
    """Return the text of ``expression``, with ``name`` for each reference."""
    return _render(expression, name)[0]


def _render(node: Expression, name: Callable[[Reference], str]) -> tuple[str, int]:
    """Return the text of ``node`` and the precedence of its outer operator."""
    if node.kind is ExpressionKind.QUANTITY and node.quantity is not None:
        quantity = node.quantity
        number = format(quantity.number, "g")
        if quantity.units in ("", "dimensionless"):
            return number, _ATOM
        return f"{number} {quantity.units}", _ATOM
    if node.kind is ExpressionKind.BOOLEAN:
        return ("true" if node.boolean else "false"), _ATOM
    if node.kind is ExpressionKind.REFERENCE and node.target is not None:
        return name(node.target), _ATOM
    if node.kind is ExpressionKind.UNARY and node.operand is not None:
        assert node.operator is not None
        symbol, precedence = _UNARY[node.operator]
        text, inner = _render(node.operand, name)
        return symbol + (text if inner >= precedence else f"({text})"), precedence
    if node.kind is ExpressionKind.BINARY and node.operands is not None:
        assert node.operator is not None
        symbol, precedence = _BINARY[node.operator]
        left, right = (_render(operand, name) for operand in node.operands)
        # Power groups to the right and comparisons do not chain; the other
        # operators group to the left.
        chained = precedence != _COMPARISON
        right_assoc = node.operator is Operator.POWER
        left_text = (
            left[0]
            if left[1] > precedence
            or (left[1] == precedence and chained and not right_assoc)
            else f"({left[0]})"
        )
        right_text = (
            right[0]
            if right[1] > precedence
            or (right[1] == precedence and chained and right_assoc)
            else f"({right[0]})"
        )
        return f"{left_text} {symbol} {right_text}", precedence
    return f"<{node.kind.value}>", _ATOM

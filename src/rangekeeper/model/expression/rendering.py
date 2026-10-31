"""Write Expression records as equation text, with the operator table of the parser.

``render`` writes the fewest brackets that keep the meaning. Calls of equation
functions are written as ``rx.<name>(...)`` and Flow methods as
``x.<name>(...)``, from the function registry. A date literal is written
``date(2027, 1, 1)``, as in Python, and NEVER as ``NEVER``.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from rangekeeper.model.expression import syntax
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import EquationFunction, Form
from rangekeeper.model.expression.syntax import (
    CONDITION_SPELLINGS,
    SPELLINGS,
    Precedence,
    Spelling,
)
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import ExpressionKind, Operator
from rangekeeper.schema.records import Call, Expression, Reference

_Namer = Callable[[Reference], str]


@dataclass(frozen=True, slots=True, kw_only=True)
class _Style:
    """How one text writes a reference and an operator."""

    name: _Namer
    spellings: Mapping[Operator, Spelling]


def render(*, expression: Expression, name: _Namer) -> str:
    """Return the text of ``expression``, with ``name`` for each reference.

    The text has the fewest brackets that keep its meaning. A call of a
    Function that is not an equation function, a selection and a query have
    a placeholder, such as ``<call>``: they have no equation text.
    """
    return _render(expression, _Style(name=name, spellings=SPELLINGS))[0]


def render_condition(*, expression: Expression, name: _Namer) -> str:
    """Return the text of a rule's condition, where ``==`` tests a value."""
    return _render(expression, _Style(name=name, spellings=CONDITION_SPELLINGS))[0]


def _render(node: Expression, style: _Style) -> tuple[str, Precedence]:
    """Return the text of ``node`` and the precedence of its outer operator."""
    writer = _WRITERS.get(node.kind)
    if writer is None:
        return f"<{node.kind.value}>", Precedence.ATOM
    return writer(node, style)


def _write_quantity(node: Expression, style: _Style) -> tuple[str, Precedence]:
    quantity = node.quantity
    assert quantity is not None
    units = quantity.units or "dimensionless"
    # Quantity text reads back to the same magnitude.
    text = str(Quantity(magnitude=quantity.magnitude, units=units))
    return text.removesuffix(" dimensionless"), Precedence.ATOM


def _write_boolean(node: Expression, style: _Style) -> tuple[str, Precedence]:
    return (syntax.TRUE if node.boolean else syntax.FALSE), Precedence.ATOM


def _write_date(node: Expression, style: _Style) -> tuple[str, Precedence]:
    # A date literal records a calendar date or NEVER (#387).
    if node.never is not None:
        return syntax.NEVER, Precedence.ATOM
    assert node.date is not None
    day = node.date
    return f"{syntax.DATE}({day.year}, {day.month}, {day.day})", Precedence.ATOM


def _write_reference(node: Expression, style: _Style) -> tuple[str, Precedence]:
    assert node.target is not None
    return style.name(node.target), Precedence.ATOM


def _write_unary(node: Expression, style: _Style) -> tuple[str, Precedence]:
    assert node.operator is not None and node.operand is not None
    spelling = style.spellings[node.operator]
    text, inner = _render(node.operand, style)
    if inner < spelling.precedence:
        text = f"({text})"
    # A word needs a space before its operand: ``not a``, but ``-a``.
    space = " " if spelling.symbol.isalpha() else ""
    return f"{spelling.symbol}{space}{text}", spelling.precedence


def _write_binary(node: Expression, style: _Style) -> tuple[str, Precedence]:
    assert node.operator is not None and node.operands is not None
    spelling = style.spellings[node.operator]
    precedence = spelling.precedence
    (left, left_inner), (right, right_inner) = (
        _render(operand, style) for operand in node.operands
    )
    # ``**`` groups to the right and comparisons do not chain; the other
    # operators group to the left.
    grouped = precedence is not Precedence.COMPARISON
    right_first = node.operator is Operator.POWER
    if left_inner < precedence or (
        left_inner == precedence and not (grouped and not right_first)
    ):
        left = f"({left})"
    if right_inner < precedence or (
        right_inner == precedence and not (grouped and right_first)
    ):
        right = f"({right})"
    return f"{left} {spelling.symbol} {right}", precedence


def _write_call(node: Expression, style: _Style) -> tuple[str, Precedence]:
    assert node.call is not None
    function = functions.get(node.call.function)
    if function is None:
        return "<call>", Precedence.ATOM
    positional, named = _arguments(node.call, function, style)
    if function.form is Form.METHOD:
        subject, inner = _render((node.call.arguments or ())[0], style)
        if inner < Precedence.ATOM:
            subject = f"({subject})"
        return f"{subject}.{function.name}({', '.join(named)})", Precedence.ATOM
    listed = ", ".join((*positional, *named))
    return f"{function.code}({listed})", Precedence.ATOM


def _arguments(
    call: Call, function: EquationFunction, style: _Style
) -> tuple[list[str], list[str]]:
    """Return the text of the positional and the named arguments of a call.

    A method's subject is its first positional argument; the method form
    writes it before the name, so it is not in the list.
    """
    skip = 1 if function.form is Form.METHOD else 0
    positional = [_render(item, style)[0] for item in (call.arguments or ())[skip:]]
    named = [
        f"{item.name}={_render(item.expression, style)[0]}"
        for item in call.named_arguments or ()
    ]
    return positional, named


_Writer = Callable[[Expression, _Style], tuple[str, Precedence]]
_WRITERS: dict[ExpressionKind, _Writer] = {
    ExpressionKind.QUANTITY: _write_quantity,
    ExpressionKind.BOOLEAN: _write_boolean,
    ExpressionKind.DATE: _write_date,
    ExpressionKind.REFERENCE: _write_reference,
    ExpressionKind.UNARY: _write_unary,
    ExpressionKind.BINARY: _write_binary,
    ExpressionKind.CALL: _write_call,
}


__all__ = ["render", "render_condition"]

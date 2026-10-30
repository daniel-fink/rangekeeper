"""Write Expression records as equation text, with the operator table of the parser.

``render`` writes the fewest brackets that keep the meaning. Calls of equation
functions are written as ``rx.<name>(...)`` and Flow methods as
``x.<name>(...)``, from the function registry. NEVER is written ``NEVER``; a
date literal has no text form yet and is written ``<date 2027-01-01>``.
"""

from collections.abc import Callable

from rangekeeper.model.expression import syntax
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import EquationFunction, Form
from rangekeeper.model.expression.syntax import SPELLINGS, Precedence
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import ExpressionKind, Operator
from rangekeeper.schema.records import Call, Expression, Reference

_Namer = Callable[[Reference], str]


def render(*, expression: Expression, name: _Namer) -> str:
    """Return the text of ``expression``, with ``name`` for each reference.

    The text has the fewest brackets that keep its meaning. A call of a
    Function that is not an equation function, a selection and a query have
    a placeholder, such as ``<call>``: they have no equation text.
    """
    return _render(expression, name)[0]


def _render(node: Expression, name: _Namer) -> tuple[str, Precedence]:
    """Return the text of ``node`` and the precedence of its outer operator."""
    writer = _WRITERS.get(node.kind)
    if writer is None:
        return f"<{node.kind.value}>", Precedence.ATOM
    return writer(node, name)


def _write_quantity(node: Expression, name: _Namer) -> tuple[str, Precedence]:
    quantity = node.quantity
    assert quantity is not None
    units = quantity.units or "dimensionless"
    # Quantity text reads back to the same magnitude.
    text = str(Quantity(magnitude=quantity.magnitude, units=units))
    return text.removesuffix(" dimensionless"), Precedence.ATOM


def _write_boolean(node: Expression, name: _Namer) -> tuple[str, Precedence]:
    return (syntax.TRUE if node.boolean else syntax.FALSE), Precedence.ATOM


def _write_date(node: Expression, name: _Namer) -> tuple[str, Precedence]:
    # A date literal records a calendar date or NEVER (#387).
    if node.never is not None:
        return syntax.NEVER, Precedence.ATOM
    assert node.date is not None
    return f"<date {node.date.isoformat()}>", Precedence.ATOM


def _write_reference(node: Expression, name: _Namer) -> tuple[str, Precedence]:
    assert node.target is not None
    return name(node.target), Precedence.ATOM


def _write_unary(node: Expression, name: _Namer) -> tuple[str, Precedence]:
    assert node.operator is not None and node.operand is not None
    spelling = SPELLINGS[node.operator]
    text, inner = _render(node.operand, name)
    if inner < spelling.precedence:
        text = f"({text})"
    # A word needs a space before its operand: ``not a``, but ``-a``.
    space = " " if spelling.symbol.isalpha() else ""
    return f"{spelling.symbol}{space}{text}", spelling.precedence


def _write_binary(node: Expression, name: _Namer) -> tuple[str, Precedence]:
    assert node.operator is not None and node.operands is not None
    spelling = SPELLINGS[node.operator]
    precedence = spelling.precedence
    (left, left_inner), (right, right_inner) = (
        _render(operand, name) for operand in node.operands
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


def _write_call(node: Expression, name: _Namer) -> tuple[str, Precedence]:
    assert node.call is not None
    function = functions.get(node.call.function)
    if function is None:
        return "<call>", Precedence.ATOM
    positional, named = _arguments(node.call, function, name)
    if function.form is Form.METHOD:
        subject, inner = _render((node.call.arguments or ())[0], name)
        if inner < Precedence.ATOM:
            subject = f"({subject})"
        return f"{subject}.{function.name}({', '.join(named)})", Precedence.ATOM
    listed = ", ".join((*positional, *named))
    return f"{function.code}({listed})", Precedence.ATOM


def _arguments(
    call: Call, function: EquationFunction, name: _Namer
) -> tuple[list[str], list[str]]:
    """Return the text of the positional and the named arguments of a call.

    A method's subject is its first positional argument; the method form
    writes it before the name, so it is not in the list.
    """
    skip = 1 if function.form is Form.METHOD else 0
    positional = [_render(item, name)[0] for item in (call.arguments or ())[skip:]]
    named = [
        f"{item.name}={_render(item.expression, name)[0]}"
        for item in call.named_arguments or ()
    ]
    return positional, named


_Writer = Callable[[Expression, _Namer], tuple[str, Precedence]]
_WRITERS: dict[ExpressionKind, _Writer] = {
    ExpressionKind.QUANTITY: _write_quantity,
    ExpressionKind.BOOLEAN: _write_boolean,
    ExpressionKind.DATE: _write_date,
    ExpressionKind.REFERENCE: _write_reference,
    ExpressionKind.UNARY: _write_unary,
    ExpressionKind.BINARY: _write_binary,
    ExpressionKind.CALL: _write_call,
}


__all__ = ["render"]

"""The text form of an equation: ``parse`` reads it and ``render`` writes it.

Equation text is the Python form of an equation inside a string, with ``=`` for
equality, ``and``, ``or`` and ``not`` for the logical operators, and quantity
literals without quotes: ``noi = coverage * debt_service``. ``parse`` makes the
same Expression records as the record constructors, and ``render`` writes
records as text with the same operator table, so text that ``parse`` reads
reads back to the same records.

Names are value keys of one entity, or ``code.key`` for a value of another
entity. Functions and Flow methods (``rx.max(a, b)``, ``x.at(on=...)``) parse,
but no equation function is available yet: the catalogue is
[#278](https://github.com/daniel-fink/rangekeeper/issues/278), from the registry
of [#309](https://github.com/daniel-fink/rangekeeper/issues/309).
"""

from collections.abc import Callable
from typing import Protocol
from uuid import UUID, uuid4

from rangekeeper.duration.dates import NEVER
from rangekeeper.model.expression import syntax
from rangekeeper.model.expression.syntax import (
    SPELLINGS,
    Binary,
    Call,
    Constant,
    Literal,
    Member,
    Name,
    Node,
    Precedence,
    Unary,
)
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.enums import ExpressionKind, Operator
from rangekeeper.schema.records import Expression, Reference
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    EquationError,
    MissingReferenceError,
    UnitError,
)

# The namespace of equation functions, and the namespace that computes on values.
FUNCTIONS = "rx"
VALUES = "rk"
# Words that equation text reserves; a value key cannot be one of them.
RESERVED = frozenset({FUNCTIONS, VALUES, syntax.NEVER})


class Names(Protocol):
    """What the names in equation text refer to, and the units of its literals."""

    @property
    def units(self) -> UnitSystem:
        """The unit system that reads quantity literals."""
        ...

    def value(self, path: tuple[str, ...]) -> UUID:
        """Return the UUID of the Value that a key, or a code and a key, names.

        One part is a key of the entity whose equation it is. Two parts are the
        code of another entity and one of its keys. A path that names no Value
        raises MissingReferenceError, and one that names several raises
        AmbiguousReferenceError; both give the nearest ``candidates``.
        """
        ...


def parse(text: str, *, names: Names) -> Expression:
    """Return the Expression records of equation text, with a new UUID for each node.

    Each name becomes a reference to the Value that ``names`` gives, and each
    literal a Quantity that ``names.units`` reads, as ``Quantity(text=...)``
    does. Text that does not parse, an unknown name, invalid units and a call
    raise EquationError with a code and the position of the part that fails.
    """
    return _Reader(text, names).build(syntax.parse(text))


def render(expression: Expression, *, name: Callable[[Reference], str]) -> str:
    """Return the text of ``expression``, with ``name`` for each reference.

    The text has the fewest brackets that keep its meaning. Calls, selections
    and queries have a placeholder, such as ``<call>``, and date literals are
    ``<date 2027-01-01>``: they have no equation text yet.
    """
    return _render(expression, name)[0]


class _Reader:
    """Make the Expression records of the syntax tree of one equation text."""

    __slots__ = ("_text", "_names")

    def __init__(self, text: str, names: Names) -> None:
        self._text = text
        self._names = names

    def build(self, node: Node) -> Expression:
        """Return the records of ``node`` and its operands; raise EquationError."""
        match node:
            case Literal():
                return self._literal(node)
            case Constant():
                return _constant(node.word)
            case Name() | Member():
                return self._reference(node)
            case Call():
                raise self._call(node)
            case Unary():
                return _unary(node.operator, self.build(node.operand))
            case Binary():
                left, right = self.build(node.left), self.build(node.right)
                return _binary(node.operator, left, right)
        raise TypeError(f"unknown syntax node {node!r}")

    def _literal(self, node: Literal) -> Expression:
        units = node.units or "dimensionless"
        try:
            quantity = self._names.units.parse_quantity(f"{node.number} {units}")
        except UnitError as error:
            raise self._error(
                str(error),
                code=Code.UNITS,
                node=node,
                start=node.units_start,
                suggestions=error.suggestions,
            ) from error
        return Expression(id=uuid4(), kind=ExpressionKind.QUANTITY, quantity=quantity)

    def _reference(self, node: Name | Member) -> Expression:
        parts = syntax.path(node)
        if parts is None or len(parts) > 2:
            raise self._error(
                f"{self._source(node)!r} is not a value; values have no members "
                "in equation text",
                code=Code.EQUATION_FUNCTION,
                node=node,
            )
        if parts[0] in (FUNCTIONS, VALUES):
            raise self._function(node, parts)
        try:
            target = self._names.value(parts)
        except (MissingReferenceError, AmbiguousReferenceError) as error:
            raise self._error(
                str(error), code=error.code, node=node, suggestions=error.candidates
            ) from error
        return Expression(
            id=uuid4(),
            kind=ExpressionKind.REFERENCE,
            target=Reference(target=target),
        )

    def _call(self, node: Call) -> EquationError:
        """Return the error for a call: no equation function is available yet."""
        callee = node.callee
        parts = syntax.path(callee)
        if parts is not None and parts[0] in (FUNCTIONS, VALUES):
            return self._function(callee, parts)
        if isinstance(callee, Member):
            # Report a missing value before the method that it does not have.
            self.build(callee.base)
            return self._error(
                f"equation text has no method {callee.name!r}",
                code=Code.EQUATION_FUNCTION,
                node=callee,
            )
        if isinstance(callee, Name):
            return self._error(
                f"{callee.name!r} is not an equation function; equation functions "
                f"are named {FUNCTIONS}.<name>",
                code=Code.EQUATION_FUNCTION,
                node=callee,
                suggestions=(f"{FUNCTIONS}.{callee.name}",),
            )
        return self._error(
            "equation text calls only functions and methods",
            code=Code.EQUATION_FUNCTION,
            node=callee,
        )

    def _function(self, node: Node, parts: tuple[str, ...]) -> EquationError:
        """Return the error for a name in ``rx`` or ``rk``."""
        name = ".".join(parts[1:])
        if parts[0] == VALUES:
            message = (
                f"{VALUES!r} computes on values now; an equation writes {FUNCTIONS}."
            )
            suggestions = (f"{FUNCTIONS}.{name}",) if name else ()
        elif name:
            message = f"{'.'.join(parts)!r} is not an equation function"
            suggestions = ()
        else:
            message = f"{FUNCTIONS!r} is reserved for the names of equation functions"
            suggestions = ()
        return self._error(
            message, code=Code.EQUATION_FUNCTION, node=node, suggestions=suggestions
        )

    def _source(self, node: Node) -> str:
        return self._text[node.start : node.end]

    def _error(
        self,
        message: str,
        *,
        code: Code,
        node: Node,
        start: int | None = None,
        suggestions: tuple[str, ...] = (),
    ) -> EquationError:
        return EquationError(
            message,
            code=code,
            text=self._text,
            start=node.start if start is None else start,
            end=node.end,
            suggestions=suggestions,
        )


def _constant(word: str) -> Expression:
    if word == syntax.NEVER:
        return Expression(id=uuid4(), kind=ExpressionKind.DATE, never=NEVER)
    return Expression(
        id=uuid4(), kind=ExpressionKind.BOOLEAN, boolean=word == syntax.TRUE
    )


def _unary(operator: Operator, operand: Expression) -> Expression:
    return Expression(
        id=uuid4(), kind=ExpressionKind.UNARY, operator=operator, operand=operand
    )


def _binary(operator: Operator, left: Expression, right: Expression) -> Expression:
    return Expression(
        id=uuid4(),
        kind=ExpressionKind.BINARY,
        operator=operator,
        operands=(left, right),
    )


# Writing records as text.

_Namer = Callable[[Reference], str]


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


_Writer = Callable[[Expression, _Namer], tuple[str, Precedence]]
_WRITERS: dict[ExpressionKind, _Writer] = {
    ExpressionKind.QUANTITY: _write_quantity,
    ExpressionKind.BOOLEAN: _write_boolean,
    ExpressionKind.DATE: _write_date,
    ExpressionKind.REFERENCE: _write_reference,
    ExpressionKind.UNARY: _write_unary,
    ExpressionKind.BINARY: _write_binary,
}


__all__ = ["RESERVED", "Names", "parse", "render"]

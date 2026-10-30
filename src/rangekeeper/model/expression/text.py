"""The text form of an equation: ``parse`` reads it and ``render`` writes it.

Equation text is the Python form of an equation inside a string, with ``=`` for
equality, ``and``, ``or`` and ``not`` for the logical operators, and quantity
literals without quotes: ``noi = coverage * debt_service``. ``parse`` builds
the records with the functions that the Python form (``rx``) uses, so text and
``rx`` make the same records. ``render`` writes records as text with the same
operator table, so text that ``parse`` reads reads back to the same records.

Names are value keys of one entity, or ``code.key`` for a value of another
entity. Functions are called as ``rx.<name>(...)`` and Flow methods as
``x.<name>(...)``, from the equation-function registry
(``rangekeeper.model.expression.catalogue``).
"""

from typing import Protocol

from rangekeeper.duration import NEVER, Never
from rangekeeper.model.expression import syntax, terms
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import PREFIX, EquationFunction
from rangekeeper.model.expression.rendering import render
from rangekeeper.model.expression.syntax import (
    Binary,
    Call,
    Constant,
    Literal,
    Member,
    Name,
    Node,
    Unary,
)
from rangekeeper.model.expression.terms import Symbol, Term
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.enums import ParameterKind
from rangekeeper.schema.records import Expression
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import (
    AmbiguousReferenceError,
    ContractError,
    EquationError,
    MissingReferenceError,
    UnitError,
)

# The namespace of equation functions, and the namespace that computes on values.
FUNCTIONS = PREFIX
VALUES = "rk"
# Words that equation text reserves; a value key cannot be one of them.
RESERVED = frozenset({FUNCTIONS, VALUES, syntax.NEVER})


class Names(Protocol):
    """What the names in equation text refer to, and the units of its literals."""

    @property
    def units(self) -> UnitSystem:
        """The unit system that reads quantity literals."""
        ...

    def value(self, path: tuple[str, ...]) -> Symbol:
        """Return the Value that a key, or a code and a key, names.

        One part is a key of the entity whose equation it is. Two parts are the
        code of another entity and one of its keys. A path that names no Value
        raises MissingReferenceError, and one that names several raises
        AmbiguousReferenceError; both give the nearest ``candidates``.
        """
        ...


def parse(*, text: str, names: Names) -> Expression:
    """Return the Expression records of equation text, with a new UUID for each node.

    Each name becomes a reference to the Value that ``names`` gives, and each
    literal a Quantity that ``names.units`` reads, as ``Quantity(text=...)``
    does. Each call is bound to its equation function and checked. Text that
    does not parse, an unknown name, invalid units and a call that is not
    valid raise EquationError with a code and the position of the part that
    fails.
    """
    return read(text=text, names=names).to_expression()


def read(*, text: str, names: Names) -> Term:
    """Return the Term of equation text: its records, and their kind and units.

    It raises as ``parse`` does.
    """
    return _Reader(text, names).build(syntax.parse(text))


class _Reader:
    """Build the Term of the syntax tree of one equation text."""

    __slots__ = ("_text", "_names")

    def __init__(self, text: str, names: Names) -> None:
        self._text = text
        self._names = names

    def build(self, node: Node) -> Term:
        """Return the Term of ``node`` and its operands; raise EquationError."""
        match node:
            case Literal():
                return self._literal(node)
            case Constant():
                return terms.constant(_CONSTANTS[node.word])
            case Name() | Member():
                return self._reference(node)
            case Call():
                return self._call(node)
            case Unary():
                return terms.unary(node.operator, self.build(node.operand))
            case Binary():
                left, right = self.build(node.left), self.build(node.right)
                return terms.binary(node.operator, left, right)
        raise TypeError(f"unknown syntax node {node!r}")

    def _literal(self, node: Literal) -> Term:
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
        return terms.quantity(quantity)

    def _reference(self, node: Name | Member) -> Term:
        parts = syntax.path(node)
        if parts is None or len(parts) > 2:
            raise self._error(
                f"{self._source(node)!r} is not a value; values have no members "
                "in equation text",
                code=Code.EQUATION_FUNCTION,
                node=node,
            )
        if parts[0] in (FUNCTIONS, VALUES):
            raise self._namespace(node, parts)
        try:
            symbol = self._names.value(parts)
        except (MissingReferenceError, AmbiguousReferenceError) as error:
            raise self._error(
                str(error), code=error.code, node=node, suggestions=error.candidates
            ) from error
        return terms.reference(symbol, name=".".join(parts))

    def _call(self, node: Call) -> Term:
        """Return the Term of a call of an equation function or a Flow method."""
        function, subject = self._callee(node.callee)
        given = [] if subject is None else [subject]
        given.extend(item.value for item in node.arguments if item.name is None)
        positional = [self.build(item) for item in given]
        named = {
            item.name: self.build(item.value)
            for item in node.arguments
            if item.name is not None
        }
        try:
            return terms.apply(function, positional=positional, named=named)
        except ContractError as error:
            located = _located(function, node, given)
            name = (error.values or {}).get("argument")
            raise self._error(
                str(error),
                code=error.code or Code.EQUATION_FUNCTION,
                node=located.get(name, node) if isinstance(name, str) else node,
                suggestions=_suggestions(error),
            ) from error

    def _callee(self, callee: Node) -> tuple[EquationFunction, Node | None]:
        """Return the function that ``callee`` names, and the subject of a method."""
        parts = syntax.path(callee)
        if parts is not None and parts[0] in (FUNCTIONS, VALUES):
            if parts[0] == VALUES or len(parts) == 1:
                raise self._namespace(callee, parts)
            return self._lookup(callee, name=".".join(parts[1:]), method=False), None
        if isinstance(callee, Member):
            # Report a missing value before the method that it does not have.
            self.build(callee.base)
            return self._lookup(callee, name=callee.name, method=True), callee.base
        if isinstance(callee, Name):
            raise self._error(
                f"{callee.name!r} is not an equation function; equation functions "
                f"are named {FUNCTIONS}.<name>",
                code=Code.EQUATION_FUNCTION,
                node=callee,
                suggestions=(f"{FUNCTIONS}.{callee.name}",),
            )
        raise self._error(
            "equation text calls only functions and methods",
            code=Code.EQUATION_FUNCTION,
            node=callee,
        )

    def _lookup(self, node: Node, *, name: str, method: bool) -> EquationFunction:
        try:
            if method:
                return functions.method(name=name)
            return functions.function(name=name)
        except ContractError as error:
            raise self._error(
                str(error),
                code=Code.EQUATION_FUNCTION,
                node=node,
                suggestions=_suggestions(error),
            ) from error

    def _namespace(self, node: Node, parts: tuple[str, ...]) -> EquationError:
        """Return the error for ``rk.`` or a bare ``rx``."""
        name = ".".join(parts[1:])
        if parts[0] == VALUES:
            message = (
                f"{VALUES!r} computes on values now; an equation writes {FUNCTIONS}."
            )
            suggestions: tuple[str, ...] = (f"{FUNCTIONS}.{name}",) if name else ()
        else:
            message = (
                f"{'.'.join(parts)!r} is a function; call it"
                if name
                else f"{FUNCTIONS!r} is reserved for the names of equation functions"
            )
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


_CONSTANTS: dict[str, bool | Never] = {
    syntax.TRUE: True,
    syntax.FALSE: False,
    syntax.NEVER: NEVER,
}


def _located(
    function: EquationFunction, node: Call, given: list[Node]
) -> dict[str, Node]:
    """Return the syntax node of each argument of a call, by parameter name."""
    positional = (
        p for p in function.parameters if p.call is ParameterKind.POSITIONAL_OR_NAMED
    )
    located: dict[str, Node] = {
        parameter.name: item for parameter, item in zip(positional, given, strict=False)
    }
    # A named argument is the one that a duplicate binding reports.
    located.update(
        (item.name, item) for item in node.arguments if item.name is not None
    )
    return located


def _suggestions(error: ContractError) -> tuple[str, ...]:
    found = (error.values or {}).get("suggestions") or ()
    return tuple(str(item) for item in found)


__all__ = ["RESERVED", "Names", "parse", "read", "render"]

"""The units of equations: what each part of an equation gives, and where units disagree.

``Analysis`` reads the units of the Values that an equation references and works
out the units of each part of the equation, as Quantity arithmetic does: a sum
keeps the units of its operands, a product multiplies them, and a date plus a
length is a date. It records each sum, difference and comparison whose operands
have incompatible units. Model validation reports them as ``incompatible_units``
(ADR-016), and a ModelDraft uses the same analysis to work out the units of the
values that it does not declare (D44).

A part that the analysis cannot read, such as a call of an equation function, a
selection or a query, has unknown units; it is not checked, and it gives no
units to a value.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import Enum
from uuid import UUID

from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import Availability, EquationFunction
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.enums import DomainKind, ExpressionKind, Operator, ValueKind
from rangekeeper.schema.records import Call, Expression, Function, Value


class Kind(Enum):
    """What an expression gives."""

    QUANTITY = "quantity"
    DATE = "date"
    BOOLEAN = "boolean"


@dataclass(frozen=True, slots=True)
class Dimension:
    """What an expression gives: a quantity in units, a date or a Boolean.

    ``flow`` is True when the expression references a whole Flow Value, so that
    it gives an amount for each Period.
    """

    kind: Kind
    units: str | None = None
    flow: bool = False


DATE = Dimension(kind=Kind.DATE)
BOOLEAN = Dimension(kind=Kind.BOOLEAN)


@dataclass(frozen=True, slots=True)
class Mismatch:
    """An operation of an equation whose two operands have incompatible units."""

    operation: Expression
    units: tuple[str, str]


# The Dimension of the Value or Movement that a reference targets, or None.
Lookup = Callable[[UUID], Dimension | None]

_ADDITIVE = frozenset({Operator.ADD, Operator.SUBTRACT})
_COMPARISONS = frozenset(
    {
        Operator.EQUAL,
        Operator.NOT_EQUAL,
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
    }
)
_LOGICAL = frozenset({Operator.LOGICAL_AND, Operator.LOGICAL_OR})
# What a call gives, by the result kind of its equation function.
_RESULTS = {DomainKind.DATE: Kind.DATE, DomainKind.BOOLEAN: Kind.BOOLEAN}


class Analysis:
    """Work out the Dimension of expressions, and record each mismatch of units."""

    __slots__ = ("_units", "_lookup", "_functions", "_compatible", "mismatches")

    def __init__(
        self,
        *,
        units: UnitSystem,
        lookup: Lookup,
        functions: Mapping[UUID, Function] | None = None,
    ) -> None:
        self._units = units
        self._lookup = lookup
        self._functions = functions or {}
        # Whether two units texts are compatible, by the pair, read once.
        self._compatible: dict[tuple[str, str], bool] = {}
        self.mismatches: list[Mismatch] = []

    def dimension(self, node: Expression) -> Dimension | None:
        """Return what ``node`` gives, or None when its units are unknown."""
        visit = _VISITS.get(node.kind)
        return None if visit is None else visit(self, node)

    def _literal(self, node: Expression) -> Dimension | None:
        assert node.quantity is not None
        units = node.quantity.units or "dimensionless"
        return Dimension(kind=Kind.QUANTITY, units=units)

    def _reference(self, node: Expression) -> Dimension | None:
        assert node.target is not None
        return self._lookup(node.target.target)

    def _call(self, node: Expression) -> Dimension | None:
        """Return the result of a call from its Function record's result units."""
        call = node.call
        function = None if call is None else self._functions.get(call.function)
        result = None if function is None else function.result
        if result is None or result.units is None:
            return None
        return Dimension(kind=Kind.QUANTITY, units=result.units)

    def _unary(self, node: Expression) -> Dimension | None:
        assert node.operand is not None
        operand = self.dimension(node.operand)
        if node.operator is Operator.LOGICAL_NOT:
            return BOOLEAN
        return operand

    def _binary(self, node: Expression) -> Dimension | None:
        assert node.operands is not None and node.operator is not None
        left, right = (self.dimension(item) for item in node.operands)
        if node.operator in _LOGICAL:
            return BOOLEAN
        if node.operator in _COMPARISONS:
            self._check(node, left, right)
            return BOOLEAN
        if node.operator in _ADDITIVE:
            return self._sum(node, left, right)
        if left is None or right is None:
            return None
        return self._product(node.operator, left, right)

    def _sum(
        self,
        node: Expression,
        left: Dimension | None,
        right: Dimension | None,
    ) -> Dimension | None:
        """Return a sum or difference: the known units, or a date plus a length."""
        if DATE.kind in (_kind(left), _kind(right)):
            return DATE
        self._check(node, left, right)
        known = left if left is not None else right
        if known is None:
            return None
        return replace(known, flow=_flow(left) or _flow(right))

    def _product(
        self,
        operator: Operator,
        left: Dimension,
        right: Dimension,
    ) -> Dimension | None:
        """Return a product or a quotient of quantities, or a power of a ratio."""
        if left.units is None or right.units is None:
            return None
        flow = left.flow or right.flow
        if operator is Operator.MULTIPLY:
            units = self._units.multiply(left.units, right.units)
        elif operator is Operator.DIVIDE:
            units = self._units.divide(left.units, right.units)
        elif self.compatible(left.units, "dimensionless"):
            units = "dimensionless"
        else:
            # A power of a quantity with units depends on the exponent's value.
            return None
        return Dimension(kind=Kind.QUANTITY, units=units, flow=flow)

    def _check(
        self,
        node: Expression,
        left: Dimension | None,
        right: Dimension | None,
    ) -> None:
        """Record a mismatch when two quantities have incompatible units."""
        if left is None or right is None or left.units is None or right.units is None:
            return
        if not self.compatible(left.units, right.units):
            self.mismatches.append(Mismatch(node, (left.units, right.units)))

    def compatible(self, left: str, right: str) -> bool:
        """Return whether two units texts have the same dimensions."""
        pair = (left, right)
        found = self._compatible.get(pair)
        if found is None:
            found = self._compatible[pair] = self._units.compatible(left, right)
        return found


class Inference(Analysis):
    """The analysis of a draft, which also reads the units of equation functions.

    A call of an equation function has the units that its registry entry gives
    (#309): ``result_units``, or the units of the argument that ``units_from``
    names, as ``EquationFunction.units`` gives them; a growth profile of an
    amount per year gives the units of each Period's amount (#500). Model
    validation does not check these units yet, so a draft infers
    them only for the values that it does not declare.
    """

    __slots__ = ()

    def _call(self, node: Expression) -> Dimension | None:
        call = node.call
        entry = None if call is None else functions.get(call.function)
        if call is None or entry is None:
            return super()._call(node)
        return self._equation_function(entry, call)

    def _equation_function(
        self,
        entry: EquationFunction,
        call: Call,
    ) -> Dimension | None:
        """Return the result of an equation function from the units of its arguments.

        It is a Flow when the entry gives a Flow, or when a periodwise function
        takes a Flow.
        """
        names = [parameter.name for parameter in entry.parameters]
        given = [
            *zip(names, call.arguments or (), strict=False),
            *((item.name, item.expression) for item in call.named_arguments or ()),
        ]
        arguments = {name: self.dimension(item) for name, item in given}
        kind = _RESULTS.get(entry.result, Kind.QUANTITY)
        if kind is not Kind.QUANTITY:
            return Dimension(kind=kind)
        units = entry.units(
            arguments={
                name: None if item is None else item.units
                for name, item in arguments.items()
            }
        )
        if units is None:
            return None
        periodwise = entry.availability is Availability.PERIODWISE
        flow = entry.result is DomainKind.FLOW or (
            periodwise and any(_flow(item) for item in arguments.values())
        )
        return Dimension(kind=Kind.QUANTITY, units=units, flow=flow)


def of_value(value: Value, *, units: str | None) -> Dimension | None:
    """Return the Dimension of a Value with these Measure units, or None.

    A date Value gives a date; a measurement gives a quantity, and a Flow a
    quantity in each Period. A property Value, or a Value with no units, gives
    None.
    """
    if value.kind is ValueKind.DATE:
        return DATE
    if units is None or value.kind not in (ValueKind.MEASUREMENT, ValueKind.FLOW):
        return None
    return Dimension(kind=Kind.QUANTITY, units=units, flow=value.kind is ValueKind.FLOW)


def _kind(dimension: Dimension | None) -> Kind | None:
    return None if dimension is None else dimension.kind


def _flow(dimension: Dimension | None) -> bool:
    return dimension is not None and dimension.flow


_Visit = Callable[[Analysis, Expression], Dimension | None]
_VISITS: dict[ExpressionKind, _Visit] = {
    ExpressionKind.QUANTITY: Analysis._literal,
    ExpressionKind.DATE: lambda analysis, node: DATE,
    ExpressionKind.BOOLEAN: lambda analysis, node: BOOLEAN,
    ExpressionKind.REFERENCE: Analysis._reference,
    # A call of the method, so that an Inference reads equation functions.
    ExpressionKind.CALL: lambda analysis, node: analysis._call(node),
    ExpressionKind.UNARY: Analysis._unary,
    ExpressionKind.BINARY: Analysis._binary,
}

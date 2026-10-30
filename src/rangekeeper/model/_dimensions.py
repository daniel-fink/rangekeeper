"""The units of equations: what each part of an equation gives, and where units disagree.

``Analysis`` reads the units of the Values that an equation references and works
out the units of each part of the equation, as Quantity arithmetic does: a sum
keeps the units of its operands, a product multiplies them, and a date plus a
length is a date. It records each sum, difference and comparison whose operands
have incompatible units. Model validation reports them as ``incompatible_units``
(ADR-016), and a ModelDraft uses the same analysis to work out the units of the
values that it does not declare (D44).

A call of an equation function has the units that its registry entry gives. A
part that the analysis cannot read, such as a selection or a query, has unknown
units; it is not checked, and it gives no units to a value.
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from enum import Enum
from uuid import UUID

from rangekeeper.duration import Period
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import EquationFunction
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
    it gives an amount for each Period; ``periods`` are those Periods, when the
    declarations give them.
    """

    kind: Kind
    units: str | None = None
    flow: bool = False
    periods: tuple[Period, ...] | None = None


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
        """Return the result of a call: from its equation function, or its record.

        A call of an equation function has the units that its registry entry
        gives (#309): ``result_units``, or the units of the argument that
        ``units_from`` names, as ``EquationFunction.units`` gives them; a
        growth profile of an amount per year gives the units of each Period's
        amount (#500). Another call has its Function record's result units.
        """
        call = node.call
        if call is None:
            return None
        entry = functions.get(call.function)
        if entry is not None:
            return self._equation_function(entry, call)
        function = self._functions.get(call.function)
        result = None if function is None else function.result
        if result is None or result.units is None:
            return None
        return Dimension(kind=Kind.QUANTITY, units=result.units)

    def _equation_function(
        self,
        entry: EquationFunction,
        call: Call,
    ) -> Dimension | None:
        """Return the result of an equation function from the units of its arguments.

        It is a Flow when the entry gives a Flow, or when one of its periodwise
        parameters takes a Flow. A Flow has the Periods of the argument that
        ``periods_from`` names, or of its periodwise Flows; a Flow made from
        amounts has the Periods of the Flow that it defines, which are not
        known here.
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
        shaping = [
            arguments.get(name)
            for name in entry.periodwise
            if name in given_names(given)
        ]
        lifted = [item for item in shaping if _flow(item)]
        if not lifted and any(item is None for item in shaping):
            # An unknown argument could be a Flow, so the shape is unknown.
            return None
        if entry.result is not DomainKind.FLOW and not lifted:
            # A scalar result, such as total() or max() of a Flow.
            return Dimension(kind=Kind.QUANTITY, units=units)
        if entry.periods_from is not None:
            lifted = [arguments.get(entry.periods_from)]
        _, periods = _shape(*lifted)
        return Dimension(kind=Kind.QUANTITY, units=units, flow=True, periods=periods)

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
        """Return a sum or difference, or a date plus a length.

        Its operands have the same units, so one known operand gives them. A
        known Flow gives the shape too; a known scalar beside an unknown
        operand does not, because that operand could be a Flow.
        """
        if DATE.kind in (_kind(left), _kind(right)):
            return DATE
        self._check(node, left, right)
        return _shaped(left, right)

    def _product(
        self,
        operator: Operator,
        left: Dimension,
        right: Dimension,
    ) -> Dimension | None:
        """Return a product or a quotient of quantities, or a power of a ratio."""
        if left.units is None or right.units is None:
            return None
        flow, periods = _shape(left, right)
        if operator is Operator.MULTIPLY:
            units = self._units.multiply(left.units, right.units)
        elif operator is Operator.DIVIDE:
            units = self._units.divide(left.units, right.units)
        elif self.compatible(left.units, "dimensionless"):
            units = "dimensionless"
        else:
            # A power of a quantity with units depends on the exponent's value.
            return None
        return Dimension(kind=Kind.QUANTITY, units=units, flow=flow, periods=periods)

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
    if value.kind is ValueKind.MEASUREMENT:
        return Dimension(kind=Kind.QUANTITY, units=units)
    movements = () if value.flow is None else value.flow.movements
    periods = tuple(item.period for item in movements if item.period is not None)
    return Dimension(
        kind=Kind.QUANTITY,
        units=units,
        flow=True,
        periods=periods if periods and len(periods) == len(movements) else None,
    )


def _kind(dimension: Dimension | None) -> Kind | None:
    return None if dimension is None else dimension.kind


def _shaped(*operands: Dimension | None) -> Dimension | None:
    """Return what operands with the same units give, when their shape is known.

    The first known operand gives the units. A known Flow gives the shape; with
    no known Flow, every operand must be known.
    """
    known = [item for item in operands if item is not None]
    flows = [item for item in known if item.flow]
    if not known or (not flows and len(known) < len(operands)):
        return None
    flow, periods = _shape(*known)
    return replace(known[0], flow=flow, periods=periods)


def given_names(given: Sequence[tuple[str, Expression]]) -> set[str]:
    """Return the names of the parameters that a call gives."""
    return {name for name, _ in given}


def _flow(dimension: Dimension | None) -> bool:
    return dimension is not None and dimension.flow


def _shape(*operands: Dimension | None) -> tuple[bool, tuple[Period, ...] | None]:
    """Return whether operands give a Flow, and the first Periods that they give."""
    flows = [item for item in operands if item is not None and item.flow]
    periods = next((item.periods for item in flows if item.periods), None)
    return bool(flows), periods


_Visit = Callable[[Analysis, Expression], Dimension | None]
_VISITS: dict[ExpressionKind, _Visit] = {
    ExpressionKind.QUANTITY: Analysis._literal,
    ExpressionKind.DATE: lambda analysis, node: DATE,
    ExpressionKind.BOOLEAN: lambda analysis, node: BOOLEAN,
    ExpressionKind.REFERENCE: Analysis._reference,
    ExpressionKind.CALL: Analysis._call,
    ExpressionKind.UNARY: Analysis._unary,
    ExpressionKind.BINARY: Analysis._binary,
}

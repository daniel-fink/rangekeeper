"""Flow-valued equations as one scalar equation for each period.

An equation between Flows applies period by period (D32, G18). ``per_period``
writes it as one equation for each period, over the Movements of its Flows:
the rows that a solve takes, as the passive Flow builders write them. A
reference to a Flow becomes a reference to its Movement of that period, and
a value applies to every period. A periodwise function, such as ``rx.max``,
becomes one call for each period, so the solve sees each period's ``max``
and picks its active side (#308). The running Flow methods ``cumulative()``
and ``diff()``, and ``total()``, ``first()`` and ``last()``, become sums and
differences of the Movements.

The other calls (``rx.profile``, ``rx.flow.event``, ``rx.finance`` and the
methods that read dates) need values that the solve finds or fixes first;
lowering them is the staged solve (#276), and ``per_period`` raises
UnsupportedError for them.
"""

from collections.abc import Callable, Mapping, Sequence
from uuid import UUID, uuid4

from rangekeeper.model.expression.authoring import add_all, subtract
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import EquationFunction, Form
from rangekeeper.schema.enums import ExpressionKind
from rangekeeper.schema.records import Argument, Call, Expression, Reference
from rangekeeper.schema.runtime import UNSET
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, UnsupportedError


def per_period(
    *,
    expression: Expression,
    flows: Mapping[UUID, Sequence[UUID]],
) -> tuple[Expression, ...]:
    """Return one scalar equation for each period of a Flow-valued equation.

    ``flows`` gives the Movement UUIDs of each Flow Value, in period order;
    every Flow that the equation names has the same number of Movements. An
    equation that names no Flow is returned as it is. Each node of the
    result has a new UUID. Flows with other numbers of Movements raise
    ContractError with ``ALIGNMENT_DIFFER``; a call that this lowering does
    not write raises UnsupportedError.
    """
    counts = {len(flows[target]) for target in _targets(expression) if target in flows}
    if not counts:
        return (expression,)
    if len(counts) > 1:
        raise ContractError(
            "the Flows of an equation must have the same Periods",
            code=Code.ALIGNMENT_DIFFER,
            values={"movements": sorted(counts)},
        )
    (count,) = counts
    lowering = _Lowering(flows, count)
    return tuple(lowering.at(expression, period) for period in range(count))


class _Lowering:
    """Write the nodes of one Flow-valued equation for one period at a time."""

    __slots__ = ("_flows", "_count")

    def __init__(self, flows: Mapping[UUID, Sequence[UUID]], count: int) -> None:
        self._flows = flows
        self._count = count

    def at(self, node: Expression, period: int) -> Expression:
        """Return ``node`` in ``period``, with a new UUID for each node."""
        if node.kind is ExpressionKind.REFERENCE:
            return self._reference(node, period)
        if node.kind is ExpressionKind.UNARY:
            assert node.operand is not None
            return node.replace(id=uuid4(), operand=self.at(node.operand, period))
        if node.kind is ExpressionKind.BINARY:
            assert node.operands is not None
            return node.replace(
                id=uuid4(),
                operands=tuple(self.at(item, period) for item in node.operands),
            )
        if node.kind is ExpressionKind.CALL:
            return self._call(node, period)
        return node.replace(id=uuid4())

    def _reference(self, node: Expression, period: int) -> Expression:
        assert node.target is not None
        movements = self._flows.get(node.target.target)
        target = (
            node.target if movements is None else Reference(target=movements[period])
        )
        return node.replace(id=uuid4(), target=target)

    def _call(self, node: Expression, period: int) -> Expression:
        assert node.call is not None
        function = functions.get(node.call.function)
        if function is not None and function.periodwise:
            return self._periodwise(node, period)
        method = _METHODS.get(function.name) if function is not None else None
        if function is None or function.form is not Form.METHOD or method is None:
            raise UnsupportedError(
                f"{_spelled(function)} in a Flow-valued equation needs the "
                "staged solve (#276)",
                targets=(node.call.function,),
            )
        subject = (node.call.arguments or ())[0]
        return method(lambda index: self.at(subject, index), period, self._count)

    def _periodwise(self, node: Expression, period: int) -> Expression:
        """Return one call of a periodwise function for one period."""
        call = node.call
        assert call is not None
        return node.replace(
            id=uuid4(),
            call=Call(
                function=call.function,
                arguments=tuple(self.at(item, period) for item in call.arguments or ())
                or UNSET,
                named_arguments=tuple(
                    Argument(
                        name=item.name, expression=self.at(item.expression, period)
                    )
                    for item in call.named_arguments or ()
                )
                or UNSET,
            ),
        )


# The Flow methods that become sums and differences of Movements: each
# takes the subject in a period, the period and the number of periods.
_Subject = Callable[[int], Expression]


def _cumulative(subject: _Subject, period: int, count: int) -> Expression:
    return add_all([subject(index) for index in range(period + 1)])


def _diff(subject: _Subject, period: int, count: int) -> Expression:
    if period == 0:
        return subject(0)
    return subtract(subject(period), subject(period - 1))


def _total(subject: _Subject, period: int, count: int) -> Expression:
    return add_all([subject(index) for index in range(count)])


def _first(subject: _Subject, period: int, count: int) -> Expression:
    return subject(0)


def _last(subject: _Subject, period: int, count: int) -> Expression:
    return subject(count - 1)


_METHODS: Mapping[str, Callable[[_Subject, int, int], Expression]] = {
    "cumulative": _cumulative,
    "diff": _diff,
    "total": _total,
    "first": _first,
    "last": _last,
}


def _spelled(function: EquationFunction | None) -> str:
    if function is None:
        return "a call of a Function that is not an equation function"
    return function.spelling


def _targets(node: Expression) -> set[UUID]:
    """Return the UUID of each Value or Movement that ``node`` references."""
    found: set[UUID] = set()

    def visit(data: object) -> None:
        if isinstance(data, dict):
            if data.get("kind") == "reference" and isinstance(data.get("target"), dict):
                found.add(UUID(data["target"]["target"]))
            for child in data.values():
                visit(child)
        elif isinstance(data, list):
            for child in data:
                visit(child)

    visit(node.to_data())
    return found


__all__ = ["per_period"]

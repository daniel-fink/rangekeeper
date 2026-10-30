"""Piecewise equations: ``max`` and ``min`` of values that the solve finds (#308).

A call of the ``rx.max`` Function is the largest of its operands, and a call
of the ``rx.min`` Function the smallest. One operand of each call is its
**active side**: when each call takes the operand of its side, an equation
with these calls is affine. This module reads and applies sides; it solves
nothing:

- ``Pieces.of(model)`` finds the ``rx.max`` and ``rx.min`` Functions that a
  Model declares, by their codes;
- ``Pieces.active`` reads the active side of each call at given values;
- ``Pieces.reduce`` writes an expression with each call replaced by the
  operand of its side.

``open_calls``, ``sides``, ``chosen``, ``bounds`` and ``disagreeing`` apply
them to the assertions of a Binding. The staged solve
(``execution.staging``) picks the sides, solves the affine problem and checks
the sides at its solution. Verification evaluates the original equations
with the active side at the candidate's values, so it does not depend on the
sides that the solve picked.
"""

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from types import MappingProxyType
from uuid import UUID, uuid4

from rangekeeper.execution.preparation import Assertion, Binding
from rangekeeper.model import Model
from rangekeeper.model.expression.evaluation import evaluate
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import Expression, ExpressionKind, Operator
from rangekeeper.schema.runtime import UNSET
from rangekeeper.shared.errors import UnsupportedError

Sides = Mapping[UUID, int]
"""The active side of each call: the call Expression's UUID, and the index of its operand."""

# A side holds within this tolerance of another operand: an absolute floor in
# the units of the call's first operand, and a share of the larger magnitude.
# The backend's feasibility tolerance is 1e-7 on rows scaled to a largest
# coefficient of one, so a near tie keeps its side.
TIE_ABSOLUTE = 1e-6
TIE_RELATIVE = 1e-9


@dataclass(frozen=True)
class Kind:
    """What one piecewise Function selects.

    ``sign`` is 1 for the largest operand and -1 for the smallest. ``bound``
    is the relation of the side to each other operand.
    """

    sign: float
    bound: Operator

    def pick(self, numbers: Sequence[float]) -> int:
        """Return the index of the selected number; the first of equal ones."""
        return max(range(len(numbers)), key=lambda index: self.sign * numbers[index])

    def holds(self, numbers: Sequence[float], side: int) -> bool:
        """Return whether ``side`` is selected within the tie tolerance."""
        selected = numbers[side]
        return all(
            self.sign * (selected - number) + _tie(selected, number) >= 0
            for number in numbers
        )


def _tie(left: float, right: float) -> float:
    return TIE_ABSOLUTE + TIE_RELATIVE * max(abs(left), abs(right))


# The piecewise Functions, by the code of their Function record: the codes of
# the equation-function catalogue (#309, #278).
KINDS: Mapping[str, Kind] = MappingProxyType(
    {
        "rx.max": Kind(sign=1.0, bound=Operator.GREATER_THAN_OR_EQUAL),
        "rx.min": Kind(sign=-1.0, bound=Operator.LESS_THAN_OR_EQUAL),
    }
)


@dataclass(frozen=True)
class Pieces:
    """The piecewise Functions of one Model, by Function UUID."""

    kinds: Mapping[UUID, Kind]

    @classmethod
    def of(cls, model: Model) -> "Pieces":
        """Return the ``rx.max`` and ``rx.min`` Functions that ``model`` declares."""
        functions = (model.definitions.functions if model.definitions else None) or ()
        return cls(
            MappingProxyType(
                {
                    function.id: KINDS[function.code]
                    for function in functions
                    if function.code in KINDS
                }
            )
        )

    def kind(self, node: Expression) -> Kind | None:
        """Return the Kind of a call of a piecewise Function, else None.

        The call has at least two positional operands and no named arguments.
        """
        call = node.call if node.kind is ExpressionKind.CALL else None
        if call is None or call.named_arguments or len(call.arguments or ()) < 2:
            return None
        return self.kinds.get(call.function)

    def calls(self, node: Expression) -> tuple[Expression, ...]:
        """Return the piecewise calls in ``node``, each after the calls inside it."""
        found = [
            child
            for child, _, _ in walk(node)
            if isinstance(child, Expression) and self.kind(child) is not None
        ]
        return tuple(reversed(found))

    def reduce(self, node: Expression, sides: Sides) -> Expression:
        """Return ``node`` with each call that ``sides`` names replaced by its side.

        The result keeps the nodes that it does not replace, with their
        UUIDs; a node without such a call is returned unchanged.
        """
        operands = _operands(node) if self.kind(node) is not None else ()
        if node.id in sides and operands:
            return self.reduce(operands[sides[node.id]], sides)
        return _rebuilt(node, lambda child: self.reduce(child, sides))

    def active(
        self,
        node: Expression,
        *,
        values: Mapping[UUID, Quantity],
        units: UnitSystem,
        prefer: Sides = MappingProxyType({}),
    ) -> dict[UUID, int]:
        """Return the active side of each call in ``node`` at ``values``.

        A side in ``prefer`` stays when it holds within the tie tolerance, so
        that a near tie does not change sides. A reference without a value
        raises UnsupportedError.
        """
        found: dict[UUID, int] = {}
        for call in self.calls(node):
            kind = self.kind(call)
            assert kind is not None
            numbers = self._numbers(call, sides=found, values=values, units=units)
            preferred = prefer.get(call.id)
            if preferred is not None and kind.holds(numbers, preferred):
                found[call.id] = preferred
            else:
                found[call.id] = kind.pick(numbers)
        return found

    def _numbers(
        self,
        call: Expression,
        *,
        sides: Sides,
        values: Mapping[UUID, Quantity],
        units: UnitSystem,
    ) -> list[float]:
        """Return the number of each operand of ``call``, in its first operand's units."""
        try:
            operands = [
                evaluate(self.reduce(operand, sides), values, units=units)
                for operand in _operands(call)
            ]
        except KeyError as error:
            raise UnsupportedError(
                "expression reference has no explicit solve role"
            ) from error
        first = operands[0]
        numbers = [first.number]
        numbers.extend(
            units.convert(quantity=operand, to=first.units).number
            for operand in operands[1:]
        )
        if not all(math.isfinite(number) for number in numbers):
            raise UnsupportedError("an operand of max or min is not finite")
        return numbers


def open_calls(binding: Binding, *, pieces: Pieces) -> tuple[Expression, ...]:
    """Return the piecewise calls of ``binding`` that read an unknown.

    A call whose references are all fixed is a constant, which the compiler
    evaluates; it needs no side.
    """
    unknowns = set(binding.unknowns)
    return tuple(
        call
        for item in binding.assertions
        for call in pieces.calls(item.predicate)
        if _references(call) & unknowns
    )


def opened(binding: Binding, *, pieces: Pieces) -> tuple[bool, ...]:
    """Return, for each assertion of ``binding``, whether a call in it reads an unknown."""
    unknowns = set(binding.unknowns)
    return tuple(
        any(_references(call) & unknowns for call in pieces.calls(item.predicate))
        for item in binding.assertions
    )


def sides(
    binding: Binding,
    *,
    pieces: Pieces,
    values: Mapping[UUID, Quantity],
    prefer: Sides = MappingProxyType({}),
) -> dict[UUID, int]:
    """Return the active side of each piecewise call of ``binding`` at ``values``."""
    found: dict[UUID, int] = {}
    for item in binding.assertions:
        found.update(
            pieces.active(
                item.predicate, values=values, units=binding.units, prefer=prefer
            )
        )
    return found


def varying(
    binding: Binding,
    *,
    pieces: Pieces,
    sides: Sides,
    values: Mapping[UUID, Quantity],
) -> dict[UUID, int]:
    """Return ``sides`` with each side that reads no unknown moved to one that does.

    A call whose side reads no unknown, while another of its operands reads
    one, takes the active side at ``values`` among those operands. A side
    that reads no unknown removes the unknowns from its equation, which can
    make the affine problem infeasible.
    """
    unknowns = set(binding.unknowns)
    found = dict(sides)
    for item in binding.assertions:
        for call in pieces.calls(item.predicate):
            kind = pieces.kind(call)
            reading = [
                index
                for index, operand in enumerate(_operands(call))
                if _references(pieces.reduce(operand, found)) & unknowns
            ]
            if kind is None or call.id not in found or not reading:
                continue
            if found[call.id] in reading:
                continue
            numbers = pieces._numbers(
                call, sides=found, values=values, units=binding.units
            )
            found[call.id] = max(reading, key=lambda index: kind.sign * numbers[index])
    return found


def chosen(binding: Binding, *, pieces: Pieces, sides: Sides) -> Binding:
    """Return ``binding`` with each call that ``sides`` names replaced by its side."""
    return replace(
        binding,
        assertions=tuple(
            replace(item, predicate=pieces.reduce(item.predicate, sides))
            for item in binding.assertions
        ),
    )


def bounds(binding: Binding, *, pieces: Pieces, sides: Sides) -> tuple[Assertion, ...]:
    """Return the bounds that keep each side active: one for each other operand.

    The side of a ``max`` call is at least each other operand, and the side of
    a ``min`` call at most. Each bound keeps the Constraint of its call.
    """
    found: list[Assertion] = []
    for item in binding.assertions:
        for call in pieces.calls(item.predicate):
            kind = pieces.kind(call)
            if kind is None or call.id not in sides:
                continue
            operands = [pieces.reduce(x, sides) for x in _operands(call)]
            side = operands[sides[call.id]]
            found.extend(
                replace(item, predicate=_compare(kind.bound, side, other))
                for index, other in enumerate(operands)
                if index != sides[call.id]
            )
    return tuple(found)


def disagreeing(
    binding: Binding,
    *,
    pieces: Pieces,
    sides: Sides,
    values: Mapping[UUID, Quantity],
) -> tuple[Assertion, ...]:
    """Return the assertions with a call whose side does not hold at ``values``."""
    found = []
    for item in binding.assertions:
        active = pieces.active(
            item.predicate, values=values, units=binding.units, prefer=sides
        )
        if any(sides.get(id, side) != side for id, side in active.items()):
            found.append(item)
    return tuple(found)


def _operands(call: Expression) -> tuple[Expression, ...]:
    return () if call.call is None else call.call.arguments or ()


def _compare(relation: Operator, left: Expression, right: Expression) -> Expression:
    return Expression(
        id=uuid4(),
        kind=ExpressionKind.BINARY,
        operator=relation,
        operands=(left, right),
    )


def _references(node: Expression) -> set[UUID]:
    return {
        child.target.target
        for child, _, _ in walk(node)
        if isinstance(child, Expression)
        and child.kind is ExpressionKind.REFERENCE
        and child.target is not None
    }


_Change = Callable[[Expression], Expression]


def _rebuilt(node: Expression, change: _Change) -> Expression:
    """Return ``node`` with ``change`` applied to each Expression directly in it.

    A node whose children do not change is returned unchanged.
    """
    rebuild = _REBUILDS.get(node.kind)
    return node if rebuild is None else rebuild(node, change)


def _rebuilt_binary(node: Expression, change: _Change) -> Expression:
    operands = node.operands or ()
    changed = tuple(change(item) for item in operands)
    return node if _same(changed, operands) else node.replace(operands=changed)


def _rebuilt_unary(node: Expression, change: _Change) -> Expression:
    if node.operand is None:
        return node
    changed = change(node.operand)
    return node if changed is node.operand else node.replace(operand=changed)


def _rebuilt_call(node: Expression, change: _Change) -> Expression:
    call = node.call
    if call is None:
        return node
    arguments = call.arguments or ()
    named = call.named_arguments or ()
    changed = tuple(change(item) for item in arguments)
    expressions = tuple(change(item.expression) for item in named)
    unchanged_named = _same(expressions, tuple(item.expression for item in named))
    if _same(changed, arguments) and unchanged_named:
        return node
    return node.replace(
        call=call.replace(
            arguments=UNSET if _same(changed, arguments) else changed,
            named_arguments=UNSET
            if unchanged_named
            else tuple(
                item.replace(expression=expression)
                for item, expression in zip(named, expressions, strict=True)
            ),
        )
    )


def _same(left: Sequence[Expression], right: Sequence[Expression]) -> bool:
    return all(a is b for a, b in zip(left, right, strict=True))


_REBUILDS: Mapping[ExpressionKind, Callable[[Expression, _Change], Expression]] = (
    MappingProxyType(
        {
            ExpressionKind.BINARY: _rebuilt_binary,
            ExpressionKind.UNARY: _rebuilt_unary,
            ExpressionKind.CALL: _rebuilt_call,
        }
    )
)


__all__ = [
    "KINDS",
    "Kind",
    "Pieces",
    "Sides",
    "bounds",
    "chosen",
    "disagreeing",
    "open_calls",
    "opened",
    "sides",
    "varying",
]

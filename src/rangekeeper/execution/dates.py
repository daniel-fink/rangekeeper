"""Date equations in a solve: the dates that fixed dates determine (#280).

A date Value has the role fixed or free, as a number has. Dates are not
numbers, so no affine row holds them. ``settle`` works before the affine
stages:

1. A date equation ``x = e``, where ``x`` is a free date and every reference
   of ``e`` is a fixed or determined date, determines ``x``:
   ``a_start = shared_start + 1 year``. This repeats until no equation
   determines another date.
2. Each assertion that reads only dates is then decided exactly, as
   verification decides it: a true one needs no row, and a false one is
   ``False``, so the backend proves the problem infeasible (ADR-016, #153).
3. The other assertions stay. A free date that an assertion still reads
   raises UnsupportedError: no date equation determines it.

Verification checks every date equation again on the candidate's dates.
"""

from collections.abc import Mapping
from dataclasses import replace
from types import MappingProxyType
from uuid import UUID, uuid4

from rangekeeper.duration.dates import DateValue
from rangekeeper.execution.errors import UnsupportedError
from rangekeeper.execution.preparation import Assertion, Binding
from rangekeeper.model.expression.evaluation import compare_dates, evaluate_date
from rangekeeper.quantity import UnitSystem
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import Expression, ExpressionKind, Operator
from rangekeeper.shared.errors import ContractError

# The comparisons that dates support.
_ORDERED = frozenset(
    {
        Operator.EQUAL,
        Operator.NOT_EQUAL,
        Operator.LESS_THAN,
        Operator.LESS_THAN_OR_EQUAL,
        Operator.GREATER_THAN,
        Operator.GREATER_THAN_OR_EQUAL,
    }
)


def settle(binding: Binding) -> Binding:
    """Return ``binding`` with the dates that its date equations determine.

    The determined dates join ``dates`` and leave ``date_unknowns``. The
    assertions that read only dates are decided: a true one is removed, and
    a false one is replaced by ``False``. Raise UnsupportedError when an
    assertion reads a free date that no date equation determines.
    """
    if not binding.date_unknowns:
        if not any(_reads_dates(item, binding) for item in binding.assertions):
            return binding
    dates = _determined(binding)
    free = set(binding.date_unknowns) - dates.keys()
    settled = replace(
        binding,
        dates=MappingProxyType(dates),
        date_unknowns=tuple(id for id in binding.date_unknowns if id in free),
    )
    kept: list[Assertion] = []
    for item in binding.assertions:
        read = _references(item.predicate)
        if read & free:
            keys = [binding.key(binding.references[id]) for id in read & free]
            raise UnsupportedError(
                "no date equation of fixed dates determines the free dates "
                + ", ".join(sorted(keys)),
                document_id=item.document,
                targets=(item.constraint.id,),
                equation=binding.text(item.predicate),
            )
        if read and read <= dates.keys():
            if not decide(item.predicate, dates=dates, units=binding.units):
                kept.append(replace(item, predicate=_false()))
            continue
        kept.append(item)
    return replace(settled, assertions=tuple(kept))


def decide(
    node: Expression, *, dates: Mapping[UUID, DateValue], units: UnitSystem
) -> bool:
    """Return whether a predicate over dates holds, exactly.

    It takes date comparisons, ``and``, ``or``, ``not`` and Boolean literals.
    """
    if node.kind is ExpressionKind.BOOLEAN:
        return bool(node.boolean)
    if node.kind is ExpressionKind.UNARY and node.operator is Operator.LOGICAL_NOT:
        assert node.operand is not None
        return not decide(node.operand, dates=dates, units=units)
    operands = node.operands or ()
    if node.kind is ExpressionKind.BINARY and node.operator in (
        Operator.LOGICAL_AND,
        Operator.LOGICAL_OR,
    ):
        found = [decide(item, dates=dates, units=units) for item in operands]
        return all(found) if node.operator is Operator.LOGICAL_AND else any(found)
    if node.kind is not ExpressionKind.BINARY or node.operator not in _ORDERED:
        raise UnsupportedError(
            f"unsupported date predicate: {node.kind}/{node.operator}"
        )
    left, right = (_date(item, dates=dates, units=units) for item in operands)
    return compare_dates(node.operator, left, right)


def _determined(binding: Binding) -> dict[UUID, DateValue]:
    """Return the fixed dates and each date that a date equation determines."""
    dates = dict(binding.dates)
    free = set(binding.date_unknowns)
    changed = True
    while changed:
        changed = False
        for item in binding.assertions:
            found = _solved(item.predicate, dates=dates, free=free, units=binding.units)
            if found is not None:
                dates[found[0]] = found[1]
                free.discard(found[0])
                changed = True
    return dates


def _solved(
    node: Expression,
    *,
    dates: Mapping[UUID, DateValue],
    free: set[UUID],
    units: UnitSystem,
) -> tuple[UUID, DateValue] | None:
    """Return the free date and its value that an equation ``x = e`` determines."""
    if node.kind is not ExpressionKind.BINARY or node.operator is not Operator.EQUAL:
        return None
    left, right = node.operands or (None, None)
    assert left is not None and right is not None
    for unknown, other in ((left, right), (right, left)):
        if (
            unknown.kind is ExpressionKind.REFERENCE
            and unknown.target is not None
            and unknown.target.target in free
            and _references(other) <= dates.keys()
        ):
            return unknown.target.target, _date(other, dates=dates, units=units)
    return None


def _date(
    node: Expression, *, dates: Mapping[UUID, DateValue], units: UnitSystem
) -> DateValue:
    try:
        return evaluate_date(node, dates, units=units)
    except ContractError as error:
        raise UnsupportedError(str(error)) from error


def _reads_dates(item: Assertion, binding: Binding) -> bool:
    return bool(_references(item.predicate) & binding.dates.keys())


def _references(node: Expression) -> set[UUID]:
    return {
        child.target.target
        for child, _, _ in walk(node)
        if isinstance(child, Expression)
        and child.kind is ExpressionKind.REFERENCE
        and child.target is not None
    }


def _false() -> Expression:
    return Expression(id=uuid4(), kind=ExpressionKind.BOOLEAN, boolean=False)


__all__ = ["decide", "settle"]

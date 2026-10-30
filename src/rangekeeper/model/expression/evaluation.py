"""Pure arithmetic over expressions and explicitly supplied quantities and dates.

``evaluate`` and ``evaluate_date`` evaluate scalar and date expressions;
``evaluate_fixed`` evaluates any expression of equation text on fixed content,
Flows and calls included, with the value function of each equation function.
"""

import math
import operator
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import cast
from uuid import UUID

from rangekeeper.duration import Period
from rangekeeper.duration.dates import NEVER, DateValue, order, shift
from rangekeeper.model.expression.catalogue import functions, periodwise
from rangekeeper.model.expression.functions import Content
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.schema.records import Expression, ExpressionKind, Operator
from rangekeeper.shared.errors import ContractError, NumericalError, UnsupportedError


def finite_quantity(magnitude: float, units: str) -> Quantity:
    """Reject Boolean, complex and nonfinite numerical results."""
    if type(magnitude) not in (int, float) or not math.isfinite(magnitude):
        raise NumericalError("expression evaluation produced a non-finite magnitude")
    return Quantity(magnitude=float(magnitude), units=units)


def evaluate(
    node: Expression,
    values: Mapping[UUID, Quantity],
    *,
    units: UnitSystem,
) -> Quantity:
    """Read only supplied values; never obtain quantities from a Model or resolver."""
    if node.kind is ExpressionKind.QUANTITY:
        if node.quantity is None:
            raise _malformed(node, "quantity expression requires a quantity")
        return node.quantity
    if node.kind is ExpressionKind.REFERENCE:
        if node.target is None:
            raise _malformed(node, "reference expression requires a target")
        return values[node.target.target]
    if node.kind is ExpressionKind.UNARY and node.operator is Operator.NEGATE:
        if node.operand is None:
            raise _malformed(node, "negation requires an operand")
        value = evaluate(node.operand, values, units=units)
        return finite_quantity(-value.number, value.units)
    if node.kind is not ExpressionKind.BINARY or node.operator not in {
        Operator.ADD,
        Operator.SUBTRACT,
        Operator.MULTIPLY,
        Operator.DIVIDE,
        Operator.POWER,
    }:
        raise UnsupportedError(
            f"unsupported numerical expression: {node.kind}/{node.operator}"
        )
    if node.operands is None or len(node.operands) != 2:
        raise _malformed(node, "binary expression requires two operands")
    left, right = (evaluate(child, values, units=units) for child in node.operands)
    a, b = left.number, right.number
    if node.operator in (Operator.ADD, Operator.SUBTRACT):
        b = units.convert(quantity=right, to=left.units).number
        return finite_quantity(
            a + b if node.operator is Operator.ADD else a - b, left.units
        )
    if node.operator is Operator.MULTIPLY:
        return finite_quantity(a * b, f"({left.units}) * ({right.units})")
    if node.operator is Operator.DIVIDE:
        return finite_quantity(a / b, f"({left.units}) / ({right.units})")
    b = units.convert(quantity=right, to="dimensionless").number
    return finite_quantity(a**b, f"({left.units}) ** {b}")


_ORDERED = {
    Operator.EQUAL: operator.eq,
    Operator.NOT_EQUAL: operator.ne,
    Operator.LESS_THAN: operator.lt,
    Operator.LESS_THAN_OR_EQUAL: operator.le,
    Operator.GREATER_THAN: operator.gt,
    Operator.GREATER_THAN_OR_EQUAL: operator.ge,
}


def evaluate_date(
    node: Expression,
    values: Mapping[UUID, Quantity | DateValue],
    *,
    units: UnitSystem,
) -> DateValue:
    """Evaluate a date Expression: a date or NEVER literal or reference, plus or minus a length.

    Read only supplied values. A length is a whole number of days, weeks,
    months, quarters or years; NEVER plus or minus a length is NEVER.
    """
    if node.kind is ExpressionKind.DATE:
        if node.never is not None:
            return NEVER
        if node.date is None:
            raise _malformed(node, "date expression requires a date or NEVER")
        return node.date
    if node.kind is ExpressionKind.REFERENCE:
        if node.target is None:
            raise _malformed(node, "reference expression requires a target")
        value = values[node.target.target]
        if not (value is NEVER or isinstance(value, date)):
            raise ContractError(
                "a date expression references a date Value",
                targets=(node.target.target,),
            )
        return value
    if node.kind is not ExpressionKind.BINARY or node.operator not in (
        Operator.ADD,
        Operator.SUBTRACT,
    ):
        raise UnsupportedError(
            f"unsupported date expression: {node.kind}/{node.operator}"
        )
    if node.operands is None or len(node.operands) != 2:
        raise _malformed(node, "binary expression requires two operands")
    left, right = node.operands
    if node.operator is Operator.ADD and not _is_date(left, values):
        left, right = right, left
    length = evaluate(right, values, units=units)  # type: ignore[arg-type]
    if node.operator is Operator.SUBTRACT:
        length = Quantity(magnitude=-length.number, units=length.units)
    return shift(on=evaluate_date(left, values, units=units), by=length)


def compare_dates(relation: Operator, left: DateValue, right: DateValue) -> bool:
    """Compare two dates or NEVER; NEVER equals NEVER and is later than every date."""
    if relation not in _ORDERED:
        raise UnsupportedError(f"dates do not support {relation}")
    return bool(_ORDERED[relation](order(left), order(right)))


def _is_date(node: Expression, values: Mapping[UUID, object]) -> bool:
    """Whether an operand gives a date: a date literal or Value, or a shift of one."""
    if node.kind is ExpressionKind.DATE:
        return True
    if node.kind is ExpressionKind.REFERENCE and node.target is not None:
        value = values.get(node.target.target)
        return value is NEVER or isinstance(value, date)
    if node.kind is ExpressionKind.BINARY and node.operands is not None:
        return node.operator in (Operator.ADD, Operator.SUBTRACT) and any(
            _is_date(item, values) for item in node.operands
        )
    return False


def _malformed(node: Expression, message: str) -> ContractError:
    """Return the error for an Expression record that lacks a part of its kind."""
    return ContractError(message, targets=(node.id,), values={"kind": node.kind})


# Expressions over fixed content: Quantities, Flows, dates and calls.

_Arithmetic = Callable[[Quantity, Quantity], Quantity]
_ARITHMETIC: dict[Operator, _Arithmetic] = {
    Operator.ADD: operator.add,
    Operator.SUBTRACT: operator.sub,
    Operator.MULTIPLY: operator.mul,
    Operator.DIVIDE: operator.truediv,
}


def evaluate_fixed(
    *,
    expression: Expression,
    values: Mapping[UUID, Content],
    periods: Sequence[Period] | None = None,
) -> Content:
    """Evaluate an Expression on fixed content, with the value functions of its calls.

    ``values`` gives the content of each referenced Value: a Quantity, a Flow,
    a date, NEVER or a Boolean. Arithmetic applies period by period to Flows,
    and a Quantity applies to every period. A comparison of Flows holds when it
    holds in every period. A call evaluates the value function that its
    equation function mirrors; ``periods`` are the Periods of the Flow that the
    expression defines, for a function that makes a Flow from amounts. It reads
    no Model and solves nothing.
    """
    evaluator = _FIXED.get(expression.kind)
    if evaluator is None:
        raise UnsupportedError(
            f"unsupported expression on fixed data: {expression.kind}"
        )
    return evaluator(expression, values, periods)


def _fixed_literal(
    node: Expression, values: Mapping[UUID, Content], periods: Sequence[Period] | None
) -> Content:
    if node.kind is ExpressionKind.BOOLEAN:
        return bool(node.boolean)
    if node.kind is ExpressionKind.DATE:
        return NEVER if node.never is not None else _required(node.date, node)
    quantity = _required(node.quantity, node)
    return Quantity(magnitude=quantity.magnitude, units=quantity.units)


def _fixed_reference(
    node: Expression, values: Mapping[UUID, Content], periods: Sequence[Period] | None
) -> Content:
    target = _required(node.target, node).target
    if target not in values:
        raise ContractError(
            "a referenced Value has no fixed content", targets=(target,)
        )
    return values[target]


def _fixed_unary(
    node: Expression, values: Mapping[UUID, Content], periods: Sequence[Period] | None
) -> Content:
    value = evaluate_fixed(
        expression=_required(node.operand, node), values=values, periods=periods
    )
    if node.operator is Operator.LOGICAL_NOT:
        return not _boolean(value)
    return periodwise(operator.neg, value)


def _fixed_binary(
    node: Expression, values: Mapping[UUID, Content], periods: Sequence[Period] | None
) -> Content:
    left, right = (
        evaluate_fixed(expression=item, values=values, periods=periods)
        for item in _required(node.operands, node)
    )
    relation = _required(node.operator, node)
    if relation in (Operator.LOGICAL_AND, Operator.LOGICAL_OR):
        both = (_boolean(left), _boolean(right))
        return all(both) if relation is Operator.LOGICAL_AND else any(both)
    if _is_date_value(left) or _is_date_value(right):
        return _fixed_date(relation, left, right)
    if relation in _ORDERED:
        return _holds(relation, left, right)
    if relation is Operator.POWER:
        return periodwise(
            lambda a, b: a ** b.to(units="dimensionless").number, left, right
        )
    return periodwise(_ARITHMETIC[relation], left, right)


def _fixed_call(
    node: Expression, values: Mapping[UUID, Content], periods: Sequence[Period] | None
) -> Content:
    call = _required(node.call, node)
    function = functions.get(call.function)
    if function is None:
        raise UnsupportedError(
            "the call is not an equation function", targets=(call.function,)
        )
    names = [parameter.name for parameter in function.parameters]
    given = [
        *zip(names, call.arguments or (), strict=False),
        *((item.name, item.expression) for item in call.named_arguments or ()),
    ]
    arguments = {
        name: evaluate_fixed(expression=item, values=values, periods=periods)
        for name, item in given
    }
    return function.evaluate(arguments=arguments, periods=periods)


def _fixed_date(relation: Operator, left: Content, right: Content) -> Content:
    if relation in _ORDERED:
        if not (_is_date_value(left) and _is_date_value(right)):
            raise ContractError("a date compares only with a date or NEVER")
        return compare_dates(relation, left, right)  # type: ignore[arg-type]
    if relation is Operator.ADD and not _is_date_value(left):
        left, right = right, left
    if relation not in (Operator.ADD, Operator.SUBTRACT) or not isinstance(
        right, Quantity
    ):
        raise ContractError("date arithmetic adds or subtracts a length to a date")
    length = right if relation is Operator.ADD else -right
    return shift(on=left, by=length)  # type: ignore[arg-type]


def _holds(relation: Operator, left: Content, right: Content) -> bool:
    """Return whether a comparison holds, in every period for Flows."""
    test = cast(Callable[[object, object], object], _ORDERED[relation])
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(test(left, right))
    outcome = periodwise(
        lambda a, b: Quantity(magnitude=int(bool(test(a, b))), units="dimensionless"),
        left,
        right,
    )
    if isinstance(outcome, Quantity):
        return bool(outcome.magnitude)
    return all(movement.magnitude for movement in outcome.movements)


def _is_date_value(value: object) -> bool:
    return value is NEVER or isinstance(value, date)


def _boolean(value: Content) -> bool:
    if not isinstance(value, bool):
        raise ContractError("a logical operator takes conditions")
    return value


def _required[T](part: T | None, node: Expression) -> T:
    if part is None:
        raise _malformed(node, f"a {node.kind} expression lacks its content")
    return part


_FixedEvaluator = Callable[
    [Expression, Mapping[UUID, Content], Sequence[Period] | None], Content
]
_FIXED: dict[ExpressionKind, _FixedEvaluator] = {
    ExpressionKind.QUANTITY: _fixed_literal,
    ExpressionKind.BOOLEAN: _fixed_literal,
    ExpressionKind.DATE: _fixed_literal,
    ExpressionKind.REFERENCE: _fixed_reference,
    ExpressionKind.UNARY: _fixed_unary,
    ExpressionKind.BINARY: _fixed_binary,
    ExpressionKind.CALL: _fixed_call,
}

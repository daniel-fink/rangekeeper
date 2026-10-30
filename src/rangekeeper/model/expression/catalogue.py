"""The built-in equation functions, and ``functions``, the registry that holds them.

Each entry mirrors a value function on fixed data: ``rx.max`` mirrors Python's
``max`` period by period, and each Flow method mirrors the Flow method of the
same name.
"""

from collections.abc import Callable, Mapping, Sequence
from datetime import date

from rangekeeper.duration import Period
from rangekeeper.flow import Flow
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import DomainKind, ParameterKind
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, NumericalError

from .functions import (
    Availability,
    Content,
    EquationFunction,
    EquationFunctions,
    EvaluationStage,
    Form,
    FunctionParameter,
)

functions = EquationFunctions()


# Fixed arguments.


def _flow(arguments: Mapping[str, Content], name: str) -> Flow:
    value = arguments[name]
    if not isinstance(value, Flow):
        raise TypeError(f"{name} must be a Flow")
    return value


def _quantity(arguments: Mapping[str, Content], name: str) -> Quantity:
    value = arguments[name]
    if not isinstance(value, Quantity):
        raise TypeError(f"{name} must be a Quantity")
    return value


def _date(arguments: Mapping[str, Content], name: str) -> date:
    value = arguments[name]
    if not isinstance(value, date):
        raise ContractError(
            f"{name} must be a calendar date", values={"argument": name}
        )
    return value


def _whole(arguments: Mapping[str, Content], name: str) -> int:
    number = _quantity(arguments, name).to(units="dimensionless").number
    if number != int(number):
        raise ContractError(
            f"{name} must be a whole number", values={"argument": name, name: number}
        )
    return int(number)


# Period by period.


def _amounts(value: Content, count: int) -> list[Quantity]:
    """Return one Quantity for each of ``count`` periods: a Flow's amounts or a scalar."""
    if isinstance(value, Flow):
        if any(movement.magnitude is None for movement in value.movements):
            raise NumericalError("an amount of the Flow is unresolved")
        return [
            Quantity(magnitude=movement.magnitude, units=value.units)
            for movement in value.movements
        ]
    if isinstance(value, Quantity):
        return [value] * count
    raise TypeError("a periodwise argument must be a Quantity or a Flow")


def periodwise(operation: Callable[..., Quantity], *values: Content) -> Quantity | Flow:
    """Apply a scalar operation to Quantities, or period by period to Flows.

    A Quantity applies to every period. Flows must have the same Periods or
    dates; the result has them too.
    """
    flows = [value for value in values if isinstance(value, Flow)]
    if not flows:
        return operation(*values)
    shape = flows[0]
    coordinates = [(m.period, m.date) for m in shape.movements]
    for other in flows[1:]:
        if [(m.period, m.date) for m in other.movements] != coordinates:
            raise ContractError(
                "the Flows of a periodwise function must have the same Periods",
                code=Code.ALIGNMENT_DIFFER,
            )
    columns = [_amounts(value, len(coordinates)) for value in values]
    results = [operation(*row) for row in zip(*columns, strict=True)]
    if not results:
        return Flow(units=shape.units, movements=())
    units = results[0].units
    amounts: dict[Period | date, Quantity] = {}
    for (period, day), result in zip(coordinates, results, strict=True):
        amounts[period if period is not None else _day(day)] = result.to(units=units)
    return Flow(units=units, amounts=amounts)


def _day(day: date | None) -> date:
    assert day is not None  # A Movement has a Period or a date.
    return day


def _larger(left: Quantity, right: Quantity) -> Quantity:
    return left if left >= right else right


# The built-in entries.

_FLOW = FunctionParameter(
    name="flow",
    kind=DomainKind.FLOW,
    description="The Flow that the method is called on.",
    call=ParameterKind.POSITIONAL_OR_NAMED,
)


def _maximum(
    arguments: Mapping[str, Content], periods: Sequence[Period] | None
) -> Content:
    return periodwise(_larger, arguments["left"], arguments["right"])


def _at(arguments: Mapping[str, Content], periods: Sequence[Period] | None) -> Content:
    return _flow(arguments, "flow").at(on=_date(arguments, "on"))


def _total(
    arguments: Mapping[str, Content], periods: Sequence[Period] | None
) -> Content:
    total = _flow(arguments, "flow").total()
    assert total is not None  # The default treatment raises for unresolved amounts.
    return total


def _shift(
    arguments: Mapping[str, Content], periods: Sequence[Period] | None
) -> Content:
    return _flow(arguments, "flow").shift(by=_whole(arguments, "by"))


for _function in (
    EquationFunction(
        name="max",
        form=Form.FUNCTION,
        summary="The larger of two values, period by period for Flows.",
        parameters=(
            FunctionParameter(
                name="left",
                kind=DomainKind.QUANTITY,
                description="A value or a Flow.",
                call=ParameterKind.POSITIONAL_OR_NAMED,
            ),
            FunctionParameter(
                name="right",
                kind=DomainKind.QUANTITY,
                description="A value or a Flow, in units compatible with left.",
                call=ParameterKind.POSITIONAL_OR_NAMED,
            ),
        ),
        result=DomainKind.QUANTITY,
        stage=EvaluationStage.AFTER_AFFINE,
        availability=Availability.PERIODWISE,
        mirrors="Python's built-in max, period by period",
        units_from="left",
        unit_rule="The arguments have compatible units; the result has the units "
        "of the larger argument.",
        evaluator=_maximum,
    ),
    EquationFunction(
        name="at",
        form=Form.METHOD,
        summary="The amount of the period that contains a date.",
        parameters=(
            _FLOW,
            FunctionParameter(
                name="on",
                kind=DomainKind.DATE,
                description="The date.",
            ),
        ),
        result=DomainKind.QUANTITY,
        stage=EvaluationStage.AFFINE,
        availability=Availability.COMPLETE,
        mirrors="rangekeeper.flow.Flow.at",
        units_from="flow",
        unit_rule="The result has the units of the Flow.",
        evaluator=_at,
    ),
    EquationFunction(
        name="total",
        form=Form.METHOD,
        summary="The sum of the amounts of a Flow.",
        parameters=(_FLOW,),
        result=DomainKind.QUANTITY,
        stage=EvaluationStage.AFFINE,
        availability=Availability.COMPLETE,
        mirrors="rangekeeper.flow.Flow.total",
        units_from="flow",
        unit_rule="The result has the units of the Flow.",
        evaluator=_total,
    ),
    EquationFunction(
        name="shift",
        form=Form.METHOD,
        summary="Each period's amount from the period `by` periods away.",
        parameters=(
            _FLOW,
            FunctionParameter(
                name="by",
                kind=DomainKind.NUMBER,
                description="A whole number of periods; -1 gives each period "
                "the amount of the next period.",
            ),
        ),
        result=DomainKind.FLOW,
        stage=EvaluationStage.AFFINE,
        availability=Availability.SHIFTED,
        mirrors="rangekeeper.flow.Flow.shift",
        units_from="flow",
        unit_rule="The result has the units of the Flow.",
        evaluator=_shift,
    ),
):
    functions.register(_function)


__all__ = ["functions", "periodwise"]

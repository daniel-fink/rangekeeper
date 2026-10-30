"""The built-in equation functions, and ``functions``, the registry that holds them.

Each entry mirrors a value function on fixed data: ``rx.max`` mirrors Python's
``max`` period by period, and each Flow method mirrors the Flow method of the
same name.
"""

import inspect
from collections.abc import Callable, Mapping, Sequence
from datetime import date

from rangekeeper import finance, profile
from rangekeeper.duration import NEVER, Never, Period
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
    Evaluator,
    Form,
    FunctionParameter,
)


def _extension(name: str) -> EquationFunction | None:
    """Return the equation function of a profile from the extension point, if any."""
    namespace, _, short = name.partition(".")
    if namespace != "profile" or short not in profile.profiles:
        return None
    kind = profile.profiles.get(short)
    accepted = inspect.signature(kind).parameters
    return profile_function(
        short, kind, [item for item in _OPTIONS if item in accepted]
    )


functions = EquationFunctions(extension=_extension)


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


def _date_value(arguments: Mapping[str, Content], name: str) -> date | Never:
    value = arguments[name]
    if isinstance(value, Never | date):
        return value
    raise ContractError(
        f"{name} must be a calendar date or NEVER", values={"argument": name}
    )


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


def _smaller(left: Quantity, right: Quantity) -> Quantity:
    return left if left <= right else right


# The built-in entries.

_FLOW = FunctionParameter(
    name="flow",
    kind=DomainKind.FLOW,
    description="The Flow that the method is called on.",
    call=ParameterKind.POSITIONAL_OR_NAMED,
)


def _extreme(
    name: str, *, word: str, select: Callable[[Quantity, Quantity], Quantity]
) -> EquationFunction:
    """Return ``rx.max`` or ``rx.min``: the larger or the smaller of two values.

    The solve picks the active side of each call (G77, #308); its Function
    code, ``rx.max`` or ``rx.min``, is the one that the solve recognises.
    """

    def evaluate(
        arguments: Mapping[str, Content], periods: Sequence[Period] | None
    ) -> Content:
        return periodwise(select, arguments["left"], arguments["right"])

    return EquationFunction(
        name=name,
        form=Form.FUNCTION,
        summary=f"The {word} of two values, period by period for Flows.",
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
        mirrors=f"Python's built-in {name}, period by period",
        units_from="left",
        periodwise=("left", "right"),
        unit_rule="The arguments have compatible units; the result has the units "
        f"of the {word} argument.",
        evaluator=evaluate,
    )


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
    _extreme("max", word="larger", select=_larger),
    _extreme("min", word="smaller", select=_smaller),
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
        periods_from="flow",
        unit_rule="The result has the units of the Flow.",
        evaluator=_shift,
    ),
):
    functions.register(_function)


# The Flow methods without arguments, the date windows and the extremes.


def _plain(name: str) -> Evaluator:
    """Return the evaluator of the Flow method ``name``, which takes no argument."""

    def evaluate(
        arguments: Mapping[str, Content], periods: Sequence[Period] | None
    ) -> Content:
        method: Callable[[], Content] = getattr(_flow(arguments, "flow"), name)
        return method()

    return evaluate


def _since(
    arguments: Mapping[str, Content], periods: Sequence[Period] | None
) -> Content:
    return _flow(arguments, "flow").since(on=_date_value(arguments, "on"))


def _until(
    arguments: Mapping[str, Content], periods: Sequence[Period] | None
) -> Content:
    return _flow(arguments, "flow").until(on=_date_value(arguments, "on"))


_ON = FunctionParameter(
    name="on",
    kind=DomainKind.DATE,
    description="The date, or NEVER.",
)
# Each Flow method without arguments: its summary, result, stage and
# availability.
_PLAIN = (
    (
        "cumulative",
        "The running totals of a Flow.",
        DomainKind.FLOW,
        EvaluationStage.AFFINE,
        Availability.RUNNING,
    ),
    (
        "diff",
        "Each amount less the amount before it.",
        DomainKind.FLOW,
        EvaluationStage.AFFINE,
        Availability.RUNNING,
    ),
    (
        "first",
        "The amount of the first period.",
        DomainKind.QUANTITY,
        EvaluationStage.AFFINE,
        Availability.COMPLETE,
    ),
    (
        "last",
        "The amount of the last period.",
        DomainKind.QUANTITY,
        EvaluationStage.AFFINE,
        Availability.COMPLETE,
    ),
    (
        "min",
        "The smallest amount of a Flow.",
        DomainKind.QUANTITY,
        EvaluationStage.AFTER_AFFINE,
        Availability.COMPLETE,
    ),
    (
        "max",
        "The largest amount of a Flow.",
        DomainKind.QUANTITY,
        EvaluationStage.AFTER_AFFINE,
        Availability.COMPLETE,
    ),
)
for _name, _summary, _result, _stage, _availability in _PLAIN:
    functions.register(
        EquationFunction(
            name=_name,
            form=Form.METHOD,
            summary=_summary,
            parameters=(_FLOW,),
            result=_result,
            stage=_stage,
            availability=_availability,
            mirrors=f"rangekeeper.flow.Flow.{_name}",
            unit_rule="The result has the units of the Flow.",
            evaluator=_plain(_name),
            units_from="flow",
            periods_from="flow",
        )
    )
for _name, _summary, _evaluator in (
    ("since", "The same periods, with zero before a date.", _since),
    ("until", "The same periods, with zero after a date.", _until),
):
    functions.register(
        EquationFunction(
            name=_name,
            form=Form.METHOD,
            summary=_summary,
            parameters=(_FLOW, _ON),
            result=DomainKind.FLOW,
            stage=EvaluationStage.AFFINE,
            availability=Availability.PERIODWISE,
            mirrors=f"rangekeeper.flow.Flow.{_name}",
            unit_rule="The result has the units of the Flow.",
            evaluator=_evaluator,
            units_from="flow",
            periods_from="flow",
        )
    )


# Flows made from amounts: an event and the profiles. Each makes a Flow over
# the Periods of the Flow that the equation defines.


def _required_periods(
    periods: Sequence[Period] | None, *, function: str
) -> Sequence[Period]:
    if periods is None:
        raise ContractError(
            f"{function} makes a Flow over the Periods of the Flow that it defines; "
            "give those Periods",
            code=Code.EQUATION_FUNCTION,
            values={"function": function},
        )
    return periods


def _event(
    arguments: Mapping[str, Content], periods: Sequence[Period] | None
) -> Content:
    target = _required_periods(periods, function="rx.flow.event")
    amount = _quantity(arguments, "amount")
    on = _date_value(arguments, "on")
    zero = Quantity(magnitude=0, units=amount.units)
    return Flow(
        units=amount.units,
        amounts={
            period: amount
            if on is not NEVER and period.start <= on < period.end
            else zero
            for period in target
        },
    )


functions.register(
    EquationFunction(
        name="flow.event",
        form=Form.FUNCTION,
        summary="A Flow with one amount, in the period that contains a date.",
        parameters=(
            FunctionParameter(
                name="amount",
                kind=DomainKind.QUANTITY,
                description="The amount.",
            ),
            FunctionParameter(
                name="on",
                kind=DomainKind.DATE,
                description="The date of the amount; NEVER gives zero in every period.",
            ),
        ),
        result=DomainKind.FLOW,
        stage=EvaluationStage.AFFINE,
        availability=Availability.PERIODWISE,
        mirrors="rangekeeper.flow.Flow, with the amount on its date and zero elsewhere",
        unit_rule="The result has the units of the amount.",
        evaluator=_event,
        units_from="amount",
    )
)


# Valuation and interest, on one date basis (D4, D23).

_RATE = FunctionParameter(
    name="rate",
    kind=DomainKind.QUANTITY,
    units="% pa",
    description="An effective rate per year, such as 7 % pa.",
)


def _npv(arguments: Mapping[str, Content], periods: Sequence[Period] | None) -> Content:
    return finance.npv(
        flow=_flow(arguments, "flow"),
        rate=_quantity(arguments, "rate"),
        on=_date(arguments, "on"),
    )


def _irr(arguments: Mapping[str, Content], periods: Sequence[Period] | None) -> Content:
    return finance.irr(flow=_flow(arguments, "flow"))


def _interest(
    arguments: Mapping[str, Content], periods: Sequence[Period] | None
) -> Content:
    return finance.interest(
        balance=_flow(arguments, "balance"), rate=_quantity(arguments, "rate")
    )


for _function in (
    EquationFunction(
        name="finance.npv",
        form=Form.FUNCTION,
        summary="The net present value of a Flow on a date.",
        parameters=(
            FunctionParameter(
                name="flow",
                kind=DomainKind.FLOW,
                description="The cash flow.",
            ),
            _RATE,
            FunctionParameter(
                name="on",
                kind=DomainKind.DATE,
                description="The date of the value.",
            ),
        ),
        result=DomainKind.QUANTITY,
        stage=EvaluationStage.AFFINE,
        availability=Availability.COMPLETE,
        mirrors="rangekeeper.finance.npv",
        unit_rule="The result has the units of the Flow.",
        evaluator=_npv,
        units_from="flow",
    ),
    EquationFunction(
        name="finance.irr",
        form=Form.FUNCTION,
        summary="The internal rate of return of a Flow: the rate whose NPV is zero.",
        parameters=(
            FunctionParameter(
                name="flow",
                kind=DomainKind.FLOW,
                description="The cash flow, with both signs.",
            ),
        ),
        result=DomainKind.QUANTITY,
        stage=EvaluationStage.AFTER_AFFINE,
        availability=Availability.COMPLETE,
        mirrors="rangekeeper.finance.irr",
        unit_rule="The result is a rate per year, in % pa.",
        evaluator=_irr,
        result_units="% pa",
    ),
    EquationFunction(
        name="finance.interest",
        form=Form.FUNCTION,
        summary="The interest on a balance in each period.",
        parameters=(
            FunctionParameter(
                name="balance",
                kind=DomainKind.FLOW,
                description="The balance of each period.",
            ),
            _RATE,
        ),
        result=DomainKind.FLOW,
        stage=EvaluationStage.AFFINE,
        availability=Availability.PERIODWISE,
        mirrors="rangekeeper.finance.interest",
        unit_rule="The result has the units of the balance.",
        evaluator=_interest,
        units_from="balance",
        periods_from="balance",
    ),
):
    functions.register(_function)


# Profiles (D12): each profile of rangekeeper.profile is an equation function
# under its own name in lower case. The amount, initial= or total=, gives the
# Flow its units; the other arguments are the options of the profile.

_INITIAL = FunctionParameter(
    name="initial",
    kind=DomainKind.QUANTITY,
    description="The amount of the first period, or on base.",
)
_TOTAL = FunctionParameter(
    name="total",
    kind=DomainKind.QUANTITY,
    description="The total that the profile divides over the periods.",
)
_OPTIONS = {
    "rate": FunctionParameter(
        name="rate",
        kind=DomainKind.QUANTITY,
        units="% pa",
        description="The growth rate per year, such as 2 % pa.",
    ),
    "start": FunctionParameter(
        name="start",
        kind=DomainKind.DATE,
        required=False,
        description="The date from which the profile has amounts; NEVER gives "
        "zero in every period.",
    ),
    "every": FunctionParameter(
        name="every",
        kind=DomainKind.QUANTITY,
        units="year",
        required=False,
        description="A length, such as 5 years: an amount on start and once "
        "each length after it.",
    ),
    "base": FunctionParameter(
        name="base",
        kind=DomainKind.DATE,
        required=False,
        description="The date of the initial amount; by default the start of "
        "the first period.",
    ),
    "length": FunctionParameter(
        name="length",
        kind=DomainKind.QUANTITY,
        units="year",
        required=False,
        description="The length of time over which the total is divided, such "
        "as 2 years.",
    ),
}
# Each built-in profile: its class and the options that an equation gives it.
_PROFILES: tuple[tuple[str, type, tuple[str, ...]], ...] = (
    ("constant", profile.Constant, ("start", "every")),
    ("linear", profile.Linear, ("rate", "start", "every", "base")),
    ("compounding", profile.Compounding, ("rate", "start", "every", "base")),
    ("uniform", profile.Uniform, ("start", "length")),
    ("scurve", profile.SCurve, ("start", "length")),
)


def _profiled(name: str, kind: type) -> Evaluator:
    """Return the evaluator of the profile ``kind``: ``Flow.from_profile``."""

    def evaluate(
        arguments: Mapping[str, Content], periods: Sequence[Period] | None
    ) -> Content:
        target = _required_periods(periods, function=f"rx.profile.{name}")
        amount = kind.takes  # type: ignore[attr-defined]
        options = {key: value for key, value in arguments.items() if key != amount}
        shape = kind(**options)
        return Flow.from_profile(
            profile=shape, periods=target, **{amount: _quantity(arguments, amount)}
        )

    return evaluate


def profile_function(name: str, kind: type, options: Sequence[str]) -> EquationFunction:
    """Return the equation function of a profile: ``rx.profile.<name>``.

    ``kind`` is the profile class, and ``options`` the names of its options
    that an equation can give: ``rate``, ``start``, ``every``, ``base`` and
    ``length``.
    """
    growth = kind.takes == "initial"  # type: ignore[attr-defined]
    word = "growth" if growth else "distribution"
    return EquationFunction(
        name=f"profile.{name}",
        form=Form.FUNCTION,
        summary=f"A Flow made by the {word} profile {kind.__name__}.",
        parameters=(
            _INITIAL if growth else _TOTAL,
            *(_OPTIONS[item] for item in options),
        ),
        result=DomainKind.FLOW,
        stage=EvaluationStage.AFFINE,
        availability=Availability.PERIODWISE,
        mirrors=f"rangekeeper.flow.Flow.from_profile with rangekeeper.profile.{kind.__name__}",
        unit_rule="The result has the units of the amount.",
        evaluator=_profiled(name, kind),
        units_from="initial" if growth else "total",
    )


for _name, _kind, _options in _PROFILES:
    functions.register(profile_function(_name, _kind, _options))


__all__ = ["functions", "periodwise", "profile_function"]

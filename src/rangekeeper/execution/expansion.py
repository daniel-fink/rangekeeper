"""Flow-valued equations and equation functions in a solve (#276, #277).

An equation over Flows holds in each period (#279). ``expand`` writes each
assertion of a Binding over scalar values and Movements, one assertion for
each period of the Flow that the equation defines, so that the compiler, the
staged solve, the piecewise solve and verification work on scalar rows:

- A reference to a Flow Value is the reference to its Movement in the period.
  A scalar applies to every period.
- A call of ``rx.max`` or ``rx.min`` is a call of the same Function in each
  period, which ``execution.piecewise`` solves.
- A call of another equation function in the affine stage, such as a profile,
  ``rx.flow.event``, ``rx.finance.npv``, ``rx.finance.interest`` or a Flow
  method such as ``cumulative()``, is linear in its unknown arguments once
  its other arguments are fixed. ``expand`` reads the coefficients of that
  linear map from the function's own value function, on fixed data: the
  constant at zero unknowns, and the change for each unknown. Each period is
  then a sum of a constant and coefficients times references. One more
  evaluation checks that the map is linear.
- A call after the affine stage (D4), such as ``rx.finance.irr(flow=cash)``,
  takes the Movements of its Flow as positional arguments; when earlier
  stages determine them, the compiler evaluates the call (``resolve``).
  ``x.max()`` and ``x.min()`` become ``max`` and ``min`` calls over the
  periods of their Flow, which ``execution.piecewise`` solves.
- An equation that fixes an IRR, ``r = rx.finance.irr(flow=cash)`` with ``r``
  fixed, becomes its NPV row at that rate: the NPV of the Flow at ``r`` is
  zero (D5, #277). The row holds at any rate on a Flow of zeros, so the
  assertion keeps the Flow, and acceptance applies the sign check of ``irr``
  to it (``fixed_irr_flows``, #518).

A call whose references are all fixed is evaluated once. Each expanded
assertion keeps the Constraint of its equation.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from uuid import NAMESPACE_URL, UUID, uuid5

from rangekeeper.duration import Period
from rangekeeper.execution.errors import UnsupportedError
from rangekeeper.execution.preparation import Assertion, Binding
from rangekeeper.flow import Flow, Movement
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.evaluation import evaluate_fixed
from rangekeeper.model.expression.functions import (
    Content,
    EquationFunction,
    EvaluationStage,
    Form,
)
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import ValueKind
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import (
    Argument,
    Call,
    Expression,
    ExpressionKind,
    Operator,
    Reference,
    Value,
)
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, NumericalError

# The UUIDs of expanded nodes: the same node in the same period gets the same UUID.
NAMESPACE = uuid5(NAMESPACE_URL, "https://daniel-fink.github.io/rangekeeper/expansion")
# The probe of one unknown, a power of two so that the scale is exact.
PROBE = 2.0**20
# The relative and absolute tolerance of the check that a lowered call is linear.
LINEAR_RELATIVE = 1e-9
LINEAR_ABSOLUTE = 1e-6
# The piecewise functions that apply period by period.
PERIODWISE = frozenset({"rx.max", "rx.min"})
# The bounds on a reduction that hold in every period: the relation of the
# reduction's side to the other side, and the reduction (D5).
_SPREAD = {
    Operator.GREATER_THAN_OR_EQUAL: "Flow.min",
    Operator.LESS_THAN_OR_EQUAL: "Flow.max",
}
_MIRRORED = {
    Operator.GREATER_THAN_OR_EQUAL: Operator.LESS_THAN_OR_EQUAL,
    Operator.LESS_THAN_OR_EQUAL: Operator.GREATER_THAN_OR_EQUAL,
}
# The reductions of a Flow that are piecewise over its periods.
REDUCTIONS = {"Flow.max": "Flow.max", "Flow.min": "Flow.min"}


def expand(binding: Binding) -> Binding:
    """Return ``binding`` with its Flow-valued equations written for each period.

    An assertion without a Flow and without an equation function call is
    unchanged. Raise UnsupportedError for a call that is not linear in its
    unknown arguments, or that reads a value without a role.
    """
    expansion = _Expansion(binding)
    found: list[Assertion] = []
    for item in binding.assertions:
        found.extend(expansion.assertion(item))
    return replace(binding, assertions=tuple(found))


@dataclass
class _Expansion:
    """The expansion of the assertions of one Binding."""

    binding: Binding
    lowered: dict[UUID, list[Expression]] = field(default_factory=dict)

    # Assertions.

    def assertion(self, item: Assertion) -> tuple[Assertion, ...]:
        """Return the scalar assertions of one assertion."""
        node = item.predicate
        if not self.touches(node):
            return (item,)
        if node.kind is ExpressionKind.BINARY and node.operator is Operator.LOGICAL_AND:
            return tuple(
                part
                for child in node.operands or ()
                for part in self.assertion(replace(item, predicate=child))
            )
        item = self.target(item)
        node = item.predicate
        spread = self.spread(node)
        if spread is not None:
            return tuple(replace(item, predicate=row) for row in spread)
        periods = self.periods(node)
        if periods is None:
            return (replace(item, predicate=self.at(node, None, None)),)
        return tuple(
            replace(item, predicate=self.at(node, index, periods))
            for index in range(len(periods))
        )

    def touches(self, node: Expression) -> bool:
        """Return whether ``node`` reads a Flow Value or calls an equation function."""
        for child, _, _ in walk(node):
            if not isinstance(child, Expression):
                continue
            if self.flow_value(child) is not None:
                return True
            function = _function(child)
            if function is not None and function.code not in PERIODWISE:
                return True
        return False

    def periods(self, node: Expression) -> tuple[Period, ...] | None:
        """Return the Periods of the Flow that an equation defines, else None.

        They are the declared Periods of the first Flow Value that the
        equation reads outside a call that gives a scalar.
        """
        for child in _outside_scalar_calls(node):
            value = self.flow_value(child)
            if value is not None:
                return _periods(value)
        return None

    # Expressions, period by period.

    def at(
        self,
        node: Expression,
        index: int | None,
        periods: Sequence[Period] | None,
    ) -> Expression:
        """Return ``node`` in one period: ``index`` of ``periods``, or a scalar."""
        value = self.flow_value(node)
        if value is not None:
            return self.movement(node, value=value, index=index, periods=periods)
        if node.kind is ExpressionKind.CALL:
            return self.call(node, index=index, periods=periods)
        return _rebuilt(
            node,
            lambda child: self.at(child, index, periods),
            id=_id(node, index),
        )

    def movement(
        self,
        node: Expression,
        *,
        value: Value,
        index: int | None,
        periods: Sequence[Period] | None,
    ) -> Expression:
        """Return the reference to a Flow Value's Movement in one period."""
        if index is None or periods is None:
            raise UnsupportedError(
                f"the Flow {value.key} is used where a scalar is expected"
            )
        movement = _movement(value, periods[index])
        return Expression(
            id=_id(node, index),
            kind=ExpressionKind.REFERENCE,
            target=Reference(target=movement.id),
        )

    def call(
        self,
        node: Expression,
        *,
        index: int | None,
        periods: Sequence[Period] | None,
    ) -> Expression:
        """Return a call in one period: piecewise, evaluated, lowered or deferred."""
        function = _function(node)
        if function is None:
            return node
        if function.code in PERIODWISE:
            return _rebuilt(
                node, lambda child: self.at(child, index, periods), id=_id(node, index)
            )
        if self.fixed(node):
            return self.constant(node, function=function, index=index, periods=periods)
        if function.stage is EvaluationStage.AFFINE:
            return self.linear(node, index=index, periods=periods)
        if function.code in REDUCTIONS:
            return self.reduction(node)
        return self.deferred(node, function=function)

    # Calls.

    def constant(
        self,
        node: Expression,
        *,
        function: EquationFunction,
        index: int | None,
        periods: Sequence[Period] | None,
    ) -> Expression:
        """Return the value of a call whose references are all fixed."""
        result = self.evaluate(node, probes={}, periods=periods)
        return _literal(_amount(result, index, periods), id=_id(node, index))

    def linear(
        self,
        node: Expression,
        *,
        index: int | None,
        periods: Sequence[Period] | None,
    ) -> Expression:
        """Return a call of the affine stage as a sum in one period."""
        sums = self.lowered.get(node.id)
        if sums is None:
            sums = self.lower(node, periods=periods)
            self.lowered[node.id] = sums
        return sums[0 if index is None or len(sums) == 1 else index]

    def lower(
        self, node: Expression, *, periods: Sequence[Period] | None
    ) -> list[Expression]:
        """Return each period of a call as a constant plus coefficients times unknowns.

        The coefficients come from the call's value function: the result at
        zero unknowns, and the change for each unknown alone. One more
        evaluation, with every unknown at another value, checks that the call
        is linear in them.
        """
        self.require_linear(node)
        atoms = self.unknowns(node)
        base = self.numbers(node, probes={}, periods=periods)
        columns = {
            atom: [
                (changed - fixed) / PROBE
                for changed, fixed in zip(
                    self.numbers(node, probes={atom: PROBE}, periods=periods),
                    base,
                    strict=True,
                )
            ]
            for atom in atoms
        }
        self.check_linear(node, base=base, columns=columns, periods=periods)
        units = self.result_units(node, periods=periods)
        return [
            _sum(
                node,
                period=period,
                constant=Quantity(magnitude=constant, units=units),
                terms=[
                    (column[period], self.binding.value_units[atom], atom)
                    for atom, column in columns.items()
                ],
            )
            for period, constant in enumerate(base)
        ]

    def reduction(self, node: Expression) -> Expression:
        """Return ``x.max()`` or ``x.min()`` as a call over the periods of ``x``."""
        flow = _operands(node)[0]
        periods = self.periods(flow)
        if periods is None or len(periods) < 2:
            raise UnsupportedError("a reduction of a Flow needs two or more periods")
        assert node.call is not None
        return Expression(
            id=_id(node, None),
            kind=ExpressionKind.CALL,
            call=Call(
                function=node.call.function,
                arguments=tuple(
                    self.at(flow, index, periods) for index in range(len(periods))
                ),
            ),
        )

    def deferred(self, node: Expression, *, function: EquationFunction) -> Expression:
        """Return a call after the affine stage, with its Flow's Movements as arguments.

        The compiler evaluates it when earlier stages determine them
        (``resolve``). Its Flow must be a Flow Value, and its other arguments
        fixed.
        """
        flows = [item for item in _operands(node) if self.flow_value(item) is not None]
        others = [item for item in _operands(node) if self.flow_value(item) is None]
        if len(flows) != 1 or any(not self.fixed(item) for item in others):
            raise UnsupportedError(
                f"{function.spelling} reads a Flow Value and fixed values only",
                code=Code.UNSUPPORTED_CAPABILITY,
            )
        value = self.flow_value(flows[0])
        assert value is not None and node.call is not None
        return Expression(
            id=_id(node, None),
            kind=ExpressionKind.CALL,
            call=Call(
                function=node.call.function,
                arguments=tuple(
                    Expression(
                        id=_id(flows[0], index),
                        kind=ExpressionKind.REFERENCE,
                        target=Reference(target=movement.id),
                    )
                    for index, movement in enumerate(_flow(value).movements)
                ),
            ),
        )

    # A bound on a minimum or a maximum (#277).

    def spread(self, node: Expression) -> tuple[Expression, ...] | None:
        """Return a bound on ``x.min()`` or ``x.max()`` as one row for each period.

        ``x.min() >= c`` holds when ``x >= c`` in every period, and
        ``x.max() <= c`` when ``x <= c`` in every period; the same holds with
        the sides exchanged (D5). Another predicate gives None.
        """
        if node.kind is not ExpressionKind.BINARY or node.operator not in _MIRRORED:
            return None
        left, right = node.operands or (None, None)
        assert left is not None and right is not None
        for side, other, relation in (
            (left, right, node.operator),
            (right, left, _MIRRORED[node.operator]),
        ):
            function = _function(side)
            if function is None or _SPREAD[relation] != function.code:
                continue
            flow = _operands(side)[0]
            periods = self.periods(flow)
            if periods is None:
                return None
            return tuple(
                Expression(
                    id=_id(node, f"spread/{index}"),
                    kind=ExpressionKind.BINARY,
                    operator=relation,
                    operands=(
                        self.at(flow, index, periods),
                        self.at(other, index, periods),
                    ),
                )
                for index in range(len(periods))
            )
        return None

    # A fixed IRR (#277).

    def target(self, item: Assertion) -> Assertion:
        """Return an equation that fixes an IRR as its NPV row at that rate.

        ``r = rx.finance.irr(flow=cash)`` with ``r`` fixed is
        ``rx.finance.npv(flow=cash, rate=r, on=start) = 0``, where ``start``
        begins the Flow's first period. The assertion keeps the Flow in
        ``irr_flow``. Another equation is unchanged.
        """
        node = item.predicate
        if (
            node.kind is not ExpressionKind.BINARY
            or node.operator is not Operator.EQUAL
        ):
            return item
        left, right = node.operands or (None, None)
        assert left is not None and right is not None
        for rate, call in ((left, right), (right, left)):
            function = _function(call)
            if (
                function is not None
                and function.code == "rx.finance.irr"
                and rate.kind is ExpressionKind.REFERENCE
                and self.fixed(rate)
            ):
                return replace(
                    item,
                    predicate=self.npv_row(node, rate=rate, call=call),
                    irr_flow=_operands(call)[0],
                )
        return item

    def npv_row(
        self, node: Expression, *, rate: Expression, call: Expression
    ) -> Expression:
        """Return ``npv(flow=cash, rate=r, on=start) = 0`` for ``r = irr(flow=cash)``."""
        (flow,) = _operands(call)
        periods = self.periods(flow)
        if periods is None:
            raise UnsupportedError("a fixed IRR needs a Flow with Periods")
        npv = functions.function(name="finance.npv")
        units = self.result_units(flow, periods=periods)
        on = Expression(
            id=_id(node, "on"), kind=ExpressionKind.DATE, date=periods[0].start
        )
        value = Expression(
            id=_id(node, "npv"),
            kind=ExpressionKind.CALL,
            call=Call(
                function=npv.id,
                named_arguments=(
                    Argument(name="flow", expression=flow),
                    Argument(name="rate", expression=rate),
                    Argument(name="on", expression=on),
                ),
            ),
        )
        zero = _literal(Quantity(magnitude=0, units=units), id=_id(node, "zero"))
        return Expression(
            id=_id(node, "row"),
            kind=ExpressionKind.BINARY,
            operator=Operator.EQUAL,
            operands=(value, zero),
        )

    # Values.

    def flow_value(self, node: Expression) -> Value | None:
        """Return the Flow Value that ``node`` references, else None."""
        if node.kind is not ExpressionKind.REFERENCE or node.target is None:
            return None
        try:
            found = self.binding.model.resolve(node.target)
        except LookupError:
            return None
        if isinstance(found, Value) and found.kind is ValueKind.FLOW:
            return found
        return None

    def atoms(self, node: Expression) -> list[UUID]:
        """Return the scalar Values and Movements that ``node`` reads, in order."""
        found: list[UUID] = []
        for child, _, _ in walk(node):
            if not isinstance(child, Expression) or child.target is None:
                continue
            value = self.flow_value(child)
            ids = (
                [m.id for m in _flow(value).movements]
                if value is not None
                else [child.target.target]
            )
            found.extend(id for id in ids if id not in found)
        return found

    def unknowns(self, node: Expression) -> list[UUID]:
        """Return the unknowns that ``node`` reads."""
        unknown = set(self.binding.unknowns)
        return [atom for atom in self.atoms(node) if atom in unknown]

    def fixed(self, node: Expression) -> bool:
        """Return whether every value that ``node`` reads is fixed."""
        return all(
            atom in self.binding.assignments or atom in self.binding.dates
            for atom in self.atoms(node)
        )

    def content(self, probes: Mapping[UUID, float]) -> Callable[[Expression], Content]:
        """Return the content of a reference: fixed, or a probe for an unknown."""

        def scalar(atom: UUID) -> Content:
            if atom in self.binding.dates:
                return self.binding.dates[atom]
            if atom in self.binding.assignments:
                return self.binding.assignments[atom]
            if atom in self.binding.value_units:
                return Quantity(
                    magnitude=probes.get(atom, 0.0),
                    units=self.binding.value_units[atom],
                )
            raise UnsupportedError("expression reference has no explicit solve role")

        def read(node: Expression) -> Content:
            value = self.flow_value(node)
            if value is None:
                assert node.target is not None
                return scalar(node.target.target)
            shape = _flow(value)
            return Flow(
                units=shape.units,
                amounts={
                    _coordinate(movement): _amount_of(scalar(movement.id)).to(
                        units=shape.units
                    )
                    for movement in shape.movements
                },
            )

        return read

    def evaluate(
        self,
        node: Expression,
        *,
        probes: Mapping[UUID, float],
        periods: Sequence[Period] | None,
    ) -> Content:
        """Evaluate ``node`` with the value functions of its calls, on fixed data."""
        read = self.content(probes)
        values = {
            child.target.target: read(child)
            for child, _, _ in walk(node)
            if isinstance(child, Expression)
            and child.kind is ExpressionKind.REFERENCE
            and child.target is not None
        }
        try:
            return evaluate_fixed(expression=node, values=values, periods=periods)
        except (ContractError, LookupError) as error:
            # A value function refuses its arguments, such as a date outside a Flow.
            raise UnsupportedError(
                str(error), code=Code.UNSUPPORTED_CAPABILITY
            ) from error
        except (ArithmeticError, TypeError) as error:
            raise NumericalError(str(error)) from error

    def numbers(
        self,
        node: Expression,
        *,
        probes: Mapping[UUID, float],
        periods: Sequence[Period] | None,
    ) -> list[float]:
        """Return the number of each period of ``node``'s result, or its scalar."""
        result = self.evaluate(node, probes=probes, periods=periods)
        if isinstance(result, Quantity):
            return [result.number]
        if isinstance(result, Flow):
            return [
                0.0 if movement.magnitude is None else float(movement.number)
                for movement in _aligned(result, periods)
            ]
        raise UnsupportedError("an equation function gave no amount")

    def result_units(
        self, node: Expression, *, periods: Sequence[Period] | None
    ) -> str:
        """Return the units of ``node``'s result at zero unknowns."""
        result = self.evaluate(node, probes={}, periods=periods)
        if isinstance(result, (Quantity, Flow)):
            return result.units
        raise UnsupportedError("an equation function gave no amount")

    def require_linear(self, node: Expression) -> None:
        """Raise UnsupportedError when an unknown is in a position that is not linear."""
        if not self.linear_in(node):
            keys = [
                self.binding.key(Reference(target=id)) for id in self.unknowns(node)
            ]
            raise UnsupportedError(
                "the call is not linear in the unknowns " + ", ".join(keys),
                code=Code.NONAFFINE_UNKNOWNS,
                targets=tuple(self.unknowns(node)),
                unknowns=keys,
            )

    def linear_in(self, node: Expression) -> bool:
        """Return whether ``node`` is linear in the unknowns that it reads."""
        if not self.unknowns(node):
            return True
        rule = _LINEAR.get((node.kind, node.operator))
        if rule is not None:
            return rule(self, node)
        if node.kind is ExpressionKind.REFERENCE:
            return True
        function = _function(node)
        if function is None or function.stage is not EvaluationStage.AFFINE:
            return False
        linear = _linear_parameters(function)
        return all(
            self.linear_in(argument) if name in linear else not self.unknowns(argument)
            for name, argument in _arguments(node, function)
        )

    def check_linear(
        self,
        node: Expression,
        *,
        base: list[float],
        columns: Mapping[UUID, list[float]],
        periods: Sequence[Period] | None,
    ) -> None:
        """Raise UnsupportedError when the lowered call is not linear."""
        if not columns:
            return
        probes = {atom: PROBE * (index + 2) for index, atom in enumerate(columns)}
        actual = self.numbers(node, probes=probes, periods=periods)
        for period, value in enumerate(actual):
            expected = base[period] + sum(
                columns[atom][period] * probe for atom, probe in probes.items()
            )
            tolerance = LINEAR_ABSOLUTE + LINEAR_RELATIVE * max(
                abs(value), abs(expected)
            )
            if abs(value - expected) > tolerance:
                raise UnsupportedError(
                    "the call is not linear in its unknown arguments",
                    code=Code.NONAFFINE_UNKNOWNS,
                    targets=tuple(columns),
                )


def _linear_arithmetic(expansion: _Expansion, node: Expression) -> bool:
    return all(expansion.linear_in(child) for child in node.operands or ())


def _linear_negation(expansion: _Expansion, node: Expression) -> bool:
    return node.operand is not None and expansion.linear_in(node.operand)


def _linear_product(expansion: _Expansion, node: Expression) -> bool:
    operands = node.operands or ()
    reading = [item for item in operands if expansion.unknowns(item)]
    return len(reading) <= 1 and all(expansion.linear_in(item) for item in reading)


def _linear_quotient(expansion: _Expansion, node: Expression) -> bool:
    left, right = node.operands or (None, None)
    assert left is not None and right is not None
    return not expansion.unknowns(right) and expansion.linear_in(left)


_Rule = Callable[[_Expansion, Expression], bool]
_LINEAR: dict[tuple[ExpressionKind, Operator | None], _Rule] = {
    (ExpressionKind.BINARY, Operator.ADD): _linear_arithmetic,
    (ExpressionKind.BINARY, Operator.SUBTRACT): _linear_arithmetic,
    (ExpressionKind.BINARY, Operator.MULTIPLY): _linear_product,
    (ExpressionKind.BINARY, Operator.DIVIDE): _linear_quotient,
    (ExpressionKind.UNARY, Operator.NEGATE): _linear_negation,
}


def _linear_parameters(function: EquationFunction) -> frozenset[str]:
    """Return the parameters in which an affine-stage function is linear.

    The registry gives no linearity for each parameter. Each affine-stage
    function is linear in its first parameter, the amount or the Flow that it
    takes (``total``, ``initial``, ``amount``, ``flow``, ``balance``), and in
    each Flow parameter; it needs its other arguments, such as rates and
    dates, fixed.
    """
    parameters = function.parameters
    names = {parameters[0].name} if parameters else set()
    names.update(item.name for item in parameters if item.kind.value == "flow")
    return frozenset(names)


def _function(node: Expression) -> EquationFunction | None:
    if node.kind is not ExpressionKind.CALL or node.call is None:
        return None
    return functions.get(node.call.function)


def _operands(node: Expression) -> list[Expression]:
    call = node.call
    if call is None:
        return []
    return [
        *(call.arguments or ()),
        *(item.expression for item in call.named_arguments or ()),
    ]


def _arguments(
    node: Expression, function: EquationFunction
) -> list[tuple[str, Expression]]:
    call = node.call
    assert call is not None
    names = [item.name for item in function.parameters]
    return [
        *zip(names, call.arguments or (), strict=False),
        *((item.name, item.expression) for item in call.named_arguments or ()),
    ]


def _outside_scalar_calls(node: Expression) -> list[Expression]:
    """Return the nodes of ``node`` that are not inside a call that gives a scalar."""
    found = [node]
    function = _function(node)
    if (
        function is not None
        and function.result.value != "flow"
        and function.code not in PERIODWISE
    ):
        return found
    for child in (
        *(node.operands or ()),
        *((node.operand,) if node.operand is not None else ()),
        *_operands(node),
    ):
        found.extend(_outside_scalar_calls(child))
    return found


def _flow(value: Value) -> Flow:
    if value.flow is None:
        raise UnsupportedError(f"the Flow Value {value.key} declares no Movements")
    return value.flow


def _periods(value: Value) -> tuple[Period, ...]:
    periods = tuple(m.period for m in _flow(value).movements if m.period is not None)
    if len(periods) != len(_flow(value).movements):
        raise UnsupportedError(f"the Flow Value {value.key} is not over Periods")
    return periods


def _movement(value: Value, period: Period) -> Movement:
    for movement in _flow(value).movements:
        if movement.period == period:
            return movement
    raise ContractError(
        f"the Flow {value.key} has no Movement in {period}",
        code=Code.ALIGNMENT_DIFFER,
        targets=(value.id,),
    )


def _coordinate(movement: Movement) -> Period:
    if movement.period is None:
        raise UnsupportedError("a Flow equation needs Movements over Periods")
    return movement.period


def _aligned(result: Flow, periods: Sequence[Period] | None) -> list[Movement]:
    """Return the Movements of ``result`` in the order of ``periods``."""
    if periods is None:
        return list(result.movements)
    by_period = {movement.period: movement for movement in result.movements}
    missing = [period for period in periods if period not in by_period]
    if missing:
        raise UnsupportedError(
            "an equation function gave a Flow over other Periods",
            code=Code.UNSUPPORTED_CAPABILITY,
        )
    return [by_period[period] for period in periods]


def _amount_of(content: Content) -> Quantity:
    if not isinstance(content, Quantity):
        raise UnsupportedError("a Movement takes an amount")
    return content


def _amount(
    result: Content, index: int | None, periods: Sequence[Period] | None
) -> Quantity:
    if isinstance(result, Quantity):
        return result
    if isinstance(result, Flow) and index is not None:
        movement = _aligned(result, periods)[index]
        return Quantity(
            magnitude=0 if movement.magnitude is None else movement.magnitude,
            units=result.units,
        )
    raise UnsupportedError("an equation function gave no amount in the period")


def _id(node: Expression, part: object) -> UUID:
    return node.id if part is None else uuid5(NAMESPACE, f"{node.id}/{part}")


def _literal(quantity: Quantity, *, id: UUID) -> Expression:
    return Expression(id=id, kind=ExpressionKind.QUANTITY, quantity=quantity)


def _sum(
    node: Expression,
    *,
    period: int,
    constant: Quantity,
    terms: Sequence[tuple[float, str, UUID]],
) -> Expression:
    """Return ``constant + c1 * x1 + ...``, without the terms whose coefficient is zero."""
    result = _literal(constant, id=_id(node, f"{period}/constant"))
    for coefficient, units, atom in terms:
        if coefficient == 0:
            continue
        scale = (
            "dimensionless"
            if units == constant.units
            else f"({constant.units}) / ({units})"
        )
        product = Expression(
            id=_id(node, f"{period}/{atom}"),
            kind=ExpressionKind.BINARY,
            operator=Operator.MULTIPLY,
            operands=(
                _literal(
                    Quantity(magnitude=coefficient, units=scale),
                    id=_id(node, f"{period}/{atom}/coefficient"),
                ),
                Expression(
                    id=_id(node, f"{period}/{atom}/reference"),
                    kind=ExpressionKind.REFERENCE,
                    target=Reference(target=atom),
                ),
            ),
        )
        result = Expression(
            id=_id(node, f"{period}/{atom}/sum"),
            kind=ExpressionKind.BINARY,
            operator=Operator.ADD,
            operands=(result, product),
        )
    return result


def _rebuilt(
    node: Expression, change: Callable[[Expression], Expression], *, id: UUID
) -> Expression:
    """Return ``node`` with ``change`` applied to its children, under a new UUID."""
    if node.kind is ExpressionKind.UNARY and node.operand is not None:
        operand = change(node.operand)
        return node if operand is node.operand else node.replace(id=id, operand=operand)
    if node.kind is ExpressionKind.BINARY and node.operands is not None:
        operands = tuple(change(item) for item in node.operands)
        if all(a is b for a, b in zip(operands, node.operands, strict=True)):
            return node
        return node.replace(id=id, operands=operands)
    if node.kind is ExpressionKind.CALL and node.call is not None:
        arguments = tuple(change(item) for item in node.call.arguments or ())
        named = tuple(
            item.replace(expression=change(item.expression))
            for item in node.call.named_arguments or ()
        )
        unchanged = all(
            a is b for a, b in zip(arguments, node.call.arguments or (), strict=True)
        ) and all(
            a.expression is b.expression
            for a, b in zip(named, node.call.named_arguments or (), strict=True)
        )
        if unchanged:
            return node
        return node.replace(
            id=id,
            call=node.call.replace(
                arguments=arguments
                if node.call.arguments is not None
                else node.call.arguments,
                named_arguments=named
                if node.call.named_arguments is not None
                else node.call.named_arguments,
            ),
        )
    return node


def fixed_irr_flows(
    binding: Binding, *, values: Mapping[UUID, Quantity]
) -> Iterator[Flow]:
    """Return the Flow of each equation that fixes an IRR, at ``values``.

    ``values`` gives each value that the Flows read. ``binding`` is expanded.
    """
    solved = _Expansion(replace(binding, assignments=values, unknowns=()))
    for item in binding.assertions:
        if item.irr_flow is not None:
            periods = solved.periods(item.irr_flow)
            flow = solved.evaluate(item.irr_flow, probes={}, periods=periods)
            assert isinstance(flow, Flow)
            yield flow


# Evaluation of the calls that the expansion defers.


def resolve(
    node: Expression, *, values: Mapping[UUID, Quantity], binding: Binding
) -> Expression | None:
    """Return ``node`` with each deferred call evaluated, or None when one cannot be.

    A deferred call takes the Movements of one Flow as its positional
    arguments (``_Expansion.deferred``). It is evaluated when ``values``
    gives each of them.
    """
    function = _function(node)
    if function is not None and _deferred(node, function):
        return _evaluated(node, function=function, values=values, binding=binding)
    rebuilt = _rebuilt(
        node,
        lambda child: resolve(child, values=values, binding=binding) or _MISSING,
        id=node.id,
    )
    if any(child is _MISSING for child, _, _ in walk(rebuilt)):
        return None
    return rebuilt


_MISSING = Expression(
    id=uuid5(NAMESPACE, "missing"), kind=ExpressionKind.BOOLEAN, boolean=False
)


def _deferred(node: Expression, function: EquationFunction) -> bool:
    return (
        function.stage is EvaluationStage.AFTER_AFFINE
        and function.code not in PERIODWISE
        and function.code not in REDUCTIONS
        and function.form is Form.FUNCTION
        and node.call is not None
        and bool(node.call.arguments)
        and not node.call.named_arguments
    )


def _evaluated(
    node: Expression,
    *,
    function: EquationFunction,
    values: Mapping[UUID, Quantity],
    binding: Binding,
) -> Expression | None:
    """Return the value of a deferred call as a literal, or None without its values."""
    assert node.call is not None
    amounts: dict[Period, Quantity] = {}
    for item in node.call.arguments or ():
        if item.target is None or item.target.target not in values:
            return None
        found = binding.model.resolve(item.target)
        if not isinstance(found, Movement) or found.period is None:
            return None
        amounts[found.period] = values[item.target.target]
    units = next(iter(amounts.values())).units
    flow = Flow(
        units=units,
        amounts={period: amount.to(units=units) for period, amount in amounts.items()},
    )
    name = function.parameters[0].name
    try:
        result = function.evaluate(arguments={name: flow})
    except NumericalError:
        raise  # keeps its code and values, such as ``no_sign_change``
    except (ArithmeticError, ValueError) as error:
        raise NumericalError(str(error)) from error
    if not isinstance(result, Quantity):
        raise UnsupportedError(f"{function.spelling} gave no amount")
    return _literal(result, id=node.id)


__all__ = ["expand", "fixed_irr_flows", "resolve"]

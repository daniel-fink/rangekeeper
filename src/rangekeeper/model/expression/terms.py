"""The Python form of equations: Terms, which operators and equation functions build.

A value handle and a ``Term`` take Python's operators and the Flow methods;
``rangekeeper.expressions`` (``rx``) gives the equation functions (D32). Each
operation makes the Expression records that equation text makes for the same
equation: the parser builds its records with the same functions. A call is
checked when it is written: its arguments by name, kind and units, with
suggestions for a near miss. ``project.equations(...)`` takes a Term as it
takes equation text.
"""

from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from types import MappingProxyType
from typing import Protocol, TypeAlias
from uuid import UUID, uuid4

from rangekeeper.duration import NEVER, Never, Period
from rangekeeper.model.expression.catalogue import functions
from rangekeeper.model.expression.functions import (
    EquationFunction,
    Form,
    FunctionParameter,
)
from rangekeeper.model.expression.rendering import render
from rangekeeper.quantity import Quantity, default_units
from rangekeeper.schema import records
from rangekeeper.schema.enums import (
    DomainKind,
    ExpressionKind,
    Operator,
    ParameterKind,
    ValueKind,
)
from rangekeeper.schema.records import Argument, Call, Expression, Reference
from rangekeeper.schema.runtime import UNSET
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError, UnitError


class Symbol(Protocol):
    """A Value that an equation names: its UUID, key, kind and units."""

    @property
    def id(self) -> UUID:
        """The UUID of the Value."""
        ...

    @property
    def key(self) -> str:
        """The key of the Value."""
        ...

    @property
    def kind(self) -> ValueKind | None:
        """The kind of the Value: a measurement, a Flow or a date.

        None for a value that an equation defines and no call declares: the
        draft works out its kind when it commits (D44).
        """
        ...

    @property
    def units(self) -> str | None:
        """The declared units, or None for a Value without units."""
        ...

    @property
    def periods(self) -> tuple[Period, ...] | None:
        """The declared Periods of a Flow, or None when its equations give them."""
        ...


# The kind of content of a reference to each kind of Value. A Term's kind is
# QUANTITY for every numerical scalar, and None when it is not known.
_REFERENCE_KINDS = {
    ValueKind.MEASUREMENT: DomainKind.QUANTITY,
    ValueKind.FLOW: DomainKind.FLOW,
    ValueKind.DATE: DomainKind.DATE,
}
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
_LOGIC = frozenset({Operator.LOGICAL_AND, Operator.LOGICAL_OR})
# The kinds of argument that each kind of parameter takes.
_ACCEPTS: Mapping[DomainKind, frozenset[DomainKind]] = MappingProxyType(
    {
        DomainKind.QUANTITY: frozenset({DomainKind.QUANTITY}),
        DomainKind.NUMBER: frozenset({DomainKind.QUANTITY}),
        DomainKind.FLOW: frozenset({DomainKind.FLOW}),
        DomainKind.DATE: frozenset({DomainKind.DATE}),
        DomainKind.BOOLEAN: frozenset({DomainKind.BOOLEAN}),
    }
)
_WORDS = {
    DomainKind.QUANTITY: "a value",
    DomainKind.NUMBER: "a number",
    DomainKind.FLOW: "a Flow",
    DomainKind.DATE: "a date",
    DomainKind.BOOLEAN: "a condition",
}


class Symbolic:
    """Python's operators and the Flow methods, which build equations as Terms.

    ``+``, ``-``, ``*``, ``/`` and ``**`` build arithmetic; ``==`` builds an
    equality, and ``!=``, ``<``, ``<=``, ``>`` and ``>=`` comparisons; ``&``,
    ``|`` and ``~`` combine conditions, as ``and``, ``or`` and ``not`` do in
    equation text. Another operand is a handle, a Term, a Quantity, quantity
    text such as ``"2 % pa"``, a number, a ``datetime.date`` or
    ``rk.duration.NEVER``. A Term has no truth value: ``if`` and ``and`` on a
    Term raise TypeError.
    """

    __slots__ = ()

    def _as_term(self) -> "Term":
        raise NotImplementedError

    def __add__(self, other: object) -> "Term":
        return binary(Operator.ADD, self, other)

    def __radd__(self, other: object) -> "Term":
        return binary(Operator.ADD, other, self)

    def __sub__(self, other: object) -> "Term":
        return binary(Operator.SUBTRACT, self, other)

    def __rsub__(self, other: object) -> "Term":
        return binary(Operator.SUBTRACT, other, self)

    def __mul__(self, other: object) -> "Term":
        return binary(Operator.MULTIPLY, self, other)

    def __rmul__(self, other: object) -> "Term":
        return binary(Operator.MULTIPLY, other, self)

    def __truediv__(self, other: object) -> "Term":
        return binary(Operator.DIVIDE, self, other)

    def __rtruediv__(self, other: object) -> "Term":
        return binary(Operator.DIVIDE, other, self)

    def __pow__(self, other: object) -> "Term":
        return binary(Operator.POWER, self, other)

    def __rpow__(self, other: object) -> "Term":
        return binary(Operator.POWER, other, self)

    def __neg__(self) -> "Term":
        return unary(Operator.NEGATE, self)

    def __eq__(self, other: object) -> "Term":  # type: ignore[override]
        return binary(Operator.EQUAL, self, other)

    def __ne__(self, other: object) -> "Term":  # type: ignore[override]
        return binary(Operator.NOT_EQUAL, self, other)

    def __lt__(self, other: object) -> "Term":
        return binary(Operator.LESS_THAN, self, other)

    def __le__(self, other: object) -> "Term":
        return binary(Operator.LESS_THAN_OR_EQUAL, self, other)

    def __gt__(self, other: object) -> "Term":
        return binary(Operator.GREATER_THAN, self, other)

    def __ge__(self, other: object) -> "Term":
        return binary(Operator.GREATER_THAN_OR_EQUAL, self, other)

    def __and__(self, other: object) -> "Term":
        return binary(Operator.LOGICAL_AND, self, other)

    def __rand__(self, other: object) -> "Term":
        return binary(Operator.LOGICAL_AND, other, self)

    def __or__(self, other: object) -> "Term":
        return binary(Operator.LOGICAL_OR, self, other)

    def __ror__(self, other: object) -> "Term":
        return binary(Operator.LOGICAL_OR, other, self)

    def __invert__(self) -> "Term":
        return unary(Operator.LOGICAL_NOT, self)

    def __bool__(self) -> bool:
        raise TypeError(
            "an equation has no truth value; combine conditions with &, | and ~"
        )

    def __hash__(self) -> int:
        return object.__hash__(self)

    # The Flow methods. tools/expressions/generate.py writes this part from
    # the registry; do not edit it by hand.
    # BEGIN GENERATED METHODS
    def at(self, *, on: "Operand") -> "Term":
        """Return the amount of the period that contains a date.

        ``on``: The date.

        Mirrors ``rangekeeper.flow.Flow.at``.
        """
        return call("Flow.at", self, on=on)

    def cumulative(self) -> "Term":
        """Return the running totals of a Flow.

        Mirrors ``rangekeeper.flow.Flow.cumulative``.
        """
        return call("Flow.cumulative", self)

    def diff(self) -> "Term":
        """Return each amount less the amount before it.

        Mirrors ``rangekeeper.flow.Flow.diff``.
        """
        return call("Flow.diff", self)

    def first(self) -> "Term":
        """Return the amount of the first period.

        Mirrors ``rangekeeper.flow.Flow.first``.
        """
        return call("Flow.first", self)

    def last(self) -> "Term":
        """Return the amount of the last period.

        Mirrors ``rangekeeper.flow.Flow.last``.
        """
        return call("Flow.last", self)

    def max(self) -> "Term":
        """Return the largest amount of a Flow.

        Mirrors ``rangekeeper.flow.Flow.max``.
        """
        return call("Flow.max", self)

    def min(self) -> "Term":
        """Return the smallest amount of a Flow.

        Mirrors ``rangekeeper.flow.Flow.min``.
        """
        return call("Flow.min", self)

    def shift(self, *, by: "Operand") -> "Term":
        """Return each period's amount from the period `by` periods away.

        ``by``: A whole number of periods; -1 gives each period the amount of
        the next period.

        Mirrors ``rangekeeper.flow.Flow.shift``.
        """
        return call("Flow.shift", self, by=by)

    def since(self, *, on: "Operand") -> "Term":
        """Return the same periods, with zero before a date.

        ``on``: The date, or NEVER.

        Mirrors ``rangekeeper.flow.Flow.since``.
        """
        return call("Flow.since", self, on=on)

    def total(self) -> "Term":
        """Return the sum of the amounts of a Flow.

        Mirrors ``rangekeeper.flow.Flow.total``.
        """
        return call("Flow.total", self)

    def until(self, *, on: "Operand") -> "Term":
        """Return the same periods, with zero after a date.

        ``on``: The date, or NEVER.

        Mirrors ``rangekeeper.flow.Flow.until``.
        """
        return call("Flow.until", self, on=on)

    # END GENERATED METHODS


class Term(Symbolic):
    """An expression in the Python form of equations, with the records that it makes.

    Operators on handles and Terms, and the ``rx`` functions, make Terms; a
    Term is not made directly. ``text`` is its equation text, which reads
    back to the same records; ``kind`` and ``units`` are what the Term gives,
    when they are known. ``project.equations(term)`` adds a Boolean Term as
    an equation.
    """

    __slots__ = ("_expression", "_kind", "_units", "_names", "_periods", "_amounts")
    _expression: Expression
    _kind: DomainKind | None
    _units: str | None
    _names: Mapping[UUID, str]
    # The Periods of a Flow when the declarations give them; ``_amounts``
    # marks a Flow made from amounts, which takes the Periods of the Flow that
    # its equation defines.
    _periods: tuple[Period, ...] | None
    _amounts: bool

    def __init__(self) -> None:
        raise TypeError("operators, rx functions and value handles make Terms")

    @classmethod
    def _of(
        cls,
        expression: Expression,
        *,
        kind: DomainKind | None,
        units: str | None = None,
        names: Mapping[UUID, str] = MappingProxyType({}),
        shape: "_Shape" = (None, False),
    ) -> "Term":
        term = cls.__new__(cls)
        term._expression = expression
        term._kind = kind
        term._units = units
        term._names = names
        term._periods, term._amounts = shape
        return term

    @property
    def kind(self) -> DomainKind | None:
        """What the Term gives: a value, a Flow, a date or a condition; None if unknown.

        ``DomainKind.QUANTITY`` is every numerical scalar.
        """
        return self._kind

    @property
    def units(self) -> str | None:
        """The units of the Term, when the declarations give them; otherwise None."""
        return self._units

    @property
    def periods(self) -> tuple[Period, ...] | None:
        """The Periods of a Flow, when its declarations give them; otherwise None."""
        return self._periods

    @property
    def text(self) -> str:
        """The equation text of the Term: ``noi = coverage * debt_service``.

        Each value is written by its key. The text reads back to the same
        records.
        """
        return render(
            expression=self._expression,
            name=lambda target: self._names.get(target.target, str(target.target)),
        )

    def to_expression(self) -> Expression:
        """Return the Expression records of the Term, with a new UUID for each node."""
        return _fresh(self._expression)

    def _as_term(self) -> "Term":
        return self

    def __repr__(self) -> str:
        return f"<term {self.text}>"


# Building Terms. The equation text parser builds its records with these
# functions too.


def reference(symbol: Symbol, *, name: str) -> Term:
    """Return the Term of a reference to a Value; ``name`` is how text writes it."""
    return Term._of(
        Expression(
            id=uuid4(),
            kind=ExpressionKind.REFERENCE,
            target=Reference(target=symbol.id),
        ),
        kind=None if symbol.kind is None else _REFERENCE_KINDS.get(symbol.kind),
        units=symbol.units,
        names=MappingProxyType({symbol.id: name}),
        shape=(symbol.periods, False),
    )


def quantity(value: records.Quantity) -> Term:
    """Return the Term of a quantity literal."""
    return Term._of(
        Expression(id=uuid4(), kind=ExpressionKind.QUANTITY, quantity=value),
        kind=DomainKind.QUANTITY,
        units=value.units,
    )


def constant(value: bool | date | Never) -> Term:
    """Return the Term of ``True``, ``False``, a calendar date or NEVER."""
    if isinstance(value, bool):
        return Term._of(
            Expression(id=uuid4(), kind=ExpressionKind.BOOLEAN, boolean=value),
            kind=DomainKind.BOOLEAN,
        )
    if value is NEVER:
        expression = Expression(id=uuid4(), kind=ExpressionKind.DATE, never=NEVER)
    else:
        assert isinstance(value, date)
        expression = Expression(id=uuid4(), kind=ExpressionKind.DATE, date=value)
    return Term._of(expression, kind=DomainKind.DATE)


def operand(value: object) -> Term:
    """Return the Term of a Python value: a handle, a Term, a literal or a date.

    Text is quantity text, such as ``"2 % pa"``; a number is dimensionless.
    Other types raise TypeError; invalid units raise UnitError.
    """
    if isinstance(value, Symbolic):
        return value._as_term()
    if isinstance(value, bool | Never):
        return constant(value)
    if isinstance(value, date) and not isinstance(value, datetime):
        return constant(value)
    if isinstance(value, records.Quantity):
        return _signed(value)
    if isinstance(value, str):
        return _signed(default_units.parse_quantity(value))
    if isinstance(value, int | float):
        return _signed(Quantity(magnitude=float(value), units="dimensionless"))
    raise TypeError(
        f"an equation cannot use a {type(value).__name__}; use a value handle, "
        "a Term, a Quantity, quantity text, a number or a date"
    )


def _signed(value: records.Quantity) -> Term:
    """Return the Term of a Python quantity: a negative one is a negated literal.

    A literal in equation text has no sign, so ``-1`` in text is the negation
    of ``1``; the Python form makes the same records.
    """
    if value.magnitude < 0:
        positive = Quantity(magnitude=-value.magnitude, units=value.units)
        return unary(Operator.NEGATE, quantity(positive))
    return quantity(value)


def unary(operator: Operator, value: object) -> Term:
    """Return the Term of negation or ``not``."""
    term = operand(value)
    negation = operator is Operator.NEGATE
    return Term._of(
        Expression(
            id=uuid4(),
            kind=ExpressionKind.UNARY,
            operator=operator,
            operand=term._expression,
        ),
        kind=term._kind if negation else DomainKind.BOOLEAN,
        units=term._units if negation else None,
        names=term._names,
        shape=(term._periods, term._amounts) if negation else (None, False),
    )


def binary(operator: Operator, left: object, right: object) -> Term:
    """Return the Term of an operator between two operands.

    A Flow applies period by period. Two Flows whose declarations give other
    Periods raise ContractError with the code ``ALIGNMENT_DIFFER``, and an
    equation of a Flow made from amounts, such as a profile, with no Flow
    that gives its Periods raises ContractError with ``EQUATION_FUNCTION``.
    """
    first, second = operand(left), operand(right)
    shape = _combined((first, second))
    if operator in _COMPARISONS:
        _require_periods(shape)
        shape = (None, False)
    return Term._of(
        Expression(
            id=uuid4(),
            kind=ExpressionKind.BINARY,
            operator=operator,
            operands=(first._expression, second._expression),
        ),
        kind=_binary_kind(operator, first, second),
        units=_binary_units(operator, first, second),
        names=_merged(first, second),
        shape=shape,
    )


def call(code: str, /, *arguments: object, **named: object) -> Term:
    """Return the Term of a call of the equation function or Flow method ``code``.

    ``code`` is ``rx.<name>`` for a function and ``Flow.<name>`` for a method,
    whose first argument is the Flow. The arguments are bound and checked
    when the call is written: an unknown or missing argument, an argument
    given twice or by position where only a name is accepted, and an
    argument of the wrong kind or units raise ContractError with the code
    ``EQUATION_FUNCTION`` or ``UNITS``, and ``suggestions`` in ``values``.
    """
    function = _function(code)
    positional = [operand(item) for item in arguments]
    by_name = {name: operand(item) for name, item in named.items()}
    return apply(function, positional=positional, named=by_name)


def apply(
    function: EquationFunction,
    *,
    positional: Sequence[Term],
    named: Mapping[str, Term],
) -> Term:
    """Return the Term of a call of ``function`` with Terms as its arguments.

    The arguments are bound and checked as for ``call``. The records give
    each argument that a call can give by position as a positional argument,
    in signature order, and every other argument by name, so the same call
    makes the same records however its arguments are written.
    """
    bound = _bind(function, positional, named)
    for parameter in function.parameters:
        if parameter.name in bound:
            _check(function, parameter, bound[parameter.name])
    ordered = [p for p in function.parameters if p.name in bound]
    leading = _leading(function, bound)
    expression = Expression(
        id=uuid4(),
        kind=ExpressionKind.CALL,
        call=Call(
            function=function.id,
            arguments=tuple(bound[p.name]._expression for p in leading) or UNSET,
            named_arguments=tuple(
                Argument(name=p.name, expression=bound[p.name]._expression)
                for p in ordered
                if p not in leading
            )
            or UNSET,
        ),
    )
    kind = _call_kind(function, bound)
    return Term._of(
        expression,
        kind=kind,
        units=_call_units(function, bound),
        names=_merged(*bound.values()),
        shape=_call_shape(function, bound)
        if kind is DomainKind.FLOW
        else (None, False),
    )


def given(**arguments: object) -> dict[str, object]:
    """Return the arguments that are not None: the optional arguments of a call."""
    return {name: value for name, value in arguments.items() if value is not None}


# Private helpers.


def _function(code: str) -> EquationFunction:
    prefix, _, name = code.partition(".")
    if prefix == "Flow":
        return functions.method(name=name)
    return functions.function(name=name)


def _misuse(
    message: str,
    *,
    function: EquationFunction,
    argument: str | None = None,
    suggestions: Iterable[str] = (),
    code: Code = Code.EQUATION_FUNCTION,
) -> ContractError:
    values: dict[str, object] = {
        "function": function.code,
        "suggestions": list(suggestions),
    }
    if argument is not None:
        values["argument"] = argument
    return ContractError(message, code=code, values=values)


def _bind(
    function: EquationFunction,
    positional: Sequence[Term],
    named: Mapping[str, Term],
) -> dict[str, Term]:
    """Bind the arguments of a call to the parameters of ``function``, by position and by name."""
    accepts = [
        p for p in function.parameters if p.call is ParameterKind.POSITIONAL_OR_NAMED
    ]
    if len(positional) > len(accepts):
        names = [p.name for p in function.parameters if p not in accepts]
        message = (
            f"{function.spelling} takes its arguments by name (D14)"
            if names
            else f"{function.spelling} takes {len(accepts)} arguments, not "
            f"{len(positional)}"
        )
        raise _misuse(
            message, function=function, suggestions=[f"{name}=" for name in names]
        )
    bound = {p.name: term for p, term in zip(accepts, positional, strict=False)}
    for name, term in named.items():
        function.parameter(name=name)
        if name in bound:
            raise _misuse(
                f"argument {name!r} of {function.spelling} is given twice",
                function=function,
                argument=name,
            )
        bound[name] = term
    missing = [
        p.name for p in function.parameters if p.required and p.name not in bound
    ]
    if missing:
        raise _misuse(
            f"{function.spelling} needs the argument {missing[0]!r}",
            function=function,
            argument=missing[0],
            suggestions=[f"{name}=" for name in missing],
        )
    return bound


def _check(
    function: EquationFunction,
    parameter: FunctionParameter,
    term: Term,
) -> None:
    """Require an argument of the kind and the units that its parameter takes."""
    accepted = _ACCEPTS.get(parameter.kind, frozenset())
    if parameter.name in function.periodwise:
        accepted = accepted | {DomainKind.FLOW}
    if term._kind is not None and term._kind not in accepted:
        subject = function.form is Form.METHOD and parameter is function.parameters[0]
        message = (
            f"{function.name}() is a method of a Flow, not of "
            f"{_WORDS.get(term._kind, 'this value')}"
            if subject
            else f"argument {parameter.name!r} of {function.spelling} takes "
            f"{_WORDS[parameter.kind]}, not {_WORDS.get(term._kind, 'this value')}"
        )
        raise _misuse(message, function=function, argument=parameter.name)
    if parameter.units is None or term._units is None:
        return
    try:
        compatible = default_units.compatible(parameter.units, term._units)
    except UnitError:
        compatible = False
    if not compatible:
        raise _misuse(
            f"argument {parameter.name!r} of {function.spelling} takes units like "
            f"{parameter.units!r}, not {term._units!r}",
            function=function,
            argument=parameter.name,
            code=Code.UNITS,
        )


def _leading(
    function: EquationFunction, bound: Mapping[str, Term]
) -> list[FunctionParameter]:
    """Return the parameters that the records give by position: the leading run."""
    leading = []
    for parameter in function.parameters:
        if parameter.call is not ParameterKind.POSITIONAL_OR_NAMED:
            break
        if parameter.name not in bound:
            break
        leading.append(parameter)
    return leading


def _call_kind(
    function: EquationFunction, bound: Mapping[str, Term]
) -> DomainKind | None:
    lifted = any(
        bound[name]._kind is DomainKind.FLOW
        for name in function.periodwise
        if name in bound
    )
    return DomainKind.FLOW if lifted else function.result


def _call_units(function: EquationFunction, bound: Mapping[str, Term]) -> str | None:
    return function.units(arguments={name: term._units for name, term in bound.items()})


def _combined(terms: Sequence[Term]) -> "_Shape":
    """Return the shape of Flows that combine period by period; they need one set of Periods."""
    known = [t._periods for t in terms if t._periods is not None]
    for other in known[1:]:
        if other != known[0]:
            raise ContractError(
                "Flows with different Periods do not combine: "
                f"{_span(known[0])} and {_span(other)}",
                code=Code.ALIGNMENT_DIFFER,
                values={"periods": [len(known[0]), len(other)]},
            )
    if known:
        return known[0], False
    return None, any(t._amounts for t in terms)


def _require_periods(shape: "_Shape") -> None:
    """Require Periods for a Flow made from amounts in an equation (D44)."""
    if shape[1]:
        raise ContractError(
            "a Flow made from amounts takes the Periods of the Flow that its "
            "equation defines; declare that Flow with periods=",
            code=Code.EQUATION_FUNCTION,
        )


def _call_shape(function: EquationFunction, bound: Mapping[str, Term]) -> "_Shape":
    if function.periods_from is not None:
        source = bound[function.periods_from]
        return source._periods, source._amounts
    lifted = [bound[name] for name in function.periodwise if name in bound]
    if lifted:
        return _combined(lifted)
    return None, True


def _span(periods: tuple[Period, ...]) -> str:
    if not periods:
        return "no Periods"
    return f"{periods[0].start.isoformat()} to {periods[-1].end.isoformat()}"


def _binary_kind(operator: Operator, left: Term, right: Term) -> DomainKind | None:
    if operator in _COMPARISONS or operator in _LOGIC:
        return DomainKind.BOOLEAN
    kinds = {left._kind, right._kind}
    for kind in (DomainKind.DATE, DomainKind.FLOW):
        if kind in kinds:
            return kind
    return None if None in kinds else DomainKind.QUANTITY


def _binary_units(operator: Operator, left: Term, right: Term) -> str | None:
    if operator not in (Operator.ADD, Operator.SUBTRACT):
        return None
    if DomainKind.DATE in (left._kind, right._kind):
        return None
    return left._units if left._units is not None else right._units


def _merged(*terms: Term) -> Mapping[UUID, str]:
    names: dict[UUID, str] = {}
    for term in terms:
        names.update(term._names)
    return MappingProxyType(names)


def _fresh(expression: Expression) -> Expression:
    """Return a copy of the records with a new UUID for each Expression node."""

    def visit(data: object) -> object:
        if isinstance(data, dict):
            return {
                key: str(uuid4()) if key == "id" else visit(item)
                for key, item in data.items()
            }
        if isinstance(data, list):
            return [visit(item) for item in data]
        return data

    data = visit(expression.to_data())
    assert isinstance(data, dict)
    fresh = Expression.from_data(data)
    assert isinstance(fresh, Expression)
    return fresh


# The Periods of a Flow, if known, and whether it is a Flow made from amounts.
_Shape: TypeAlias = tuple[tuple[Period, ...] | None, bool]
Operand: TypeAlias = Symbolic | Quantity | str | int | float | date | Never
"""What an equation operator or function takes: a handle, a Term, a Quantity,
quantity text, a number, a date or NEVER."""


__all__ = [
    "Operand",
    "Symbol",
    "Symbolic",
    "Term",
    "apply",
    "binary",
    "call",
    "constant",
    "given",
    "operand",
    "quantity",
    "reference",
    "unary",
]

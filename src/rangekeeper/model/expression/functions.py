"""The registry of equation functions: each function that an equation can call.

Each equation function is declared once, in an ``EquationFunction``
(ADR-015, D32): its name, its parameters with their kinds and units, its
result, its evaluation stage, its availability rule and the value function
that it mirrors. The equation text parser, ``rangekeeper.expressions``
(``rx``) and the function table of the expressions reference are made from
these declarations.

A function is called as ``rx.<name>(...)``, such as ``rx.max(a, b)``. A method
is called on a Flow, such as ``operating.at(on=sale_date)``. In records, a
call is a ``call`` Expression whose Function record the registry makes: the
same function always has the same Function UUID.
"""

from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from difflib import get_close_matches
from enum import StrEnum
from typing import TypeAlias
from uuid import NAMESPACE_URL, UUID, uuid5

from rangekeeper.duration import Never, Period
from rangekeeper.flow import Flow
from rangekeeper.quantity import Quantity
from rangekeeper.schema.enums import DomainKind, ParameterKind
from rangekeeper.schema.records import Domain, Function, Parameter
from rangekeeper.shared.codes import Code
from rangekeeper.shared.errors import ContractError

# The content that an equation function takes and gives on fixed data.
Content: TypeAlias = Quantity | Flow | date | Never | bool
# The UUID namespace of the Function records that the registry makes.
NAMESPACE = uuid5(NAMESPACE_URL, "https://daniel-fink.github.io/rangekeeper/functions")
# The namespace of equation functions in text and in Python (D21).
PREFIX = "rx"


class Form(StrEnum):
    """How an equation calls a function."""

    FUNCTION = "function"
    """A function in the ``rx`` namespace, such as ``rx.max(a, b)``."""
    METHOD = "method"
    """A method of a Flow, such as ``operating.at(on=sale_date)``."""


class EvaluationStage(StrEnum):
    """When the solve evaluates a function (D4)."""

    AFFINE = "affine"
    """In the affine stage: the function is linear in its unknown arguments
    once its other arguments are fixed."""
    AFTER_AFFINE = "after_affine"
    """After the affine stage, from determined values, and checked by
    verification. A fixed result can become an affine row (D5)."""


class Availability(StrEnum):
    """When a result is known, from when its arguments are known.

    A rule reads only values that are known on its date (G53).
    """

    PERIODWISE = "periodwise"
    """A period's result is known when the arguments' amounts in that period
    are known. A scalar function is periodwise."""
    RUNNING = "running"
    """A period's result is known when the arguments' amounts up to that
    period are known."""
    SHIFTED = "shifted"
    """A period's result is known when the arguments' amounts ``by`` periods
    away are known."""
    COMPLETE = "complete"
    """The result is known when every amount of the arguments is known."""


@dataclass(frozen=True, slots=True, kw_only=True)
class FunctionParameter:
    """A parameter of an equation function: its name, kind, units and use.

    ``kind`` is the kind of content that the argument gives, such as
    ``DomainKind.FLOW`` or ``DomainKind.DATE``; ``DomainKind.QUANTITY``
    accepts any numerical scalar. ``units`` are units whose dimension the
    argument must have, such as ``"% pa"`` for a rate; None accepts any
    units. ``call`` says how a call gives the argument: by name only, as
    most functions do (D14), or by position too, as ``rx.max`` does.
    """

    name: str
    kind: DomainKind
    description: str
    units: str | None = None
    required: bool = True
    call: ParameterKind = ParameterKind.NAMED_ONLY

    def record(self) -> Parameter:
        """Return the Parameter record of this parameter."""
        return Parameter(
            name=self.name,
            domain=Domain(kind=self.kind),
            kind=self.call,
            required=self.required,
        )


# The value function of an equation function: it takes the arguments by
# parameter name, with the Periods of the Flow that the call defines.
Evaluator: TypeAlias = Callable[
    [Mapping[str, Content], Sequence[Period] | None], Content
]


@dataclass(frozen=True, slots=True, kw_only=True)
class EquationFunction:
    """One equation function: its signature, its stage, and what it mirrors.

    ``name`` is the name after ``rx.`` for a function, such as
    ``"finance.npv"``, and the method name for a method, such as ``"at"``.
    A method's first parameter is the Flow that it is called on.
    ``periodwise`` names the parameters that take a value or a Flow: a Flow
    there applies the function period by period, so ``rx.max(0 AUD, need)``
    is a Flow when ``need`` is a Flow. ``mirrors`` names the value function that gives the
    same result on fixed data, such as ``rangekeeper.finance.npv``.
    ``result_units`` are the units of every result, such as ``"% pa"``;
    otherwise ``units_from`` names the parameter whose units give the result's
    units, when it has them: the same units, or the units that ``units_of``
    makes of them, such as ``AUD`` for each Period of a profile of an amount in
    ``AUD pa``. ``units(arguments=)`` applies the rule. A Flow result has the Periods of the parameter that
    ``periods_from`` names, or of its periodwise Flows; a function with neither
    makes a Flow from amounts, over the Periods of the Flow that it defines.
    """

    name: str
    form: Form
    summary: str
    parameters: tuple[FunctionParameter, ...]
    result: DomainKind
    stage: EvaluationStage
    availability: Availability
    mirrors: str
    unit_rule: str
    evaluator: Evaluator = field(repr=False, compare=False)
    result_units: str | None = None
    units_from: str | None = None
    units_of: Callable[[str], str] | None = field(
        default=None, repr=False, compare=False
    )
    periods_from: str | None = None
    periodwise: tuple[str, ...] = ()
    version: str = "1"

    @property
    def code(self) -> str:
        """The code of the Function record: ``rx.<name>`` or ``Flow.<name>``."""
        return (
            f"{PREFIX}.{self.name}"
            if self.form is Form.FUNCTION
            else (f"Flow.{self.name}")
        )

    @property
    def id(self) -> UUID:
        """The UUID of the Function record, the same in every Model."""
        return uuid5(NAMESPACE, f"{self.code}/{self.version}")

    def parameter(self, *, name: str) -> FunctionParameter:
        """Return the parameter with this name; an unknown name raises ContractError."""
        for item in self.parameters:
            if item.name == name:
                return item
        shown = self.parameters[1:] if self.form is Form.METHOD else self.parameters
        names = [item.name for item in shown]
        raise ContractError(
            f"{self.spelling} has no argument {name!r}",
            code=Code.EQUATION_FUNCTION,
            values={
                "function": self.code,
                "argument": name,
                "suggestions": get_close_matches(name, names, n=3) or names,
            },
        )

    @property
    def spelling(self) -> str:
        """How an equation writes the call, such as ``rx.max(...)`` or ``x.at(...)``."""
        return f"{self.code}()" if self.form is Form.FUNCTION else f"x.{self.name}()"

    def record(self) -> Function:
        """Return the Function record that a Model stores for this function."""
        return Function(
            id=self.id,
            code=self.code,
            name=self.summary,
            version=self.version,
            parameters=tuple(item.record() for item in self.parameters) or None,
            result=Domain(kind=self.result),
            semantics=f"{self.summary} Mirrors {self.mirrors}.",
            unit_rule=self.unit_rule,
        )

    def units(self, *, arguments: Mapping[str, str | None]) -> str | None:
        """Return the units of the result from the units of the arguments, or None.

        ``arguments`` gives the units of each argument by parameter name, or
        None when they are unknown.
        """
        if self.result_units is not None:
            return self.result_units
        source = None if self.units_from is None else arguments.get(self.units_from)
        if source is None:
            return None
        return source if self.units_of is None else self.units_of(source)

    def evaluate(
        self,
        *,
        arguments: Mapping[str, Content],
        periods: Sequence[Period] | None = None,
    ) -> Content:
        """Return the result on fixed arguments, from the value function it mirrors.

        ``arguments`` gives each argument by parameter name. ``periods`` are the
        Periods of the Flow that the call defines, for a function that makes a
        Flow from amounts.
        """
        return self.evaluator(arguments, periods)


class EquationFunctions:
    """Equation functions by code; ``catalogue.functions`` holds the built-ins.

    ``extension`` returns the equation function of a name that is not
    registered, such as a profile that an installed distribution registers,
    or None; the registry then holds it too.
    """

    __slots__ = ("_entries", "_ids", "_extension")

    def __init__(
        self,
        *,
        extension: Callable[[str], EquationFunction | None] | None = None,
    ) -> None:
        self._entries: dict[str, EquationFunction] = {}
        self._ids: dict[UUID, EquationFunction] = {}
        self._extension = extension

    def register(self, function: EquationFunction) -> EquationFunction:
        """Add an equation function and return it; a code in use raises ContractError."""
        if not isinstance(function, EquationFunction):
            raise TypeError("function must be an EquationFunction")
        if function.code in self._entries:
            raise ContractError(
                f"the equation function {function.code!r} is registered",
                code=Code.EXTENSION_CONFLICT,
                values={"function": function.code},
            )
        self._entries[function.code] = function
        self._ids[function.id] = function
        return function

    def function(self, *, name: str) -> EquationFunction:
        """Return the function ``rx.<name>``; an unknown name raises ContractError."""
        code = f"{PREFIX}.{name}"
        if code not in self._entries and self._extension is not None:
            found = self._extension(name)
            if found is not None and found.code == code:
                self.register(found)
        return self._find(code, form=Form.FUNCTION)

    def method(self, *, name: str) -> EquationFunction:
        """Return the Flow method ``name``; an unknown name raises ContractError."""
        return self._find(f"Flow.{name}", form=Form.METHOD)

    def get(self, id: UUID) -> EquationFunction | None:
        """Return the equation function of a Function UUID, or None for another Function."""
        return self._ids.get(id)

    def __iter__(self) -> Iterator[EquationFunction]:
        # Functions first, then methods, each by code.
        return iter(
            sorted(
                self._entries.values(),
                key=lambda item: (item.form is Form.METHOD, item.code),
            )
        )

    def __len__(self) -> int:
        return len(self._entries)

    def _find(self, code: str, *, form: Form) -> EquationFunction:
        found = self._entries.get(code)
        if found is not None:
            return found
        # Compare the names as text writes them: ``rx.max``, or ``at``.
        spelled = code if form is Form.FUNCTION else code.removeprefix("Flow.")
        known = [
            item.code if form is Form.FUNCTION else item.name
            for item in self._entries.values()
            if item.form is form
        ]
        kind = "equation function" if form is Form.FUNCTION else "Flow method"
        raise ContractError(
            f"{spelled!r} is not an {kind}",
            code=Code.EQUATION_FUNCTION,
            values={
                "function": code,
                "suggestions": get_close_matches(spelled, known, n=3, cutoff=0.6),
            },
        )


__all__ = [
    "Availability",
    "Content",
    "EquationFunction",
    "EquationFunctions",
    "EvaluationStage",
    "Evaluator",
    "Form",
    "FunctionParameter",
]

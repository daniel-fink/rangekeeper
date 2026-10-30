"""Stage 7: verify a serialized candidate independently against the original mathematics."""

import math
from collections.abc import Iterator, Mapping, Set
from dataclasses import dataclass
from uuid import UUID

from rangekeeper.duration.dates import NEVER, DateValue
from rangekeeper.execution.dates import decide
from rangekeeper.execution.errors import NumericalError, UnsupportedError
from rangekeeper.execution.expansion import resolve
from rangekeeper.execution.piecewise import Pieces
from rangekeeper.execution.preparation import Assertion, Binding
from rangekeeper.model import Model
from rangekeeper.model.expression.evaluation import (
    evaluate,
    finite_quantity,
)
from rangekeeper.model.targets import recorded_scalar
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.run import Severity
from rangekeeper.run._rule.predicate import evaluate as truth
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import (
    Diagnostic,
    Expression,
    ExpressionKind,
    Operator,
    Reference,
)
from rangekeeper.shared.codes import Code


@dataclass(frozen=True, kw_only=True)
class Tolerances:
    """Acceptance policy, distinct from Specification convergence/solver settings.

    Each comparison uses absolute + relative * max(abs(left), abs(right)), in
    the evaluated left side's units. The absolute floor is explicitly 1e-8 of
    that unit by default, not a currency-independent monetary tolerance. Every
    diagnostic records its resulting dimensional tolerance and signed residual.
    Boolean assertions and copied assignments are checked exactly.
    """

    absolute: float = 1e-8
    relative: float = 1e-9

    def __post_init__(self) -> None:
        for name in ("absolute", "relative"):
            value = getattr(self, name)
            if isinstance(value, bool) or not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if self.relative >= 1:
            raise ValueError("relative acceptance tolerance must be less than one")


@dataclass(frozen=True, kw_only=True)
class Verification:
    """Whether a candidate passed verification, with the residual diagnostics.

    ``passed`` is true when every assignment, equality and bound holds within
    the tolerances. Verification has no storage side effects.
    """

    passed: bool
    diagnostics: tuple[Diagnostic, ...]


def verify(
    *,
    binding: Binding,
    candidate: Model,
    tolerances: Tolerances = Tolerances(),
) -> Verification:
    """Check exact assignments and every original equality/bound on candidate values.

    Call after codec reconstruction of the proposed Model. This function does not
    use compiled rows, solver feasibility flags, or mutable backend variable values.
    Diagnostics target declarations in the input/contributor revisions so rejected
    candidates never need to be persisted just to support their evidence.
    """
    values = {}
    for id in (*binding.assignments, *binding.unknowns):
        value = recorded_scalar(candidate, binding.references[id])
        if value is None:
            raise NumericalError(f"candidate has no quantity for {id}")
        values[id] = binding.units.convert(quantity=value, to=binding.value_units[id])
    dated = {
        id: _recorded_date(candidate, binding.references[id]) for id in binding.dates
    }
    diagnostics = _date_changes(binding, dated)
    passed = not diagnostics
    pieces = Pieces.of(binding.model)
    for id, assigned in binding.assignments.items():
        if values[id].to_data() != assigned.to_data():
            passed = False
            diagnostics.append(
                Diagnostic(
                    severity=Severity.ERROR,
                    code=Code.ASSIGNMENT_REJECTED.value,
                    message="Candidate changed an explicit assignment.",
                    document=binding.model.id,
                    target=binding.references[id].target,
                    references=(binding.references[id],),
                )
            )
    for assertion in binding.assertions:
        if _reads(assertion.predicate) & dated.keys():
            holds = decide(assertion.predicate, dates=dated, units=binding.units)
            passed &= holds
            diagnostics.append(_date_check(binding, assertion, holds=holds))
            continue
        for relation, left, right, boolean, scale in _comparisons(
            _active(assertion.predicate, pieces=pieces, values=values, binding=binding),
            values,
            units=binding.units,
            fixed=binding.assignments.keys(),
        ):
            residual = left.number - right.number
            tolerance = (
                0.0
                if boolean
                else tolerances.absolute
                + tolerances.relative * max(abs(left.number), abs(right.number), scale)
            )
            if not math.isfinite(residual) or not math.isfinite(tolerance):
                raise NumericalError("acceptance residual or tolerance is not finite")
            valid = (
                residual < 0
                if relation == "less_than"
                else (
                    residual > 0
                    if relation == "greater_than"
                    else (
                        abs(residual) <= tolerance
                        if relation == "equal"
                        else (
                            residual <= tolerance
                            if relation == "less_than_or_equal"
                            else -residual <= tolerance
                        )
                    )
                )
            )
            passed &= valid
            diagnostics.append(
                Diagnostic(
                    severity=Severity.INFO if valid else Severity.ERROR,
                    code=Code.CONSTRAINT_RESIDUAL.value,
                    message=(
                        f"Independent original-expression check: {relation}; signed residual left-right, "
                        f"unscaled in left-side units; tolerance = {tolerances.absolute} + "
                        f"{tolerances.relative} * max(abs(left), abs(right)) (Boolean and fixed strict predicates: exact). "
                        f"Accepted={valid}."
                    ),
                    document=assertion.document,
                    target=assertion.constraint.id,
                    references=tuple(
                        node.target
                        for node, _, _ in walk(assertion.predicate)
                        if isinstance(node, Expression)
                        and node.kind is ExpressionKind.REFERENCE
                        and node.target is not None
                    ),
                    values=_equation_values(binding, assertion),
                    residual=Quantity(magnitude=residual, units=left.units),
                    tolerance=Quantity(magnitude=tolerance, units=left.units),
                )
            )
    return Verification(passed=passed, diagnostics=tuple(diagnostics))


def _equation_values(binding: Binding, assertion: Assertion) -> dict[str, str]:
    """Return the text of an equation and, for a Model equation, its Formulation.

    The Formulation is named by its name, such as ``"Funding"``, or by its
    code for the default Formulation of an entity.
    """
    values = {"equation": binding.text(assertion.predicate)}
    model = binding.model
    if assertion.document != model.id:
        return values
    owner = model.owner_of(assertion.constraint.id)
    if owner is not None:
        formulation = model.formulation(owner)
        group = formulation.name or formulation.code
        if group is not None:
            values["formulation"] = group
    return values


def _active(
    node: Expression,
    *,
    pieces: Pieces,
    values: Mapping[UUID, Quantity],
    binding: Binding,
) -> Expression:
    """Return ``node`` with each ``max`` and ``min`` call at its active side.

    The side is read from the candidate's values, not from the solve, so the
    check of the original equation does not depend on the sides it picked.
    """
    resolved = resolve(node, values=values, binding=binding)
    if resolved is None:
        raise NumericalError("candidate has no quantity for a deferred call")
    try:
        sides = pieces.active(resolved, values=values, units=binding.units)
    except UnsupportedError:
        raise
    except (ArithmeticError, ValueError, TypeError) as error:
        raise NumericalError(str(error)) from error
    return pieces.reduce(resolved, sides)


# The predicates other than strict comparisons that fixed values decide
# exactly. Verification keeps its own list: it does not read the compiler.
_DECIDED = frozenset({Operator.NOT_EQUAL, Operator.LOGICAL_OR, Operator.LOGICAL_NOT})


def _decided(node: Expression) -> bool:
    """Return whether ``node`` is a ``!=``, ``or`` or ``not`` predicate."""
    return (
        node.kind in (ExpressionKind.BINARY, ExpressionKind.UNARY)
        and node.operator in _DECIDED
    )


def _truth(
    node: Expression,
    values: Mapping[UUID, Quantity],
    *,
    units: UnitSystem,
    fixed: Set[UUID],
) -> bool:
    """Decide a ``!=``, ``or`` or ``not`` predicate exactly from its fixed values."""
    if any(
        child.target.target not in fixed
        for child, _, _ in walk(node)
        if isinstance(child, Expression)
        and child.kind is ExpressionKind.REFERENCE
        and child.target is not None
    ):
        raise UnsupportedError(
            "strict comparisons, !=, or and not require only fixed assigned or"
            " literal operands"
        )
    return bool(truth(node, values, units=units))


def _recorded_date(candidate: Model, reference: Reference) -> DateValue:
    """Return the date or NEVER that the candidate records for a date Value."""
    value = candidate.value(id=reference.target)
    if value.never is not None:
        return NEVER
    if value.date is None:
        raise NumericalError(f"candidate has no date for {reference.target}")
    return value.date


def _date_changes(
    binding: Binding, dated: Mapping[UUID, DateValue]
) -> list[Diagnostic]:
    """Return a diagnostic for each fixed or determined date that the candidate changed."""
    return [
        _changed(binding, id)
        for id, fixed in binding.dates.items()
        if dated[id] != fixed
    ]


def _changed(binding: Binding, id: UUID) -> Diagnostic:
    return Diagnostic(
        severity=Severity.ERROR,
        code=Code.ASSIGNMENT_REJECTED.value,
        message="Candidate changed a fixed or determined date.",
        document=binding.model.id,
        target=binding.references[id].target,
        references=(binding.references[id],),
    )


def _date_check(binding: Binding, assertion: Assertion, *, holds: bool) -> Diagnostic:
    """Return the exact check of an equation over dates (#280)."""
    zero = Quantity(magnitude=0, units="dimensionless")
    return Diagnostic(
        severity=Severity.INFO if holds else Severity.ERROR,
        code=Code.CONSTRAINT_RESIDUAL.value,
        message=f"Independent original-expression check of dates: exact. Accepted={holds}.",
        document=assertion.document,
        target=assertion.constraint.id,
        references=tuple(Reference(target=id) for id in _reads(assertion.predicate)),
        values=_equation_values(binding, assertion),
        residual=Quantity(magnitude=0 if holds else 1, units="dimensionless"),
        tolerance=zero,
    )


def _reads(node: Expression) -> set[UUID]:
    return {
        child.target.target
        for child, _, _ in walk(node)
        if isinstance(child, Expression)
        and child.kind is ExpressionKind.REFERENCE
        and child.target is not None
    }


def _largest(
    node: Expression,
    values: Mapping[UUID, Quantity],
    *,
    units: UnitSystem,
    to: str,
) -> float:
    """Return the largest magnitude of the terms of a sum, in the units ``to``.

    A currency amount has 15 significant digits (ADR-023), so a sum of large
    amounts that cancel, such as a cash flow that a loan draw offsets, keeps a
    residual of the order of ``1e-15`` times its largest term. The relative
    tolerance reads that term.
    """
    if node.kind is ExpressionKind.BINARY and node.operator in (
        Operator.ADD,
        Operator.SUBTRACT,
    ):
        return max(
            _largest(item, values, units=units, to=to) for item in node.operands or ()
        )
    if node.kind is ExpressionKind.UNARY and node.operator is Operator.NEGATE:
        assert node.operand is not None
        return _largest(node.operand, values, units=units, to=to)
    value = evaluate(node, values, units=units)
    return abs(units.convert(quantity=value, to=to).number)


def _comparisons(
    node: Expression,
    values: Mapping[UUID, Quantity],
    *,
    units: UnitSystem,
    fixed: Set[UUID] = frozenset(),
) -> Iterator[tuple[str, Quantity, Quantity, bool, float]]:
    """Retain conjunction order; fixed strict predicates use exact comparison.

    A ``!=``, ``or`` or ``not`` predicate of fixed values is decided exactly,
    as a Boolean constant. Each comparison gives its relation, both sides,
    whether it is exact, and the largest term of a sum on either side
    (``_largest``), in the left side's units.
    """
    try:
        if node.kind is ExpressionKind.BOOLEAN or _decided(node):
            holds = (
                node.boolean
                if node.kind is ExpressionKind.BOOLEAN
                else _truth(node, values, units=units, fixed=fixed)
            )
            yield (
                "equal",
                finite_quantity(0 if holds else 1, "dimensionless"),
                finite_quantity(0, "dimensionless"),
                True,
                0.0,
            )
        elif (
            node.kind is ExpressionKind.BINARY and node.operator is Operator.LOGICAL_AND
        ):
            if node.operands is None or len(node.operands) != 2:
                raise UnsupportedError("conjunction requires two operands")
            for child in node.operands:
                yield from _comparisons(child, values, units=units, fixed=fixed)
        elif node.kind is ExpressionKind.BINARY and node.operator in (
            Operator.EQUAL,
            Operator.LESS_THAN_OR_EQUAL,
            Operator.GREATER_THAN_OR_EQUAL,
            Operator.LESS_THAN,
            Operator.GREATER_THAN,
        ):
            if node.operands is None or len(node.operands) != 2:
                raise UnsupportedError("comparison requires two operands")
            strict = node.operator in (Operator.LESS_THAN, Operator.GREATER_THAN)
            if strict and any(
                child.target.target not in fixed
                for child, _, _ in walk(node)
                if isinstance(child, Expression)
                and child.kind is ExpressionKind.REFERENCE
                and child.target is not None
            ):
                raise UnsupportedError(
                    "strict predicates require only fixed assigned or literal operands"
                )
            left = evaluate(node.operands[0], values, units=units)
            right = units.convert(
                quantity=evaluate(node.operands[1], values, units=units), to=left.units
            )
            scale = max(
                _largest(item, values, units=units, to=left.units)
                for item in node.operands
            )
            yield node.operator.value, left, right, strict, scale
        else:
            raise UnsupportedError("unsupported predicate in numerical acceptance")
    except UnsupportedError:
        raise
    except (ArithmeticError, ValueError, TypeError) as error:
        raise NumericalError(str(error)) from error

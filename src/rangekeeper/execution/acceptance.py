"""Stage 7: verify a serialized candidate independently against the original mathematics."""

import math
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID

from rangekeeper.execution.errors import NumericalError, UnsupportedError
from rangekeeper.execution.preparation import Binding
from rangekeeper.model import Model
from rangekeeper.model.expression.evaluation import (
    evaluate,
    finite_quantity,
)
from rangekeeper.model.targets import recorded_scalar
from rangekeeper.quantity import Quantity, UnitSystem
from rangekeeper.run import Severity
from rangekeeper.schema.index import walk
from rangekeeper.schema.records import (
    Diagnostic,
    Expression,
    ExpressionKind,
    Operator,
)
from rangekeeper.shared.codes import Code


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class Verification:
    """Whether a candidate passed verification, with the residual diagnostics.

    ``passed`` is true when every assignment, equality and bound holds within
    the tolerances. Verification has no storage side effects.
    """

    passed: bool
    diagnostics: tuple[Diagnostic, ...]


def verify(
    binding: Binding, candidate: Model, *, tolerances: Tolerances = Tolerances()
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
        values[id] = binding.units.convert(value, to=binding.value_units[id])
    diagnostics = []
    passed = True
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
        for relation, left, right, boolean in _comparisons(
            assertion.predicate,
            values,
            units=binding.units,
            fixed=binding.assignments.keys(),
        ):
            residual = left.number - right.number
            tolerance = (
                0.0
                if boolean
                else tolerances.absolute
                + tolerances.relative * max(abs(left.number), abs(right.number))
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
                    values={"equation": binding.text(assertion.predicate)},
                    residual=Quantity(magnitude=residual, units=left.units),
                    tolerance=Quantity(magnitude=tolerance, units=left.units),
                )
            )
    return Verification(passed, tuple(diagnostics))


def _comparisons(
    node: Expression,
    values: Mapping[UUID, Quantity],
    *,
    units: UnitSystem,
    fixed=frozenset(),
):
    """Retain conjunction order; fixed strict predicates use exact comparison."""
    try:
        if node.kind is ExpressionKind.BOOLEAN:
            yield (
                "equal",
                finite_quantity(0 if node.boolean else 1, "dimensionless"),
                finite_quantity(0, "dimensionless"),
                True,
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
                evaluate(node.operands[1], values, units=units), to=left.units
            )
            yield node.operator.value, left, right, strict
        else:
            raise UnsupportedError("unsupported predicate in numerical acceptance")
    except UnsupportedError:
        raise
    except (ArithmeticError, ValueError, TypeError) as error:
        raise NumericalError(str(error)) from error

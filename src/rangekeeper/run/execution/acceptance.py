"""Independently check proposed serialized quantities against original mathematics."""

from rangekeeper.run import Severity

from dataclasses import dataclass
from collections.abc import Mapping
from uuid import UUID
import math

from rangekeeper.model import Model
from rangekeeper.schema.records import Diagnostic, Quantity
from rangekeeper.run.execution.preparation import Prepared
from rangekeeper.run.execution.errors import NumericalError, UnsupportedProblem
from rangekeeper.model.scope import recorded_scalar
from rangekeeper.schema.records import Expression, ExpressionKind, Operator
from rangekeeper.schema.index import walk
from rangekeeper.model.expression.evaluation import (
    evaluate,
    finite_quantity,
    UnsupportedExpression,
)
from rangekeeper.shared.units import UnitSystem


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
class Acceptance:
    """Numerical outcome with evidence; no storage side effects."""

    accepted: bool
    diagnostics: tuple[Diagnostic, ...]


def check(
    prepared: Prepared, candidate: Model, *, tolerances: Tolerances = Tolerances()
) -> Acceptance:
    """Check exact assignments and every original equality/bound on candidate values.

    Call after codec reconstruction of the proposed Model. This function does not
    use compiled rows, solver feasibility flags, or mutable backend variable values.
    Diagnostics target declarations in the input/contributor revisions so rejected
    candidates never need to be persisted just to support their evidence.
    """
    values = {}
    for id in (*prepared.assignments, *prepared.unknowns):
        value = recorded_scalar(candidate, prepared.references[id])
        if value is None:
            raise NumericalError(f"candidate has no quantity for {id}")
        values[id] = prepared.units.convert(value, to=prepared.value_units[id])
    diagnostics = []
    accepted = True
    for id, assigned in prepared.assignments.items():
        if values[id].to_data() != assigned.to_data():
            accepted = False
            diagnostics.append(
                Diagnostic(
                    severity=Severity.ERROR,
                    code="assignment_rejected",
                    message="Candidate changed an explicit assignment.",
                    document=prepared.model.id,
                    target=prepared.references[id].target,
                    references=(prepared.references[id],),
                )
            )
    for assertion in prepared.assertions:
        for relation, left, right, boolean in _comparisons(
            assertion.predicate,
            values,
            units=prepared.units,
            fixed=prepared.assignments.keys(),
        ):
            residual = float(left.magnitude - right.magnitude)
            tolerance = (
                0.0
                if boolean
                else tolerances.absolute
                + tolerances.relative
                * max(abs(float(left.magnitude)), abs(float(right.magnitude)))
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
            accepted &= valid
            diagnostics.append(
                Diagnostic(
                    severity=Severity.INFO if valid else Severity.ERROR,
                    code="constraint_residual",
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
                    residual=Quantity(magnitude=residual, units=left.units),
                    tolerance=Quantity(magnitude=tolerance, units=left.units),
                )
            )
    return Acceptance(accepted, tuple(diagnostics))


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
            yield "equal", finite_quantity(
                0 if node.boolean else 1, "dimensionless"
            ), finite_quantity(0, "dimensionless"), True
        elif (
            node.kind is ExpressionKind.BINARY and node.operator is Operator.LOGICAL_AND
        ):
            if node.operands is None or len(node.operands) != 2:
                raise UnsupportedProblem("conjunction requires two operands")
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
                raise UnsupportedProblem("comparison requires two operands")
            strict = node.operator in (Operator.LESS_THAN, Operator.GREATER_THAN)
            if strict and any(
                child.target.target not in fixed
                for child, _, _ in walk(node)
                if isinstance(child, Expression)
                and child.kind is ExpressionKind.REFERENCE
                and child.target is not None
            ):
                raise UnsupportedProblem(
                    "strict predicates require only fixed assigned or literal operands"
                )
            left = evaluate(node.operands[0], values, units=units)
            right = units.convert(
                evaluate(node.operands[1], values, units=units), to=left.units
            )
            yield node.operator.value, left, right, strict
        else:
            raise UnsupportedProblem("unsupported predicate in numerical acceptance")
    except UnsupportedExpression as error:
        raise UnsupportedProblem(str(error)) from error
    except UnsupportedProblem:
        raise
    except (ArithmeticError, ValueError, TypeError) as error:
        raise NumericalError(str(error)) from error

"""Independently check proposed serialized quantities against original mathematics."""

from dataclasses import dataclass
import math

from ..model import Model
from .._schema.records import Diagnostic, Quantity
from .preparation import Prepared
from .evaluator import comparisons
from .errors import NumericalError


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
        value = candidate.value(id)
        if value.quantity is None:
            raise NumericalError(f"candidate has no quantity for {id}")
        values[id] = prepared.units.convert(value.quantity, to=prepared.value_units[id])
    diagnostics = []
    accepted = True
    for id, assigned in prepared.assignments.items():
        if values[id].to_data() != assigned.to_data():
            accepted = False
            diagnostics.append(
                Diagnostic(
                    severity="error",
                    code="assignment_rejected",
                    message="Candidate changed an explicit assignment.",
                    document=prepared.model.id,
                    target=id,
                )
            )
    for assertion in prepared.assertions:
        for relation, left, right, boolean in comparisons(
            assertion.predicate, values, units=prepared.units
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
                abs(residual) <= tolerance
                if relation == "equal"
                else (
                    residual <= tolerance
                    if relation == "less_than_or_equal"
                    else -residual <= tolerance
                )
            )
            accepted &= valid
            diagnostics.append(
                Diagnostic(
                    severity="info" if valid else "error",
                    code="constraint_residual",
                    message=(
                        f"Independent original-expression check: {relation}; signed residual left-right, "
                        f"unscaled in left-side units; tolerance = {tolerances.absolute} + "
                        f"{tolerances.relative} * max(abs(left), abs(right)) (Boolean: exact). "
                        f"Accepted={valid}."
                    ),
                    document=assertion.document,
                    target=assertion.constraint.id,
                    residual=Quantity(magnitude=residual, units=left.units),
                    tolerance=Quantity(magnitude=tolerance, units=left.units),
                )
            )
    return Acceptance(accepted, tuple(diagnostics))

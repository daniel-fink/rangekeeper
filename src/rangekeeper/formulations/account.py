"""Signed account continuity and the explicit nonnegative-principal interest case."""

from uuid import UUID
from ..model import Model
from .._schema.records import Formulation, ValueReference, Expression
from .flow import build_accumulation
from ._alignment import aligned, shape, target
from ._construction import construct
from .expression import reference, literal, equal, multiply, binary


def build_balance(
    model: Model, *, id: UUID, movements: UUID, initial: ValueReference, result: UUID
) -> Formulation:
    """Declare signed balance continuity, with no overdraft-dependent behavior."""
    return build_accumulation(
        model, id=id, source=movements, initial=initial, result=result
    )


def build_interest(
    model: Model,
    *,
    id: UUID,
    principal: UUID,
    rate: ValueReference,
    result: UUID,
    nonnegative_principal: bool
) -> Formulation:
    """Declare periodic principal * rate and enforce principal >= 0.

    The caller must explicitly select this case. Piecewise overdraft interest is
    outside affine execution. Result and principal coordinates must match.
    """
    if nonnegative_principal is not True:
        raise ValueError(
            "symbolic overdraft interest is unsupported; use known-data calculation"
        )
    equations: list[tuple[str, Expression]] = []
    for m, matches in aligned(model, (principal,), result):
        p = target(principal, matches[0])
        equations.extend(
            (
                (
                    m.key + "/interest",
                    equal(
                        reference(target(result, m)),
                        multiply(reference(p), reference(rate)),
                    ),
                ),
                (
                    m.key + "/nonnegative",
                    binary(
                        "greater_than_or_equal",
                        reference(p),
                        literal(0, shape(model, principal).units),
                    ),
                ),
            )
        )
    return construct(id, "interest", equations, (principal, rate.value, result))

"""Finite periodic growth equations; rates are per declared step, not inferred annual rates."""

from uuid import UUID
from ..model import Model
from .._schema.records import Formulation, Reference
from ._alignment import shape, target, owner
from ._construction import construct
from .expression import reference, literal, equal, add, multiply


def build_compound(
    model: Model, *, id: UUID, initial: Reference, rate: Reference, result: UUID
) -> Formulation:
    """Declare first amount = initial, then prior amount * (1 + periodic rate).

    All amounts can remain unresolved. A fixed dimensionless rate makes the
    equations affine; an unknown rate generally does not. No amounts are read.
    """
    equations, prior = [], initial
    for index, item in enumerate(shape(model, result).movements):
        current = target(result, item)
        rhs = (
            reference(prior)
            if index == 0
            else multiply(reference(prior), add(literal(1), reference(rate)))
        )
        equations.append((str(item.id), equal(reference(current), rhs)))
        prior = current
    return construct(
        id, "compound", equations, (owner(model, initial), owner(model, rate), result)
    )


def build_linear(
    model: Model, *, id: UUID, initial: Reference, increment: Reference, result: UUID
) -> Formulation:
    """Declare initial + step index * increment; first index is zero.

    Increment has amount units, not a dimensionless proportional rate.
    """
    equations = [
        (
            str(m.id),
            equal(
                reference(target(result, m)),
                add(reference(initial), multiply(literal(i), reference(increment))),
            ),
        )
        for i, m in enumerate(shape(model, result).movements)
    ]
    return construct(
        id,
        "linear",
        equations,
        (owner(model, initial), owner(model, increment), result),
    )

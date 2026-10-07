"""Finite periodic growth equations; rates are per declared step, not inferred annual rates."""

from uuid import UUID
from ..model import Model
from .._schema.records import Formulation, Reference
from .flow import aligned, shape
from .authoring import declare
from ..model.scope import target_value
from .expression import reference, literal, equal, add, multiply


def compound(
    model: Model, *, id: UUID, initial: Reference, rate: Reference, result: UUID
) -> Formulation:
    """Declare first amount = initial, then prior amount * (1 + periodic rate).

    All amounts can remain unresolved. A fixed dimensionless rate makes the
    equations affine; an unknown rate generally does not. No amounts are read.
    """
    equations, prior = [], initial
    for index, item in enumerate(shape(model, result).movements):
        current = Reference(target=item.id)
        rhs = (
            reference(prior)
            if index == 0
            else multiply(reference(prior), add(literal(1), reference(rate)))
        )
        equations.append((str(item.id), equal(reference(current), rhs)))
        prior = current
    return declare(
        id,
        "compound",
        equations,
        (target_value(model, initial).id, target_value(model, rate).id, result),
    )


def linear(
    model: Model, *, id: UUID, initial: Reference, increment: Reference, result: UUID
) -> Formulation:
    """Declare initial + step index * increment; first index is zero.

    Increment has amount units, not a dimensionless proportional rate.
    """
    equations = [
        (
            str(m.id),
            equal(
                reference(Reference(target=m.id)),
                add(reference(initial), multiply(literal(i), reference(increment))),
            ),
        )
        for i, m in enumerate(shape(model, result).movements)
    ]
    return declare(
        id,
        "linear",
        equations,
        (target_value(model, initial).id, target_value(model, increment).id, result),
    )

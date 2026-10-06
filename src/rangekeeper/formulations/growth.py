"""Finite periodic growth equations; rates are per declared step, not inferred annual rates."""

from uuid import UUID
from ..model import Model
from .._schema.records import Formulation, ValueReference
from ._alignment import shape, target
from ._construction import construct
from .expression import reference, literal, equal, add, multiply


def build_compound(
    model: Model,
    *,
    id: UUID,
    initial: ValueReference,
    rate: ValueReference,
    result: UUID
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
        equations.append((item.key, equal(reference(current), rhs)))
        prior = current
    return construct(id, "compound", equations, (initial.value, rate.value, result))


def build_linear(
    model: Model,
    *,
    id: UUID,
    initial: ValueReference,
    increment: ValueReference,
    result: UUID
) -> Formulation:
    """Declare initial + step index * increment; first index is zero.

    Increment has amount units, not a dimensionless proportional rate.
    """
    equations = [
        (
            m.key,
            equal(
                reference(target(result, m)),
                add(reference(initial), multiply(literal(i), reference(increment))),
            ),
        )
        for i, m in enumerate(shape(model, result).movements)
    ]
    return construct(id, "linear", equations, (initial.value, increment.value, result))

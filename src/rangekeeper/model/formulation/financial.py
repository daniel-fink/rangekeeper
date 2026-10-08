"""Declared discount and present-value equations; no financial results are calculated here."""

from uuid import UUID
from rangekeeper.model import Model
from rangekeeper.schema.records import Formulation, Reference
from rangekeeper.model.formulation.flow import aligned, shape
from rangekeeper.model.formulation.authoring import declare
from rangekeeper.model.scope import target_value
from rangekeeper.model.expression.authoring import (
    reference,
    literal,
    equal,
    add,
    divide,
    power,
    sum as expression_sum,
)


def discount(
    model: Model,
    *,
    id: UUID,
    series: UUID,
    rate: Reference,
    discounted: UUID,
    first_period: int = 1,
) -> Formulation:
    """Declare amount / (1 + periodic rate)**n; n starts at first_period.

    Series and discounted identify Flow Values in compatible units.
    Rate is a scalar Reference, dimensionless per Flow step. No day-count or annualization is inferred.
    Negative initial exponents and coordinate mismatches raise ValueError.
    """
    if type(first_period) is not int or first_period < 0:
        raise ValueError("first_period must be a nonnegative integer")
    equations = [
        (
            m.id,
            equal(
                reference(Reference(target=m.id)),
                divide(
                    reference(Reference(target=matches[0].id)),
                    power(add(literal(1), reference(rate)), literal(i + first_period)),
                ),
            ),
        )
        for i, (m, matches) in enumerate(aligned(model, (series,), discounted))
    ]
    return declare(
        id, "discount", equations, (series, target_value(model, rate).id, discounted)
    )


def pv(model: Model, *, id: UUID, sequence: UUID, value: Reference) -> Formulation:
    """Relate sequence (a discounted Flow Value UUID) to value (a scalar Reference).

    Both have compatible amount units. This builder sums; it does not discount.
    """
    equation = equal(
        reference(value),
        expression_sum(
            [
                reference(Reference(target=m.id))
                for m in shape(model, sequence).movements
            ]
        ),
    )
    return declare(
        id,
        "present_value",
        [("total", equation)],
        (sequence, target_value(model, value).id),
    )

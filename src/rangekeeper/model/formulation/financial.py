"""Declared discount, present-value and interest equations; no financial results are calculated here."""

from uuid import UUID

from rangekeeper.model import Model
from rangekeeper.model.expression.authoring import (
    add,
    binary,
    divide,
    equal,
    literal,
    multiply,
    power,
    reference,
)
from rangekeeper.model.expression.authoring import (
    sum as expression_sum,
)
from rangekeeper.model.formulation.authoring import declare
from rangekeeper.model.formulation.flow import aligned, shape
from rangekeeper.model.scope import target_value
from rangekeeper.schema.enums import Operator
from rangekeeper.schema.records import Expression, Formulation, Reference


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


def interest(
    model: Model,
    *,
    id: UUID,
    principal: UUID,
    rate: Reference,
    interest: UUID,
    nonnegative_principal: bool,
) -> Formulation:
    """Relate principal and interest Flow Value UUIDs through a scalar rate Reference.

    Rate is dimensionless per step; principal and interest have compatible units.
    Enforce principal >= 0.
    """
    if nonnegative_principal is not True:
        raise ValueError(
            "symbolic overdraft interest is unsupported; use known-data calculation"
        )
    prepared = shape(model, principal)
    equations: list[tuple[str, Expression]] = []
    for movement, matches in aligned(
        model, (principal,), interest, shapes={principal: prepared}
    ):
        p = Reference(target=matches[0].id)
        equations.extend(
            (
                (
                    str(movement.id) + "/interest",
                    equal(
                        reference(Reference(target=movement.id)),
                        multiply(reference(p), reference(rate)),
                    ),
                ),
                (
                    str(movement.id) + "/nonnegative",
                    binary(
                        Operator.GREATER_THAN_OR_EQUAL,
                        reference(p),
                        literal(0, prepared.units),
                    ),
                ),
            )
        )
    return declare(
        id, "interest", equations, (principal, target_value(model, rate).id, interest)
    )

"""Declared discount and reversion equations; no financial results are calculated here."""

from collections.abc import Mapping
from uuid import UUID
from ..model import Model
from .._schema.records import Formulation, Reference
from ._alignment import aligned, shape, target, owner
from ._construction import construct
from .expression import reference, literal, equal, add, divide, power, sum_expressions


def build_discount(
    model: Model,
    *,
    id: UUID,
    source: UUID,
    rate: Reference,
    result: UUID,
    first_period: int = 1
) -> Formulation:
    """Declare amount / (1 + periodic rate)**n; n starts at first_period.

    Rate is dimensionless per Flow step. No day-count or annualization is inferred.
    Negative initial exponents and coordinate mismatches raise ValueError.
    """
    if type(first_period) is not int or first_period < 0:
        raise ValueError("first_period must be a nonnegative integer")
    equations = [
        (
            m.id,
            equal(
                reference(target(result, m)),
                divide(
                    reference(target(source, matches[0])),
                    power(add(literal(1), reference(rate)), literal(i + first_period)),
                ),
            ),
        )
        for i, (m, matches) in enumerate(aligned(model, (source,), result))
    ]
    return construct(id, "discount", equations, (source, owner(model, rate), result))


def build_present_value(
    model: Model, *, id: UUID, source: UUID, result: Reference
) -> Formulation:
    """Declare total PV as an ordered sum of an explicitly discounted Flow."""
    equation = equal(
        reference(result),
        sum_expressions(
            [reference(target(source, m)) for m in shape(model, source).movements]
        ),
    )
    return construct(
        id, "present_value", [("total", equation)], (source, owner(model, result))
    )


def build_reversion(
    model: Model,
    *,
    id: UUID,
    income: UUID,
    capitalization: Reference,
    result: UUID,
    mapping: Mapping[UUID, UUID]
) -> Formulation:
    """Declare sale = income / capitalization using result-Movement UUID to income-Movement UUID mapping.

    All result Movement UUIDs must be mapped. This makes any next-period income assumption
    explicit. Capitalization units must turn income units into sale units.
    """
    source = {m.id: m for m in shape(model, income).movements}
    destination = shape(model, result).movements
    if set(mapping) != {m.id for m in destination} or not set(mapping.values()) <= set(
        source
    ):
        raise ValueError("reversion requires a complete valid Movement mapping")
    equations = [
        (
            m.id,
            equal(
                reference(target(result, m)),
                divide(
                    reference(target(income, source[mapping[m.id]])),
                    reference(capitalization),
                ),
            ),
        )
        for m in destination
    ]
    return construct(
        id, "reversion", equations, (income, owner(model, capitalization), result)
    )

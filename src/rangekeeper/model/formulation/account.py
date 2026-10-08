"""Passive nonnegative interest and account schedule declarations."""

from uuid import UUID

from rangekeeper.calculations.account import (
    Balance,
    CurrentInterest,
    InterestTreatment,
    check_conventions,
)
from rangekeeper.model import Model
from rangekeeper.model.scope import target_value
from rangekeeper.schema.records import Formulation, Reference, Expression
from rangekeeper.schema.enums import Operator
from rangekeeper.model.formulation.flow import aligned, shape
from rangekeeper.model.formulation.authoring import declare
from rangekeeper.model.expression.authoring import (
    reference,
    literal,
    equal,
    multiply,
    binary,
    add,
)


def interest(
    model: Model,
    *,
    id: UUID,
    principal: UUID,
    rate: Reference,
    result: UUID,
    nonnegative_principal: bool,
) -> Formulation:
    """Declare periodic principal * rate and enforce principal >= 0."""
    if nonnegative_principal is not True:
        raise ValueError(
            "symbolic overdraft interest is unsupported; use known-data calculation"
        )
    prepared = shape(model, principal)
    equations: list[tuple[str, Expression]] = []
    for movement, matches in aligned(
        model, (principal,), result, shapes={principal: prepared}
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
        id, "interest", equations, (principal, target_value(model, rate).id, result)
    )


def schedule(
    model: Model,
    *,
    id: UUID,
    transactions: UUID,
    starting: Reference,
    rate: Reference | UUID,
    closing: UUID,
    interest: UUID,
    balance: Balance = Balance.CLOSING,
    current_interest: CurrentInterest = CurrentInterest.EXCLUDED,
    treatment: InterestTreatment = InterestTreatment.SEPARATE,
    nonnegative_principal: bool,
) -> Formulation:
    """Declare one account schedule over explicit Values without reading magnitudes.

    The transaction and result Flows share order. Flow rates match coordinates.
    Rates must be fixed in an execution Specification; unknown-rate products and
    overdrafts are outside the supported affine execution capability.
    """
    check_conventions(
        balance=balance, current_interest=current_interest, treatment=treatment
    )
    if nonnegative_principal is not True:
        raise ValueError(
            "symbolic overdraft interest is unsupported; use known-data calculation"
        )
    ids = (transactions, closing, interest) + (
        () if isinstance(rate, Reference) else (rate,)
    )
    if len(set(ids)) != len(ids):
        raise ValueError("schedule Flow Values must have distinct identities")
    shapes = {identity: shape(model, identity) for identity in ids}
    source = shapes[transactions]
    if not source.movements:
        raise ValueError("account schedule requires at least one transaction")
    coordinates = tuple(m.coordinate for m in source.movements)
    for identity in (closing, interest):
        if tuple(m.coordinate for m in shapes[identity].movements) != coordinates:
            raise ValueError("schedule result coordinate order must match transactions")
    sources = (transactions, interest) + (
        () if isinstance(rate, Reference) else (rate,)
    )
    equations: list[tuple[str, Expression]] = []
    prior = starting
    for destination, matches in aligned(model, sources, closing, shapes=shapes):
        transaction, charge = matches[:2]
        period_rate = (
            rate if isinstance(rate, Reference) else Reference(target=matches[2].id)
        )
        opening = reference(prior)
        before_interest = add(opening, reference(Reference(target=transaction.id)))
        selected = opening if balance is Balance.OPENING else before_interest
        interest_symbol = reference(Reference(target=charge.id))
        rate_symbol = reference(period_rate)
        closing_symbol = reference(Reference(target=destination.id))
        key = str(destination.id)
        interest_base = (
            add(selected, interest_symbol)
            if current_interest is CurrentInterest.INCLUDED
            else selected
        )
        closing_balance = (
            add(before_interest, interest_symbol)
            if treatment is InterestTreatment.FINANCED
            else before_interest
        )
        equations.extend(
            (
                (
                    key + "/interest",
                    equal(interest_symbol, multiply(rate_symbol, interest_base)),
                ),
                (key + "/closing", equal(closing_symbol, closing_balance)),
                (
                    key + "/opening_nonnegative",
                    binary(
                        Operator.GREATER_THAN_OR_EQUAL,
                        opening,
                        literal(0, source.units),
                    ),
                ),
                (
                    key + "/base_nonnegative",
                    binary(
                        Operator.GREATER_THAN_OR_EQUAL,
                        selected,
                        literal(0, source.units),
                    ),
                ),
                (
                    key + "/closing_nonnegative",
                    binary(
                        Operator.GREATER_THAN_OR_EQUAL,
                        closing_symbol,
                        literal(0, source.units),
                    ),
                ),
                (
                    key + "/rate_lower",
                    binary(Operator.GREATER_THAN, rate_symbol, literal(-1)),
                ),
            )
        )
        if current_interest is CurrentInterest.INCLUDED:
            equations.append(
                (
                    key + "/rate_upper",
                    binary(Operator.LESS_THAN, rate_symbol, literal(1)),
                )
            )
        prior = Reference(target=destination.id)
    bound_rate = target_value(model, rate).id if isinstance(rate, Reference) else rate
    return declare(
        id,
        "account_schedule",
        equations,
        (transactions, target_value(model, starting).id, bound_rate, closing, interest),
    )

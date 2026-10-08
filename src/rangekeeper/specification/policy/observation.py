"""Resolve recorded or previously decided quantities at explicit observation dates."""

from collections.abc import Sequence
from datetime import date

from rangekeeper.schema.records import ObservationBinding, ObservedQuantity, Quantity
from rangekeeper.model import Model
from rangekeeper.model.scope import (
    recorded_quantity,
    resolve_reference,
    scope_for_model,
)
from rangekeeper.specification.policy._availability import available_on, evidence_dates
from rangekeeper.specification.policy.result import Observation


class PolicyCapabilityError(ValueError):
    """Missing, unavailable or endogenous quantities cannot drive a finite policy."""


def _observe(scope, *, at, bindings, evidence, prior, controlled):
    result = []
    for binding in bindings:
        token = binding.target.target
        if token in prior:
            quantity, when = prior[token]
            available = max(when, binding.available_at or when)
        else:
            if token in controlled:
                raise PolicyCapabilityError(
                    "policy observation requires an earlier decision; recorded controls are not current decisions"
                )
            target = binding.target.to_data()
            _, movement = resolve_reference(target, scope.targets)
            available = available_on(
                movement_date=(
                    date.fromisoformat(movement["date"])
                    if movement and movement.get("date")
                    else None
                ),
                period_end=(
                    date.fromisoformat(movement["period"]["end_exclusive"])
                    if movement and movement.get("period")
                    else None
                ),
                scenario_dates=(evidence[token],) if token in evidence else (),
                declared=binding.available_at,
            )
            data = recorded_quantity(target, scope.targets, scope.measures)
            quantity = Quantity.from_data(data) if data is not None else None
        if available is None or available > at:
            raise PolicyCapabilityError(
                f"observation {binding.name} is unavailable at {at}"
            )
        if quantity is None:
            raise PolicyCapabilityError(
                f"observation {binding.name} is unresolved; endogenous sequential policies are unsupported"
            )
        result.append(
            ObservedQuantity(
                name=binding.name,
                target=binding.target,
                quantity=quantity,
                available_at=available,
            )
        )
    return Observation(at, tuple(result))


def observe(
    model: Model,
    *,
    at: date,
    bindings: Sequence[ObservationBinding],
) -> Observation:
    """Read available quantities without mutation or inferred zero values.

    Undated period Movements become available on their last included date. Scalar
    observations require provenance or a declared date; explicit dates can delay
    access but cannot advance a coordinate or provenance boundary.
    """
    if type(at) is not date:
        raise TypeError("at must be a date")
    bindings = tuple(bindings)
    if any(not isinstance(binding, ObservationBinding) for binding in bindings):
        raise TypeError("bindings must be ObservationBinding records")
    scope = scope_for_model(model)
    evidence = evidence_dates(model.provenance.to_data() if model.provenance else {})
    return _observe(
        scope,
        at=at,
        bindings=bindings,
        evidence=evidence,
        prior={},
        controlled=frozenset(),
    )
